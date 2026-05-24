# backend/routes/stores.py
from flask import Blueprint, request, jsonify, g

from ..models import (
    get_stores, create_store, delete_store, get_store_by_username, update_store,
    verify_password, get_manager_by_username
)
from ..auth import require_auth, generate_token, validate_password_strength

bp = Blueprint("stores", __name__)

# Rate limiter will be applied using limiter.limit() decorator after app initialization

# Blueprint-level error handler to ensure JSON responses
@bp.errorhandler(Exception)
def handle_store_error(e):
    """Handle all exceptions in stores blueprint and return JSON"""
    import traceback
    import sys
    from werkzeug.exceptions import HTTPException
    
    error_msg = str(e)
    error_type = type(e).__name__
    
    # Log the full error for debugging
    print("=" * 80)
    print(f"STORES BLUEPRINT ERROR: {error_type}: {error_msg}")
    print(f"Path: {request.path}")
    print("FULL TRACEBACK:")
    traceback.print_exc(file=sys.stdout)
    print("=" * 80)
    
    # Get status code from HTTPException if applicable
    status_code = 500
    if isinstance(e, HTTPException):
        status_code = e.code
    
    # Always return JSON error response
    import os
    if os.getenv("FLASK_ENV") == "development":
        return jsonify({
            "error": f"Error: {error_msg}",
            "error_type": error_type
        }), status_code
    else:
        return jsonify({
            "error": "An error occurred. Please try again."
        }), status_code


def _get_client_ip():
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"

@bp.get("/")
@require_auth()
def list_stores():
    """List stores for the current tenant, optionally filtered by manager_username"""
    tenant_id = g.tenant_id
    # Get manager_username from query parameter if provided
    manager_username = request.args.get("manager_username")
    stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
    # Don't return passwords in the list
    for store in stores:
        store.pop("password", None)
    return jsonify(stores)

@bp.post("/")
@require_auth(roles=['manager'])
def add_store():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "Store name is required"}), 400
        if len(name) > 100:
            return jsonify({"error": "Store name is too long (max 100 characters)"}), 400
        
        username = data.get("username")
        if not username:
            return jsonify({"error": "Username is required"}), 400
        if len(username) > 50:
            return jsonify({"error": "Username is too long (max 50 characters)"}), 400
        
        password = data.get("password")
        if not password:
            return jsonify({"error": "Password is required"}), 400
        if len(password) > 200:
            return jsonify({"error": "Password is too long (max 200 characters)"}), 400
        
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        total_boxes = data.get("total_boxes")
        if total_boxes is None:
            return jsonify({"error": "Total boxes is required"}), 400
        
        # Validate total_boxes is a positive integer
        try:
            total_boxes = int(total_boxes)
            if total_boxes < 1:
                return jsonify({"error": "Total boxes must be a positive integer"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Total boxes must be a positive integer"}), 400
        
        # Get opening_time and closing_time (optional, format: "HH:MM" in 24-hour format)
        opening_time = data.get("opening_time")
        closing_time = data.get("closing_time")
        
        # Validate time format if provided
        import re
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
        if opening_time and not time_pattern.match(opening_time):
            return jsonify({"error": "Opening time must be in 24-hour format (HH:MM), e.g., '09:00'"}), 400
        if closing_time and not time_pattern.match(closing_time):
            return jsonify({"error": "Closing time must be in 24-hour format (HH:MM), e.g., '17:00'"}), 400
        
        # Get tenant_id and manager_username from authenticated user
        tenant_id = g.tenant_id
        user = g.current_user
        manager_username = user.get('username')
        if not manager_username:
            return jsonify({"error": "Manager authentication required"}), 401
        
        client_ip = _get_client_ip()
        store_id = create_store(
            tenant_id=tenant_id,
            name=name,
            username=username,
            password=password,
            total_boxes=total_boxes,
            manager_username=manager_username,
            allowed_ip=client_ip,
            opening_time=opening_time,
            closing_time=closing_time
        )
        # Return store info without password
        store_info = {
            "id": store_id,
            "name": name,
            "username": username,
            "total_boxes": total_boxes,
            "allowed_ip": client_ip,
            "opening_time": opening_time,
            "closing_time": closing_time
        }
        
        # Return response immediately - inventory will be created on first inventory access
        # This ensures store creation responds instantly (< 1 second)
        return jsonify(store_info), 201
    except ValueError as e:
        # Handle validation errors (duplicate store name, etc.)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Log the error for debugging
        import traceback
        import os
        error_msg = str(e)
        error_type = type(e).__name__
        traceback.print_exc()
        
        # Check if store was actually created despite the error
        # Wrap in try-except to prevent cascading errors
        try:
            from backend.models import get_store_by_name
            from backend.database import db
            
            # Rollback any pending transaction first to clear the session
            db.session.rollback()
            
            # Only check if name and tenant_id are available
            if 'name' in locals() and 'tenant_id' in locals():
                # Create a new session context to check if store exists
                # This avoids the PendingRollbackError
                existing_store = None
                try:
                    # Query the store directly with a fresh session state
                    from backend.models import Store
                    existing_store = Store.query.filter_by(
                        tenant_id=tenant_id,
                        name=name
                    ).first()
                except Exception as query_error:
                    print(f"Warning: Failed to query store: {query_error}")
                
                if existing_store:
                    # Store was created successfully, return success even if something else failed
                    store_info = {
                        "id": str(existing_store.id),
                        "name": existing_store.name,
                        "username": existing_store.username,
                        "total_boxes": existing_store.total_boxes,
                        "allowed_ip": existing_store.allowed_ip or (client_ip if 'client_ip' in locals() else None)
                    }
                    return jsonify(store_info), 201
        except Exception as check_error:
            # If checking for existing store fails, log it but continue with error response
            print(f"Warning: Failed to check if store exists: {check_error}")
            # Make sure to rollback to clear any pending state
            try:
                from backend.database import db
                db.session.rollback()
            except:
                pass
        
        # Store doesn't exist or check failed, rollback and return error
        try:
            from backend.database import db
            db.session.rollback()
        except:
            pass  # Ignore rollback errors
        
        # Return JSON error response
        if os.getenv("FLASK_ENV") == "development":
            return jsonify({
                "error": f"Failed to create store: {error_msg}",
                "error_type": error_type
            }), 500
        else:
            return jsonify({"error": "Failed to create store. Please try again."}), 500

@bp.post("/login")
def store_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    # Try to find store (tenant_id will be extracted from store record)
    store = get_store_by_username(username)
    if not store:
        return jsonify({"error": "Invalid credentials"}), 401

    stored_password = store.get("password")
    if not stored_password or not verify_password(password, stored_password):
        return jsonify({"error": "Invalid credentials"}), 401

    allowed_ip = store.get("allowed_ip")
    client_ip = _get_client_ip()
    if allowed_ip and client_ip != allowed_ip:
        return jsonify({
            "error": "Access denied from this location.",
            "details": f"This store can only be accessed from IP {allowed_ip}. You are coming from {client_ip}."
        }), 403

    tenant_id = store.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": "Store configuration error"}), 500

    token = generate_token({
        "role": "store",
        "tenant_id": tenant_id,
        "storeId": store.get("name"),
        "storeName": store.get("name"),
        "username": username
    })

    store.pop("password", None)
    response_data = {**store, "token": token}
    return jsonify(response_data), 200

@bp.put("/")
@require_auth(roles=['manager'])
def edit_store():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "Store name is required"}), 400
        
        new_name = data.get("new_name")
        username = data.get("username")
        password = data.get("password")
        total_boxes = data.get("total_boxes")
        raw_use_current_ip = data.get("use_current_ip")
        use_current_ip = str(raw_use_current_ip).lower() in ("1", "true", "yes", "on")
        allowed_ip = data.get("allowed_ip") if "allowed_ip" in data else None
        opening_time = data.get("opening_time")
        closing_time = data.get("closing_time")
        
        # Validate time format if provided
        import re
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
        if opening_time is not None and opening_time != "" and not time_pattern.match(opening_time):
            return jsonify({"error": "Opening time must be in 24-hour format (HH:MM), e.g., '09:00'"}), 400
        if closing_time is not None and closing_time != "" and not time_pattern.match(closing_time):
            return jsonify({"error": "Closing time must be in 24-hour format (HH:MM), e.g., '17:00'"}), 400
        
        # Validate password strength if password is being updated
        if password:
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                return jsonify({"error": error_msg}), 400
        
        # Validate total_boxes if provided
        if total_boxes is not None:
            try:
                total_boxes = int(total_boxes)
                if total_boxes < 1:
                    return jsonify({"error": "Total boxes must be a positive integer"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Total boxes must be a positive integer"}), 400
        
        ip_to_set = None
        if use_current_ip:
            ip_to_set = _get_client_ip()
        elif allowed_ip is not None:
            ip_to_set = allowed_ip or None

        tenant_id = g.tenant_id
        success = update_store(
            tenant_id=tenant_id,
            name=name,
            new_name=new_name,
            username=username,
            password=password,
            total_boxes=total_boxes,
            allowed_ip=ip_to_set,
            opening_time=opening_time if opening_time != "" else None,
            closing_time=closing_time if closing_time != "" else None
        )
        if success:
            # Return updated store info
            stores = get_stores(tenant_id=tenant_id)
            updated_store = next((s for s in stores if s.get("name") == (new_name or name)), None)
            if updated_store:
                updated_store.pop("password", None)
                return jsonify(updated_store), 200
            return jsonify({"message": f"Store '{name}' updated successfully"}), 200
        else:
            return jsonify({"error": f"Store '{name}' not found or no changes made"}), 404
    except Exception as e:
        import traceback
        import os
        error_msg = str(e)
        traceback.print_exc()
        # Don't expose internal error details to client in production
        if os.getenv("FLASK_ENV") == "development":
            return jsonify({"error": f"Failed to update store: {error_msg}"}), 500
        else:
            return jsonify({"error": "Failed to update store. Please try again."}), 500

@bp.delete("/")
@require_auth(roles=['manager'])
def remove_store():
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "Store name is required"}), 400
    
    tenant_id = g.tenant_id
    success = delete_store(tenant_id=tenant_id, name=name)
    if success:
        return jsonify({"message": f"Store '{name}' deleted successfully"}), 200
    else:
        return jsonify({"error": f"Store '{name}' not found"}), 404

@bp.post("/manager/login")
def manager_login():
    """Manager login endpoint"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Try to find manager (we'll need tenant_id from the manager record)
    manager = get_manager_by_username(username)
    if not manager:
        return jsonify({"error": "Invalid credentials"}), 401
    
    stored_password = manager.get("password")
    if not stored_password:
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Verify password (only bcrypt hashed passwords accepted)
    if not verify_password(password, stored_password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    tenant_id = manager.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": "Manager configuration error"}), 500
    
    # Check tenant status
    from ..models import Tenant
    tenant = Tenant.query.get(tenant_id)
    if tenant and tenant.status != 'active':
        return jsonify({"error": f"Account is {tenant.status}. Please contact support."}), 403
    
    # Determine role
    if manager.get("is_super_admin"):
        role = "super-admin"
    elif manager.get("is_admin"):
        role = "admin"
        regions = manager.get("regions", [])
    else:
        role = "manager"
    
    # Generate JWT token
    token_data = {
        "role": role,
        "tenant_id": tenant_id,
        "name": manager.get("name", "Manager"),
        "username": username,
        "is_super_admin": manager.get("is_super_admin", False),
        "is_admin": manager.get("is_admin", False)
    }
    
    if role == "admin":
        token_data["regions"] = regions
    
    token = generate_token(token_data)
    
    # Don't return password
    manager.pop("password", None)
    response_data = {
        "role": role,
        "tenant_id": tenant_id,
        "name": manager.get("name", "Manager"),
        "username": username,
        "token": token
    }
    
    if role == "admin":
        response_data["regions"] = regions
    
    return jsonify(response_data), 200


