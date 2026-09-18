"""
Unit test for PATCH /api/v1/alert-rules/{rule_id} endpoint and UpdateAlertRuleRequest schema.
"""
import uuid
import pytest
from app.modules.alerts.schemas import UpdateAlertRuleRequest


def test_update_alert_rule_schema_validation():
    req = UpdateAlertRuleRequest(
        threshold_pct=10.0,
        channel="telegram",
    )
    assert req.threshold_pct == 10.0
    assert req.channel == "telegram"
    assert req.condition_type is None

    # Invalid condition type
    with pytest.raises(ValueError, match="condition_type must be one of"):
        UpdateAlertRuleRequest(condition_type="invalid_type")

    # Invalid channel
    with pytest.raises(ValueError, match="channel must be one of"):
        UpdateAlertRuleRequest(channel="invalid_channel")
