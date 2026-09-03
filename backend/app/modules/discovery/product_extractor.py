"""
ProductDataExtractor — enriches discovered products with price/title/availability.

Fetches /products/{handle}.json AFTER the URL is discovered via sitemap.
This is strictly separate from discovery (sitemap-first).

The .json endpoint returns Shopify's product object:
{
  "product": {
    "id": 123,
    "title": "Blue Widget",
    "handle": "blue-widget",
    "variants": [
      {"id": 456, "price": "19.99", "available": true, ...}
    ],
    "images": [{"src": "https://...", ...}],
    ...
  }
}

We extract the MINIMUM variant price as the "current price" since that's
what's most relevant to a dropshipper watching competitor pricing.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedProductData:
    """Parsed product data from /products/{handle}.json."""

    title: str | None
    price: float | None
    currency: str
    is_available: bool
    image_url: str | None
    raw_data: dict


def extract_product_data(json_response: dict) -> ExtractedProductData | None:
    """
    Parse a Shopify /products/{handle}.json response.

    Returns ExtractedProductData on success, None if the structure is
    unrecognizable (logs a warning).

    Price strategy: minimum variant price (most competitive / dropshipper-relevant).
    Availability: True if ANY variant is available.
    """
    try:
        product = json_response.get("product", {})
        if not product:
            logger.warning("Product JSON has no 'product' key")
            return None

        title = product.get("title") or None

        # Extract price from variants
        variants = product.get("variants", [])
        price: float | None = None
        is_available = False

        for variant in variants:
            # Availability
            if variant.get("available", False):
                is_available = True

            # Price — stored as string in Shopify API
            variant_price_str = variant.get("price", "")
            if variant_price_str:
                try:
                    variant_price = float(variant_price_str)
                    if price is None or variant_price < price:
                        price = variant_price
                except ValueError:
                    pass

        # Primary image
        image_url: str | None = None
        images = product.get("images", [])
        if images:
            image_url = images[0].get("src") or None

        return ExtractedProductData(
            title=title,
            price=price,
            currency="USD",  # Shopify storefront API does not return currency in .json
            is_available=is_available,
            image_url=image_url,
            raw_data=json_response,
        )

    except Exception as exc:
        logger.warning("Error extracting product data: %s", exc)
        return None
