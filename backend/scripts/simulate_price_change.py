"""
Simulate a price change and test alert generation in PricePlus.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/simulate_price_change.py [mock_old_price]

Example:
  PYTHONPATH=. .venv/bin/python scripts/simulate_price_change.py 25.0
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

# Import all ORM models first to register foreign keys in SQLAlchemy Metadata
from app.modules.auth.models import User  # noqa: F401
from app.modules.stores.models import CompetitorStore  # noqa: F401
from app.modules.discovery.models import DiscoveredProduct  # noqa: F401
from app.modules.tracking.models import TrackedProduct  # noqa: F401
from app.modules.monitoring.models import ProductSnapshot, PriceChange  # noqa: F401
from app.modules.alerts.models import AlertRule, Alert  # noqa: F401

from app.core.db import AsyncSessionLocal
from app.modules.alerts.dispatcher import process_pending_alerts
from app.modules.monitoring.orchestrator import run_monitoring_cycle


async def main():
    old_price_mock = float(sys.argv[1]) if len(sys.argv) > 1 else 25.0

    async with AsyncSessionLocal() as db:
        print("\n🔍 Step 1: Finding tracked products...")
        result = await db.execute(
            select(TrackedProduct, DiscoveredProduct)
            .join(DiscoveredProduct, DiscoveredProduct.id == TrackedProduct.discovered_product_id)
            .where(TrackedProduct.is_active == True)
        )
        tracked_items = list(result.all())

        if not tracked_items:
            print("❌ No active tracked products found. Please track a product from the frontend first!")
            return

        tracked, discovered = tracked_items[0]
        print(f"✅ Selected Tracked Product: '{discovered.title or discovered.handle}' (ID: {tracked.id})")
        print(f"   Current Price in DB: ${discovered.current_price}")

        print("\n⚙️ Step 2: Ensuring an Alert Rule exists...")
        rule_res = await db.execute(
            select(AlertRule).where(
                AlertRule.tracked_product_id == tracked.id,
                AlertRule.is_enabled == True,
            )
        )
        rule = rule_res.scalar_one_or_none()
        if not rule:
            rule = AlertRule(
                id=uuid.uuid4(),
                user_id=tracked.user_id,
                tracked_product_id=tracked.id,
                condition_type="any_change",
                channel="email",
                is_enabled=True,
                cool_down_minutes=0,
            )
            db.add(rule)
            await db.commit()
            await db.refresh(rule)
            print(f"✅ Created AlertRule: 'any_change' (ID: {rule.id})")
        else:
            print(f"✅ Found existing AlertRule: '{rule.condition_type}' (ID: {rule.id})")

        print(f"\n📸 Step 3: Seeding synthetic previous snapshot with old price = ${old_price_mock:.2f}...")
        synthetic_snap = ProductSnapshot(
            id=uuid.uuid4(),
            tracked_product_id=tracked.id,
            discovered_product_id=discovered.id,
            user_id=tracked.user_id,
            price=old_price_mock,
            currency=discovered.currency or "USD",
            is_available=True,
            http_status=200,
            captured_at=datetime.now(UTC),
        )
        db.add(synthetic_snap)
        await db.commit()
        print("✅ Previous snapshot created successfully.")

        print("\n🔄 Step 4: Running monitoring cycle (polls store & detects price change)...")
        mon_result = await run_monitoring_cycle(db)
        print(f"   Cycle Result: {mon_result}")

        print("\n🔔 Step 5: Dispatching pending alerts...")
        alerts_sent = await process_pending_alerts(db)
        print(f"   Alerts Sent Count: {alerts_sent}")

        print("\n📊 Step 6: Verifying generated records in DB...")
        change_res = await db.execute(
            select(PriceChange)
            .where(PriceChange.tracked_product_id == tracked.id)
            .order_by(PriceChange.detected_at.desc())
            .limit(1)
        )
        latest_change = change_res.scalar_one_or_none()

        if latest_change:
            print("🎉 SUCCESS! PriceChange Detected:")
            print(f"   - Change Type : {latest_change.change_type}")
            print(f"   - Old Price   : ${latest_change.old_price:.2f}")
            print(f"   - New Price   : ${latest_change.new_price:.2f}")
            print(f"   - % Change    : {latest_change.pct_change:.1f}%")

        alert_res = await db.execute(
            select(Alert)
            .where(Alert.user_id == tracked.user_id)
            .order_by(Alert.created_at.desc())
            .limit(1)
        )
        latest_alert = alert_res.scalar_one_or_none()
        if latest_alert:
            print("🎉 SUCCESS! Alert Generated:")
            print(f"   - Summary   : {latest_alert.trigger_summary}")
            print(f"   - Channel   : {latest_alert.channel}")
            print(f"   - Delivered : {latest_alert.delivered}")
            if latest_alert.delivery_error:
                print(f"   - Delivery Note: {latest_alert.delivery_error}")

        print("\n✨ Simulation complete! Check your frontend Dashboard, Product History, and Alerts pages to view the updates!")


if __name__ == "__main__":
    asyncio.run(main())
