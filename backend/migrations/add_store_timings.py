"""
Migration script to add opening_time and closing_time columns to stores table.
This allows managers to set store operating hours for time clock restrictions.
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
    """Add opening_time and closing_time columns to stores table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'stores'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("⚠ stores table does not exist. This migration may not be needed.")
                return
            
            # Check if opening_time column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'stores' 
                    AND column_name = 'opening_time'
                );
            """))
            opening_time_exists = result.scalar()
            
            if not opening_time_exists:
                # Add opening_time column
                print("Adding opening_time column...")
                db.session.execute(text("""
                    ALTER TABLE stores 
                    ADD COLUMN opening_time VARCHAR(5);
                """))
            else:
                print("✓ opening_time column already exists")
            
            # Check if closing_time column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'stores' 
                    AND column_name = 'closing_time'
                );
            """))
            closing_time_exists = result.scalar()
            
            if not closing_time_exists:
                # Add closing_time column
                print("Adding closing_time column...")
                db.session.execute(text("""
                    ALTER TABLE stores 
                    ADD COLUMN closing_time VARCHAR(5);
                """))
            else:
                print("✓ closing_time column already exists")
            
            db.session.commit()
            print("✓ Migration complete: opening_time and closing_time columns added successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate()
