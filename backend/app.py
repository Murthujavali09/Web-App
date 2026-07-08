# backend/app.py
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import click
import sys
import os
from pathlib import Path

# If this module is executed directly (python backend/app.py), the
# import system will set sys.path[0] to the `backend/` directory which
# prevents importing the `backend` package using absolute imports
# like `backend.config`. Insert the project root into sys.path when
# running as a script so absolute imports work.
if __package__ is None:
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from backend.config import Config
from backend.database import db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    # Disable Flask's default HTML error pages - we'll handle errors ourselves
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.config['DEBUG'] = False  # Disable debug mode HTML error pages
    CORS(app)

    db.init_app(app)
    
    # Import models here to register them with SQLAlchemy before creating tables
    # This must happen after db.init_app() but before db.create_all()
    from backend import models
    # Explicitly import StoreBilling to ensure it's registered with SQLAlchemy
    from backend.models import StoreBilling  # noqa: F401
    
    # Create all database tables
    # For serverless functions, we should allow the app to start even if DB is unavailable
    # The database connection will be attempted on first use
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            error_msg = str(e)
            # Provide helpful error messages for common issues
            if "could not translate host name" in error_msg or "No such host is known" in error_msg:
                print("\n" + "="*80)
                print("DATABASE CONNECTION WARNING: Hostname cannot be resolved")
                print("="*80)
                print(f"Error: {error_msg}")
                print("\nThis usually means:")
                print("1. The DATABASE_URL hostname is incomplete or incorrect")
                print("2. For Render.com: Make sure the hostname includes the full domain")
                print("   Example: dpg-xxxxx-xxxxx-a.oregon-postgres.render.com")
                print("   NOT: dpg-xxxxx-xxxxx-a")
                print("3. Check your .env file or environment variables")
                print("4. Verify the database is running and accessible")
                print("\nNOTE: App will continue to start. Database will be connected on first use.")
                print("="*80 + "\n")
            elif "SSL connection" in error_msg:
                print("\n" + "="*80)
                print("DATABASE SSL CONNECTION WARNING")
                print("="*80)
                print(f"Error: {error_msg}")
                print("\nThis usually means:")
                print("1. The database requires SSL but the connection failed")
                print("2. Check your DATABASE_URL includes sslmode=require")
                print("3. For Render.com: SSL is required")
                print("\nNOTE: App will continue to start. Database will be connected on first use.")
                print("="*80 + "\n")
            else:
                print(f"\nWARNING: Database connection failed: {error_msg}")
                print("NOTE: App will continue to start. Database will be connected on first use.\n")
            # Don't re-raise - allow app to start and handle DB errors at request time
            # This is important for serverless functions where DB might not be available at cold start
    
    # Check email configuration at startup
    try:
        from backend.routes.tenants import get_email_config
        email_config = get_email_config()
        if not email_config['configured']:
            print("\n" + "="*80)
            print("WARNING  EMAIL CONFIGURATION WARNING")
            print("="*80)
            print("SMTP credentials are not configured. Emails will NOT be sent!")
            print("\nTo enable email sending, set these environment variables:")
            print("  SMTP_USER=your-email@gmail.com")
            print("  SMTP_PASSWORD=your-app-password")
            print("  SMTP_HOST=smtp.gmail.com (optional, default)")
            print("  SMTP_PORT=587 (optional, default)")
            print("  FROM_EMAIL=your-email@gmail.com (optional)")
            print("\nFor Gmail:")
            print("  1. Enable 2-factor authentication")
            print("  2. Generate an 'App Password' at: https://myaccount.google.com/apppasswords")
            print("  3. Use the app password as SMTP_PASSWORD (not your regular password)")
            print("="*80 + "\n")
        else:
            print(f"OK Email configured: {email_config['from_email']} via {email_config['host']}:{email_config['port']}")
    except Exception as e:
        print(f"WARNING  Warning: Could not check email configuration: {e}")
    
    # Check Stripe webhook configuration at startup
    try:
        from backend.routes.tenants import get_stripe_config
        stripe_config = get_stripe_config()
        if not stripe_config['webhook_secret']:
            env_mode = os.getenv("FLASK_ENV", os.getenv("ENVIRONMENT", "production")).lower()
            is_dev = env_mode == "development"
            print("\n" + "="*80)
            print("WARNING  STRIPE WEBHOOK CONFIGURATION WARNING")
            print("="*80)
            if is_dev:
                print("Development mode: Webhook secret not configured.")
                print("\nFor local development:")
                print("  1. Run: stripe listen --forward-to http://localhost:5000/api/tenants/webhook/stripe")
                print("  2. Copy the webhook signing secret (whsec_...)")
                print("  3. Set in .env: STRIPE_WEBHOOK_SECRET_DEV=whsec_xxxxxxxxxxxxx")
            else:
                print("Production mode: Webhook secret not configured.")
                print("\nFor production:")
                print("  1. Go to Stripe Dashboard > Developers > Webhooks")
                print("  2. Add endpoint: https://your-domain.com/api/tenants/webhook/stripe")
                print("  3. Select event: checkout.session.completed")
                print("  4. Copy the signing secret and set: STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx")
            print("\nSee WEBHOOK_SETUP.md for detailed instructions")
            print("="*80 + "\n")
        else:
            print(f"OK Stripe webhook configured ({'dev' if stripe_config.get('is_dev') else 'production'} mode)")
    except Exception as e:
        print(f"WARNING  Warning: Could not check Stripe webhook configuration: {e}")
    
    # Initialize rate limiter
    # Don't apply default limits globally - only apply to specific routes that need protection
    # This prevents static files and favicon from being rate limited
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=None,  # No global limits - apply limits only to specific routes
        storage_uri="memory://",  # Use in-memory storage (use Redis in production)
        headers_enabled=True,
        swallow_errors=True  # Don't crash on rate limit errors, just return 429
    )
    # Make limiter available globally for blueprints
    app.extensions['limiter'] = limiter

    from backend.routes.employees import bp as employees_bp
    from backend.routes.timeclock import bp as timeclock_bp
    from backend.routes.inventory import bp as inventory_bp
    from backend.routes.eod import bp as eod_bp
    from backend.routes.stores import bp as stores_bp
    from backend.routes.face import bp as face_bp
    from backend.routes.inventory_history import bp as inventory_history_bp
    from backend.routes.managers import bp as managers_bp
    from backend.routes.admins import bp as admins_bp
    from backend.routes.tenants import bp as tenants_bp
    from backend.routes.billings import bp as billings_bp
    from backend.routes.auto_clockout import bp as auto_clockout_bp
    from backend.routes.alerts import bp as alerts_bp

    # Register error handlers BEFORE blueprints to ensure they catch all errors
    # Global error handler to ensure all API errors return JSON
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all unhandled exceptions and return JSON for API routes"""
        from flask import request
        import traceback
        import sys
        from werkzeug.exceptions import HTTPException
        
        # Check if this is an API request
        if request.path.startswith('/api/'):
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Log the full error for debugging
            print("=" * 80)
            print(f"UNHANDLED EXCEPTION: {error_type}: {error_msg}")
            print(f"Path: {request.path}")
            print(f"Method: {request.method}")
            print(f"Full URL: {request.url}")
            print("FULL TRACEBACK:")
            traceback.print_exc(file=sys.stdout)
            print("=" * 80)
            
            # Get status code from HTTPException if applicable
            status_code = 500
            if isinstance(e, HTTPException):
                status_code = e.code
            
            # Return JSON error response
            import os
            if os.getenv("FLASK_ENV") == "development":
                response = jsonify({
                    "error": f"Internal server error: {error_msg}",
                    "error_type": error_type
                })
            else:
                response = jsonify({
                    "error": "Internal server error. Please try again."
                })
            
            response.status_code = status_code
            return response
        
        # For non-API routes, let Flask handle it
        raise
    
    # Add 404 handler to log missing routes
    @app.errorhandler(404)
    def handle_404(e):
        """Handle 404 errors and log the requested URL"""
        from flask import request
        print("=" * 80)
        print("404 NOT FOUND ERROR")
        print(f"Requested URL: {request.url}")
        print(f"Requested Path: {request.path}")
        print(f"Request Method: {request.method}")
        print(f"Referrer: {request.referrer}")
        print("=" * 80)
        
        # For API routes, return JSON
        if request.path.startswith('/api/'):
            return jsonify({"error": f"Route not found: {request.path}"}), 404
        
        # For non-API routes, let Flask handle it (will show default 404 page)
        return e
    
    # Register blueprints - order matters! More specific routes first
    app.register_blueprint(tenants_bp, url_prefix="/api/tenants")
    app.register_blueprint(inventory_history_bp, url_prefix="/api/inventory/history")
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    app.register_blueprint(timeclock_bp, url_prefix="/api/timeclock")
    app.register_blueprint(inventory_bp, url_prefix="/api/inventory")
    app.register_blueprint(eod_bp, url_prefix="/api/eod")
    app.register_blueprint(stores_bp, url_prefix="/api/stores")
    app.register_blueprint(face_bp, url_prefix="/api/face")
    app.register_blueprint(managers_bp, url_prefix="/api/managers")
    app.register_blueprint(admins_bp, url_prefix="/api/admins")
    app.register_blueprint(billings_bp, url_prefix="/api/billings")
    app.register_blueprint(auto_clockout_bp, url_prefix="/api/auto-clockout")
    app.register_blueprint(alerts_bp, url_prefix="/api/alerts")
    
    # Apply rate limiting to login endpoints
    # Flask-Limiter will automatically apply rate limits based on decorators
    try:
        limiter.limit("5 per minute")(stores_bp.view_functions['store_login'])
        limiter.limit("5 per minute")(stores_bp.view_functions['manager_login'])
        limiter.limit("5 per minute")(managers_bp.view_functions['super_admin_login'])
    except (KeyError, AttributeError):
        # Endpoints not found or limiter not available - this is okay during development
        pass

    # Ensure API routes always return JSON, even for error responses
    @app.after_request
    def ensure_json_for_api(response):
        """Ensure API routes return JSON content type, convert HTML errors to JSON"""
        from flask import request
        if request.path.startswith('/api/'):
            # Get response data to check if it's HTML
            response_data = response.get_data(as_text=True)
            
            # Check if response is HTML (starts with <!doctype or <html)
            is_html = False
            if response_data and (response_data.strip().lower().startswith('<!doctype') or 
                                 response_data.strip().lower().startswith('<html') or
                                 (response.content_type and 'text/html' in response.content_type)):
                is_html = True
            
            # If response is HTML (error page), convert to JSON
            if is_html and response.status_code >= 400:
                import os
                error_msg = "Internal server error. Please try again."
                if os.getenv("FLASK_ENV") == "development":
                    # Try to extract error message from HTML
                    if 'Exception:' in response_data or 'Error:' in response_data:
                        # Extract first error line
                        lines = response_data.split('\n')
                        for line in lines:
                            if 'Exception:' in line or 'Error:' in line:
                                error_msg = line.strip()[:200]
                                break
                    else:
                        error_msg = f"HTML error page received. Check server logs for details."
                json_response = jsonify({"error": error_msg})
                json_response.status_code = response.status_code
                return json_response
            
            # Ensure content-type is application/json for API error responses
            if response.status_code >= 400:
                response.content_type = 'application/json'
        return response
    
    # Ensure exceptions are propagated (already set above, but being explicit)
    # This ensures our error handlers catch exceptions before Flask's default handlers
    
    @app.get("/api/health")
    def health():
        return {"status": "ok"}
    
    # Serve favicon to prevent 404 errors
    @app.get("/favicon.ico")
    def favicon():
        return "", 204  # No Content - prevents 404 but doesn't serve a file
    
    # Debug routes removed for production security
    # To enable debug routes, only do so in development environment
    import os
    if os.getenv("FLASK_ENV") == "development":
        @app.get("/api/debug/routes")
        def debug_routes():
            routes = []
            for rule in app.url_map.iter_rules():
                routes.append({
                    "endpoint": rule.endpoint,
                    "methods": list(rule.methods),
                    "rule": str(rule)
                })
            return jsonify({"routes": routes})

    # Project root path - handle both local and serverless environments
    # In serverless (Vercel), files are in /var/task/, so we need to find the project root
    _current_file = Path(__file__).resolve()
    
    # Try to find project root by looking for common markers
    project_root = None
    possible_roots = [
        _current_file.parent.parent,  # Standard: backend/app.py -> root
        Path("/var/task"),  # Vercel serverless
        Path.cwd(),  # Current working directory
    ]
    
    # Also try walking up from current file
    test_path = _current_file.parent
    for _ in range(5):  # Max 5 levels up
        if (test_path / "backend" / "app.py").exists() or (test_path / "api" / "index.py").exists():
            possible_roots.append(test_path)
            break
        test_path = test_path.parent
    
    # Find the first valid project root
    for root in possible_roots:
        if root.exists():
            # Check if this looks like the project root
            if (root / "backend" / "app.py").exists() or (root / "api" / "index.py").exists():
                project_root = root
                break
    
    # Fallback to standard resolution if nothing found
    if project_root is None:
        project_root = _current_file.parent.parent
    
    frontend_pages = project_root / "frontend" / "pages"
    frontend_static = project_root / "frontend" / "static"

    # Serve public landing page at root
    @app.get("/")
    def serve_root():
        return send_from_directory(frontend_pages, "index.html")
    
    # Serve login page at /login.html
    @app.get("/login.html")
    def serve_login_html():
        return send_from_directory(frontend_pages, "login.html")
    
    # Serve login page at /login
    @app.get("/login")
    def serve_login():
        return send_from_directory(frontend_pages, "login.html")
    
    # Serve public landing page at /index.html
    @app.get("/index.html")
    def serve_index():
        return send_from_directory(frontend_pages, "index.html")
    
    # Serve HTML pages from frontend/pages
    @app.get("/<path:page>.html")
    def serve_page(page):
        return send_from_directory(frontend_pages, f"{page}.html")
    
    # Serve signup page as root signup route
    @app.get("/signup")
    def serve_signup():
        return send_from_directory(frontend_pages, "signup.html")
    
    @app.get("/signup-success")
    def serve_signup_success():
        return send_from_directory(frontend_pages, "signup-success.html")

    # Serve static CSS files
    @app.get("/static/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(frontend_static / "css", filename)

    # Serve static JS files
    @app.get("/static/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(frontend_static / "js", filename)


    # CLI command to seed default stores
    @app.cli.command("seed-stores")
    def seed_stores_command():
        from backend.models import Store, add_default_inventory_to_store, hash_password
        stores_count = Store.query.count()
        if stores_count == 0:
            store1 = Store(
                name="Downtown Store",
                username="downtown",
                password=hash_password("Store@123"),
                total_boxes=0,
                manager_username=None
            )
            store2 = Store(
                name="West Houston",
                username="westhouston",
                password=hash_password("Store@123"),
                total_boxes=0,
                manager_username=None
            )
            db.session.add(store1)
            db.session.add(store2)
            db.session.commit()
            
            # Get tenant_id (assuming first tenant or default tenant)
            from backend.models import Tenant
            tenant = Tenant.query.first()
            tenant_id = tenant.id if tenant else None
            
            if tenant_id:
                # Add default inventory items for each store
                count1 = add_default_inventory_to_store(tenant_id=tenant_id, store_name="Downtown Store")
                count2 = add_default_inventory_to_store(tenant_id=tenant_id, store_name="West Houston")
                click.echo(f"OK Seeded default stores with inventory:")
                click.echo(f"  - Downtown Store: {count1} items")
                click.echo(f"  - West Houston: {count2} items")
            else:
                click.echo("Warning: No tenant found, skipping inventory creation")
                click.echo("OK Seeded default stores (no inventory added)")
        else:
            click.echo("Stores already exist; skipping seed")
    
    # CLI command to add default inventory to existing stores
    @app.cli.command("add-inventory")
    @click.argument("store_name")
    def add_inventory_command(store_name):
        """Add default inventory items to a specific store"""
        from backend.models import Store, add_default_inventory_to_store
        
        store = Store.query.filter_by(name=store_name).first()
        if not store:
            click.echo(f"ERROR Error: Store '{store_name}' not found")
            click.echo("\nAvailable stores:")
            for s in Store.query.all():
                click.echo(f"  - {s.name}")
            return
        
        count = add_default_inventory_to_store(tenant_id=store.tenant_id, store_name=store_name)
        click.echo(f"OK Added {count} new inventory items to store '{store_name}'")
        
        # Show total inventory count
        from backend.models import Inventory
        total = Inventory.query.filter_by(store_id=store_name).count()
        click.echo(f"  Total inventory items: {total}")
    
    # CLI command to run database migrations
    @app.cli.command("migrate")
    def migrate_command():
        """Run database migrations"""
        from backend.migrations.add_device_type_to_inventory import migrate
        migrate()
    
    # CLI command to add inventory_sold column to EOD table
    @app.cli.command("add-inventory-sold-to-eod")
    def add_inventory_sold_to_eod_command():
        """Add inventory_sold column to eod table"""
        from backend.migrations.add_inventory_sold_to_eod import migrate
        migrate()
    
    # CLI command to add default inventory to existing stores
    @app.cli.command("add-inventory-to-stores")
    def add_inventory_to_stores_command():
        """Add default inventory to all existing stores that don't have inventory"""
        from backend.migrations.add_default_inventory_to_existing_stores import migrate
        migrate()
    
    # CLI command to show inventory count for all stores
    @app.cli.command("check-inventory")
    def check_inventory_command():
        """Show inventory item count for all stores"""
        from backend.models import Store, Inventory
        
        stores = Store.query.all()
        if not stores:
            click.echo("No stores found")
            return
        
        click.echo("\nInventory Inventory Status:")
        click.echo("-" * 40)
        for store in stores:
            count = Inventory.query.filter_by(store_id=store.name).count()
            click.echo(f"{store.name:20} {count:3} items")
        click.echo("-" * 40)

    # CLI command to create billings table
    @app.cli.command("create-billings-table")
    def create_billings_table_command():
        """Create the store_billings table if it doesn't exist"""
        from backend.models import StoreBilling
        
        with app.app_context():
            # Import the model to ensure it's registered
            # Then create all tables
            db.create_all()
            click.echo("OK store_billings table created (or already exists)")
    
    # CLI command to add billing_month column
    @app.cli.command("add-billing-month")
    def add_billing_month_command():
        """Add billing_month column to store_billings table"""
        from backend.migrations.add_billing_month_column import migrate
        migrate()
    
    # CLI command to add location column to managers table
    @app.cli.command("add-manager-location")
    def add_manager_location_command():
        """Add location column to managers table"""
        from backend.migrations.add_manager_location import migrate
        migrate()

    # CLI command to add admin fields to managers table
    @app.cli.command("add-admin-fields")
    def add_admin_fields_command():
        """Add is_admin and regions columns to managers table"""
        from backend.migrations.add_admin_fields_to_managers import migrate
        migrate()
    
    # CLI command to add store timings
    @app.cli.command("add-store-timings")
    def add_store_timings_command():
        """Add opening_time and closing_time columns to stores table"""
        from backend.migrations.add_store_timings import migrate
        migrate()
    
    # CLI command to create alerts table
    @app.cli.command("create-alerts-table")
    def create_alerts_table_command():
        """Create the alerts table if it doesn't exist"""
        from backend.migrations.add_alerts_table import migrate
        migrate()

    @app.cli.command("seed-dev")
    @click.option("--reset-super-admin", is_flag=True, help="Reset super admin password from .env")
    @click.option("--no-demo-manager", is_flag=True, help="Skip creating demo manager account")
    @click.option("--no-demo-stores", is_flag=True, help="Skip creating realistic demo stores")
    def seed_dev_command(reset_super_admin, no_demo_manager, no_demo_stores):
        """Seed tenant, super admin (from .env), demo manager, and sample stores for local dev"""
        from backend.seed_dev import seed_dev

        with app.app_context():
            db.create_all()
            result = seed_dev(
                create_demo_manager=not no_demo_manager,
                create_demo_stores=not no_demo_stores,
                force_reset_super_admin=reset_super_admin,
            )

        click.echo("")
        click.echo("Development database seeded successfully.")
        click.echo("-" * 50)
        click.echo(f"Tenant: {result['company_name']} (id={result['tenant_id']})")
        click.echo(f"Tenant email (for /api/tenants/login): {result['tenant_email']}")
        click.echo("")
        click.echo("Super Admin (login page - use USERNAME field):")
        click.echo(f"  Username: {result['super_admin_username']}")
        click.echo(f"  Password: {result['super_admin_password']}")
        click.echo("")
        if result.get("demo_manager_username"):
            click.echo("Demo Manager:")
            click.echo(f"  Username: {result['demo_manager_username']}")
            click.echo(f"  Password: {result['demo_manager_password']}")
            click.echo("")
        if result["stores_created"]:
            click.echo("Demo Stores:")
            for s in result["stores_created"]:
                click.echo(f"  {s['name']}: username={s['username']} password={s['password']}")
            click.echo("")
        click.echo("Log in at http://localhost:5000/")
        click.echo("-" * 50)

    return app

if __name__ == "__main__":
    app = create_app()
    # Only run in debug mode if explicitly set in environment
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode)

