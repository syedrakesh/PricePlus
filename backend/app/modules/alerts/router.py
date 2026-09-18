"""
Alerts router — CRUD for alert rules and list of fired alerts.

Endpoints:
  POST   /alert-rules              create a new alert rule
  GET    /alert-rules              list all alert rules for the user
  DELETE /alert-rules/{id}         delete an alert rule
  PATCH  /alert-rules/{id}/toggle  enable/disable a rule

  GET    /alerts                   list all fired alerts (paginated)
  GET    /alerts/unread-count      quick count for UI badge
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import get_current_user_id
from app.modules.alerts.models import Alert, AlertRule
from app.modules.alerts.schemas import (
    AlertListResponse,
    AlertResponse,
    AlertRuleListResponse,
    AlertRuleResponse,
    CreateAlertRuleRequest,
    TestNotificationRequest,
    UpdateAlertRuleRequest,
)
from app.modules.tracking.models import TrackedProduct

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_owned_tracked(
    tracked_product_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> TrackedProduct:
    result = await db.execute(
        select(TrackedProduct).where(
            TrackedProduct.id == tracked_product_id,
            TrackedProduct.user_id == user_id,
        )
    )
    tracked = result.scalar_one_or_none()
    if tracked is None:
        raise HTTPException(status_code=404, detail="Tracked product not found")
    return tracked


@router.post("/alert-rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    data: CreateAlertRuleRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> AlertRuleResponse:
    """
    Create a new alert rule for a tracked product.

    condition_type options:
    - price_drop_pct: fire when price drops by >= threshold_pct %
    - price_increase_pct: fire when price increases by >= threshold_pct %
    - price_below: fire when price falls below threshold_price
    - price_above: fire when price rises above threshold_price
    - any_change: fire on any price or availability change
    - out_of_stock: fire when product becomes unavailable
    - back_in_stock: fire when product becomes available again
    """
    user_id = uuid.UUID(user_id_str)

    tracked_uuid: uuid.UUID | None = None
    if data.tracked_product_id:
        try:
            tracked_uuid = uuid.UUID(data.tracked_product_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Tracked product not found") from None

        await _get_owned_tracked(tracked_uuid, user_id, db)

    # Check for existing duplicate rule for this scope and condition
    dup_query = select(AlertRule).where(
        AlertRule.user_id == user_id,
        AlertRule.condition_type == data.condition_type,
    )
    if tracked_uuid is None:
        dup_query = dup_query.where(AlertRule.tracked_product_id.is_(None))
    else:
        dup_query = dup_query.where(AlertRule.tracked_product_id == tracked_uuid)

    if data.threshold_pct is not None:
        dup_query = dup_query.where(AlertRule.threshold_pct == data.threshold_pct)
    else:
        dup_query = dup_query.where(AlertRule.threshold_pct.is_(None))

    if data.threshold_price is not None:
        dup_query = dup_query.where(AlertRule.threshold_price == data.threshold_price)
    else:
        dup_query = dup_query.where(AlertRule.threshold_price.is_(None))

    dup_result = await db.execute(dup_query)
    existing_rule = dup_result.scalars().first()

    if existing_rule:
        if not existing_rule.is_enabled:
            existing_rule.is_enabled = True
            await db.commit()
            await db.refresh(existing_rule)
            return AlertRuleResponse.from_orm_model(existing_rule)
        raise HTTPException(
            status_code=400,
            detail="An identical alert rule already exists for this scope.",
        )

    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        tracked_product_id=tracked_uuid,
        condition_type=data.condition_type,
        threshold_pct=data.threshold_pct,
        threshold_price=data.threshold_price,
        channel=data.channel,
        webhook_url=data.webhook_url,
        cool_down_minutes=data.cool_down_minutes,
        is_enabled=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return AlertRuleResponse.from_orm_model(rule)


@router.get("/alert-rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> AlertRuleListResponse:
    """List all alert rules for the authenticated user."""
    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(AlertRule)
        .where(AlertRule.user_id == user_id)
        .order_by(AlertRule.created_at.desc())
    )
    rules = list(result.scalars().all())
    return AlertRuleListResponse(
        rules=[AlertRuleResponse.from_orm_model(r) for r in rules],
        total=len(rules),
    )


@router.delete("/alert-rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> None:
    """Delete an alert rule. Returns 204 No Content."""
    user_id = uuid.UUID(user_id_str)
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert rule not found") from None

    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_uuid,
            AlertRule.user_id == user_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    await db.delete(rule)
    await db.commit()


@router.patch("/alert-rules/{rule_id}/toggle", response_model=AlertRuleResponse)
async def toggle_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> AlertRuleResponse:
    """Toggle an alert rule between enabled and disabled."""
    user_id = uuid.UUID(user_id_str)
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert rule not found") from None

    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_uuid,
            AlertRule.user_id == user_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    rule.is_enabled = not rule.is_enabled
    await db.commit()
    await db.refresh(rule)
    return AlertRuleResponse.from_orm_model(rule)


@router.patch("/alert-rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str,
    data: UpdateAlertRuleRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> AlertRuleResponse:
    """Update an existing alert rule for the authenticated user."""
    user_id = uuid.UUID(user_id_str)
    try:
        rule_uuid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert rule not found") from None

    result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == rule_uuid,
            AlertRule.user_id == user_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    update_data = data.model_dump(exclude_unset=True)

    if "tracked_product_id" in update_data:
        val = update_data.pop("tracked_product_id")
        if val:
            try:
                t_uuid = uuid.UUID(val)
                await _get_owned_tracked(t_uuid, user_id, db)
                rule.tracked_product_id = t_uuid
            except ValueError:
                raise HTTPException(status_code=404, detail="Tracked product not found") from None
        else:
            rule.tracked_product_id = None

    for key, val in update_data.items():
        setattr(rule, key, val)

    # Post-update validation check
    pct_conditions = {"price_drop_pct", "price_increase_pct"}
    price_conditions = {"price_below", "price_above"}
    if rule.condition_type in pct_conditions and rule.threshold_pct is None:
        raise HTTPException(status_code=400, detail=f"threshold_pct is required for condition_type={rule.condition_type!r}")
    if rule.condition_type in price_conditions and rule.threshold_price is None:
        raise HTTPException(status_code=400, detail=f"threshold_price is required for condition_type={rule.condition_type!r}")
    channels = [c.strip() for c in rule.channel.split(",") if c.strip()]
    if "webhook" in channels and not rule.webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required when channel includes 'webhook'")

    await db.commit()
    await db.refresh(rule)
    return AlertRuleResponse.from_orm_model(rule)



@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    delivered_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> AlertListResponse:
    """List all fired alerts for the authenticated user (most recent first)."""
    user_id = uuid.UUID(user_id_str)

    base_filter = Alert.user_id == user_id
    if delivered_only:
        base_filter = base_filter & (Alert.delivered == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).where(base_filter))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    alerts_result = await db.execute(
        select(Alert)
        .where(base_filter)
        .order_by(Alert.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    alerts = list(alerts_result.scalars().all())

    return AlertListResponse(
        alerts=[AlertResponse.from_orm_model(a) for a in alerts],
        total=total,
    )


@router.get("/alerts/unread-count")
async def unread_alert_count(
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> dict:
    """Return count of alerts not yet delivered (for UI badge)."""
    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(func.count()).where(
            Alert.user_id == user_id,
            Alert.delivered == False,  # noqa: E712
        )
    )
    return {"unread_count": result.scalar_one()}


@router.post("/alerts/test-notification")
async def test_notification_endpoint(
    data: TestNotificationRequest,
    db: AsyncSession = Depends(get_db),
    user_id_str: str = Depends(get_current_user_id),
) -> dict:
    """Trigger a test notification for the authenticated user (email or telegram)."""
    user_id = uuid.UUID(user_id_str)
    from app.modules.alerts.dispatcher import send_test_notification

    success, msg = await send_test_notification(
        user_id=user_id,
        channel=data.channel.lower().strip(),
        db=db,
        override_telegram_chat_id=data.telegram_chat_id,
        override_telegram_bot_token=data.telegram_bot_token,
        override_notification_email=data.notification_email,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}

