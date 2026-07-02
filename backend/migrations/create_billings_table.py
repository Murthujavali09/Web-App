"""
Migration script to create the store_billings table.
Run this script to create the table if it doesn't exist.
"""
from backend.app import create_app
from backend.database import db

def migrate():
    """Create the store_billings table"""
    app = create_app()
    with app.app_context():
        # Import the model to register it with SQLAlchemy
        from backend.models import StoreBilling
        
        # Create all tables (this will create store_billings if it doesn't exist)
        db.create_all()
        
        print("✓ Migration complete: store_billings table created (if it didn't exist)")

if __name__ == "__main__":
    migrate()

