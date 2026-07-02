"""
Migration script to add default inventory to existing stores that don't have any inventory items.

Run this script to add default inventory items to all existing stores.

Usage:
    python backend/migrations/add_default_inventory_to_existing_stores.py
"""

import sys
import os

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app import create_app
from backend.database import db
from backend.models import Store, Inventory, add_default_inventory_to_store

def migrate():
    """Add default inventory to all existing stores that don't have inventory"""
    app = create_app()
    
    with app.app_context():
        try:
            # Get all stores
            stores = Store.query.all()
            
            if not stores:
                print("[INFO] No stores found in the database.")
                return
            
            print(f"Found {len(stores)} store(s). Checking inventory...")
            
            total_added = 0
            for store in stores:
                # Check if store already has inventory
                existing_count = Inventory.query.filter_by(
                    tenant_id=store.tenant_id,
                    store_id=store.name
                ).count()
                
                if existing_count > 0:
                    print(f"  - Store '{store.name}': Already has {existing_count} inventory items. Skipping.")
                    continue
                
                # Add default inventory
                print(f"  - Store '{store.name}': Adding default inventory...")
                try:
                    count = add_default_inventory_to_store(
                        tenant_id=store.tenant_id,
                        store_name=store.name
                    )
                    total_added += count
                    print(f"    [OK] Added {count} inventory items to store '{store.name}'")
                except Exception as e:
                    print(f"    [ERROR] Failed to add inventory to store '{store.name}': {str(e)}")
            
            print(f"\n[OK] Migration complete! Added inventory to stores.")
            print(f"  Total items added: {total_added}")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    migrate()

