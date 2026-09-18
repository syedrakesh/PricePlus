"""
Unit tests for multi-channel alert rules.
"""
import pytest
from app.modules.alerts.schemas import CreateAlertRuleRequest, UpdateAlertRuleRequest, normalize_and_validate_channels


def test_normalize_and_validate_channels():
    # Comma-separated string
    res = normalize_and_validate_channels("email, telegram")
    assert res == "email,telegram"

    # List of strings
    res_list = normalize_and_validate_channels(["email", "webhook"])
    assert res_list == "email,webhook"

    # Duplicates handling
    res_dups = normalize_and_validate_channels(["email", "telegram", "email"])
    assert res_dups == "email,telegram"

    # Invalid channel error
    with pytest.raises(ValueError, match="Invalid channel"):
        normalize_and_validate_channels("email, invalid_channel")

    # Empty channel list
    with pytest.raises(ValueError, match="At least one notification channel must be selected"):
        normalize_and_validate_channels("")


def test_create_alert_rule_multi_channel():
    req = CreateAlertRuleRequest(
        condition_type="price_drop_pct",
        threshold_pct=5.0,
        channel="email, telegram",
    )
    assert req.channel == "email,telegram"

    # Multi-channel with webhook requires webhook_url
    with pytest.raises(ValueError, match="webhook_url is required when channel includes 'webhook'"):
        CreateAlertRuleRequest(
            condition_type="price_drop_pct",
            threshold_pct=5.0,
            channel="email, webhook",
        )

    # Valid webhook URL provided
    req_wh = CreateAlertRuleRequest(
        condition_type="price_drop_pct",
        threshold_pct=5.0,
        channel="email, webhook",
        webhook_url="https://example.com/webhook",
    )
    assert req_wh.channel == "email,webhook"
    assert req_wh.webhook_url == "https://example.com/webhook"


def test_update_alert_rule_multi_channel():
    req = UpdateAlertRuleRequest(channel=["telegram", "email"])
    assert req.channel == "telegram,email"
