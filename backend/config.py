import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
# Check for .env in both project root and backend folder
ENV_PATH_ROOT = BASE_DIR / ".env"
ENV_PATH_BACKEND = Path(__file__).resolve().parent / ".env"
# Load .env from backend folder first (if exists), then from root
if ENV_PATH_BACKEND.exists():
    load_dotenv(ENV_PATH_BACKEND, override=True)
elif ENV_PATH_ROOT.exists():
    load_dotenv(ENV_PATH_ROOT, override=True)

# Initialize Stripe early to avoid initialization issues
# Import and set API key as early as possible
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
stripe = None

try:
    import stripe
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
        # Force Stripe to initialize its internal modules by accessing them
        # This ensures all modules are loaded before we try to use them
        try:
            # Test that Stripe is properly initialized by checking a simple attribute
            _ = stripe.api_key
            # Try to access a module to ensure it's loaded
            # This will fail if Stripe isn't properly initialized
            _ = stripe.Customer
            print(f"INFO: Stripe initialized with API key (length: {len(STRIPE_SECRET_KEY)}, starts with: {STRIPE_SECRET_KEY[:7]}...)")
        except (AttributeError, TypeError) as init_error:
            print(f"WARNING: Stripe initialized but internal modules may not be loaded: {init_error}")
            print(f"WARNING: This may cause issues when using Stripe API. Try reinstalling stripe: pip install --upgrade stripe")
    else:
        print("WARNING: STRIPE_SECRET_KEY not found in environment variables")
except ImportError:
    print("WARNING: Stripe library not installed")
    print("WARNING: Install with: pip install stripe")
except Exception as e:
    print(f"WARNING: Error initializing Stripe: {e}")
    import traceback
    traceback.print_exc()


class Config:
    BASE_DIR = BASE_DIR
    
    # PostgreSQL Database Configuration
    # Format: postgresql://username:password@localhost:5432/database_name
    # Default falls back to SQLite for easy setup
    database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRESQL_URI")
    is_postgresql = database_url and ("postgresql://" in database_url or "postgres://" in database_url)
    
    if database_url:
        # Only use PostgreSQL if explicitly configured
        # For Render.com and other cloud PostgreSQL services, ensure SSL is enabled
        if is_postgresql:
            # Validate and parse the database URL
            from urllib.parse import urlparse
            try:
                parsed = urlparse(database_url)
                hostname = parsed.hostname
                
                # Check if hostname looks incomplete (common issue with Render.com)
                if hostname and not "." in hostname and hostname.startswith("dpg-"):
                    print(f"WARNING: Database hostname '{hostname}' appears incomplete.")
                    print(f"WARNING: Render.com hostnames should include the full domain (e.g., '{hostname}.oregon-postgres.render.com')")
                    print(f"WARNING: Please check your DATABASE_URL environment variable.")
                    print(f"WARNING: Current hostname: {hostname}")
                
                # Add SSL parameters if not already present
                if "?" not in database_url:
                    database_url += "?sslmode=require"
                elif "sslmode" not in database_url:
                    database_url += "&sslmode=require"
            except Exception as e:
                print(f"WARNING: Error parsing DATABASE_URL: {e}")
                print(f"WARNING: DATABASE_URL value (masked): {database_url[:20]}...{database_url[-10:] if len(database_url) > 30 else ''}")
        
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # Default to SQLite (doesn't require psycopg2)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'timetrack.db'}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configure engine options
    engine_options = {
        "pool_pre_ping": True,  # Enable connection health checks
        "pool_recycle": 300,    # Recycle connections after 5 minutes
    }
    
    # Add SSL connect args for PostgreSQL (psycopg2)
    if is_postgresql:
        engine_options["connect_args"] = {
            "sslmode": "require"
        }
    
    SQLALCHEMY_ENGINE_OPTIONS = engine_options
    
    # SECURITY WARNING: Never use the default "dev-key" in production!
    # Set SECRET_KEY environment variable to a strong random string (min 32 chars)
    SECRET_KEY = os.getenv("SECRET_KEY")
    
    # Super Admin credentials (for managing managers)
    SUPER_ADMIN_USERNAME = os.getenv('SUPER_ADMIN_USERNAME', 'superadmin')
    SUPER_ADMIN_PASSWORD = os.getenv('SUPER_ADMIN_PASSWORD', 'superadmin123')
    
    # Stripe configuration
    STRIPE_SECRET_KEY = STRIPE_SECRET_KEY
    
    # Upload directories
    # Note: In serverless environments (like Vercel), the filesystem is read-only
    # File uploads should be handled via cloud storage (S3, Cloudinary, etc.)
    UPLOAD_DIR = BASE_DIR / "uploads"
    # Only create directory if not in a read-only filesystem (serverless environment)
    try:
        UPLOAD_DIR.mkdir(exist_ok=True)
    except (OSError, PermissionError):
        # Serverless environment - directory creation not allowed
        # File uploads should use cloud storage instead
        pass
    
    # Note: Legacy YubiKey environment variables are ignored
    