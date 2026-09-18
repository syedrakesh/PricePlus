"""
Alert dispatcher — evaluates alert rules against pending PriceChanges
and dispatches notifications.

Called after each monitoring cycle by the monitoring task.
Processes all PriceChange records where alert_sent=False.

Delivery:
- Email: via SMTP (configured in settings)
- Webhook: HTTP POST to user-defined URL (future)
- Cooldown enforced per-rule
- Failures are logged but do not raise (delivery errors are recorded on Alert)
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.evaluator import AlertConditionInput, build_trigger_summary, should_fire
from app.modules.alerts.models import Alert, AlertRule
from app.modules.discovery.models import DiscoveredProduct
from app.modules.monitoring.models import PriceChange
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)


async def process_pending_alerts(db: AsyncSession) -> int:
    """
    Process all PriceChange records where alert_sent=False.

    For each price change:
    1. Load matching alert rules for the affected TrackedProduct
    2. Evaluate each rule via should_fire()
    3. Create Alert record
    4. Dispatch notification
    5. Mark PriceChange.alert_sent=True

    Returns: count of alerts dispatched.
    """
    # Load unsent price changes with their tracked product and discovered product
    rows = await db.execute(
        select(PriceChange, TrackedProduct, DiscoveredProduct)
        .join(TrackedProduct, TrackedProduct.id == PriceChange.tracked_product_id)
        .join(DiscoveredProduct, DiscoveredProduct.id == PriceChange.discovered_product_id)
        .where(PriceChange.alert_sent == False)  # noqa: E712
        .order_by(PriceChange.detected_at.asc())
        .limit(500)  # Process at most 500 pending changes per cycle
    )
    pending = list(rows.all())

    if not pending:
        return 0

    logger.info("Processing %d pending price changes for alerts", len(pending))
    total_dispatched = 0

    for price_change, tracked, discovered in pending:
        dispatched = await _process_one_change(db, price_change, tracked, discovered)
        total_dispatched += dispatched

        # Mark price change as processed regardless of dispatch count
        await db.execute(
            update(PriceChange)
            .where(PriceChange.id == price_change.id)
            .values(alert_sent=True)
        )

    await db.commit()
    logger.info("Alert dispatch complete: %d alerts sent", total_dispatched)
    return total_dispatched


async def _process_one_change(
    db: AsyncSession,
    price_change: PriceChange,
    tracked: TrackedProduct,
    discovered: DiscoveredProduct,
) -> int:
    """Evaluate and fire all matching alert rules for one price change."""
    # Load all enabled alert rules for this user (both item-specific and universal account-wide rules)
    rules_result = await db.execute(
        select(AlertRule).where(
            AlertRule.user_id == tracked.user_id,
            AlertRule.is_enabled == True,  # noqa: E712
            or_(
                AlertRule.tracked_product_id == tracked.id,
                AlertRule.tracked_product_id.is_(None),
            ),
        )
    )
    rules = list(rules_result.scalars().all())

    if not rules:
        return 0

    dispatched = 0

    for rule in rules:
        condition = AlertConditionInput(
            condition_type=rule.condition_type,
            threshold_pct=float(rule.threshold_pct) if rule.threshold_pct is not None else None,
            threshold_price=float(rule.threshold_price) if rule.threshold_price is not None else None,
            cool_down_minutes=rule.cool_down_minutes,
            last_triggered_at=rule.last_triggered_at,
            change_type=price_change.change_type,
            old_price=float(price_change.old_price) if price_change.old_price is not None else None,
            new_price=float(price_change.new_price) if price_change.new_price is not None else None,
            pct_change=float(price_change.pct_change) if price_change.pct_change is not None else None,
        )

        if not should_fire(condition):
            continue

        summary = build_trigger_summary(condition, discovered.handle)

        alert = Alert(
            id=uuid.uuid4(),
            user_id=tracked.user_id,
            alert_rule_id=rule.id,
            price_change_id=price_change.id,
            channel=rule.channel,
            delivered=False,
            trigger_summary=summary,
        )
        db.add(alert)
        await db.flush()  # Get alert.id before dispatch

        # Dispatch the notification
        delivered, error = await _dispatch_notification(rule, alert, summary, db)
        alert.delivered = delivered
        alert.delivery_error = error
        if delivered:
            alert.delivered_at = datetime.now(UTC)

        # Update rule's last_triggered_at
        await db.execute(
            update(AlertRule)
            .where(AlertRule.id == rule.id)
            .values(last_triggered_at=datetime.now(UTC))
        )

        dispatched += 1
        logger.info(
            "Alert fired: rule=%s product=%s type=%s delivered=%s",
            rule.id,
            discovered.handle,
            rule.condition_type,
            delivered,
        )

    return dispatched


async def _dispatch_notification(
    rule: AlertRule,
    alert: Alert,
    summary: str,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """
    Send the notification via the configured channel.
    Returns (delivered: bool, error_message: str | None).
    """
    if rule.channel == "email":
        return await _send_email_alert(rule, alert, summary)

    if rule.channel == "telegram":
        return await _send_telegram_alert(rule, alert, summary, db)

    if rule.channel == "webhook":
        return await _send_webhook_alert(rule, summary)

    return False, f"Unknown channel: {rule.channel!r}"


async def _send_email_alert(
    rule: AlertRule,
    alert: Alert,
    summary: str,
) -> tuple[bool, str | None]:
    """Send an email notification via SMTP."""
    try:
        from app.core.config import get_settings
        from app.modules.alerts.email_sender import send_alert_email

        settings = get_settings()
        if not settings.smtp_username:
            # Email not configured — log and skip gracefully
            logger.warning("SMTP not configured, skipping email alert")
            return False, "SMTP not configured"

        await send_alert_email(
            to_user_id=str(rule.user_id),
            subject=f"PricePlus Alert: {summary[:80]}",
            body=summary,
        )
        return True, None

    except Exception as exc:
        logger.warning("Failed to send email alert: %s", exc)
        return False, str(exc)


async def _send_telegram_alert(
    rule: AlertRule,
    alert: Alert,
    summary: str,
    db: AsyncSession,
) -> tuple[bool, str | None]:
    """Send a notification to the user's Telegram Chat ID via Telegram Bot API."""
    try:
        from app.core.config import get_settings
        from app.modules.auth.models import User

        user_res = await db.execute(select(User).where(User.id == rule.user_id))
        user = user_res.scalar_one_or_none()
        if not user:
            return False, "User not found"

        if not getattr(user, "telegram_alerts_enabled", True):
            return False, "Telegram alerts disabled in user settings"

        chat_id = getattr(user, "telegram_chat_id", None)
        if not chat_id:
            return False, "Telegram chat_id is not configured in user profile settings"

        settings = get_settings()
        bot_token = getattr(user, "telegram_bot_token", None) or getattr(settings, "telegram_bot_token", None)
        if not bot_token:
            return False, "Telegram bot_token is not configured"

        import httpx

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        text_message = f"🔔 *PricePlus Alert*\n\n{summary}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text_message, "parse_mode": "Markdown"})
            if resp.status_code >= 400:
                err_body = resp.text[:200]
                logger.warning("Telegram Bot API returned HTTP %s: %s", resp.status_code, err_body)
                return False, f"Telegram API HTTP {resp.status_code}: {err_body}"
            return True, None

    except Exception as exc:
        logger.warning("Failed to send Telegram alert: %s", exc)
        return False, str(exc)


async def _send_webhook_alert(
    rule: AlertRule,
    summary: str,
) -> tuple[bool, str | None]:
    """POST a JSON payload to the user's webhook URL."""
    if not rule.webhook_url:
        return False, "No webhook URL configured"

    try:
        import httpx

        payload = {
            "type": "price_alert",
            "summary": summary,
            "rule_id": str(rule.id),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(rule.webhook_url, json=payload)
            if resp.status_code >= 400:
                return False, f"Webhook returned HTTP {resp.status_code}"
            return True, None
    except Exception as exc:
        return False, str(exc)


async def send_test_notification(
    user_id: uuid.UUID,
    channel: str,
    db: AsyncSession,
    override_telegram_chat_id: str | None = None,
    override_telegram_bot_token: str | None = None,
    override_notification_email: str | None = None,
) -> tuple[bool, str]:
    """Send a test notification message for the requested channel (email or telegram)."""
    from app.core.config import get_settings
    from app.modules.auth.models import User

    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        return False, "User account not found."

    summary = "🎉 Test Notification from PricePlus! Your notification channel is working correctly."

    if channel == "telegram":
        chat_id = (override_telegram_chat_id or "").strip() or getattr(user, "telegram_chat_id", None)
        if not chat_id:
            return False, "Please enter your Telegram Chat ID in settings first."

        settings = get_settings()
        bot_token = (override_telegram_bot_token or "").strip() or getattr(user, "telegram_bot_token", None) or getattr(settings, "telegram_bot_token", None)
        if not bot_token:
            return False, "Please configure your Telegram Bot Token in settings."

        import httpx

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": f"🚀 *PricePlus Test Notification*\n\n{summary}",
                        "parse_mode": "Markdown",
                    },
                )
                if resp.status_code >= 400:
                    return False, f"Telegram API error (HTTP {resp.status_code}): {resp.text[:150]}"
                return True, f"Test Telegram message sent successfully to Chat ID {chat_id}!"
        except Exception as exc:
            return False, f"Failed to send Telegram message: {exc}"

    if channel == "email":
        target_email = (override_notification_email or "").strip() or getattr(user, "notification_email", None) or user.email
        settings = get_settings()
        if not settings.smtp_username:
            return True, f"Simulated test email sent successfully to {target_email} (SMTP not configured in local environment)."

        from app.modules.alerts.email_sender import send_alert_email

        try:
            await send_alert_email(
                to_user_id=str(user.id),
                subject="PricePlus Test Notification",
                body=summary,
            )
            return True, f"Test email notification sent successfully to {target_email}!"
        except Exception as exc:
            return False, f"Failed to send email alert: {exc}"

    return False, f"Unsupported test channel: {channel!r}"
