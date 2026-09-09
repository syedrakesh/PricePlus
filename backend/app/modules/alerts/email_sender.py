"""
Email sender for alert notifications.

Uses Python's built-in smtplib with async wrapping via asyncio.run_in_executor
so it doesn't block the event loop.

Sends multipart/alternative emails with both plain-text and HTML parts.
Email clients that support HTML will render the styled version; others
fall back to plain text automatically.
"""

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def send_alert_email(
    to_user_id: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> None:
    """
    Send a multipart (plain-text + HTML) alert email.

    Fetches the user's email address from the DB then sends via SMTP.
    Runs SMTP in a thread pool to avoid blocking the event loop.

    If html_body is None, falls back to plain-text only (MIMEText).
    """
    from app.core.config import get_settings
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import User

    settings = get_settings()

    # Fetch user email from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.email).where(User.id == uuid.UUID(to_user_id))
        )
        email = result.scalar_one_or_none()

    if not email:
        logger.warning("Cannot send alert email: user %s not found", to_user_id)
        return

    # Build message
    if html_body is not None:
        msg = _build_multipart_message(
            subject=subject,
            from_name=settings.smtp_from_name,
            from_email=settings.smtp_from_email,
            to_email=email,
            plain_text=body,
            html=html_body,
        )
    else:
        plain = MIMEText(body, "plain")
        plain["Subject"] = subject
        plain["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        plain["To"] = email
        msg = plain

    # Send in executor (SMTP is blocking I/O)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: _send_smtp(settings, email, msg.as_string()),
    )
    logger.info("Alert email sent to %s (subject=%r)", email, subject[:60])


def _build_multipart_message(
    subject: str,
    from_name: str,
    from_email: str,
    to_email: str,
    plain_text: str,
    html: str,
) -> MIMEMultipart:
    """
    Build a multipart/alternative MIME message with plain-text and HTML parts.

    Email clients prefer the last part listed (HTML), falling back to plain-text.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    # Attach plain text first (fallback), HTML second (preferred)
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    return msg


async def send_price_alert_email(
    to_user_id: str,
    product_title: str,
    product_url: str,
    store_name: str,
    change_type: str,
    old_price: float | None,
    new_price: float | None,
    pct_change: float | None,
    currency: str = "USD",
) -> None:
    """
    High-level helper: renders the price alert template and sends the email.

    This is the preferred entry point for the dispatcher — it handles both
    template rendering and delivery in one call.
    """
    from app.modules.alerts.email_template import render_price_alert

    template = render_price_alert(
        product_title=product_title,
        product_url=product_url,
        store_name=store_name,
        change_type=change_type,
        old_price=old_price,
        new_price=new_price,
        pct_change=pct_change,
        currency=currency,
    )

    await send_alert_email(
        to_user_id=to_user_id,
        subject=template.subject,
        body=template.plain_text,
        html_body=template.html,
    )


def _send_smtp(settings: object, to_email: str, message: str) -> None:
    """Synchronous SMTP send — runs in a thread pool."""
    from app.core.config import Settings
    assert isinstance(settings, Settings)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        if settings.smtp_port == 587:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(settings.smtp_from_email, to_email, message)
