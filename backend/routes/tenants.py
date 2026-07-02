# backend/routes/tenants.py
"""
Tenant management routes for multi-tenant SaaS platform.
Handles tenant signup, authentication, and plan management.
"""
from flask import Blueprint, request, jsonify, g
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import Config first to access BASE_DIR and Stripe
from ..config import Config
# Import stripe from config where it's already initialized
try:
    from ..config import stripe
    if stripe is None:
        raise ImportError("Stripe not available")
except (ImportError, AttributeError):
    # Fallback: import stripe directly if not available in config
    try:
        import stripe
    except ImportError:
        stripe = None

# Ensure .env file is loaded (Config already loads it, but ensure it's loaded here too)
# Use Config.BASE_DIR to ensure consistent path
ENV_PATH = Config.BASE_DIR / ".env"
load_dotenv(ENV_PATH if ENV_PATH.exists() else None)

from ..models import (
    Tenant, create_tenant, get_tenant_by_email, get_tenant_by_id,
    update_tenant_plan, create_manager, hash_password, verify_password
)
from ..auth import generate_token, require_auth, validate_password_strength
from ..database import db

bp = Blueprint("tenants", __name__)

# Note: Stripe API key will be set per-request in endpoints that need it
# This avoids initialization errors when Stripe is not configured

def get_stripe_config():
    """Get and validate Stripe configuration from environment"""
    # Use Config.BASE_DIR to ensure consistent .env file path
    env_path = Config.BASE_DIR / ".env"
    
    # Debug: Log .env file info
    env_exists = env_path.exists()
    if not env_exists:
        print(f"WARNING: .env file not found at {env_path}")
    else:
        print(f"INFO: Loading .env from {env_path}")
    
    # Reload env to ensure latest values
    load_dotenv(env_path if env_exists else None, override=True)
    
    # Get Stripe key with debugging
    stripe_key_raw = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_key = stripe_key_raw.strip() if stripe_key_raw else ""
    
    # Debug logging (only first few chars for security)
    if stripe_key:
        print(f"INFO: STRIPE_SECRET_KEY found (length: {len(stripe_key)}, starts with: {stripe_key[:7]}...)")
    else:
        print(f"WARNING: STRIPE_SECRET_KEY not found or empty. Raw value: {repr(stripe_key_raw)}")
        # List all env vars that start with STRIPE
        stripe_vars = {k: v[:20] + "..." if len(v) > 20 else v for k, v in os.environ.items() if k.startswith("STRIPE")}
        print(f"DEBUG: Stripe-related env vars: {stripe_vars}")
    
    price_ids = {
        'basic': os.getenv("STRIPE_PRICE_ID_BASIC", "").strip(),
        'standard': os.getenv("STRIPE_PRICE_ID_STANDARD", "").strip(),
        'premium': os.getenv("STRIPE_PRICE_ID_PREMIUM", "").strip()
    }
    
    # Support separate webhook secrets for development and production
    # Development: STRIPE_WEBHOOK_SECRET_DEV (from stripe listen command)
    # Production: STRIPE_WEBHOOK_SECRET (from Stripe Dashboard)
    env_mode = os.getenv("FLASK_ENV", os.getenv("ENVIRONMENT", "production")).lower()
    is_dev = env_mode == "development" or "localhost" in os.getenv("STRIPE_SUCCESS_URL", "")
    
    webhook_secret = ""
    if is_dev:
        # Try development webhook secret first
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET_DEV", "").strip()
        # Fallback to regular webhook secret if dev secret not set
        if not webhook_secret:
            webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    else:
        # Production: use production webhook secret
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    
    return {
        'api_key': stripe_key,
        'price_ids': price_ids,
        'webhook_secret': webhook_secret,
        'success_url': os.getenv("STRIPE_SUCCESS_URL", "http://localhost:5000/signup-success?session_id={CHECKOUT_SESSION_ID}"),
        'cancel_url': os.getenv("STRIPE_CANCEL_URL", "http://localhost:5000/signup?cancelled=true"),
        'env_path': str(env_path),
        'env_exists': env_exists,
        'is_dev': is_dev
    }

def get_email_config():
    """Get email configuration from environment variables (reloads at runtime)"""
    # Reload env to ensure we have latest values
    load_dotenv(ENV_PATH if ENV_PATH.exists() else None, override=True)
    
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("FROM_EMAIL", "").strip() or smtp_user
    
    return {
        'host': smtp_host,
        'port': smtp_port,
        'user': smtp_user,
        'password': smtp_password,
        'from_email': from_email,
        'configured': bool(smtp_user and smtp_password)
    }


def send_email(to_email, subject, body_html, body_text=None):
    """Send email using SMTP"""
    # Get email config at runtime to ensure latest values
    email_config = get_email_config()
    
    if not email_config['configured']:
        print(f"❌ EMAIL NOT CONFIGURED: SMTP credentials are missing!")
        print(f"   Required environment variables: SMTP_USER, SMTP_PASSWORD")
        print(f"   Optional: SMTP_HOST (default: smtp.gmail.com), SMTP_PORT (default: 587), FROM_EMAIL")
        print(f"   Would send email to: {to_email}")
        print(f"   Subject: {subject}")
        return False
    
    try:
        print(f"📧 Attempting to send email to {to_email}...")
        print(f"   SMTP Host: {email_config['host']}:{email_config['port']}")
        print(f"   From: {email_config['from_email']}")
        print(f"   Subject: {subject}")
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = email_config['from_email']
        msg['To'] = to_email
        
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))
        
        print(f"   Connecting to {email_config['host']}:{email_config['port']}...")
        with smtplib.SMTP(email_config['host'], email_config['port']) as server:
            print(f"   Starting TLS...")
            server.starttls()
            print(f"   Logging in as {email_config['user']}...")
            server.login(email_config['user'], email_config['password'])
            print(f"   Sending message...")
            server.send_message(msg)
        
        print(f"✅ Email sent successfully to {to_email}!")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ SMTP Authentication Error: {e}")
        print(f"   Check your SMTP_USER and SMTP_PASSWORD in environment variables")
        print(f"   For Gmail: Use an 'App Password' (not your regular password)")
        print(f"   Get app password: https://myaccount.google.com/apppasswords")
        import traceback
        traceback.print_exc()
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Error sending email: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_temp_password():
    """Generate a secure temporary password"""
    return secrets.token_urlsafe(12)


@bp.post("/signup")
def tenant_signup():
    """
    Tenant signup endpoint.
    Creates tenant account and redirects to Stripe checkout.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        company_name = data.get("company_name", "").strip()
        email = data.get("email", "").strip().lower()
        plan = data.get("plan", "basic")  # basic, standard, premium
        
        if not company_name:
            return jsonify({"error": "Company name is required"}), 400
        if not email:
            return jsonify({"error": "Email is required"}), 400
        if plan not in ["basic", "standard", "premium"]:
            return jsonify({"error": "Invalid plan. Must be basic, standard, or premium"}), 400
        
        # Check if tenant already exists
        existing = get_tenant_by_email(email)
        if existing:
            return jsonify({"error": "An account with this email already exists"}), 400
        
        # Generate temporary password (will be sent via email)
        temp_password = generate_temp_password()
        password_hash = hash_password(temp_password)
        
        # Create tenant (without Stripe info yet - will be updated after payment)
        tenant = create_tenant(
            company_name=company_name,
            email=email,
            password_hash=password_hash,
            plan=plan
        )
        
        tenant_id = tenant['id']
        
        # Get Stripe configuration
        stripe_config = get_stripe_config()
        stripe_key = stripe_config['api_key']
        
        if not stripe_key:
            # Clean up tenant since we can't proceed without Stripe
            Tenant.query.filter_by(id=tenant_id).delete()
            db.session.commit()
            
            # Provide detailed error message with debug info
            error_msg = "Stripe is not configured. STRIPE_SECRET_KEY environment variable is not set."
            env_path = Path(stripe_config.get('env_path', ''))
            debug_info = {
                "env_file_exists": stripe_config.get('env_exists', False),
                "env_file_path": stripe_config.get('env_path', 'unknown'),
                "env_file_absolute_path": str(env_path.resolve()) if stripe_config.get('env_exists') else None,
                "env_file_readable": os.access(env_path, os.R_OK) if stripe_config.get('env_exists') else False,
                "current_working_dir": str(Path.cwd()),
                "config_base_dir": str(Config.BASE_DIR),
                "note": "Make sure you have restarted your Flask server after updating the .env file"
            }
            
            # Log to console for debugging
            print(f"ERROR: {error_msg}")
            print(f"DEBUG: env_file_exists={debug_info['env_file_exists']}")
            print(f"DEBUG: env_file_path={debug_info['env_file_path']}")
            print(f"DEBUG: config_base_dir={debug_info['config_base_dir']}")
            
            return jsonify({
                "error": error_msg,
                "debug": debug_info
            }), 500
        
        # Ensure Stripe is fully initialized
        # Set API key (should already be set in config, but ensure it's set here too)
        if stripe.api_key != stripe_key:
            stripe.api_key = stripe_key
        
        # Verify Stripe is available and initialized
        if not stripe or not stripe.api_key:
            Tenant.query.filter_by(id=tenant_id).delete()
            db.session.commit()
            return jsonify({
                "error": "Stripe is not available or not properly initialized",
                "debug": {
                    "stripe_available": stripe is not None,
                    "stripe_api_key_set": bool(stripe.api_key) if stripe else False,
                    "stripe_key_length": len(stripe_key) if stripe_key else 0
                }
            }), 500
        
        try:
            # Verify Stripe is fully functional before attempting API calls
            # Check that Stripe's internal modules are loaded
            if not hasattr(stripe, 'Customer'):
                raise AttributeError("Stripe.Customer module not available - Stripe may not be properly initialized")
            
            # Verify Stripe API key is valid by attempting to create a customer
            # This will fail early if Stripe is not properly configured
            customer = stripe.Customer.create(
                email=email,
                name=company_name,
                metadata={
                    'tenant_id': str(tenant_id),
                    'plan': plan
                }
            )
            
            # Get price ID for the selected plan
            price_id = stripe_config['price_ids'].get(plan)
            if not price_id:
                # Clean up tenant since we can't proceed without price ID
                Tenant.query.filter_by(id=tenant_id).delete()
                db.session.commit()
                return jsonify({
                    "error": f"Stripe price ID not configured for plan: {plan}",
                    "debug": {
                        "available_plans": list(stripe_config['price_ids'].keys()),
                        "configured_price_ids": {k: bool(v) for k, v in stripe_config['price_ids'].items()}
                    } if os.getenv("FLASK_ENV") == "development" else {}
                }), 500
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=stripe_config['success_url'],
                cancel_url=stripe_config['cancel_url'],
                metadata={
                    'tenant_id': str(tenant_id),
                    'plan': plan
                }
            )
            
            # Update tenant with Stripe customer ID
            tenant_obj = Tenant.query.get(tenant_id)
            tenant_obj.stripe_customer_id = customer.id
            db.session.commit()
            
            return jsonify({
                "checkout_url": checkout_session.url,
                "tenant_id": tenant_id,
                "message": "Redirect to Stripe checkout"
            }), 200
            
        except stripe.error.StripeError as e:
            # Stripe API error - show the actual error message
            Tenant.query.filter_by(id=tenant_id).delete()
            db.session.commit()
            
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Log the full error for debugging
            print(f"ERROR: Stripe API error: {error_type}: {error_msg}")
            print(f"DEBUG: Stripe API key set: {bool(stripe.api_key)}")
            if stripe.api_key:
                print(f"DEBUG: Stripe API key length: {len(stripe.api_key)}, starts with: {stripe.api_key[:7]}...")
            
            # Return the actual Stripe error message
            return jsonify({
                "error": f"Stripe payment error: {error_msg}",
                "error_type": error_type,
                "error_code": getattr(e, 'code', None),
                "debug": {
                    "stripe_api_key_set": bool(stripe.api_key),
                    "stripe_api_key_prefix": stripe.api_key[:7] + "..." if stripe.api_key else None,
                    "stripe_error_type": error_type
                }
            }), 500
            
        except (AttributeError, TypeError) as e:
            # Stripe initialization error - this shouldn't happen if config is correct
            Tenant.query.filter_by(id=tenant_id).delete()
            db.session.commit()
            
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Log the full error for debugging with more detail
            import traceback
            import sys
            print("=" * 80)
            print(f"ERROR: Stripe initialization error: {error_type}")
            print(f"ERROR MESSAGE: {error_msg}")
            print(f"DEBUG: Stripe module: {stripe}")
            print(f"DEBUG: Stripe API key set: {bool(stripe.api_key) if stripe else False}")
            if stripe and stripe.api_key:
                print(f"DEBUG: Stripe API key length: {len(stripe.api_key)}, starts with: {stripe.api_key[:7]}...")
            print("FULL TRACEBACK:")
            traceback.print_exc(file=sys.stdout)
            print("=" * 80)
            
            # Return detailed error information
            return jsonify({
                "error": (
                    f"Stripe initialization error: {error_msg}. "
                    "This usually means Stripe's internal modules aren't loading properly. "
                    "Check the server console logs for full error details."
                ),
                "error_type": error_type,
                "error_message": error_msg,
                "debug": {
                    "stripe_module_available": stripe is not None,
                    "stripe_api_key_set": bool(stripe.api_key) if stripe else False,
                    "stripe_api_key_length": len(stripe.api_key) if stripe and stripe.api_key else 0,
                    "note": "See server console for full traceback"
                }
            }), 500
            
        except Exception as e:
            # Catch any other unexpected errors
            Tenant.query.filter_by(id=tenant_id).delete()
            db.session.commit()
            
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Log the full error for debugging
            import traceback
            print(f"ERROR: Unexpected error during Stripe checkout: {error_type}: {error_msg}")
            traceback.print_exc()
            
            return jsonify({
                "error": f"Unexpected error: {error_msg}",
                "error_type": error_type,
                "debug": {
                    "note": "Check server console logs for full error details"
                }
            }), 500
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to create tenant: {str(e)}"}), 500


@bp.post("/webhook/stripe")
def stripe_webhook():
    """
    Stripe webhook handler for subscription events.
    Updates tenant status and creates super admin account.
    """
    print("🔔 Webhook received!")
    
    # Get Stripe configuration
    stripe_config = get_stripe_config()
    stripe_key = stripe_config['api_key']
    webhook_secret = stripe_config['webhook_secret']
    
    if not stripe_key:
        print("❌ Error: Stripe is not configured")
        return jsonify({"error": "Stripe is not configured"}), 500
    
    if not webhook_secret:
        print("❌ Error: Webhook secret not configured")
        print("   For development: Run 'stripe listen' and set STRIPE_WEBHOOK_SECRET_DEV")
        print("   For production: Configure webhook in Stripe Dashboard and set STRIPE_WEBHOOK_SECRET")
        print("   See WEBHOOK_SETUP.md for detailed instructions")
        return jsonify({"error": "Webhook secret not configured"}), 500
    
    # Ensure Stripe is initialized
    stripe.api_key = stripe_key
    
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        print(f"✅ Webhook event verified: {event['type']}")
    except ValueError as e:
        print(f"❌ Invalid payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Invalid signature: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        print("📦 Processing checkout.session.completed event...")
        try:
            session = event['data']['object']
            print(f"   Session ID: {session.get('id')}")
            print(f"   Metadata: {session.get('metadata')}")
            
            # Check if metadata exists
            if not session.get('metadata') or 'tenant_id' not in session['metadata']:
                print("❌ Error: Missing tenant_id in session metadata")
                print(f"   Available metadata keys: {list(session.get('metadata', {}).keys())}")
                return jsonify({"error": "Missing tenant_id in session metadata"}), 400
            
            tenant_id = int(session['metadata'].get('tenant_id'))
            plan = session['metadata'].get('plan', 'basic')
            print(f"   Tenant ID: {tenant_id}, Plan: {plan}")
            
            tenant = Tenant.query.get(tenant_id)
            if not tenant:
                print(f"❌ Tenant not found: {tenant_id}")
                return jsonify({"error": "Tenant not found"}), 404
            
            print(f"✅ Found tenant: {tenant.company_name} ({tenant.email})")
            
            # Update tenant with subscription ID
            subscription_id = session.get('subscription')
            if subscription_id:
                tenant.stripe_subscription_id = subscription_id
                tenant.status = 'active'
                db.session.commit()
                print(f"✅ Tenant status updated to 'active'")
                
                # Create super admin account for this tenant
                super_admin_username = tenant.email.split('@')[0]  # Use email prefix as username
                super_admin_password = generate_temp_password()
                
                print(f"📧 Preparing to send email to: {tenant.email}")
                print(f"🔑 Generated password: {super_admin_password}")
                
                try:
                    create_manager(
                        tenant_id=tenant_id,
                        name="Super Admin",
                        username=super_admin_username,
                        password=super_admin_password,
                        is_super_admin=True
                    )
                    print(f"✅ Super admin created: {super_admin_username}")
                    
                    # Initialize storage tracking for this tenant
                    from backend.utils.storage import initialize_tenant_storage
                    initialize_tenant_storage(tenant_id)
                    
                    # Send email with login credentials
                    login_url = os.getenv("APP_LOGIN_URL", "https://app.mywebsite.com")
                    email_body = f"""
                    <html>
                    <body>
                        <h2>Welcome to Pramaan!</h2>
                        <p>Your account has been successfully created.</p>
                        <p><strong>Company:</strong> {tenant.company_name}</p>
                        <p><strong>Plan:</strong> {plan.capitalize()}</p>
                        <p><strong>Login URL:</strong> <a href="{login_url}">{login_url}</a></p>
                        <p><strong>Username:</strong> {super_admin_username}</p>
                        <p><strong>Email:</strong> {tenant.email}</p>
                        <p><strong>Password:</strong> {super_admin_password}</p>
                        <p><em>Please change your password after first login.</em></p>
                    </body>
                    </html>
                    """
                    
                    email_sent = send_email(
                        to_email=tenant.email,
                        subject="Welcome to Pramaan - Your Account is Ready",
                        body_html=email_body
                    )
                    
                    if email_sent:
                        print(f"✅ Email sent successfully to {tenant.email}")
                    else:
                        print(f"❌ CRITICAL: Email sending failed!")
                        print(f"   Tenant ID: {tenant_id}")
                        print(f"   Email: {tenant.email}")
                        print(f"   Username: {super_admin_username}")
                        print(f"   Password: {super_admin_password}")
                        print(f"   ⚠️ Please configure SMTP settings to send emails automatically")
                        print(f"   ⚠️ User must contact support or check server logs for credentials")
                    
                except ValueError as e:
                    # Manager already exists or other error
                    print(f"⚠️ Warning: Could not create super admin: {e}")
        except Exception as e:
            print(f"❌ Error processing checkout.session.completed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"Error processing webhook: {str(e)}"}), 500
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        tenant = Tenant.query.filter_by(stripe_customer_id=customer_id).first()
        if tenant:
            # Update plan based on subscription
            # You'll need to map Stripe price IDs to plans
            # For now, we'll keep the existing plan
            tenant.status = 'active' if subscription['status'] == 'active' else 'suspended'
            db.session.commit()
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        tenant = Tenant.query.filter_by(stripe_customer_id=customer_id).first()
        if tenant:
            tenant.status = 'cancelled'
            db.session.commit()
    
    print(f"✅ Webhook processed successfully for event: {event['type']}")
    return jsonify({"status": "success"}), 200


@bp.post("/login")
def tenant_login():
    """
    Tenant super admin login endpoint.
    """
    data = request.get_json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    tenant = get_tenant_by_email(email)
    if not tenant:
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Check tenant status
    tenant_obj = Tenant.query.get(tenant['id'])
    if tenant_obj.status != 'active':
        return jsonify({"error": f"Account is {tenant_obj.status}. Please contact support."}), 403
    
    # Verify password
    password_hash = tenant.get('password_hash')
    if not password_hash or not verify_password(password, password_hash):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Get super admin manager for this tenant
    from ..models import Manager
    super_admin = Manager.query.filter_by(
        tenant_id=tenant['id'],
        is_super_admin=True
    ).first()
    
    if not super_admin:
        return jsonify({"error": "Super admin account not found. Please contact support."}), 404
    
    # Generate JWT token
    token = generate_token({
        "role": "super-admin",
        "tenant_id": tenant['id'],
        "name": super_admin.name,
        "username": super_admin.username,
        "is_super_admin": True
    })
    
    return jsonify({
        "role": "super-admin",
        "tenant_id": tenant['id'],
        "company_name": tenant['company_name'],
        "name": super_admin.name,
        "username": super_admin.username,
        "token": token
    }), 200


@bp.get("/me")
@require_auth()
def get_current_tenant():
    """Get current tenant information"""
    tenant_id = g.tenant_id
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    return jsonify(tenant)


@bp.put("/plan")
@require_auth(roles=['super-admin'])
def upgrade_plan():
    """Upgrade tenant plan (handled via Stripe)"""
    # This endpoint can be used to trigger plan upgrades
    # The actual upgrade happens via Stripe checkout
    data = request.get_json()
    plan = data.get("plan")
    
    if plan not in ["basic", "standard", "premium"]:
        return jsonify({"error": "Invalid plan"}), 400
    
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    # Create Stripe checkout for plan upgrade
    # Implementation similar to signup
    return jsonify({"message": "Plan upgrade initiated"}), 200


@bp.get("/storage")
@require_auth()
def get_storage_info():
    """Get storage usage information for current tenant"""
    from backend.utils.storage import get_storage_usage_info
    
    tenant_id = g.tenant_id
    storage_info = get_storage_usage_info(tenant_id)
    
    if not storage_info:
        return jsonify({"error": "Tenant not found"}), 404
    
    return jsonify(storage_info), 200


@bp.get("/subscription")
@require_auth(roles=['super-admin'])
def get_subscription():
    """Get subscription details for current tenant"""
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    subscription_data = {
        "plan": tenant.plan,
        "status": tenant.status,
        "stripe_customer_id": tenant.stripe_customer_id,
        "stripe_subscription_id": tenant.stripe_subscription_id,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
    }
    
    # Get detailed subscription info from Stripe if available
    if tenant.stripe_subscription_id and stripe:
        try:
            stripe_config = get_stripe_config()
            stripe.api_key = stripe_config['api_key']
            
            subscription = stripe.Subscription.retrieve(tenant.stripe_subscription_id)
            subscription_data.update({
                "stripe_status": subscription.status,
                "current_period_start": datetime.fromtimestamp(subscription.current_period_start).isoformat(),
                "current_period_end": datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "items": [{
                    "price_id": item.price.id,
                    "product_id": item.price.product,
                    "quantity": item.quantity
                } for item in subscription.items.data]
            })
        except Exception as e:
            print(f"Error fetching Stripe subscription: {e}")
            subscription_data["stripe_error"] = str(e)
    
    return jsonify(subscription_data), 200


@bp.post("/subscription/upgrade")
@require_auth(roles=['super-admin'])
def upgrade_subscription():
    """Create Stripe checkout session for plan upgrade"""
    data = request.get_json()
    plan = data.get("plan")
    
    if plan not in ["basic", "standard", "premium"]:
        return jsonify({"error": "Invalid plan"}), 400
    
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    if not stripe:
        return jsonify({"error": "Stripe is not configured"}), 500
    
    try:
        stripe_config = get_stripe_config()
        stripe.api_key = stripe_config['api_key']
        
        price_id = stripe_config['price_ids'].get(plan)
        if not price_id:
            return jsonify({"error": f"Price ID not configured for plan: {plan}"}), 400
        
        # Create checkout session for subscription update
        checkout_session = stripe.checkout.Session.create(
            customer=tenant.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=stripe_config['success_url'],
            cancel_url=stripe_config['cancel_url'],
            metadata={
                'tenant_id': str(tenant_id),
                'action': 'upgrade',
                'new_plan': plan
            }
        )
        
        return jsonify({
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }), 200
        
    except Exception as e:
        print(f"Error creating upgrade checkout: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/subscription/cancel")
@require_auth(roles=['super-admin'])
def cancel_subscription():
    """Cancel subscription at period end"""
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    if not tenant.stripe_subscription_id:
        return jsonify({"error": "No active subscription found"}), 400
    
    if not stripe:
        return jsonify({"error": "Stripe is not configured"}), 500
    
    try:
        stripe_config = get_stripe_config()
        stripe.api_key = stripe_config['api_key']
        
        subscription = stripe.Subscription.modify(
            tenant.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        return jsonify({
            "message": "Subscription will be cancelled at period end",
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "current_period_end": datetime.fromtimestamp(subscription.current_period_end).isoformat()
        }), 200
        
    except Exception as e:
        print(f"Error cancelling subscription: {e}")
        return jsonify({"error": str(e)}), 500


@bp.post("/subscription/reactivate")
@require_auth(roles=['super-admin'])
def reactivate_subscription():
    """Reactivate a cancelled subscription"""
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    if not tenant.stripe_subscription_id:
        return jsonify({"error": "No subscription found"}), 400
    
    if not stripe:
        return jsonify({"error": "Stripe is not configured"}), 500
    
    try:
        stripe_config = get_stripe_config()
        stripe.api_key = stripe_config['api_key']
        
        subscription = stripe.Subscription.modify(
            tenant.stripe_subscription_id,
            cancel_at_period_end=False
        )
        
        tenant.status = 'active'
        db.session.commit()
        
        return jsonify({
            "message": "Subscription reactivated",
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "status": subscription.status
        }), 200
        
    except Exception as e:
        print(f"Error reactivating subscription: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/subscription/billing-portal")
@require_auth(roles=['super-admin'])
def get_billing_portal():
    """Get Stripe billing portal URL for customer self-service"""
    tenant_id = g.tenant_id
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return jsonify({"error": "Tenant not found"}), 404
    
    if not tenant.stripe_customer_id:
        return jsonify({"error": "No Stripe customer found"}), 400
    
    if not stripe:
        return jsonify({"error": "Stripe is not configured"}), 500
    
    try:
        stripe_config = get_stripe_config()
        stripe.api_key = stripe_config['api_key']
        
        # Create billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL", "http://localhost:5000/super-admin.html")
        )
        
        return jsonify({
            "url": portal_session.url
        }), 200
        
    except Exception as e:
        print(f"Error creating billing portal session: {e}")
        return jsonify({"error": str(e)}), 500


@bp.get("/config/debug")
def debug_config():
    """
    Debug endpoint to check Stripe configuration.
    Available in all environments for troubleshooting.
    """
    # Always allow access for debugging - remove this check
    # if os.getenv("FLASK_ENV") != "development" and os.getenv("FLASK_DEBUG") != "1":
    #     return jsonify({"error": "Not available in production"}), 403
    
    stripe_config = get_stripe_config()
    
    # Check if .env file exists and is readable
    env_path = Path(stripe_config['env_path'])
    env_exists = env_path.exists()
    env_readable = os.access(env_path, os.R_OK) if env_exists else False
    
    # Read .env file contents (without sensitive data)
    env_contents = None
    if env_exists and env_readable:
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Only show variable names, not values (for security)
                env_contents = [line.split('=')[0].strip() for line in lines if '=' in line and not line.strip().startswith('#')]
        except Exception as e:
            env_contents = f"Error reading file: {str(e)}"
    
    # Check environment variables
    env_vars = {
        'STRIPE_SECRET_KEY': 'SET' if stripe_config['api_key'] else 'NOT SET',
        'STRIPE_PRICE_ID_BASIC': 'SET' if stripe_config['price_ids']['basic'] else 'NOT SET',
        'STRIPE_PRICE_ID_STANDARD': 'SET' if stripe_config['price_ids']['standard'] else 'NOT SET',
        'STRIPE_PRICE_ID_PREMIUM': 'SET' if stripe_config['price_ids']['premium'] else 'NOT SET',
        'STRIPE_WEBHOOK_SECRET': 'SET' if stripe_config['webhook_secret'] else 'NOT SET',
    }
    
    return jsonify({
        "env_file": {
            "exists": env_exists,
            "readable": env_readable,
            "path": str(env_path),
            "absolute_path": str(env_path.resolve()) if env_exists else None,
            "variables_found": env_contents
        },
        "config_base_dir": str(Config.BASE_DIR),
        "current_working_dir": str(Path.cwd()),
        "environment_variables": env_vars,
        "stripe_config": {
            "api_key_set": bool(stripe_config['api_key']),
            "api_key_length": len(stripe_config['api_key']) if stripe_config['api_key'] else 0,
            "api_key_prefix": stripe_config['api_key'][:7] + "..." if stripe_config['api_key'] else None,
            "price_ids_configured": {k: bool(v) for k, v in stripe_config['price_ids'].items()},
            "webhook_secret_set": bool(stripe_config['webhook_secret'])
        }
    }), 200


@bp.post("/storage/recalculate")
@require_auth(roles=['super-admin'])
def recalculate_storage():
    """Recalculate storage usage from database (admin only)"""
    from backend.utils.storage import initialize_tenant_storage, get_storage_usage_info
    
    tenant_id = g.tenant_id
    current_storage = initialize_tenant_storage(tenant_id)
    
    storage_info = get_storage_usage_info(tenant_id)
    
    return jsonify({
        "message": "Storage recalculated",
        "storage": storage_info
    }), 200

