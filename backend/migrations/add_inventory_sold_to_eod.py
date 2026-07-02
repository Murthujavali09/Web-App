"""
Migration script to add inventory_sold column to eod table.
This allows tracking the number of inventory items sold in end of day reports.
"""
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from backend.app import create_app
from backend.database import db
from sqlalchemy import text

def migrate():
    """Add inventory_sold column to eod table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'eod'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("⚠ eod table does not exist. This migration may not be needed.")
                return
            
            # Check if inventory_sold column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'eod' 
                    AND column_name = 'inventory_sold'
                );
            """))
            column_exists = result.scalar()
            
            if column_exists:
                print("✓ inventory_sold column already exists")
                return
            
            # Add inventory_sold column with default value of 0
            print("Adding inventory_sold column...")
            db.session.execute(text("""
                ALTER TABLE eod 
                ADD COLUMN inventory_sold INTEGER NOT NULL DEFAULT 0;
            """))
            
            db.session.commit()
            print("✓ Migration complete: inventory_sold column added successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate()
