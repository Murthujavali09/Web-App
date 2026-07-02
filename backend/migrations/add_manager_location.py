"""
Migration script to add location column to managers table.
Run this if you have existing managers and need to add the location column.
"""
from backend.app import create_app
from backend.database import db
from sqlalchemy import text

def migrate():
    """Add location column to managers table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'managers'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("[INFO] managers table does not exist. No migration needed.")
                return
            
            # Check if location column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'managers' 
                    AND column_name = 'location'
                );
            """))
            column_exists = result.scalar()
            
            if column_exists:
                print("[OK] location column already exists")
                return
            
            print("Adding location column to managers table...")
            db.session.execute(text("""
                ALTER TABLE managers 
                ADD COLUMN location VARCHAR(100);
            """))
            
            db.session.commit()
            print("[OK] Migration complete: location column added successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {e}")
            import traceback
            traceback.print_exc()
            import sys
            sys.exit(1)

if __name__ == "__main__":
    migrate()

