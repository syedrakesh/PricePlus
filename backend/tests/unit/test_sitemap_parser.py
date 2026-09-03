"""
Unit tests for sitemap_parser.py.

Tests cover:
- Root sitemap: sitemapindex vs urlset detection
- Product sitemap identification by URL pattern
- Product URL validation (/products/{handle} pattern)
- URL normalization
- <lastmod> date parsing
- <image:image> extraction
- Malformed XML graceful handling
- Partial failure tolerance (one bad URL doesn't abort the rest)
- Multiple product sitemaps
- Query parameter preservation in sitemap index URLs
"""


import pytest

from app.modules.discovery.sitemap_parser import (
    _is_product_sitemap_url,
    _local_name,
    _parse_lastmod,
    parse_product_sitemap,
    parse_root_sitemap,
)

STORE_URL = "https://shop.example.com"
STORE_HOST = "shop.example.com"


# ─── Fixtures: XML templates ──────────────────────────────────────────────────

def _sitemap_index(*sitemap_urls: str) -> bytes:
    """Build a <sitemapindex> XML with the given child sitemap URLs."""
    from html import escape
    entries = "\n".join(
        f"    <sitemap><loc>{escape(url)}</loc></sitemap>" for url in sitemap_urls
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</sitemapindex>"""
    return xml.encode()


def _urlset(*urls: str, with_lastmod: bool = False, with_image: bool = False) -> bytes:
    """Build a <urlset> XML with the given product URLs."""
    entries = []
    for url in urls:
        lastmod = "  <lastmod>2024-01-15</lastmod>" if with_lastmod else ""
        image = (
            "  <image:image><image:loc>https://cdn.example.com/img.jpg</image:loc></image:image>"
            if with_image
            else ""
        )
        entries.append(f"  <url>\n    <loc>{url}</loc>\n{lastmod}\n{image}\n  </url>")
    content = "\n".join(entries)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
{content}
</urlset>"""
    return xml.encode()


# ─── parse_root_sitemap ───────────────────────────────────────────────────────

class TestParseRootSitemap:
    def test_sitemapindex_identifies_product_sitemaps(self):
        xml = _sitemap_index(
            "https://shop.example.com/sitemap_products_1.xml",
            "https://shop.example.com/sitemap_products_2.xml",
            "https://shop.example.com/sitemap_pages_1.xml",
            "https://shop.example.com/sitemap_blogs_1.xml",
            "https://shop.example.com/sitemap_collections_1.xml",
        )
        result = parse_root_sitemap(xml, STORE_URL)
        assert result.is_sitemapindex is True
        assert result.total_sitemaps_found == 5
        assert len(result.product_sitemap_urls) == 2
        assert "sitemap_products_1.xml" in result.product_sitemap_urls[0]
        assert "sitemap_products_2.xml" in result.product_sitemap_urls[1]

    def test_urlset_root_returns_self_as_product_sitemap(self):
        """When root IS a <urlset>, treat it directly as the product sitemap."""
        xml = _urlset("https://shop.example.com/products/blue-widget")
        result = parse_root_sitemap(xml, STORE_URL)
        assert result.is_sitemapindex is False
        assert len(result.product_sitemap_urls) == 1
        assert "sitemap.xml" in result.product_sitemap_urls[0]

    def test_malformed_xml_returns_empty(self):
        result = parse_root_sitemap(b"<this is not valid xml>>>", STORE_URL)
        assert result.product_sitemap_urls == []
        assert result.is_sitemapindex is False

    def test_empty_sitemapindex_returns_empty(self):
        xml = b"""<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></sitemapindex>"""
        result = parse_root_sitemap(xml, STORE_URL)
        assert result.product_sitemap_urls == []
        assert result.total_sitemaps_found == 0

    def test_query_params_preserved_in_sitemap_urls(self):
        """Query parameters on product sitemap URLs must be preserved exactly."""
        xml = _sitemap_index(
            "https://shop.example.com/sitemap_products_1.xml?from=1&to=500",
        )
        result = parse_root_sitemap(xml, STORE_URL)
        assert len(result.product_sitemap_urls) == 1
        assert "from=1&to=500" in result.product_sitemap_urls[0]

    def test_unknown_root_element_returns_empty(self):
        xml = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Not a sitemap</title></feed>"""
        result = parse_root_sitemap(xml, STORE_URL)
        assert result.product_sitemap_urls == []


# ─── _is_product_sitemap_url ─────────────────────────────────────────────────

class TestIsProductSitemapUrl:
    @pytest.mark.parametrize("url", [
        "https://shop.example.com/sitemap_products_1.xml",
        "https://shop.example.com/sitemap_products_2.xml",
        "https://shop.example.com/sitemap_products_1.xml?from=1&to=500",
        "https://shop.example.com/sitemap-products.xml",
        "https://shop.example.com/products-sitemap.xml",
        "https://shop.example.com/sitemap_product.xml",
    ])
    def test_product_sitemap_urls_identified(self, url: str):
        assert _is_product_sitemap_url(url) is True

    @pytest.mark.parametrize("url", [
        "https://shop.example.com/sitemap_pages_1.xml",
        "https://shop.example.com/sitemap_blogs_1.xml",
        "https://shop.example.com/sitemap_collections_1.xml",
        "https://shop.example.com/sitemap.xml",
        "https://shop.example.com/sitemap_1.xml",
    ])
    def test_non_product_sitemap_urls_rejected(self, url: str):
        assert _is_product_sitemap_url(url) is False


# ─── parse_product_sitemap ────────────────────────────────────────────────────

class TestParseProductSitemap:
    SITEMAP_URL = "https://shop.example.com/sitemap_products_1.xml"

    def test_valid_product_urls_parsed(self):
        xml = _urlset(
            "https://shop.example.com/products/blue-widget",
            "https://shop.example.com/products/red-gadget",
        )
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 2
        handles = {r.handle for r in results}
        assert handles == {"blue-widget", "red-gadget"}

    def test_non_product_urls_skipped(self):
        xml = _urlset(
            "https://shop.example.com/products/blue-widget",  # valid
            "https://shop.example.com/collections/all",        # invalid
            "https://shop.example.com/pages/about",            # invalid
            "https://shop.example.com/",                       # invalid
        )
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 1
        assert results[0].handle == "blue-widget"

    def test_lastmod_parsed(self):
        xml = _urlset("https://shop.example.com/products/widget", with_lastmod=True)
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 1
        assert results[0].lastmod is not None
        assert results[0].lastmod.year == 2024
        assert results[0].lastmod.month == 1
        assert results[0].lastmod.day == 15

    def test_image_url_extracted(self):
        xml = _urlset("https://shop.example.com/products/widget", with_image=True)
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 1
        assert results[0].image_url == "https://cdn.example.com/img.jpg"

    def test_missing_lastmod_and_image_is_ok(self):
        xml = _urlset("https://shop.example.com/products/bare-product")
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 1
        assert results[0].lastmod is None
        assert results[0].image_url is None

    def test_malformed_xml_returns_empty(self):
        results = parse_product_sitemap(b"<broken xml", self.SITEMAP_URL, STORE_HOST)
        assert results == []

    def test_empty_urlset_returns_empty(self):
        xml = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert results == []

    def test_cross_host_urls_rejected(self):
        """URLs belonging to a different store host must be rejected."""
        xml = _urlset(
            "https://other-store.com/products/stolen-product",  # wrong host
        )
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert results == []

    def test_url_normalized_to_canonical(self):
        """Product URLs are normalized: lowercase host, no trailing slash."""
        xml = _urlset("https://SHOP.EXAMPLE.COM/products/My-Widget/")
        results = parse_product_sitemap(xml, self.SITEMAP_URL, "SHOP.EXAMPLE.COM")
        assert len(results) == 1
        assert results[0].loc == "https://shop.example.com/products/my-widget"
        assert results[0].handle == "my-widget"

    def test_sitemap_source_is_set(self):
        xml = _urlset("https://shop.example.com/products/widget")
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert results[0].sitemap_source == self.SITEMAP_URL

    def test_large_urlset_parsed_correctly(self):
        """Performance: parse a urlset with 500 product URLs."""
        urls = [f"https://shop.example.com/products/product-{i}" for i in range(500)]
        xml = _urlset(*urls)
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 500

    def test_duplicate_urls_in_sitemap_both_parsed(self):
        """Deduplication happens at the DB level, not in the parser."""
        xml = _urlset(
            "https://shop.example.com/products/widget",
            "https://shop.example.com/products/widget",  # duplicate
        )
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 2  # Parser doesn't deduplicate

    def test_url_with_query_string_is_normalized(self):
        """Query strings are stripped from product URLs during normalization."""
        xml = _urlset("https://shop.example.com/products/widget?variant=123")
        results = parse_product_sitemap(xml, self.SITEMAP_URL, STORE_HOST)
        assert len(results) == 1
        assert "?" not in results[0].loc


# ─── _parse_lastmod ───────────────────────────────────────────────────────────

class TestParseLastmod:
    def test_date_format(self):
        result = _parse_lastmod("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_datetime_with_timezone(self):
        result = _parse_lastmod("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.hour == 10

    def test_datetime_with_z_suffix(self):
        result = _parse_lastmod("2024-01-15T10:30:00Z")
        assert result is not None

    def test_invalid_format_returns_none(self):
        result = _parse_lastmod("not-a-date")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_lastmod("")
        assert result is None


# ─── _local_name ─────────────────────────────────────────────────────────────

class TestLocalName:
    def test_strips_namespace(self):
        assert _local_name("{http://www.sitemaps.org/schemas/sitemap/0.9}urlset") == "urlset"

    def test_no_namespace_unchanged(self):
        assert _local_name("urlset") == "urlset"

    def test_image_namespace(self):
        assert _local_name("{http://www.google.com/schemas/sitemap-image/1.1}image") == "image"
