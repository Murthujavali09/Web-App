"""
Migration script to create alerts table.
This table stores alerts/notifications for managers.
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
    """Create alerts table if it doesn't exist"""
    app = create_app()
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'alerts'
                );
            """))
            table_exists = result.scalar()
            
            if table_exists:
                print("✓ alerts table already exists")
                return
            
            # Create alerts table
            print("Creating alerts table...")
            db.session.execute(text("""
                CREATE TABLE alerts (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    store_id VARCHAR(100),
                    manager_username VARCHAR(50),
                    alert_type VARCHAR(50) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    employee_id INTEGER,
                    employee_name VARCHAR(100),
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
                );
            """))
            
            # Create indexes
            print("Creating indexes...")
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_alerts_tenant_id ON alerts(tenant_id);
                CREATE INDEX IF NOT EXISTS ix_alerts_store_id ON alerts(store_id);
                CREATE INDEX IF NOT EXISTS ix_alerts_manager_username ON alerts(manager_username);
                CREATE INDEX IF NOT EXISTS ix_alerts_is_read ON alerts(is_read);
                CREATE INDEX IF NOT EXISTS ix_alerts_created_at ON alerts(created_at);
            """))
            
            db.session.commit()
            print("✓ Migration complete: alerts table created successfully")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    migrate()
