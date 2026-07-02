"""
Migration script to add is_admin and regions columns to managers table.
Run this if you have existing managers and need to add admin support.
"""
from backend.app import create_app
from backend.database import db
from sqlalchemy import text

def migrate():
    """Add is_admin and regions columns to managers table"""
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
            
            # Check if is_admin column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'managers' 
                    AND column_name = 'is_admin'
                );
            """))
            is_admin_exists = result.scalar()
            
            if not is_admin_exists:
                print("Adding is_admin column to managers table...")
                db.session.execute(text("""
                    ALTER TABLE managers 
                    ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
                """))
                db.session.commit()
                print("[OK] is_admin column added successfully")
            else:
                print("[OK] is_admin column already exists")
            
            # Check if regions column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'managers' 
                    AND column_name = 'regions'
                );
            """))
            regions_exists = result.scalar()
            
            if not regions_exists:
                print("Adding regions column to managers table...")
                db.session.execute(text("""
                    ALTER TABLE managers 
                    ADD COLUMN regions TEXT;
                """))
                db.session.commit()
                print("[OK] regions column added successfully")
            else:
                print("[OK] regions column already exists")
            
            print("[OK] Migration complete: admin fields added successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {e}")
            import traceback
            traceback.print_exc()
            import sys
            sys.exit(1)

if __name__ == "__main__":
    migrate()

