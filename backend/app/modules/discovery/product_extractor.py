"""
ProductDataExtractor — enriches discovered products with price/title/availability.

Fetches /products/{handle}.json AFTER the URL is discovered via sitemap.
This is strictly separate from discovery (sitemap-first).

The .json endpoint returns Shopify's public storefront product object:
{
  "product": {
    "id": 123,
    "title": "Blue Widget",
    "handle": "blue-widget",
    "tags": "filter_Appetizer, global",
    "variants": [
      {
        "price": "19.99",
        "compare_at_price": "24.99",   <- non-empty = on sale
        "available": true,             <- present on public storefront API
        "inventory_management": "shopify",
        ...
      }
    ],
    "images": [{"src": "https://...", ...}],
    ...
  }
}

Key extraction rules:
- Availability: Use `available` bool when present (public storefront API always includes it).
  Fallback to inventory_management + inventory_quantity if not present.
- Price $0.00 means the product is discontinued/hidden — stored as None + is_discontinued=True.
- compare_at_price non-empty and > price means the product is ON SALE.
  We extract compare_at_price as the original/reference price for sale detection.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedProductData:
    """Parsed product data from /products/{handle}.json."""

    title: str | None
    price: float | None
    compare_at_price: float | None  # Original price before sale; None if not on sale
    currency: str
    is_discontinued: bool           # True when price == $0.00 (hidden/discontinued product)
    is_on_sale: bool                # True when compare_at_price > price
    image_url: str | None
    tags: list[str]                 # Raw Shopify tags from product.tags
    raw_data: dict


def _parse_price(price_str: str | None) -> float | None:
    """Parse a Shopify price string (e.g. '19.99') to float. Returns None on failure."""
    if not price_str:
        return None
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return None


def extract_product_data(json_response: dict) -> ExtractedProductData | None:
    """
    Parse a Shopify /products/{handle}.json response.

    Returns ExtractedProductData on success, None if the structure is
    unrecognizable (logs a warning).

    Price rules:
    - We take the MINIMUM variant price.
    - Price $0.00 → treated as discontinued (price=None, is_discontinued=True).
    - compare_at_price non-empty and > price → is_on_sale=True.
    """
    try:
        product = json_response.get("product", {})
        if not product:
            logger.warning("Product JSON has no 'product' key")
            return None

        title = product.get("title") or None

        # Tags
        tags_raw = product.get("tags", "")
        tags: list[str] = [
            t.strip() for t in tags_raw.split(",") if t.strip()
        ] if tags_raw else []

        # Extract prices from variants
        variants = product.get("variants", [])
        min_price: float | None = None
        min_compare_at_price: float | None = None

        for variant in variants:
            # ── Current Price ─────────────────────────────────────────────────
            variant_price = _parse_price(variant.get("price"))
            if variant_price is not None:
                if min_price is None or variant_price < min_price:
                    min_price = variant_price

            # ── Compare-at Price (original/crossed-out price when on sale) ───
            # compare_at_price is "" (empty string) when no sale; non-empty = sale price
            cap_str = variant.get("compare_at_price")
            if cap_str and str(cap_str).strip():  # non-empty, non-null
                cap = _parse_price(str(cap_str).strip())
                if cap is not None and cap > 0:
                    if min_compare_at_price is None or cap < min_compare_at_price:
                        min_compare_at_price = cap

        # ── Discontinued detection (price = $0.00) ────────────────────────────
        # A $0.00 price means the product is hidden/discontinued, not actually free
        is_discontinued = (min_price is not None and min_price == 0.0)
        final_price = None if is_discontinued else min_price

        # ── Sale detection ────────────────────────────────────────────────────
        # On sale only if compare_at_price > current price (both non-None, non-zero)
        is_on_sale = (
            final_price is not None
            and min_compare_at_price is not None
            and min_compare_at_price > final_price
        )
        compare_at_price = min_compare_at_price if is_on_sale else None

        # Primary image
        image_url: str | None = None
        images = product.get("images", [])
        if images:
            image_url = images[0].get("src") or None

        currency = "USD"  # Shopify storefront .json does not expose currency in public API

        logger.debug(
            "Extracted: title=%r price=%s compare_at=%s discontinued=%s on_sale=%s",
            title, final_price, compare_at_price, is_discontinued, is_on_sale,
        )

        return ExtractedProductData(
            title=title,
            price=final_price,
            compare_at_price=compare_at_price,
            currency=currency,
            is_discontinued=is_discontinued,
            is_on_sale=is_on_sale,
            image_url=image_url,
            tags=tags,
            raw_data=json_response,
        )

    except Exception as exc:
        logger.warning("Error extracting product data: %s", exc)
        return None
