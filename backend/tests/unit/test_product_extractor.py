"""
Unit tests for product_extractor.py.

Tests the parsing of Shopify /products/{handle}.json responses.
"""

import pytest

from app.modules.discovery.product_extractor import extract_product_data


def _make_product_json(
    title: str = "Test Product",
    variants: list | None = None,
    images: list | None = None,
) -> dict:
    """Helper: build a minimal Shopify product JSON response."""
    if variants is None:
        variants = [{"price": "19.99", "available": True}]
    if images is None:
        images = [{"src": "https://cdn.example.com/product.jpg"}]
    return {
        "product": {
            "id": 1234567890,
            "title": title,
            "handle": "test-product",
            "variants": variants,
            "images": images,
        }
    }


class TestExtractProductData:
    def test_extracts_title(self):
        data = extract_product_data(_make_product_json(title="Blue Widget"))
        assert data is not None
        assert data.title == "Blue Widget"

    def test_extracts_price_from_single_variant(self):
        data = extract_product_data(_make_product_json(
            variants=[{"price": "29.99", "available": True}]
        ))
        assert data is not None
        assert data.price == pytest.approx(29.99)

    def test_extracts_minimum_price_from_multiple_variants(self):
        """When multiple variants, price should be the minimum."""
        data = extract_product_data(_make_product_json(
            variants=[
                {"price": "49.99", "available": True},
                {"price": "19.99", "available": True},  # minimum
                {"price": "34.99", "available": False},
            ]
        ))
        assert data is not None
        assert data.price == pytest.approx(19.99)

    def test_empty_variants_gives_no_price(self):
        data = extract_product_data(_make_product_json(variants=[]))
        assert data is not None
        assert data.price is None

    def test_zero_price_discontinued(self):
        """Price $0.00 means the product is discontinued/hidden, not a free item."""
        data = extract_product_data(_make_product_json(
            variants=[{"price": "0.00"}]
        ))
        assert data is not None
        assert data.price is None          # $0 treated as no price (discontinued)
        assert data.is_discontinued is True
