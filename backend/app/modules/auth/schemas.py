"""
Pydantic schemas for auth endpoints.

Strict input validation — all user-provided data passes through here
before touching the database or security layer.
"""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Request schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        MVP password policy: min 8 chars, at least one letter and one digit.
        Not overly restrictive — users can always choose stronger passwords.
        """
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower().strip()


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# ── Response schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    is_superuser: bool = False
    role_slug: str | None = "user"
    role_name: str | None = "Standard User"
    permissions: list[str] = []
    created_at: str

    model_config = {"from_attributes": True}


class AdminUserResponse(BaseModel):
    """Extended user response for superadmin — includes subscription/plan info and RBAC role."""
    id: str
    email: str
    is_active: bool
    is_superuser: bool
    role_slug: str | None = "user"
    role_name: str | None = "Standard User"
    custom_permissions: list[str] = []
    permissions: list[str] = []
    created_at: str
    plan_name: str
    plan_slug: str | None = None
    plan_id: str | None = None
    subscription_status: str

    model_config = {"from_attributes": True}


# ── RBAC schemas ─────────────────────────────────────────────────────────────

class PermissionResponse(BaseModel):
    code: str
    name: str
    category: str
    description: str

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    is_system: bool
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class RoleCreateRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=255)
    permissions: list[str] = []


class RoleMatrixUpdateRequest(BaseModel):
    permissions: list[str]


class UserRoleUpdateRequest(BaseModel):
    role_slug: str
    custom_permissions: list[str] | None = None

