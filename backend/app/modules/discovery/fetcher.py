"""
HTTP fetcher for discovery — fetches sitemaps and product JSON.

Design decisions:
- Uses httpx (async) with explicit timeouts
- Respects rate limiting with configurable delay between requests to same host
- Exponential backoff on 429 / 5xx responses
- Hard limit on response size (prevents OOM on huge responses)
- Does NOT follow redirects to a different host (SSRF prevention)
- User-Agent is set to a real browser string (some stores block bots)
"""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Limits
_MAX_RESPONSE_BYTES = 50 * 1024 * 1024  # 50 MB — sitemaps can be large
_MAX_PRODUCT_JSON_BYTES = 5 * 1024 * 1024  # 5 MB per product
_USER_AGENT = (
    "Mozilla/5.0 (compatible; PricePlus/1.0; +https://priceplus.app/bot)"
)

# Retry config
_MAX_RETRIES = 3
_RETRY_DELAYS = [1.0, 3.0, 10.0]  # seconds between retries


class FetchError(Exception):
    """Raised when an HTTP fetch fails after all retries."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def fetch_sitemap(
    url: str,
    timeout: float = 30.0,
    rate_limit_delay: float = 0.5,
) -> bytes:
    """
    Fetch a sitemap XML file.

    Args:
        url: The sitemap URL to fetch
        timeout: Request timeout in seconds
        rate_limit_delay: Seconds to wait before making the request
            (basic rate limiting — prevents hammering the store)

    Returns:
        Raw response bytes (XML content)

    Raises:
        FetchError on HTTP errors, timeouts, or size limit exceeded
    """
    if rate_limit_delay > 0:
        await asyncio.sleep(rate_limit_delay)

    return await _fetch_with_retry(
        url=url,
        timeout=timeout,
        max_bytes=_MAX_RESPONSE_BYTES,
        accept="application/xml,text/xml,*/*",
    )


async def fetch_product_json(
    store_url: str,
    handle: str,
    timeout: float = 15.0,
    rate_limit_delay: float = 0.5,
) -> dict | None:
    """
    Fetch /products/{handle}.json from a Shopify store.

    Returns the parsed JSON dict on success, None if the product is not
    accessible via .json (404, store restrictions, etc.).

    Note: This is SEPARATE from sitemap discovery. We use .json only to
    enrich discovered products with title/price/availability data.
    """
    url = f"{store_url.rstrip('/')}/products/{handle}.json"

    if rate_limit_delay > 0:
        await asyncio.sleep(rate_limit_delay)

    try:
        raw = await _fetch_with_retry(
            url=url,
            timeout=timeout,
            max_bytes=_MAX_PRODUCT_JSON_BYTES,
            accept="application/json",
        )
        import json
        return json.loads(raw)
    except FetchError as e:
        if e.status_code == 404:
            logger.debug("Product JSON not available for handle %r: 404", handle)
            return None
        logger.warning("Failed to fetch product JSON for %r: %s", handle, e)
        return None
    except Exception as e:
        logger.warning("Error parsing product JSON for %r: %s", handle, e)
        return None


async def _fetch_with_retry(
    url: str,
    timeout: float,
    max_bytes: int,
    accept: str,
) -> bytes:
    """
    Fetch a URL with exponential backoff on transient errors.

    Retries on:
    - 429 Too Many Requests (with Retry-After if provided)
    - 500, 502, 503, 504 server errors

    Does NOT retry on:
    - 404 Not Found (raise immediately)
    - 4xx client errors (raise immediately)
    - Redirect to different host (raise immediately)
    """
    parsed_url = urlparse(url)
    original_host = parsed_url.hostname or ""

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": accept,
                        "Accept-Encoding": "gzip, deflate",
                    },
                )

            # Check for redirect to different host (SSRF prevention)
            final_host = urlparse(str(response.url)).hostname or ""
            if final_host.lower() != original_host.lower():
                raise FetchError(
                    f"Redirect to different host detected: {original_host} → {final_host}",
                    status_code=None,
                )

            if response.status_code == 404:
                raise FetchError(f"Not found: {url}", status_code=404)

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", _RETRY_DELAYS[attempt]))
                logger.warning(
                    "Rate limited by %s, waiting %.1fs (attempt %d/%d)",
                    original_host,
                    retry_after,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(retry_after)
                last_error = FetchError("Rate limited", status_code=429)
                continue

            if response.status_code >= 500:
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.warning(
                    "Server error %d from %s, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    url,
                    delay,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                last_error = FetchError(
                    f"Server error: {response.status_code}",
                    status_code=response.status_code,
                )
                continue

            if response.status_code >= 400:
                raise FetchError(
                    f"HTTP {response.status_code}: {url}",
                    status_code=response.status_code,
                )

            content = response.content
            if len(content) > max_bytes:
                raise FetchError(
                    f"Response too large: {len(content)} bytes (max {max_bytes})",
                    status_code=None,
                )

            return content

        except FetchError:
            raise
        except httpx.TimeoutException:
            delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
            logger.warning(
                "Timeout fetching %s (attempt %d/%d), retrying in %.1fs",
                url,
                attempt + 1,
                _MAX_RETRIES,
                delay,
            )
            last_error = FetchError(f"Timeout fetching {url}")
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)
        except httpx.RequestError as exc:
            last_error = FetchError(f"Network error: {exc}")
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                await asyncio.sleep(delay)

    raise last_error or FetchError(f"All retries failed for {url}")
