"""
Unit tests for auth schemas — input validation.

No database or network required. Tests Pydantic validation rules.
"""

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import LoginRequest, RefreshRequest, RegisterRequest


class TestRegisterRequest:
    def test_valid_registration(self):
        r = RegisterRequest(email="user@example.com", password="Password1")
        assert r.email == "user@example.com"

    def test_email_is_lowercased(self):
        r = RegisterRequest(email="  User@EXAMPLE.COM  ", password="Password1")
        assert r.email == "user@example.com"

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="not-an-email", password="Password1")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="user@example.com", password="Abc1")

    def test_password_no_letter_rejected(self):
        with pytest.raises(ValidationError, match="letter"):
            RegisterRequest(email="user@example.com", password="12345678")

    def test_password_no_digit_rejected(self):
        with pytest.raises(ValidationError, match="digit"):
            RegisterRequest(email="user@example.com", password="NoDigitsHere")

    def test_password_too_long_rejected(self):
        with pytest.raises(ValidationError):
            RegisterRequest(email="user@example.com", password="A1" + "x" * 200)

    def test_minimum_valid_password(self):
        r = RegisterRequest(email="user@example.com", password="Abc12345")
        assert r.password == "Abc12345"


class TestLoginRequest:
    def test_valid_login(self):
        r = LoginRequest(email="user@example.com", password="anypassword")
        assert r.email == "user@example.com"

    def test_email_lowercased(self):
        r = LoginRequest(email="USER@EXAMPLE.COM", password="anypassword")
        assert r.email == "user@example.com"

    def test_empty_password_rejected(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="")


class TestRefreshRequest:
    def test_valid_refresh(self):
        r = RefreshRequest(refresh_token="some.valid.token")
        assert r.refresh_token == "some.valid.token"

    def test_empty_token_rejected(self):
        with pytest.raises(ValidationError):
            RefreshRequest(refresh_token="")
