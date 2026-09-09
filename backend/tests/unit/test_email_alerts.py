"""
Tests for Phase 7 — Email Alerts:
  1. Email template rendering (pure functions — no SMTP)
  2. Email sender with mocked SMTP (no real network calls)
  3. Dispatcher integration (mocked DB + email)

All SMTP calls are mocked with unittest.mock — no real email sent.
"""

import uuid
from email.mime.multipart import MIMEMultipart
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.alerts.email_sender import _build_multipart_message
from app.modules.alerts.email_template import (
    EmailTemplate,
    _build_change_description,
    _change_color,
    _change_label,
    _currency_symbol,
    render_price_alert,
)

# ─── Template rendering ───────────────────────────────────────────────────────

class TestRenderPriceAlert:
    def test_returns_email_template(self):
        result = render_price_alert(
            product_title="Blue Widget",
            product_url="https://store.com/products/blue-widget",
            store_name="Acme Store",
            change_type="price_decrease",
            old_price=29.99,
            new_price=19.99,
            pct_change=-33.34,
            currency="USD",
        )
        assert isinstance(result, EmailTemplate)
        assert result.subject
        assert result.plain_text
        assert result.html

    def test_price_decrease_subject(self):
        result = render_price_alert(
            product_title="Blue Widget",
            product_url="https://store.com/products/blue-widget",
            store_name="Acme",
            change_type="price_decrease",
            old_price=30.0,
            new_price=20.0,
            pct_change=-33.33,
        )
        assert "drop" in result.subject.lower() or "blue widget" in result.subject.lower()
        assert "$20.00" in result.subject or "20.00" in result.subject

    def test_price_increase_subject(self):
        result = render_price_alert(
            product_title="Red Widget",
            product_url="https://store.com/products/red-widget",
            store_name="Acme",
            change_type="price_increase",
            old_price=20.0,
            new_price=30.0,
            pct_change=50.0,
        )
        assert "increase" in result.subject.lower() or "red widget" in result.subject.lower()

    def test_out_of_stock_subject(self):
        result = render_price_alert(
            product_title="Widget X",
            product_url="https://store.com/products/widget-x",
            store_name="Acme",
            change_type="became_unavailable",
            old_price=10.0,
            new_price=None,
            pct_change=None,
        )
        assert "stock" in result.subject.lower() or "widget x" in result.subject.lower()

    def test_back_in_stock_subject(self):
        result = render_price_alert(
            product_title="Widget X",
            product_url="https://store.com/products/widget-x",
            store_name="Acme",
            change_type="became_available",
            old_price=None,
            new_price=10.0,
            pct_change=None,
        )
        assert "back" in result.subject.lower() or "stock" in result.subject.lower()

    def test_html_contains_product_title(self):
        result = render_price_alert(
            product_title="Super Widget 3000",
            product_url="https://store.com/products/widget",
            store_name="Test Store",
            change_type="price_decrease",
            old_price=50.0,
            new_price=35.0,
            pct_change=-30.0,
        )
        assert "Super Widget 3000" in result.html

    def test_html_contains_store_name(self):
        result = render_price_alert(
            product_title="Widget",
            product_url="https://store.com/products/widget",
            store_name="My Competitor Store",
            change_type="price_decrease",
            old_price=10.0,
            new_price=8.0,
            pct_change=-20.0,
        )
        assert "My Competitor Store" in result.html

    def test_html_contains_product_url(self):
        product_url = "https://store.com/products/my-product"
        result = render_price_alert(
            product_title="Widget",
            product_url=product_url,
            store_name="Store",
            change_type="price_decrease",
            old_price=10.0,
            new_price=8.0,
            pct_change=-20.0,
        )
        assert product_url in result.html

    def test_plain_text_contains_key_info(self):
        result = render_price_alert(
            product_title="Cool Product",
            product_url="https://store.com/products/cool",
            store_name="Cool Store",
            change_type="price_decrease",
            old_price=100.0,
            new_price=75.0,
            pct_change=-25.0,
        )
        assert "Cool Product" in result.plain_text
        assert "Cool Store" in result.plain_text
        assert "https://store.com/products/cool" in result.plain_text

    def test_pct_change_in_plain_text(self):
        result = render_price_alert(
            product_title="Widget",
            product_url="https://store.com/products/widget",
            store_name="Store",
            change_type="price_decrease",
            old_price=100.0,
            new_price=75.0,
            pct_change=-25.0,
        )
        assert "-25" in result.plain_text or "25.0" in result.plain_text

    def test_none_price_handled_gracefully(self):
        """No crash when old_price is None (availability change)."""
        result = render_price_alert(
            product_title="Widget",
            product_url="https://store.com/products/widget",
            store_name="Store",
            change_type="became_unavailable",
            old_price=None,
            new_price=None,
            pct_change=None,
        )
        assert result.subject
        assert result.plain_text
        assert result.html

    def test_eur_currency_symbol(self):
        result = render_price_alert(
            product_title="Widget",
            product_url="https://store.com/products/widget",
            store_name="EU Store",
            change_type="price_decrease",
            old_price=20.0,
            new_price=15.0,
            pct_change=-25.0,
            currency="EUR",
        )
        assert "€" in result.subject or "€" in result.html


class TestHelperFunctions:
    def test_currency_symbols(self):
        assert _currency_symbol("USD") == "$"
        assert _currency_symbol("EUR") == "€"
        assert _currency_symbol("GBP") == "£"
        assert _currency_symbol("CAD") == "CA$"
        assert _currency_symbol("AUD") == "A$"
        assert _currency_symbol("JPY") == "JPY "  # Unknown → code + space

    def test_change_colors(self):
        assert _change_color("price_decrease") == "#10b981"   # green
        assert _change_color("price_increase") == "#ef4444"   # red
        assert _change_color("became_unavailable") == "#f59e0b"  # amber
        assert _change_color("became_available") == "#3b82f6"    # blue
        assert _change_color("unknown_type") == "#6366f1"        # default

    def test_change_labels_include_emoji(self):
        assert "Drop" in _change_label("price_decrease")
        assert "Increase" in _change_label("price_increase")
        assert "Stock" in _change_label("became_unavailable")
        assert "Stock" in _change_label("became_available")

    def test_build_change_description_unavailable(self):
        desc = _build_change_description("became_unavailable", None, None, None, "$")
        assert "out of stock" in desc.lower()

    def test_build_change_description_available(self):
        desc = _build_change_description("became_available", None, 15.0, None, "$")
        assert "back in stock" in desc.lower()
        assert "$15.00" in desc

    def test_build_change_description_price_change(self):
        desc = _build_change_description("price_decrease", 30.0, 20.0, -33.33, "$")
        assert "$30.00" in desc
        assert "$20.00" in desc
        assert "-33.3" in desc


# ─── Multipart message builder ────────────────────────────────────────────────

class TestBuildMultipartMessage:
    def test_returns_mime_multipart(self):
        msg = _build_multipart_message(
            subject="Test Subject",
            from_name="PricePlus",
            from_email="noreply@priceplus.app",
            to_email="user@example.com",
            plain_text="Plain text body",
            html="<h1>HTML body</h1>",
        )
        assert isinstance(msg, MIMEMultipart)

    def test_subject_set(self):
        msg = _build_multipart_message(
            subject="My Alert",
            from_name="PricePlus",
            from_email="noreply@priceplus.app",
            to_email="user@example.com",
            plain_text="Body",
            html="<p>Body</p>",
        )
        assert msg["Subject"] == "My Alert"

    def test_to_and_from_set(self):
        msg = _build_multipart_message(
            subject="Alert",
            from_name="PricePlus",
            from_email="noreply@test.com",
            to_email="dest@example.com",
            plain_text="Body",
            html="<p>Body</p>",
        )
        assert "dest@example.com" in msg["To"]
        assert "noreply@test.com" in msg["From"]
        assert "PricePlus" in msg["From"]

    def test_has_two_parts(self):
        msg = _build_multipart_message(
            subject="Alert",
            from_name="PricePlus",
            from_email="noreply@test.com",
            to_email="user@example.com",
            plain_text="Plain",
            html="<p>HTML</p>",
        )
        parts = msg.get_payload()
        assert len(parts) == 2  # plain + html

    def test_html_is_second_part(self):
        """HTML must be the last part so email clients prefer it."""
        msg = _build_multipart_message(
            subject="Alert",
            from_name="PricePlus",
            from_email="noreply@test.com",
            to_email="user@example.com",
            plain_text="Plain text",
            html="<p>HTML content</p>",
        )
        parts = msg.get_payload()
        html_part = parts[-1]
        assert html_part.get_content_type() == "text/html"


# ─── SMTP mock tests ──────────────────────────────────────────────────────────

def _make_mock_db_session(return_email: str | None):
    """Build a mock async context manager that returns the given email from execute."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_email
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)

    mock_factory = MagicMock(return_value=mock_db)
    return mock_factory


class TestSendAlertEmailSmtpMock:
    @pytest.mark.asyncio
    @patch("app.modules.alerts.email_sender._send_smtp")
    async def test_send_plain_text_email(self, mock_send_smtp):
        """Verify SMTP is called with correct arguments for plain-text email."""
        user_id = str(uuid.uuid4())
        user_email = "testuser@example.com"

        mock_factory = _make_mock_db_session(user_email)

        import app.core.db as db_module
        from app.modules.alerts import email_sender

        # Patch the session factory that email_sender imports at call time
        original = getattr(db_module, "AsyncSessionLocal", None)
        db_module.AsyncSessionLocal = mock_factory
        try:
            await email_sender.send_alert_email(
                to_user_id=user_id,
                subject="Test Alert",
                body="Price dropped!",
            )
        finally:
            if original is None:
                delattr(db_module, "AsyncSessionLocal")
            else:
                db_module.AsyncSessionLocal = original

        mock_send_smtp.assert_called_once()
        args = mock_send_smtp.call_args[0]
        assert args[1] == user_email
        assert "Test Alert" in args[2]

    @pytest.mark.asyncio
    @patch("app.modules.alerts.email_sender._send_smtp")
    async def test_send_html_email_uses_multipart(self, mock_send_smtp):
        """When html_body is provided, message should be multipart/alternative."""
        user_id = str(uuid.uuid4())
        user_email = "testuser@example.com"

        mock_factory = _make_mock_db_session(user_email)

        import app.core.db as db_module
        from app.modules.alerts import email_sender

        db_module.AsyncSessionLocal = mock_factory
        try:
            await email_sender.send_alert_email(
                to_user_id=user_id,
                subject="HTML Alert",
                body="Plain text body",
                html_body="<h1>HTML Body</h1>",
            )
        finally:
            del db_module.AsyncSessionLocal

        mock_send_smtp.assert_called_once()
        message_str = mock_send_smtp.call_args[0][2]
        # multipart/alternative messages contain MIME boundaries
        assert "Content-Type: multipart" in message_str

    @pytest.mark.asyncio
    @patch("app.modules.alerts.email_sender._send_smtp")
    async def test_user_not_found_does_not_send(self, mock_send_smtp):
        """If user email not found in DB, SMTP should NOT be called."""
        user_id = str(uuid.uuid4())

        mock_factory = _make_mock_db_session(None)  # No email found

        import app.core.db as db_module
        from app.modules.alerts import email_sender

        db_module.AsyncSessionLocal = mock_factory
        try:
            await email_sender.send_alert_email(
                to_user_id=user_id,
                subject="Alert",
                body="Body",
            )
        finally:
            del db_module.AsyncSessionLocal

        mock_send_smtp.assert_not_called()


class TestSendPriceAlertEmail:
    @pytest.mark.asyncio
    @patch("app.modules.alerts.email_sender.send_alert_email")
    async def test_renders_template_and_calls_send(self, mock_send):
        """send_price_alert_email renders the template and delegates to send_alert_email."""
        mock_send.return_value = None

        from app.modules.alerts.email_sender import send_price_alert_email
        await send_price_alert_email(
            to_user_id=str(uuid.uuid4()),
            product_title="Blue Widget",
            product_url="https://store.com/products/blue-widget",
            store_name="Test Store",
            change_type="price_decrease",
            old_price=30.0,
            new_price=20.0,
            pct_change=-33.33,
            currency="USD",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        # Should have passed html_body (template was rendered)
        args, kwargs = call_kwargs
        # html_body should be non-None
        html_body = kwargs.get("html_body") or (args[3] if len(args) > 3 else None)
        assert html_body is not None
        assert "<html" in html_body.lower()
