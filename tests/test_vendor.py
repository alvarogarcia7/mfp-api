"""Tests for vendored modules."""

import sys
from pathlib import Path

import pytest

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from vendor import mfp_client


class TestMfpClient:
    """Test mfp_client module."""

    def test_is_auth_error_with_auth_exception(self):
        """Test that auth-related exceptions are detected."""
        exc = Exception("401 unauthorized")
        assert mfp_client.is_auth_error(exc)

    def test_is_auth_error_with_not_connected(self):
        """Test NotConnectedError is recognized as auth error."""
        exc = mfp_client.NotConnectedError("test")
        assert mfp_client.is_auth_error(exc)

    def test_is_auth_error_with_non_auth_error(self):
        """Test that non-auth errors are not marked as auth."""
        exc = Exception("Some other error")
        assert not mfp_client.is_auth_error(exc)

    def test_cookies_to_jar_empty(self):
        """Test creating jar from empty dict."""
        jar = mfp_client.cookies_to_jar({})
        assert len(jar) == 0

    def test_cookies_to_jar_single_cookie(self):
        """Test creating jar from single cookie."""
        cookies = {"test_cookie": "test_value"}
        jar = mfp_client.cookies_to_jar(cookies)
        assert len(jar) == 1
        cookie = list(jar)[0]
        assert cookie.name == "test_cookie"
        assert cookie.value == "test_value"

    def test_cookies_to_jar_multiple_cookies(self):
        """Test creating jar from multiple cookies."""
        cookies = {
            "cookie1": "value1",
            "cookie2": "value2",
            "cookie3": "value3",
        }
        jar = mfp_client.cookies_to_jar(cookies)
        assert len(jar) == 3
