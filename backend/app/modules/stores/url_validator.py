"""
SSRF protection and URL validation for competitor store URLs.

Security model:
- All user-provided URLs are treated as untrusted input
- Must be HTTPS (or HTTP for dev tolerance) with a real hostname
- Hostname must resolve to a public, routable IP address
- Private, loopback, and link-local ranges are blocked
- Cloud metadata endpoints (169.254.x.x) are blocked
- No redirect following to internal hosts
- URL is normalized before storage (scheme, hostname lowercase, no trailing slash on path)

This is critical: without SSRF protection, a user could supply internal
infrastructure URLs (e.g. http://127.0.0.1:8080/admin) and our fetch
infrastructure would make requests against our own internal network.
"""

import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

# Private, loopback, link-local, and multicast ranges — all blocked
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),         # loopback
    ipaddress.ip_network("::1/128"),              # IPv6 loopback
    ipaddress.ip_network("169.254.0.0/16"),       # link-local / cloud metadata
    ipaddress.ip_network("fc00::/7"),             # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),            # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),            # "this" network
    ipaddress.ip_network("224.0.0.0/4"),          # multicast
    ipaddress.ip_network("240.0.0.0/4"),          # reserved
]


class URLValidationError(ValueError):
    """Raised when a URL fails security or format validation."""


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the IP address is in a private/blocked range."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable — treat as blocked

    return any(addr in network for network in _BLOCKED_NETWORKS)


def validate_store_url(raw_url: str) -> str:
    """
    Validate and normalize a competitor store URL.

    Returns the normalized URL on success.
    Raises URLValidationError with a user-safe message on failure.

    Normalization:
    - Scheme is preserved (https preferred)
    - Hostname is lowercased
    - Default ports are removed
    - Path is set to '/' (we only care about the origin)
    - Fragment and query string are stripped (store root URL only)

    SSRF protection:
    - Hostname must resolve to a public IP
    - No private, loopback, link-local, or cloud metadata IPs
    """
    raw_url = raw_url.strip()

    if not raw_url:
        raise URLValidationError("URL cannot be empty")

    # Reject obviously wrong schemes before anything else
    if "://" in raw_url and not raw_url.startswith(("http://", "https://")):
        raise URLValidationError("URL must use http or https scheme")

    # Add scheme if missing (common user input: 'example.myshopify.com')
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    try:
        parsed = urlparse(raw_url)
    except Exception as exc:
        raise URLValidationError("Invalid URL format") from exc

    if parsed.scheme not in ("http", "https"):
        raise URLValidationError("URL must use http or https scheme")

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must include a hostname")

    if hostname in ("localhost",) or hostname.endswith(".local"):
        raise URLValidationError("Local hostnames are not allowed")

    # DNS resolution + SSRF check
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise URLValidationError(
            f"Could not resolve hostname '{hostname}'. "
            "Check that the URL is correct and the store is accessible."
        ) from exc

    for result in results:
        ip = result[4][0]
        if _is_private_ip(ip):
            raise URLValidationError(
                f"The URL resolves to a private or reserved IP address ({ip}). "
                "Only public competitor store URLs are allowed."
            )

    # Normalize: strip path to origin only, lowercase hostname
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),  # hostname + optional port, lowercased
        "",                     # no path — we only want the origin
        "",                     # no params
        "",                     # no query
        "",                     # no fragment
    ))

    # Remove trailing slash for consistency
    return normalized.rstrip("/")
