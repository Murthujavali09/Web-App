"""
Seed a demo database with a tenant, owner, manager, stores, staff, inventory,
daily reports, history, billing, and alerts.

Credentials for super admin come from SUPER_ADMIN_USERNAME / SUPER_ADMIN_PASSWORD in .env
(defaults: owner / Owner@123).
"""
import os
import json
from datetime import datetime, timedelta

from backend.config import Config
from backend.database import db
from backend.models import (
    Tenant,
    Manager,
    Store,
    Employee,
    Inventory,
    InventoryHistory,
    TimeClock,
    EOD,
    StoreBilling,
    Alert,
    create_tenant,
    create_manager,
    hash_password,
)


def seed_dev(
    *,
    company_name=None,
    tenant_email=None,
    create_demo_manager=True,
    create_demo_stores=True,
    force_reset_super_admin=False,
):
    """
    Create dev tenant + super admin if missing. Returns dict with login hints.
    """
    company_name = company_name or os.getenv("DEV_TENANT_COMPANY", "Summit Wireless Group")
    tenant_email = tenant_email or os.getenv("DEV_TENANT_EMAIL", "owner@summitwireless.example")

    sa_username = Config.SUPER_ADMIN_USERNAME
    sa_password = Config.SUPER_ADMIN_PASSWORD

    if not sa_password:
        raise ValueError("SUPER_ADMIN_PASSWORD must be set in .env before seeding")

    tenant = Tenant.query.first()
    created_tenant = False

    if not tenant:
        tenant_dict = create_tenant(
            company_name=company_name,
            email=tenant_email,
            password_hash=hash_password(sa_password),
            plan="basic",
        )
        tenant = Tenant.query.get(tenant_dict["id"])
        created_tenant = True

    super_admin = Manager.query.filter_by(
        tenant_id=tenant.id, is_super_admin=True
    ).first()

    created_super_admin = False
    if not super_admin:
        create_manager(
            tenant_id=tenant.id,
            name="Alicia Bennett",
            username=sa_username,
            password=sa_password,
            is_super_admin=True,
        )
        created_super_admin = True
    elif force_reset_super_admin:
        super_admin.password = hash_password(sa_password)
        db.session.commit()

    demo_manager_username = os.getenv("DEV_MANAGER_USERNAME", "manager")
    demo_manager_password = os.getenv("DEV_MANAGER_PASSWORD", "Manager@123")
    demo_manager = Manager.query.filter_by(
        tenant_id=tenant.id, username=demo_manager_username
    ).first()

    created_demo_manager = False
    if create_demo_manager and not demo_manager:
        create_manager(
            tenant_id=tenant.id,
            name="Michael Torres",
            username=demo_manager_username,
            password=demo_manager_password,
            location="Texas Region",
        )
        created_demo_manager = True
        demo_manager = Manager.query.filter_by(
            tenant_id=tenant.id, username=demo_manager_username
        ).first()

    stores_created = []
    if create_demo_stores and Store.query.filter_by(tenant_id=tenant.id).count() == 0:
        demo_stores = [
            {
                "name": "Downtown Store",
                "username": "downtown",
                "password": "Store@123",
                "total_boxes": 64,
                "opening_time": "09:00",
                "closing_time": "21:00",
            },
            {
                "name": "West Houston",
                "username": "westhouston",
                "password": "Store@123",
                "total_boxes": 52,
                "opening_time": "10:00",
                "closing_time": "20:00",
            },
            {
                "name": "Austin Central",
                "username": "austin",
                "password": "Store@123",
                "total_boxes": 58,
                "opening_time": "09:00",
                "closing_time": "21:00",
            },
            {
                "name": "Phoenix Branch",
                "username": "phoenix",
                "password": "Store@123",
                "total_boxes": 46,
                "opening_time": "09:00",
                "closing_time": "21:00",
            },
        ]
        mgr_username = demo_manager.username if demo_manager else None
        for s in demo_stores:
            store = Store(
                name=s["name"],
                username=s["username"],
                password=hash_password(s["password"]),
                total_boxes=s["total_boxes"],
                tenant_id=tenant.id,
                manager_username=mgr_username,
                opening_time=s["opening_time"],
                closing_time=s["closing_time"],
            )
            db.session.add(store)
            db.session.commit()
            stores_created.append(
                {"name": s["name"], "username": s["username"], "password": s["password"]}
            )
        _seed_realistic_demo_data(tenant.id, mgr_username)

    return {
        "created_tenant": created_tenant,
        "created_super_admin": created_super_admin,
        "created_demo_manager": created_demo_manager,
        "stores_created": stores_created,
        "tenant_id": tenant.id,
        "company_name": tenant.company_name,
        "tenant_email": tenant.email,
        "super_admin_username": sa_username,
        "super_admin_password": sa_password,
        "demo_manager_username": demo_manager_username if create_demo_manager else None,
        "demo_manager_password": demo_manager_password if create_demo_manager else None,
    }


def _seed_realistic_demo_data(tenant_id, manager_username):
    """Populate believable multi-store retail demo data."""
    now = datetime.utcnow()
    store_names = ["Downtown Store", "West Houston", "Austin Central", "Phoenix Branch"]
    employee_templates = {
        "Downtown Store": [
            ("John Carter", "Store Lead", "555-210-1101", 24.0),
            ("Emily Smith", "Sales Associate", "555-210-1102", 18.5),
            ("David Wilson", "Inventory Specialist", "555-210-1103", 19.25),
            ("Sarah Johnson", "Sales Associate", "555-210-1104", 18.0),
        ],
        "West Houston": [
            ("Marcus Lee", "Store Lead", "555-310-2201", 23.5),
            ("Olivia Brown", "Sales Associate", "555-310-2202", 18.0),
            ("Daniel Garcia", "Repair Desk", "555-310-2203", 20.0),
            ("Priya Patel", "Sales Associate", "555-310-2204", 18.25),
        ],
        "Austin Central": [
            ("Rachel Adams", "Store Lead", "555-410-3301", 23.75),
            ("Chris Martin", "Sales Associate", "555-410-3302", 18.5),
            ("Nina Brooks", "Inventory Specialist", "555-410-3303", 19.5),
            ("Ethan Clark", "Sales Associate", "555-410-3304", 18.0),
        ],
        "Phoenix Branch": [
            ("Laura Davis", "Store Lead", "555-510-4401", 23.25),
            ("Kevin Moore", "Sales Associate", "555-510-4402", 18.0),
            ("Mia Thompson", "Sales Associate", "555-510-4403", 18.25),
            ("Noah Harris", "Inventory Specialist", "555-510-4404", 19.0),
        ],
    }

    inventory_items = [
        ("APL-IP16-128", "iPhone 16 128GB", "metro", 6),
        ("APL-IP16P-256", "iPhone 16 Pro 256GB", "unlocked", 3),
        ("SMS-S25-128", "Samsung S25 128GB", "metro", 8),
        ("SMS-S25U-256", "Samsung S25 Ultra", "unlocked", 4),
        ("GOO-PXL9-128", "Google Pixel 9", "metro", 5),
        ("GOO-PXL9P-256", "Google Pixel 9 Pro", "unlocked", 3),
        ("APL-AIRPODS-PRO", "AirPods Pro", "metro", 4),
        ("ACC-USBC-30W", "USB-C Fast Chargers", "metro", 14),
        ("ACC-CASE-IP16", "iPhone 16 Cases", "metro", 22),
        ("ACC-CASE-S25", "Samsung S25 Cases", "metro", 18),
        ("SIM-5G", "5G SIM Cards", "metro", 60),
        ("ACC-SCREEN", "Tempered Glass Protectors", "metro", 35),
    ]

    store_adjustments = {
        "Downtown Store": [0, -1, 1, -1, 0, 0, -2, -6, -3, -2, -10, -5],
        "West Houston": [2, 0, -1, 1, 1, 0, 0, -2, -1, 1, -5, -2],
        "Austin Central": [1, 1, 2, 0, -1, 1, -1, -4, 2, -2, -8, -4],
        "Phoenix Branch": [-2, -1, 0, -1, 0, -1, -2, -6, -4, -3, -12, -7],
    }

    all_employees = []
    for store_name, people in employee_templates.items():
        for name, role, phone, pay in people:
            employee = Employee(
                tenant_id=tenant_id,
                store_id=store_name,
                name=name,
                role=role,
                phone_number=phone,
                hourly_pay=pay,
                active=True,
            )
            db.session.add(employee)
            all_employees.append(employee)
    db.session.commit()

    for store_name in store_names:
        for idx, (sku, name, device_type, base_qty) in enumerate(inventory_items):
            qty = max(0, base_qty + store_adjustments[store_name][idx])
            db.session.add(Inventory(
                tenant_id=tenant_id,
                store_id=store_name,
                sku=sku,
                name=name,
                quantity=qty,
                device_type=device_type,
            ))
        db.session.commit()

        current_items = Inventory.query.filter_by(tenant_id=tenant_id, store_id=store_name).all()
        for days_ago in range(6, -1, -1):
            snapshot_items = []
            for item in current_items:
                historical_qty = max(0, item.quantity + days_ago + (len(item.name) % 3))
                snapshot_items.append({
                    "_id": str(item.id),
                    "sku": item.sku,
                    "name": item.name,
                    "quantity": historical_qty,
                    "device_type": item.device_type,
                })
            snapshot = InventoryHistory(
                tenant_id=tenant_id,
                store_id=store_name,
                snapshot_date=(now - timedelta(days=days_ago)).replace(hour=21, minute=15, second=0, microsecond=0),
                items=json.dumps(snapshot_items),
            )
            db.session.add(snapshot)
    db.session.commit()

    sales_by_store = {
        "Downtown Store": (4820.35, 2895.20, 1110.40, 394.75, 420.00, 11),
        "West Houston": (3915.80, 2204.10, 890.25, 316.45, 505.00, 8),
        "Austin Central": (5342.60, 3012.35, 1264.10, 426.15, 640.00, 13),
        "Phoenix Branch": (3276.45, 1718.20, 812.00, 256.25, 490.00, 7),
    }
    for store_name, (total, cash, card, qpay, accessories, sold) in sales_by_store.items():
        eod = EOD(
            tenant_id=tenant_id,
            store_id=store_name,
            report_date=now.date().isoformat(),
            notes="Normal business day. Inventory and cash drawer reviewed by closing lead.",
            cash_amount=cash,
            credit_amount=card,
            card1_amount=0,
            qpay_amount=qpay,
            boxes_count=sold,
            accessories_amount=accessories,
            magenta_amount=0,
            inventory_sold=sold,
            over_short=round(total - (cash + card), 2),
            total1=total,
            denom_100_count=12,
            denom_100_total=1200,
            denom_50_count=10,
            denom_50_total=500,
            denom_20_count=36,
            denom_20_total=720,
            denom_10_count=28,
            denom_10_total=280,
            denom_5_count=18,
            denom_5_total=90,
            denom_1_count=35,
            denom_1_total=35,
            total_bills=2825,
            submitted_by="Closing Lead",
        )
        db.session.add(eod)
    db.session.commit()

    employees_by_store = {}
    for emp in Employee.query.filter_by(tenant_id=tenant_id).all():
        employees_by_store.setdefault(emp.store_id, []).append(emp)
    for store_name, employees in employees_by_store.items():
        for idx, emp in enumerate(employees[:3]):
            clock_in = now.replace(hour=9 + (idx % 2), minute=idx * 7, second=0, microsecond=0)
            clock_out = None if idx < 2 else clock_in + timedelta(hours=7, minutes=45)
            db.session.add(TimeClock(
                tenant_id=tenant_id,
                employee_id=emp.id,
                employee_name=emp.name,
                store_id=store_name,
                clock_in=clock_in,
                clock_out=clock_out,
                hours_worked=round(((clock_out - clock_in).total_seconds() / 3600), 2) if clock_out else None,
                clock_in_confidence=0.91,
                clock_out_confidence=0.88 if clock_out else None,
            ))
    db.session.commit()

    billing_month = now.strftime("%Y-%m")
    for store_name in store_names:
        for bill_type, amount in [("electricity", 1240), ("wifi", 185), ("gas", 96)]:
            db.session.add(StoreBilling(
                tenant_id=tenant_id,
                store_id=store_name,
                bill_type=bill_type,
                billing_month=billing_month,
                amount=amount,
                paid=bill_type != "gas",
                payment_date=now - timedelta(days=2) if bill_type != "gas" else None,
            ))
    db.session.add(Alert(
        tenant_id=tenant_id,
        store_id="Phoenix Branch",
        manager_username=manager_username,
        alert_type="low_stock",
        title="Low stock: AirPods Pro",
        message="Phoenix Branch has only 2 AirPods Pro units remaining.",
        is_read=False,
    ))
    db.session.add(Alert(
        tenant_id=tenant_id,
        store_id="Downtown Store",
        manager_username=manager_username,
        alert_type="pending_report",
        title="EOD report due tonight",
        message="Downtown Store has one closing report pending for today.",
        is_read=False,
    ))
    db.session.commit()
