"""
Seed demo users with various roles and custom permissions for testing RBAC matrix.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.modules.auth.models import Role, User

logger = logging.getLogger(__name__)

DEMO_USERS = [
    {
        "email": "admin@priceplus.com",
        "password": "Password123",
        "is_superuser": True,
        "role_slug": "admin",
        "custom_permissions": [],
    },
    {
        "email": "manager@priceplus.com",
        "password": "Password123",
        "is_superuser": False,
        "role_slug": "manager",
        "custom_permissions": [],
    },
    {
        "email": "user@priceplus.com",
        "password": "Password123",
        "is_superuser": False,
        "role_slug": "user",
        "custom_permissions": [],
    },
    {
        "email": "viewer@priceplus.com",
        "password": "Password123",
        "is_superuser": False,
        "role_slug": "viewer",
        "custom_permissions": [],
    },
    {
        "email": "special@priceplus.com",
        "password": "Password123",
        "is_superuser": False,
        "role_slug": "user",
        "custom_permissions": ["access_admin", "export_data"],
    },
]


async def seed_demo_users(db: AsyncSession) -> None:
    """
    Create test accounts for each role and a user with custom permission overrides.
    """
    # Fetch roles map
    roles_res = await db.execute(select(Role))
    roles = {r.slug: r for r in roles_res.scalars().all()}

    for u_data in DEMO_USERS:
        email = u_data["email"]
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        role = roles.get(u_data["role_slug"])
        role_id = role.id if role else None

        if not user:
            user = User(
                email=email,
                password_hash=get_password_hash(u_data["password"]),
                is_active=True,
                is_superuser=u_data["is_superuser"],
                role_id=role_id,
                custom_permissions=u_data["custom_permissions"],
            )
            db.add(user)
            logger.info("Created test user: %s (role: %s)", email, u_data["role_slug"])
        else:
            # Update role and custom permissions if existing
            user.role_id = role_id
            user.is_superuser = u_data["is_superuser"]
            user.custom_permissions = u_data["custom_permissions"]
            logger.info("Updated test user: %s (role: %s)", email, u_data["role_slug"])

    await db.commit()
