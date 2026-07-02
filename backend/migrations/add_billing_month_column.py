"""
Migration script to add billing_month column to store_billings table.
This allows billings to be tracked monthly and reset each month.
"""
from backend.app import create_app
from backend.database import db
from sqlalchemy import text

def migrate():
    """Add billing_month column to store_billings table"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'store_billings'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("⚠ store_billings table does not exist. Run 'flask create-billings-table' first.")
                return
            
            # Check if billing_month column already exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'store_billings' 
                    AND column_name = 'billing_month'
                );
            """))
            column_exists = result.scalar()
            
            if column_exists:
                print("✓ billing_month column already exists")
                return
            
            # Get current month for existing records
            from datetime import datetime
            current_month = datetime.utcnow().strftime('%Y-%m')
            
            # Add billing_month column with default value
            print(f"Adding billing_month column (defaulting to {current_month})...")
            db.session.execute(text(f"""
                ALTER TABLE store_billings 
                ADD COLUMN billing_month VARCHAR(7) NOT NULL DEFAULT '{current_month}';
            """))
            
            # Create index on billing_month
            print("Creating index on billing_month...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_store_billings_billing_month 
                ON store_billings(billing_month);
            """))
            
            # Drop old unique constraint if it exists and create new one
            print("Updating unique constraint to include billing_month...")
            try:
                db.session.execute(text("""
                    ALTER TABLE store_billings 
                    DROP CONSTRAINT IF EXISTS uq_tenant_store_bill_type;
                """))
            except:
                pass  # Constraint might not exist
            
            # Create new unique constraint with billing_month
            try:
                db.session.execute(text("""
                    ALTER TABLE store_billings 
                    ADD CONSTRAINT uq_tenant_store_bill_type_month 
                    UNIQUE (tenant_id, store_id, bill_type, billing_month);
                """))
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Note: Could not create unique constraint (may already exist): {e}")
            
            db.session.commit()
            print("✓ Migration complete: billing_month column added successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate()

