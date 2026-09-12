"""
FastAPI auth router — HTTP handlers for authentication and dynamic RBAC matrix management.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.dependencies import (
    get_current_active_user,
    get_current_user_id,
    get_current_superuser_id,
    get_effective_user_permissions,
)
from app.core.security import hash_password, verify_password
from app.modules.auth.models import Permission, Role, RolePermission, User
from app.modules.auth.schemas import (
    AdminUpdateUserRequest,
    AdminUserResponse,
    ChangePasswordRequest,
    LoginRequest,
    PermissionResponse,
    RefreshRequest,
    RegisterRequest,
    RoleCreateRequest,
    RoleMatrixUpdateRequest,
    RoleResponse,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    UserRoleUpdateRequest,
)
from app.modules.auth.service import (
    AuthError,
    get_user_by_id,
    login_user,
    refresh_tokens,
    register_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _handle_auth_error(e: AuthError) -> None:
    """Convert domain AuthError to FastAPI HTTPException."""
    raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account."""
    try:
        return await register_user(db, data)
    except AuthError as e:
        _handle_auth_error(e)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password."""
    try:
        return await login_user(db, data)
    except AuthError as e:
        _handle_auth_error(e)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        return await refresh_tokens(db, data.refresh_token)
    except AuthError as e:
        _handle_auth_error(e)


@router.get("/me", response_model=UserResponse)
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Return the currently authenticated user's profile and effective permissions.
    """
    perms = await get_effective_user_permissions(user, db)
    role_slug = user.role.slug if user.role else "user"
    role_name = user.role.name if user.role else "Standard User"

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_slug=role_slug,
        role_name=role_name,
        permissions=sorted(list(perms)),
        created_at=user.created_at.isoformat(),
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Update the authenticated user's profile details (full_name, email, phone_number).
    """
    if data.email and data.email.lower() != user.email.lower():
        existing_res = await db.execute(select(User).where(User.email == data.email.lower()))
        if existing_res.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email is already registered by another account")
        user.email = data.email.lower()

    if data.full_name is not None:
        user.full_name = data.full_name.strip() if data.full_name else None

    if data.phone_number is not None:
        user.phone_number = data.phone_number.strip() if data.phone_number else None

    await db.commit()
    await db.refresh(user)

    perms = await get_effective_user_permissions(user, db)
    role_slug = user.role.slug if user.role else "user"
    role_name = user.role.name if user.role else "Standard User"

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_slug=role_slug,
        role_name=role_name,
        permissions=sorted(list(perms)),
        created_at=user.created_at.isoformat(),
    )


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """
    Change password for the currently authenticated user.
    """
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


# ─── RBAC Matrix & User Administration Endpoints ──────────────────────────────

@router.get("/admin/permissions", response_model=list[PermissionResponse])
async def admin_list_permissions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> list[PermissionResponse]:
    """List all registered system permissions (Superadmin/AccessAdmin only)."""
    result = await db.execute(select(Permission).order_by(Permission.category, Permission.code))
    perms = result.scalars().all()
    return [
        PermissionResponse(
            code=p.code,
            name=p.name,
            category=p.category,
            description=p.description,
        )
        for p in perms
    ]


@router.get("/admin/roles", response_model=list[RoleResponse])
async def admin_list_roles(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> list[RoleResponse]:
    """List all system roles with assigned permission codes (Superadmin/AccessAdmin only)."""
    result = await db.execute(select(Role).order_by(Role.is_system.desc(), Role.name))
    roles = list(result.scalars().all())

    response = []
    for r in roles:
        perm_codes = [rp.permission_code for rp in (r.role_permissions or [])]
        response.append(RoleResponse(
            id=str(r.id),
            slug=r.slug,
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=perm_codes,
        ))

    return response


@router.post("/admin/roles", response_model=RoleResponse, status_code=201)
async def admin_create_role(
    data: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> RoleResponse:
    """Create a custom new system role (Superadmin/AccessAdmin only)."""
    existing_res = await db.execute(select(Role).where(Role.slug == data.slug))
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Role with slug '{data.slug}' already exists")

    new_role = Role(
        slug=data.slug,
        name=data.name,
        description=data.description,
        is_system=False,
    )
    db.add(new_role)
    await db.flush()

    for code in data.permissions:
        db.add(RolePermission(role_id=new_role.id, permission_code=code))

    await db.commit()
    await db.refresh(new_role)

    return RoleResponse(
        id=str(new_role.id),
        slug=new_role.slug,
        name=new_role.name,
        description=new_role.description,
        is_system=False,
        permissions=data.permissions,
    )


@router.put("/admin/roles/{role_id}/matrix", response_model=RoleResponse)
async def admin_update_role_matrix(
    role_id: str,
    data: RoleMatrixUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> RoleResponse:
    """Update permission matrix for a role by adding/removing permission codes."""
    try:
        r_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Role not found") from None

    result = await db.execute(select(Role).where(Role.id == r_uuid))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Clear existing permissions for this role and add new ones
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))

    for p_code in data.permissions:
        db.add(RolePermission(role_id=role.id, permission_code=p_code))

    await db.commit()
    await db.refresh(role)

    return RoleResponse(
        id=str(role.id),
        slug=role.slug,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=data.permissions,
    )


@router.delete("/admin/roles/{role_id}", status_code=204)
async def admin_delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> None:
    """Delete a custom role (System default roles cannot be deleted)."""
    try:
        r_uuid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Role not found") from None

    result = await db.execute(select(Role).where(Role.id == r_uuid))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete default system roles")

    await db.delete(role)
    await db.commit()


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> list[AdminUserResponse]:
    """List all users with their current subscription plan and assigned role."""
    from app.modules.billing.models import Plan, Subscription

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = list(result.scalars().all())

    user_ids = [u.id for u in users]
    rows = []
    if user_ids:
        sub_result = await db.execute(
            select(Subscription, Plan)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(Subscription.user_id.in_(user_ids))
            .order_by(Subscription.created_at.desc())
        )
        rows = sub_result.all()

    sub_map: dict[str, tuple] = {}
    for sub, plan in rows:
        uid = str(sub.user_id)
        if uid not in sub_map:
            sub_map[uid] = (sub, plan)

    response = []
    for user in users:
        uid = str(user.id)
        sub_info = sub_map.get(uid)
        plan_name = sub_info[1].name if sub_info else "No Plan"
        plan_slug = sub_info[1].slug if sub_info else None
        sub_status = sub_info[0].status if sub_info else "none"
        plan_id = str(sub_info[1].id) if sub_info else None

        user_perms = await get_effective_user_permissions(user, db)
        role_slug = user.role.slug if user.role else "user"
        role_name = user.role.name if user.role else "Standard User"

        response.append(AdminUserResponse(
            id=uid,
            email=user.email,
            full_name=user.full_name,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            role_slug=role_slug,
            role_name=role_name,
            custom_permissions=user.custom_permissions or [],
            permissions=sorted(list(user_perms)),
            created_at=user.created_at.isoformat(),
            plan_name=plan_name,
            plan_slug=plan_slug,
            plan_id=plan_id,
            subscription_status=sub_status,
        ))

    return response


@router.patch("/admin/users/{target_user_id}", response_model=AdminUserResponse)
async def admin_update_user(
    target_user_id: str,
    data: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> AdminUserResponse:
    """
    Update target user's details (full_name, email, phone_number, is_active, role_slug, custom_permissions, plan_id).
    Superadmin only.
    """
    from app.modules.billing.models import Plan, Subscription

    try:
        user_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None

    user_res = await db.execute(select(User).where(User.id == user_uuid))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.email and data.email.lower() != user.email.lower():
        existing_res = await db.execute(select(User).where(User.email == data.email.lower()))
        if existing_res.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email is already registered by another account")
        user.email = data.email.lower()

    if data.full_name is not None:
        user.full_name = data.full_name.strip() if data.full_name else None

    if data.phone_number is not None:
        user.phone_number = data.phone_number.strip() if data.phone_number else None

    if data.is_active is not None:
        if user.is_superuser and not data.is_active:
            raise HTTPException(status_code=403, detail="Cannot deactivate a superuser")
        user.is_active = data.is_active

    if data.role_slug:
        role_res = await db.execute(select(Role).where(Role.slug == data.role_slug))
        role = role_res.scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{data.role_slug}' not found")
        user.role_id = role.id

    if data.custom_permissions is not None:
        user.custom_permissions = data.custom_permissions

    if data.plan_id:
        try:
            plan_uuid = uuid.UUID(data.plan_id)
            plan_res = await db.execute(select(Plan).where(Plan.id == plan_uuid))
            plan = plan_res.scalar_one_or_none()
            if plan:
                sub_res = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
                sub = sub_res.scalars().first()
                if sub:
                    sub.plan_id = plan.id
                else:
                    sub = Subscription(user_id=user.id, plan_id=plan.id, status="active")
                    db.add(sub)
        except ValueError:
            pass

    await db.commit()
    await db.refresh(user)

    sub_res = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
    )
    sub_row = sub_res.first()

    plan_name = sub_row[1].name if sub_row else "No Plan"
    plan_slug = sub_row[1].slug if sub_row else None
    plan_id_str = str(sub_row[1].id) if sub_row else None
    sub_status = sub_row[0].status if sub_row else "none"

    user_perms = await get_effective_user_permissions(user, db)
    role_slug = user.role.slug if user.role else "user"
    role_name = user.role.name if user.role else "Standard User"

    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_slug=role_slug,
        role_name=role_name,
        custom_permissions=user.custom_permissions or [],
        permissions=sorted(list(user_perms)),
        created_at=user.created_at.isoformat(),
        plan_name=plan_name,
        plan_slug=plan_slug,
        plan_id=plan_id_str,
        subscription_status=sub_status,
    )


@router.patch("/admin/users/{target_user_id}/role", response_model=AdminUserResponse)
async def admin_update_user_role(
    target_user_id: str,
    data: UserRoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> AdminUserResponse:
    """Assign a system or custom role and custom permission overrides to a user."""
    try:
        user_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None

    user_res = await db.execute(select(User).where(User.id == user_uuid))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_res = await db.execute(select(Role).where(Role.slug == data.role_slug))
    role = role_res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail=f"Role '{data.role_slug}' not found")

    user.role_id = role.id
    if data.custom_permissions is not None:
        user.custom_permissions = data.custom_permissions

    await db.commit()
    await db.refresh(user)

    user_perms = await get_effective_user_permissions(user, db)

    return AdminUserResponse(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_slug=role.slug,
        role_name=role.name,
        custom_permissions=user.custom_permissions or [],
        permissions=sorted(list(user_perms)),
        created_at=user.created_at.isoformat(),
        plan_name="Current Plan",
        subscription_status="active",
    )


@router.patch("/admin/users/{target_user_id}/status", response_model=UserResponse)
async def admin_toggle_user_status(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_superuser_id),
) -> UserResponse:
    """Toggle a user's active/inactive status (Superadmin only)."""
    try:
        user_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found") from None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot deactivate a superuser")

    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)

    logger.info("Admin toggled user %s active=%s", user.email, user.is_active)
    user_perms = await get_effective_user_permissions(user, db)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        role_slug=user.role.slug if user.role else "user",
        role_name=user.role.name if user.role else "Standard User",
        permissions=sorted(list(user_perms)),
        created_at=user.created_at.isoformat(),
    )
