"""
Unit tests for discovery error message sanitization and raw error logging.
"""

import pytest
from app.modules.discovery.fetcher import FetchError
from app.modules.discovery.orchestrator import _sanitize_discovery_error


def test_sanitize_sitemap_not_found_404():
    exc = FetchError("Not found: https://york-fashion.com/sitemap.xml", status_code=404)
    user_msg, raw_err = _sanitize_discovery_error(exc)

    assert "https://york-fashion.com/sitemap.xml" not in user_msg
    assert "sitemap.xml" not in user_msg
    assert "Store sitemap is unavailable or private" in user_msg
    assert "york-fashion.com" in raw_err


def test_sanitize_sitemap_forbidden_403():
    exc = FetchError("Forbidden: Access Denied", status_code=403)
    user_msg, raw_err = _sanitize_discovery_error(exc)

    assert "Access to store catalog was restricted" in user_msg
    assert "Forbidden" in raw_err


def test_sanitize_timeout():
    exc = FetchError("Request timed out after 30s", status_code=None)
    user_msg, raw_err = _sanitize_discovery_error(exc)

    assert "Store server did not respond in time" in user_msg
    assert "timed out" in raw_err


def test_sanitize_generic_exception():
    exc = ValueError("Unexpected XML token at line 1")
    user_msg, raw_err = _sanitize_discovery_error(exc)

    assert "Product discovery encountered an issue" in user_msg
    assert "Unexpected XML token" in raw_err
