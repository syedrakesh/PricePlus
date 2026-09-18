"""
Pydantic schemas for alert rule and alert endpoints.
"""

from pydantic import BaseModel, Field, field_validator

VALID_CONDITION_TYPES = {
    "price_drop_pct",
    "price_increase_pct",
    "price_below",
    "price_above",
    "any_change",
    "out_of_stock",
    "back_in_stock",
}

VALID_CHANNELS = {"email", "telegram", "webhook"}


class CreateAlertRuleRequest(BaseModel):
    tracked_product_id: str | None = Field(default=None, description="Optional. If omitted, rule applies to ALL tracked products.")
    condition_type: str = Field(description=", ".join(sorted(VALID_CONDITION_TYPES)))
    threshold_pct: float | None = Field(
        default=None,
        ge=0.01,
        le=100.0,
        description="Required for price_drop_pct / price_increase_pct",
    )
    threshold_price: float | None = Field(
        default=None,
        ge=0.0,
        description="Required for price_below / price_above",
    )
    channel: str = Field(default="email")
    webhook_url: str | None = Field(default=None, max_length=2048)
    cool_down_minutes: int = Field(default=60, ge=5, le=10080)  # 5 min to 7 days

    @field_validator("condition_type")
    @classmethod
    def validate_condition_type(cls, v: str) -> str:
        if v not in VALID_CONDITION_TYPES:
            raise ValueError(f"condition_type must be one of: {', '.join(sorted(VALID_CONDITION_TYPES))}")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v not in VALID_CHANNELS:
            raise ValueError(f"channel must be one of: {', '.join(VALID_CHANNELS)}")
        return v

    def model_post_init(self, __context: object) -> None:
        pct_conditions = {"price_drop_pct", "price_increase_pct"}
        price_conditions = {"price_below", "price_above"}
        if self.condition_type in pct_conditions and self.threshold_pct is None:
            raise ValueError(f"threshold_pct is required for condition_type={self.condition_type!r}")
        if self.condition_type in price_conditions and self.threshold_price is None:
            raise ValueError(f"threshold_price is required for condition_type={self.condition_type!r}")
        if self.channel == "webhook" and not self.webhook_url:
            raise ValueError("webhook_url is required when channel='webhook'")


class UpdateAlertRuleRequest(BaseModel):
    tracked_product_id: str | None = None
    condition_type: str | None = None
    threshold_pct: float | None = Field(default=None, ge=0.01, le=100.0)
    threshold_price: float | None = Field(default=None, ge=0.0)
    channel: str | None = None
    webhook_url: str | None = Field(default=None, max_length=2048)
    cool_down_minutes: int | None = Field(default=None, ge=5, le=10080)
    is_enabled: bool | None = None

    @field_validator("condition_type")
    @classmethod
    def validate_condition_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CONDITION_TYPES:
            raise ValueError(f"condition_type must be one of: {', '.join(sorted(VALID_CONDITION_TYPES))}")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_CHANNELS:
            raise ValueError(f"channel must be one of: {', '.join(VALID_CHANNELS)}")
        return v


class AlertRuleResponse(BaseModel):
    id: str
    user_id: str
    tracked_product_id: str | None
    condition_type: str
    threshold_pct: float | None
    threshold_price: float | None
    channel: str
    webhook_url: str | None
    is_enabled: bool
    cool_down_minutes: int
    last_triggered_at: str | None
    created_at: str

    @classmethod
    def from_orm_model(cls, rule: object) -> "AlertRuleResponse":
        from app.modules.alerts.models import AlertRule
        assert isinstance(rule, AlertRule)
        return cls(
            id=str(rule.id),
            user_id=str(rule.user_id),
            tracked_product_id=str(rule.tracked_product_id) if rule.tracked_product_id else None,
            condition_type=rule.condition_type,
            threshold_pct=float(rule.threshold_pct) if rule.threshold_pct is not None else None,
            threshold_price=float(rule.threshold_price) if rule.threshold_price is not None else None,
            channel=rule.channel,
            webhook_url=rule.webhook_url,
            is_enabled=rule.is_enabled,
            cool_down_minutes=rule.cool_down_minutes,
            last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
            created_at=rule.created_at.isoformat() if rule.created_at else "",
        )


class AlertResponse(BaseModel):
    id: str
    user_id: str
    alert_rule_id: str
    price_change_id: str | None
    channel: str
    delivered: bool
    delivery_error: str | None
    delivered_at: str | None
    trigger_summary: str | None
    created_at: str

    @classmethod
    def from_orm_model(cls, alert: object) -> "AlertResponse":
        from app.modules.alerts.models import Alert
        assert isinstance(alert, Alert)
        return cls(
            id=str(alert.id),
            user_id=str(alert.user_id),
            alert_rule_id=str(alert.alert_rule_id),
            price_change_id=str(alert.price_change_id) if alert.price_change_id else None,
            channel=alert.channel,
            delivered=alert.delivered,
            delivery_error=alert.delivery_error,
            delivered_at=alert.delivered_at.isoformat() if alert.delivered_at else None,
            trigger_summary=alert.trigger_summary,
            created_at=alert.created_at.isoformat(),
        )


class AlertRuleListResponse(BaseModel):
    rules: list[AlertRuleResponse]
    total: int


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int


class TestNotificationRequest(BaseModel):
    channel: str = Field(description="email or telegram")
    telegram_chat_id: str | None = Field(default=None, max_length=100)
    telegram_bot_token: str | None = Field(default=None, max_length=255)
    notification_email: str | None = Field(default=None, max_length=254)

