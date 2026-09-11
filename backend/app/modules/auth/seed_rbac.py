"""
Seed RBAC permissions and default system roles in the database.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Permission, Role, RolePermission, User

logger = logging.getLogger(__name__)

DEFAULT_PERMISSIONS = [
    {
        "code": "access_admin",
        "name": "Access Admin Panel",
        "category": "Admin Control",
        "description": "Access system user management, plan management, and RBAC matrix.",
    },
    {
        "code": "manage_stores",
        "name": "Manage Stores",
        "category": "Store Management",
        "description": "Connect, configure, and delete e-commerce store targets.",
    },
    {
        "code": "manage_tracking",
        "name": "Manage Tracking",
        "category": "Product Tracking",
        "description": "Track products, manage URLs, and trigger manual price scraping.",
    },
    {
        "code": "manage_alerts",
        "name": "Manage Alerts",
        "category": "Alerts & Notifications",
        "description": "Configure price threshold alert rules and webhooks.",
    },
    {
        "code": "manage_billing",
        "name": "Manage Billing",
        "category": "Billing & Plans",
        "description": "Manage subscriptions, upgrades/downgrades, and billing portal.",
    },
    {
        "code": "export_data",
        "name": "Export Data",
        "category": "Reporting & Export",
        "description": "Download pricing histories, snapshots, and reports.",
    },
]

DEFAULT_ROLES = [
    {
        "slug": "admin",
        "name": "Administrator",
        "description": "Full access to all system resources and administrative panels.",
        "is_system": True,
        "permissions": ["access_admin", "manage_stores", "manage_tracking", "manage_alerts", "manage_billing", "export_data"],
    },
    {
        "slug": "manager",
        "name": "Manager",
        "description": "Full access to store tracking, alerts, billing, and reporting.",
        "is_system": True,
        "permissions": ["manage_stores", "manage_tracking", "manage_alerts", "manage_billing", "export_data"],
    },
    {
        "slug": "user",
        "name": "Standard User",
        "description": "Standard subscriber access to stores, tracking, alerts, and billing.",
        "is_system": True,
        "permissions": ["manage_stores", "manage_tracking", "manage_alerts", "manage_billing"],
    },
    {
        "slug": "viewer",
        "name": "Viewer",
        "description": "Read-only access to view stores and price histories.",
        "is_system": True,
        "permissions": [],
    },
]


async def seed_rbac_data(db: AsyncSession) -> None:
    """
    Seed initial permissions, system roles, and assign default roles to existing users.
    """
    # 1. Seed Permissions
    for perm_data in DEFAULT_PERMISSIONS:
        result = await db.execute(select(Permission).where(Permission.code == perm_data["code"]))
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(Permission(**perm_data))
    await db.flush()

    # 2. Seed Roles & RolePermissions
    role_map: dict[str, Role] = {}
    for role_info in DEFAULT_ROLES:
        role_data = dict(role_info)
        perms = role_data.pop("permissions", [])
        result = await db.execute(select(Role).where(Role.slug == role_data["slug"]))
        role = result.scalar_one_or_none()
        if not role:
            role = Role(**role_data)
            db.add(role)
            await db.flush()
        
        role_map[role.slug] = role

        # Ensure role permissions exist
        rp_res = await db.execute(select(RolePermission).where(RolePermission.role_id == role.id))
        existing_rp = {rp.permission_code for rp in rp_res.scalars().all()}

        for p_code in perms:
            if p_code not in existing_rp:
                db.add(RolePermission(role_id=role.id, permission_code=p_code))
    
    await db.flush()

    # 3. Assign default roles to existing users who have no role_id assigned
    unassigned_users_res = await db.execute(select(User).where(User.role_id.is_(None)))
    unassigned_users = unassigned_users_res.scalars().all()

    for user in unassigned_users:
        if user.is_superuser and "admin" in role_map:
            user.role_id = role_map["admin"].id
        elif "user" in role_map:
            user.role_id = role_map["user"].id

    await db.commit()
    logger.info("RBAC permissions, roles, and default user assignments initialized successfully.")
