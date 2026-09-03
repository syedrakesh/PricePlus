"""
Sitemap XML parser — sitemap-first product discovery.

Architecture (per spec):
1. Fetch /sitemap.xml from the store root
2. Detect root type:
   - <sitemapindex>: contains <sitemap><loc> entries pointing to child sitemaps
   - <urlset>:       direct URL listing (treat whole thing as one product sitemap)
3. From a <sitemapindex>, identify PRODUCT sitemaps:
   - URL path or filename contains 'product' (case-insensitive)
   - Examples: sitemap_products_1.xml, sitemap-products.xml, products-sitemap.xml
   - Query parameters are PRESERVED exactly as-is
   - Non-product sitemaps (pages, collections, blogs) are ignored
4. For each product sitemap, parse all <url> entries:
   - Extract <loc>, <lastmod>, <image:image><image:loc>
   - Validate: <loc> must match /products/{handle} path pattern
   - Normalize: canonical URL (lowercase host, strip trailing slash, no query/fragment)

Robustness:
- Gracefully handles missing <lastmod> and <image:image>
- Returns empty list on malformed XML (logs warning, does not raise)
- Does NOT follow redirects to different hosts (SSRF prevention)
- Namespace-aware XML parsing (Shopify uses image: namespace)
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from lxml import etree

logger = logging.getLogger(__name__)

# Sitemap XML namespaces
_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
    "xhtml": "http://www.w3.org/1999/xhtml",
}

# Pattern: URL path must be exactly /products/{handle}
# handle: alphanumeric, hyphens, underscores — Shopify's slug format
_PRODUCT_PATH_RE = re.compile(
    r"^/products/([a-z0-9][a-z0-9\-_]*)/?$",
    re.IGNORECASE,
)

# Patterns that identify a sitemap as a product sitemap (applied to URL path)
_PRODUCT_SITEMAP_PATTERNS = [
    re.compile(r"sitemap[_\-]products?", re.IGNORECASE),
    re.compile(r"products?[_\-]sitemap", re.IGNORECASE),
]


@dataclass
class ParsedProductURL:
    """A single product URL parsed from a product sitemap."""

    loc: str
    """Canonical product URL (e.g. https://store.com/products/blue-widget)"""

    handle: str
    """Shopify product handle extracted from the URL path."""

    lastmod: datetime | None
    """ISO 8601 last modification date from <lastmod> tag, if present."""

    image_url: str | None
    """Primary image URL from <image:image><image:loc>, if present."""

    sitemap_source: str
    """URL of the product sitemap this was parsed from."""


class SitemapParseResult(NamedTuple):
    """Result of parsing a root sitemap."""

    product_sitemap_urls: list[str]
    """All child sitemap URLs identified as product sitemaps."""

    is_sitemapindex: bool
    """True if root was a <sitemapindex>, False if it was a direct <urlset>."""

    total_sitemaps_found: int
    """Total number of child sitemaps in the index (0 if not a sitemapindex)."""


def parse_root_sitemap(xml_bytes: bytes, store_url: str) -> SitemapParseResult:
    """
    Parse the root sitemap.xml.

    Handles both <sitemapindex> and <urlset> root elements.

    For <sitemapindex>:
      - Extracts all <sitemap><loc> URLs
      - Filters to those that look like product sitemaps
      - Returns the filtered list

    For <urlset>:
      - Treats the root itself as a product sitemap
      - Returns [store_url/sitemap.xml] as the single product sitemap

    Args:
        xml_bytes: Raw XML content of the root sitemap
        store_url: The competitor store's base URL (used as fallback)

    Returns:
        SitemapParseResult with product sitemap URLs identified
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning("Failed to parse root sitemap XML: %s", exc)
        return SitemapParseResult(
            product_sitemap_urls=[],
            is_sitemapindex=False,
            total_sitemaps_found=0,
        )

    tag = _local_name(root.tag)

    if tag == "sitemapindex":
        return _parse_sitemapindex(root)
    elif tag == "urlset":
        # Root is already a URL listing — treat it as a product sitemap
        # We'll let parse_product_sitemap() filter the URLs
        root_url = store_url.rstrip("/") + "/sitemap.xml"
        return SitemapParseResult(
            product_sitemap_urls=[root_url],
            is_sitemapindex=False,
            total_sitemaps_found=0,
        )
    else:
        logger.warning("Unknown sitemap root element: %s", root.tag)
        return SitemapParseResult(
            product_sitemap_urls=[],
            is_sitemapindex=False,
            total_sitemaps_found=0,
        )


def _parse_sitemapindex(root: etree._Element) -> SitemapParseResult:
    """Extract child sitemap URLs from a <sitemapindex> and filter to product sitemaps."""
    all_urls: list[str] = []

    for sitemap_elem in root:
        if _local_name(sitemap_elem.tag) != "sitemap":
            continue
        for child in sitemap_elem:
            if _local_name(child.tag) == "loc" and child.text:
                all_urls.append(child.text.strip())

    product_urls = [url for url in all_urls if _is_product_sitemap_url(url)]

    logger.info(
        "Sitemap index parsed: %d total, %d product sitemaps",
        len(all_urls),
        len(product_urls),
    )

    return SitemapParseResult(
        product_sitemap_urls=product_urls,
        is_sitemapindex=True,
        total_sitemaps_found=len(all_urls),
    )


def _is_product_sitemap_url(url: str) -> bool:
    """
    Return True if the sitemap URL looks like a product sitemap.

    Matches on the URL path (not query string) using known patterns.
    Query parameters are preserved when the URL is used — only the path
    is inspected for pattern matching.
    """
    # Strip query string for pattern matching only
    path = url.split("?")[0]
    return any(pattern.search(path) for pattern in _PRODUCT_SITEMAP_PATTERNS)


def parse_product_sitemap(
    xml_bytes: bytes,
    sitemap_url: str,
    store_host: str,
) -> list[ParsedProductURL]:
    """
    Parse a product sitemap <urlset> and return validated product URLs.

    Args:
        xml_bytes: Raw XML content of the product sitemap
        sitemap_url: URL this sitemap was fetched from (used for sitemap_source)
        store_host: Expected hostname of the competitor store (for host validation)

    Returns:
        List of ParsedProductURL for all valid /products/{handle} URLs found.
        Invalid URLs are logged and skipped (partial failure tolerance).
    """
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        logger.warning("Failed to parse product sitemap %s: %s", sitemap_url, exc)
        return []

    results: list[ParsedProductURL] = []

    for url_elem in root:
        if _local_name(url_elem.tag) != "url":
            continue

        loc: str | None = None
        lastmod: datetime | None = None
        image_url: str | None = None

        for child in url_elem:
            child_tag = _local_name(child.tag)

            if child_tag == "loc" and child.text:
                loc = child.text.strip()

            elif child_tag == "lastmod" and child.text:
                lastmod = _parse_lastmod(child.text.strip())

            elif child_tag == "image" and image_url is None:
                # <image:image> — extract the first image's <image:loc>
                for img_child in child:
                    if _local_name(img_child.tag) == "loc" and img_child.text:
                        image_url = img_child.text.strip()
                        break

        if not loc:
            continue

        # Validate: must be a /products/{handle} URL on the expected host
        parsed = _validate_product_url(loc, store_host)
        if parsed is None:
            logger.debug("Skipping non-product URL: %s", loc)
            continue

        handle, normalized_loc = parsed
        results.append(
            ParsedProductURL(
                loc=normalized_loc,
                handle=handle,
                lastmod=lastmod,
                image_url=image_url,
                sitemap_source=sitemap_url,
            )
        )

    logger.info(
        "Product sitemap %s: %d valid product URLs found",
        sitemap_url,
        len(results),
    )
    return results


def _validate_product_url(
    loc: str,
    store_host: str,
) -> tuple[str, str] | None:
    """
    Validate a <loc> URL from a product sitemap.

    Returns (handle, normalized_url) if valid, None otherwise.

    Validation rules:
    1. URL must parse correctly
    2. Hostname must match the store host (prevent cross-store contamination)
    3. Path must match /products/{handle} exactly
    """
    from urllib.parse import urlparse, urlunparse

    try:
        parsed = urlparse(loc)
    except Exception:
        return None

    # Hostname check — must belong to this store
    if parsed.hostname and parsed.hostname.lower() != store_host.lower():
        return None

    # Path must match /products/{handle}
    path = parsed.path.rstrip("/")
    match = _PRODUCT_PATH_RE.match(path)
    if not match:
        return None

    handle = match.group(1).lower()

    # Normalize: lowercase hostname, no query/fragment, path as-is
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        f"/products/{handle}",
        "",
        "",
        "",
    ))

    return handle, normalized


def _parse_lastmod(text: str) -> datetime | None:
    """Parse a <lastmod> value which may be a date (YYYY-MM-DD) or datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    logger.debug("Could not parse lastmod value: %r", text)
    return None


def _local_name(tag: str) -> str:
    """Strip XML namespace from a tag name. '{ns}localname' → 'localname'."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag
