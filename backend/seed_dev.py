"""
Seed a local development database with a tenant, super admin, optional manager, and sample stores.

Credentials for super admin come from SUPER_ADMIN_USERNAME / SUPER_ADMIN_PASSWORD in .env
(defaults: superadmin / superadmin123).
"""
import os

from backend.config import Config
from backend.database import db
from backend.models import (
    Tenant,
    Manager,
    Store,
    create_tenant,
    create_manager,
    hash_password,
    add_default_inventory_to_store,
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
    company_name = company_name or os.getenv("DEV_TENANT_COMPANY", "Demo Company")
    tenant_email = tenant_email or os.getenv("DEV_TENANT_EMAIL", "admin@demo.local")

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
            name="Super Admin",
            username=sa_username,
            password=sa_password,
            is_super_admin=True,
        )
        created_super_admin = True
    elif force_reset_super_admin:
        super_admin.password = hash_password(sa_password)
        db.session.commit()

    demo_manager_username = os.getenv("DEV_MANAGER_USERNAME", "manager")
    demo_manager_password = os.getenv("DEV_MANAGER_PASSWORD", "manager123")
    demo_manager = Manager.query.filter_by(
        tenant_id=tenant.id, username=demo_manager_username
    ).first()

    created_demo_manager = False
    if create_demo_manager and not demo_manager:
        create_manager(
            tenant_id=tenant.id,
            name="Demo Manager",
            username=demo_manager_username,
            password=demo_manager_password,
            location="Demo Region",
        )
        created_demo_manager = True
        demo_manager = Manager.query.filter_by(
            tenant_id=tenant.id, username=demo_manager_username
        ).first()

    stores_created = []
    if create_demo_stores and Store.query.filter_by(tenant_id=tenant.id).count() == 0:
        demo_stores = [
            {
                "name": "Lawrence",
                "username": "lawrence",
                "password": "lawrence123",
                "total_boxes": 50,
                "opening_time": "09:00",
                "closing_time": "21:00",
            },
            {
                "name": "Oakville",
                "username": "oakville",
                "password": "oakville123",
                "total_boxes": 40,
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
            add_default_inventory_to_store(tenant_id=tenant.id, store_name=s["name"])
            stores_created.append(
                {"name": s["name"], "username": s["username"], "password": s["password"]}
            )

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
