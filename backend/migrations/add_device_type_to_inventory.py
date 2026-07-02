"""
Migration script to add device_type column to inventory table.

Run this script to add the device_type column to existing inventory tables.
This will:
1. Add the device_type column with default value 'metro'
2. Update all existing rows to have device_type = 'metro'
3. Create an index on device_type for better query performance

Usage:
    python -m backend.migrations.add_device_type_to_inventory
    OR
    python backend/migrations/add_device_type_to_inventory.py
"""

import sys
import os

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app import create_app
from backend.database import db
from sqlalchemy import text

def migrate():
    """Add device_type column to inventory table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'inventory' AND column_name = 'device_type'
            """))
            
            if result.fetchone():
                print("[OK] Column 'device_type' already exists in inventory table. Skipping migration.")
                return
            
            print("Adding device_type column to inventory table...")
            
            # Step 1: Add column as nullable first (to allow existing rows)
            db.session.execute(text("""
                ALTER TABLE inventory 
                ADD COLUMN device_type VARCHAR(50) DEFAULT 'metro'
            """))
            
            # Step 2: Update all existing rows to have device_type = 'metro'
            db.session.execute(text("""
                UPDATE inventory 
                SET device_type = 'metro' 
                WHERE device_type IS NULL
            """))
            
            # Step 3: Make column NOT NULL
            db.session.execute(text("""
                ALTER TABLE inventory 
                ALTER COLUMN device_type SET NOT NULL
            """))
            
            # Step 4: Create index for better query performance
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_inventory_device_type 
                ON inventory(device_type)
            """))
            
            db.session.commit()
            print("[OK] Successfully added device_type column to inventory table!")
            print("  - All existing items have been set to device_type = 'metro'")
            print("  - Index created on device_type column")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    migrate()

