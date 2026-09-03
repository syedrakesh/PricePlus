"""
Unit tests for security utilities — password hashing and JWT tokens.

These tests require NO database or network connection.
They verify the pure security logic in isolation.
"""


import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"

    def test_correct_password_verifies(self):
        hashed = hash_password("correct-password-1")
        assert verify_password("correct-password-1", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-password-1")
        assert verify_password("wrong-password", hashed) is False

    def test_empty_password_fails_verification(self):
        hashed = hash_password("correct-password-1")
        assert verify_password("", hashed) is False

    def test_same_password_produces_different_hashes(self):
        """bcrypt uses random salt — same input should NOT produce same output."""
        h1 = hash_password("same-password-1")
        h2 = hash_password("same-password-1")
        assert h1 != h2

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = hash_password("test-password-1")
        assert hashed.startswith("$2b$")


# ── JWT access tokens ─────────────────────────────────────────────────────────

class TestAccessTokens:
    USER_ID = "11111111-1111-1111-1111-111111111111"

    def test_create_and_decode_access_token(self):
        token = create_access_token(self.USER_ID)
        decoded_id = decode_access_token(token)
        assert decoded_id == self.USER_ID

    def test_access_token_is_string(self):
        token = create_access_token(self.USER_ID)
        assert isinstance(token, str)
        assert len(token) > 10

    def test_invalid_token_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid or expired"):
            decode_access_token("completely.invalid.token")

    def test_tampered_token_raises_value_error(self):
        token = create_access_token(self.USER_ID)
        # Corrupt the payload section
        parts = token.split(".")
        parts[1] = parts[1][::-1]
        tampered = ".".join(parts)
        with pytest.raises(ValueError):
            decode_access_token(tampered)

    def test_refresh_token_rejected_as_access_token(self):
        """Token type must be enforced — refresh tokens cannot be used as access tokens."""
        refresh = create_refresh_token(self.USER_ID)
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_access_token(refresh)

    def test_different_users_get_different_tokens(self):
        t1 = create_access_token("aaaa-1111")
        t2 = create_access_token("bbbb-2222")
        assert t1 != t2

    def test_decoded_user_id_matches_input(self):
        uid = "99999999-9999-9999-9999-999999999999"
        token = create_access_token(uid)
        assert decode_access_token(token) == uid


# ── JWT refresh tokens ────────────────────────────────────────────────────────

class TestRefreshTokens:
    USER_ID = "22222222-2222-2222-2222-222222222222"

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token(self.USER_ID)
        decoded_id = decode_refresh_token(token)
        assert decoded_id == self.USER_ID

    def test_access_token_rejected_as_refresh_token(self):
        """Token type must be enforced — access tokens cannot be used as refresh tokens."""
        access = create_access_token(self.USER_ID)
        with pytest.raises(ValueError, match="Invalid token type"):
            decode_refresh_token(access)

    def test_invalid_refresh_token_raises(self):
        with pytest.raises(ValueError):
            decode_refresh_token("bad.token.here")
