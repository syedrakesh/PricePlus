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

    def test_available_true_when_any_variant_available(self):
        data = extract_product_data(_make_product_json(
            variants=[
                {"price": "10.00", "available": False},
                {"price": "10.00", "available": True},   # one available
            ]
        ))
        assert data is not None
        assert data.is_available is True

    def test_available_false_when_no_variants_available(self):
        data = extract_product_data(_make_product_json(
            variants=[
                {"price": "10.00", "available": False},
                {"price": "10.00", "available": False},
            ]
        ))
        assert data is not None
        assert data.is_available is False

    def test_extracts_first_image(self):
        data = extract_product_data(_make_product_json(
            images=[
                {"src": "https://cdn.example.com/first.jpg"},
                {"src": "https://cdn.example.com/second.jpg"},
            ]
        ))
        assert data is not None
        assert data.image_url == "https://cdn.example.com/first.jpg"

    def test_no_images_returns_none_image_url(self):
        data = extract_product_data(_make_product_json(images=[]))
        assert data is not None
        assert data.image_url is None

    def test_currency_defaults_to_usd(self):
        data = extract_product_data(_make_product_json())
        assert data is not None
        assert data.currency == "USD"

    def test_raw_data_preserved(self):
        json_input = _make_product_json()
        data = extract_product_data(json_input)
        assert data is not None
        assert data.raw_data == json_input

    def test_empty_product_key_returns_none(self):
        result = extract_product_data({"product": {}})
        assert result is None

    def test_missing_product_key_returns_none(self):
        result = extract_product_data({"not_a_product": {}})
        assert result is None

    def test_invalid_price_string_is_skipped(self):
        data = extract_product_data(_make_product_json(
            variants=[{"price": "not-a-price", "available": True}]
        ))
        assert data is not None
        assert data.price is None  # invalid price = no price extracted

    def test_empty_variants_gives_no_price(self):
        data = extract_product_data(_make_product_json(variants=[]))
        assert data is not None
        assert data.price is None
        assert data.is_available is False

    def test_zero_price_extracted(self):
        data = extract_product_data(_make_product_json(
            variants=[{"price": "0.00", "available": True}]
        ))
        assert data is not None
        assert data.price == pytest.approx(0.0)
