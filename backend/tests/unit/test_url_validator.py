"""
Unit tests for URL validation and SSRF protection.

No database or network required.
Tests cover: format validation, SSRF blocking, URL normalization.

Note: Tests that require real DNS resolution are skipped if network is unavailable.
For the private IP tests, we patch socket.getaddrinfo to return controlled IPs.
"""

from unittest.mock import patch

import pytest

from app.modules.stores.url_validator import URLValidationError, validate_store_url


def _make_addr_info(ip: str) -> list:
    """Helper: return socket.getaddrinfo-shaped result for a given IP."""
    return [(None, None, None, None, (ip, 0))]


class TestURLFormatValidation:
    def test_empty_url_rejected(self):
        with pytest.raises(URLValidationError, match="empty"):
            validate_store_url("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(URLValidationError, match="empty"):
            validate_store_url("   ")

    def test_ftp_scheme_rejected(self):
        with (
            pytest.raises(URLValidationError, match="http"),
            patch("socket.getaddrinfo", return_value=_make_addr_info("93.184.216.34")),
        ):
            validate_store_url("ftp://example.com")

    def test_no_hostname_rejected(self):
        with pytest.raises(URLValidationError):
            validate_store_url("https://")

    def test_localhost_rejected(self):
        with pytest.raises(URLValidationError, match="Local"):
            validate_store_url("https://localhost")

    def test_local_domain_rejected(self):
        with pytest.raises(URLValidationError, match="Local"):
            validate_store_url("https://mystore.local")

    def test_url_missing_scheme_gets_https_prepended(self):
        """User-friendly: bare hostnames get https:// added automatically."""
        with patch("socket.getaddrinfo", return_value=_make_addr_info("93.184.216.34")):
            result = validate_store_url("example.myshopify.com")
        assert result.startswith("https://")

    def test_http_scheme_accepted(self):
        """http:// is accepted (some stores may not have HTTPS)."""
        with patch("socket.getaddrinfo", return_value=_make_addr_info("93.184.216.34")):
            result = validate_store_url("http://example.myshopify.com")
        assert result.startswith("http://")


class TestSSRFProtection:
    """Test that private/reserved IPs are blocked."""

    def _validate_with_ip(self, url: str, ip: str) -> str:
        with patch("socket.getaddrinfo", return_value=_make_addr_info(ip)):
            return validate_store_url(url)

    def _assert_blocked(self, url: str, ip: str) -> None:
        with (
            patch("socket.getaddrinfo", return_value=_make_addr_info(ip)),
            pytest.raises(URLValidationError, match="private|reserved"),
        ):
            validate_store_url(url)

    def test_loopback_127_blocked(self):
        self._assert_blocked("https://evil.example.com", "127.0.0.1")

    def test_loopback_127_any_blocked(self):
        self._assert_blocked("https://evil.example.com", "127.0.0.2")

    def test_private_10_blocked(self):
        self._assert_blocked("https://evil.example.com", "10.0.0.1")

    def test_private_192_168_blocked(self):
        self._assert_blocked("https://evil.example.com", "192.168.1.1")

    def test_private_172_16_blocked(self):
        self._assert_blocked("https://evil.example.com", "172.16.0.1")

    def test_cloud_metadata_169_254_blocked(self):
        """AWS/GCP/Azure metadata endpoints — must be blocked."""
        self._assert_blocked("https://evil.example.com", "169.254.169.254")

    def test_zero_network_blocked(self):
        self._assert_blocked("https://evil.example.com", "0.0.0.1")

    def test_public_ip_allowed(self):
        """A legitimate public IP must not be blocked."""
        result = self._validate_with_ip("https://shop.example.com", "93.184.216.34")
        assert "shop.example.com" in result

    def test_dns_failure_raises_validation_error(self):
        import socket
        with (
            patch("socket.getaddrinfo", side_effect=socket.gaierror("NXDOMAIN")),
            pytest.raises(URLValidationError, match="resolve"),
        ):
            validate_store_url("https://this-domain-does-not-exist-xyz.example.com")


class TestURLNormalization:
    def _validate(self, url: str) -> str:
        with patch("socket.getaddrinfo", return_value=_make_addr_info("93.184.216.34")):
            return validate_store_url(url)

    def test_hostname_is_lowercased(self):
        result = self._validate("https://EXAMPLE.myshopify.com")
        assert "example.myshopify.com" in result
        assert "EXAMPLE" not in result

    def test_trailing_slash_stripped(self):
        result = self._validate("https://example.myshopify.com/")
        assert not result.endswith("/")

    def test_path_is_stripped_to_origin(self):
        """Only the origin (scheme + host) is stored — path is dropped."""
        result = self._validate("https://example.myshopify.com/collections/all")
        assert "/collections" not in result

    def test_query_string_stripped(self):
        result = self._validate("https://example.myshopify.com?ref=google")
        assert "ref" not in result

    def test_fragment_stripped(self):
        result = self._validate("https://example.myshopify.com#section")
        assert "#" not in result

    def test_same_store_different_paths_normalize_to_same(self):
        url1 = self._validate("https://example.myshopify.com/")
        url2 = self._validate("https://example.myshopify.com/products")
        assert url1 == url2
