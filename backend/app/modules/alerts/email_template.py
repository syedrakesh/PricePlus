"""
Email templates for alert notifications.

Provides both plain-text and HTML versions of each email type.
The HTML template is simple and inline-styled for maximum email client
compatibility (no external CSS, no web fonts, no images).

Template types:
  price_change  — price increase or decrease
  out_of_stock  — product became unavailable
  back_in_stock — product became available again
  any_change    — catch-all for generic changes
"""

from dataclasses import dataclass


@dataclass
class EmailTemplate:
    """Rendered email template — subject, plain text body, HTML body."""

    subject: str
    plain_text: str
    html: str


def render_price_alert(
    product_title: str,
    product_url: str,
    store_name: str,
    change_type: str,
    old_price: float | None,
    new_price: float | None,
    pct_change: float | None,
    currency: str = "USD",
) -> EmailTemplate:
    """
    Render a price alert email for a single price change event.

    Generates both plain-text and HTML versions.
    """
    currency_symbol = _currency_symbol(currency)

    # ── Subject line ──────────────────────────────────────────────────────────
    subject = _build_subject(change_type, product_title, new_price, currency_symbol)

    # ── Change description ────────────────────────────────────────────────────
    change_desc = _build_change_description(
        change_type, old_price, new_price, pct_change, currency_symbol
    )

    # ── Plain text ────────────────────────────────────────────────────────────
    plain_text = f"""\
PricePlus Alert: {subject}

Product:  {product_title}
Store:    {store_name}
Change:   {change_desc}
View:     {product_url}

──────────────────────────────
This alert was sent by PricePlus because a price change was detected
on a product you are tracking.

To manage your alerts, visit your PricePlus dashboard.
"""

    # ── HTML ──────────────────────────────────────────────────────────────────
    change_color = _change_color(change_type)
    old_price_row = ""
    if old_price is not None and new_price is not None:
        old_price_row = f"""
        <tr>
          <td style="padding:4px 0;color:#6b7280;font-size:14px;">Previous price</td>
          <td style="padding:4px 0;font-size:14px;text-decoration:line-through;color:#9ca3af;">
            {currency_symbol}{old_price:.2f}
          </td>
        </tr>"""

    pct_badge = ""
    if pct_change is not None:
        sign = "+" if pct_change > 0 else ""
        pct_badge = f"""
        <span style="display:inline-block;margin-left:8px;padding:2px 8px;
          border-radius:12px;font-size:12px;font-weight:600;
          background:{change_color}20;color:{change_color};">
          {sign}{pct_change:.1f}%
        </span>"""

    new_price_str = f"{currency_symbol}{new_price:.2f}" if new_price is not None else "N/A"
    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 16px;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
        style="background:#ffffff;border-radius:12px;overflow:hidden;
               box-shadow:0 1px 3px rgba(0,0,0,0.1);max-width:100%;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">
              PricePlus
            </h1>
            <p style="margin:6px 0 0;color:#e0e7ff;font-size:13px;">Price monitoring for smart sellers</p>
          </td>
        </tr>

        <!-- Alert badge -->
        <tr>
          <td style="padding:24px 32px 0;">
            <span style="display:inline-block;padding:4px 12px;border-radius:20px;
              font-size:12px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;
              background:{change_color}15;color:{change_color};border:1px solid {change_color}30;">
              {_change_label(change_type)}
            </span>
          </td>
        </tr>

        <!-- Product info -->
        <tr>
          <td style="padding:16px 32px 24px;">
            <h2 style="margin:0 0 4px;font-size:18px;font-weight:600;color:#111827;line-height:1.4;">
              {product_title}
            </h2>
            <p style="margin:0;font-size:13px;color:#6b7280;">{store_name}</p>
          </td>
        </tr>

        <!-- Price details -->
        <tr>
          <td style="padding:0 32px 24px;">
            <table cellpadding="0" cellspacing="0" width="100%"
              style="background:#f3f4f6;border-radius:8px;padding:16px 20px;">
              <tr>
                <td colspan="2" style="padding-bottom:12px;border-bottom:1px solid #e5e7eb;">
                  <span style="font-size:13px;font-weight:500;color:#374151;text-transform:uppercase;
                    letter-spacing:0.5px;">Price Change</span>
                </td>
              </tr>
              {old_price_row}
              <tr>
                <td style="padding:8px 0 4px;color:#111827;font-size:14px;font-weight:500;">
                  New price
                </td>
                <td style="padding:8px 0 4px;">
                  <span style="font-size:22px;font-weight:700;color:{change_color};">
                    {new_price_str}
                  </span>
                  {pct_badge}
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td style="padding:0 32px 32px;">
            <a href="{product_url}"
              style="display:inline-block;padding:12px 24px;background:#6366f1;color:#ffffff;
                font-weight:600;font-size:14px;text-decoration:none;border-radius:8px;">
              View Product →
            </a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;border-top:1px solid #f3f4f6;">
            <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
              You received this alert because you are tracking this product on PricePlus.<br>
              To manage your alerts, visit your
              <a href="#" style="color:#6366f1;text-decoration:none;">PricePlus dashboard</a>.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return EmailTemplate(subject=subject, plain_text=plain_text, html=html)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_subject(
    change_type: str,
    product_title: str,
    new_price: float | None,
    currency_symbol: str,
) -> str:
    price_str = f" — now {currency_symbol}{new_price:.2f}" if new_price is not None else ""
    labels = {
        "price_decrease": f"Price drop on {product_title}{price_str}",
        "price_increase": f"Price increase on {product_title}{price_str}",
        "became_unavailable": f"{product_title} is now out of stock",
        "became_available": f"{product_title} is back in stock{price_str}",
    }
    return labels.get(change_type, f"Price change on {product_title}{price_str}")


def _build_change_description(
    change_type: str,
    old_price: float | None,
    new_price: float | None,
    pct_change: float | None,
    currency_symbol: str,
) -> str:
    if change_type == "became_unavailable":
        return "Product is now out of stock"
    if change_type == "became_available":
        base = "Product is back in stock"
        if new_price is not None:
            base += f" at {currency_symbol}{new_price:.2f}"
        return base

    old_str = f"{currency_symbol}{old_price:.2f}" if old_price is not None else "unknown"
    new_str = f"{currency_symbol}{new_price:.2f}" if new_price is not None else "unknown"
    pct_str = ""
    if pct_change is not None:
        sign = "+" if pct_change > 0 else ""
        pct_str = f" ({sign}{pct_change:.1f}%)"
    return f"{old_str} → {new_str}{pct_str}"


def _change_color(change_type: str) -> str:
    colors = {
        "price_decrease": "#10b981",    # green — good for buyer
        "price_increase": "#ef4444",    # red
        "became_unavailable": "#f59e0b", # amber
        "became_available": "#3b82f6",   # blue
    }
    return colors.get(change_type, "#6366f1")


def _change_label(change_type: str) -> str:
    labels = {
        "price_decrease": "🔽 Price Drop",
        "price_increase": "🔼 Price Increase",
        "became_unavailable": "⚠️ Out of Stock",
        "became_available": "✅ Back in Stock",
    }
    return labels.get(change_type, "📊 Price Change")


def _currency_symbol(currency: str) -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$"}
    return symbols.get(currency.upper(), f"{currency} ")
