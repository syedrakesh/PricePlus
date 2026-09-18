"""
Seed RBAC permissions and default system roles in the database.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Permission, Role, RolePermission, User

logger = logging.getLogger(__name__)

DEFAULT_PERMISSIONS = [
    # Legacy codes (preserved for backward compatibility)
    {"code": "access_admin", "name": "Access Admin Panel", "category": "Admin Control", "description": "Access system user management, plan management, and RBAC matrix."},
    {"code": "manage_stores", "name": "Manage Stores (Legacy)", "category": "Store Management", "description": "Full store management access."},
    {"code": "manage_tracking", "name": "Manage Tracking (Legacy)", "category": "Product Tracking", "description": "Full tracking management access."},
    {"code": "manage_alerts", "name": "Manage Alerts (Legacy)", "category": "Alerts & Notifications", "description": "Full alert management access."},
    {"code": "manage_billing", "name": "Manage Billing (Legacy)", "category": "Billing & Plans", "description": "Full billing management access."},
    {"code": "export_data", "name": "Export Data (Legacy)", "category": "Reporting & Export", "description": "Full export data access."},

    # Granular Admin Controls
    {"code": "manage_users", "name": "Manage System Users", "category": "Admin Control", "description": "Create, edit, suspend, and manage platform user accounts."},
    {"code": "manage_plans", "name": "Manage Subscriptions & Plans", "category": "Admin Control", "description": "Configure pricing plans, feature tier limits, and store quotas."},
    {"code": "manage_roles", "name": "Manage RBAC Matrix & Roles", "category": "Admin Control", "description": "Define custom user groups and configure granular permission matrices."},
    {"code": "view_system_telemetry", "name": "View Engine Worker Telemetry", "category": "Admin Control", "description": "View live worker pool health, active background tasks, and platform pull stream."},
    {"code": "control_system_engine", "name": "Control Worker Engine", "category": "Admin Control", "description": "Trigger global force polls, pause/resume workers, and restart background loops."},

    # Granular Store Management
    {"code": "stores_view", "name": "View Competitor Stores", "category": "Store Management", "description": "View list of connected e-commerce competitor stores and catalog counts."},
    {"code": "stores_create", "name": "Add Competitor Stores", "category": "Store Management", "description": "Connect new competitor e-commerce stores for product tracking."},
    {"code": "stores_edit", "name": "Edit Store Configuration", "category": "Store Management", "description": "Update store crawl settings, sitemap URLs, and HTTP headers."},
    {"code": "stores_delete", "name": "Delete Competitor Stores", "category": "Store Management", "description": "Remove competitor stores and associated product tracking data."},
    {"code": "stores_trigger_discovery", "name": "Trigger Product Discovery", "category": "Store Management", "description": "Run sitemap & HTML product discovery pipelines for stores."},

    # Granular Product Tracking
    {"code": "tracking_view", "name": "View Tracked Products", "category": "Product Tracking", "description": "View list of monitored products, current prices, and stock statuses."},
    {"code": "tracking_create", "name": "Add Tracked Products", "category": "Product Tracking", "description": "Add new products from discovered catalog to active price tracking."},
    {"code": "tracking_edit", "name": "Edit Tracked Product Settings", "category": "Product Tracking", "description": "Modify target product URLs, poll priority, and check frequencies."},
    {"code": "tracking_delete", "name": "Remove Tracked Products", "category": "Product Tracking", "description": "Stop tracking and delete product items from monitoring."},
    {"code": "tracking_force_poll", "name": "Force Instant Product Poll", "category": "Product Tracking", "description": "Trigger immediate price fetch for tracked items."},

    # Granular Alerts & Notifications
    {"code": "alerts_view_rules", "name": "View Alert Rules & History", "category": "Alerts & Notifications", "description": "View configured alert rules and past notification history log."},
    {"code": "alerts_create_rule", "name": "Create Alert Rules", "category": "Alerts & Notifications", "description": "Create new price drop, price rise, or target threshold alert rules."},
    {"code": "alerts_edit_rule", "name": "Edit Alert Rules", "category": "Alerts & Notifications", "description": "Update condition types, threshold percentages, and notification channels for rules."},
    {"code": "alerts_toggle_rule", "name": "Enable / Pause Alert Rules", "category": "Alerts & Notifications", "description": "Toggle alert rules between active and paused states."},
    {"code": "alerts_delete_rule", "name": "Delete Alert Rules", "category": "Alerts & Notifications", "description": "Permanently remove alert rules."},
    {"code": "alerts_manage_channels", "name": "Configure Notification Channels", "category": "Alerts & Notifications", "description": "Configure Telegram Chat IDs, custom bot tokens, and recipient email addresses."},

    # Granular Billing & Subscriptions
    {"code": "billing_view", "name": "View Subscription & Invoices", "category": "Billing & Plans", "description": "View current plan features, quota usage, and payment invoices."},
    {"code": "billing_upgrade", "name": "Upgrade / Downgrade Plan", "category": "Billing & Plans", "description": "Checkout plan upgrades or change active subscription tiers."},
    {"code": "billing_extend", "name": "Extend Subscription", "category": "Billing & Plans", "description": "Extend active subscription duration with Stripe checkout."},

    # Granular Speed & System Settings
    {"code": "settings_speed", "name": "Configure Speed & Frequency", "category": "Speed & System Settings", "description": "Configure discovery crawl rate limits, request jitter, and poll intervals."},

    # Granular Reporting & Analytics
    {"code": "reporting_view_analytics", "name": "View Analytics & Charts", "category": "Reporting & Export", "description": "View price trend charts, snapshot timelines, and store analytics."},
    {"code": "reporting_export_csv", "name": "Export Data to CSV / JSON", "category": "Reporting & Export", "description": "Download pricing history, snapshot logs, and product reports."},
]

ALL_PERM_CODES = [p["code"] for p in DEFAULT_PERMISSIONS]

DEFAULT_ROLES = [
    {
        "slug": "admin",
        "name": "Administrator",
        "description": "Full access to all system resources, administrative panels, and granular features.",
        "is_system": True,
        "permissions": ALL_PERM_CODES,
    },
    {
        "slug": "manager",
        "name": "Manager",
        "description": "Full access to store management, product tracking, alerts, billing, and reporting.",
        "is_system": True,
        "permissions": [
            "manage_stores", "manage_tracking", "manage_alerts", "manage_billing", "export_data",
            "stores_view", "stores_create", "stores_edit", "stores_delete", "stores_trigger_discovery",
            "tracking_view", "tracking_create", "tracking_edit", "tracking_delete", "tracking_force_poll",
            "alerts_view_rules", "alerts_create_rule", "alerts_edit_rule", "alerts_toggle_rule", "alerts_delete_rule", "alerts_manage_channels",
            "billing_view", "billing_upgrade", "billing_extend", "settings_speed", "reporting_view_analytics", "reporting_export_csv"
        ],
    },
    {
        "slug": "user",
        "name": "Standard User",
        "description": "Standard subscriber access to stores, tracking, alerts, and billing.",
        "is_system": True,
        "permissions": [
            "manage_stores", "manage_tracking", "manage_alerts", "manage_billing",
            "stores_view", "stores_create", "stores_trigger_discovery",
            "tracking_view", "tracking_create", "tracking_edit", "tracking_delete", "tracking_force_poll",
            "alerts_view_rules", "alerts_create_rule", "alerts_edit_rule", "alerts_toggle_rule", "alerts_delete_rule", "alerts_manage_channels",
            "billing_view", "billing_upgrade", "billing_extend", "settings_speed", "reporting_view_analytics", "reporting_export_csv"
        ],
    },
    {
        "slug": "viewer",
        "name": "Viewer",
        "description": "Read-only access to view stores, products, and price histories.",
        "is_system": True,
        "permissions": ["stores_view", "tracking_view", "alerts_view_rules", "billing_view", "reporting_view_analytics"],
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
