# backend/routes/managers.py
from flask import Blueprint, request, jsonify, g
from ..models import get_all_managers, create_manager, update_manager, get_manager_by_username, verify_password
from ..config import Config
from ..auth import generate_token, validate_password_strength, require_auth

bp = Blueprint("managers", __name__)

@bp.get("/")
@require_auth(roles=['super-admin', 'admin'])
def list_managers():
    """List all managers for the current tenant (super-admin sees all regular managers, admin sees only managers in assigned regions)"""
    tenant_id = g.tenant_id
    user_role = g.current_user.get('role')
    all_managers = get_all_managers(tenant_id=tenant_id)
    
    # If admin, filter managers by assigned regions
    if user_role == 'admin':
        admin_regions = g.current_user.get('regions', [])
        if not admin_regions:
            # Admin with no regions sees nothing
            return jsonify([])
        
        # Filter managers to only those in admin's assigned regions
        filtered_managers = []
        for manager in all_managers:
            # Exclude super admins and other admins
            if manager.get('is_super_admin') or manager.get('is_admin'):
                continue
            # Include managers whose location matches one of admin's regions
            manager_location = manager.get('location', '').strip()
            if manager_location and manager_location in admin_regions:
                filtered_managers.append(manager)
        
        return jsonify(filtered_managers)
    
    # Super-admin sees all regular managers (excluding super-admins and admins)
    regular_managers = []
    for manager in all_managers:
        # Exclude super admins and admins from the list
        if not manager.get('is_super_admin') and not manager.get('is_admin'):
            regular_managers.append(manager)
    
    return jsonify(regular_managers)

@bp.post("/")
@require_auth(roles=['super-admin'])
def add_manager():
    """Create a new manager (super-admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "Manager name is required"}), 400
        if len(name) > 100:
            return jsonify({"error": "Manager name is too long (max 100 characters)"}), 400
        
        username = data.get("username")
        if not username:
            return jsonify({"error": "Username is required"}), 400
        if len(username) > 50:
            return jsonify({"error": "Username is too long (max 50 characters)"}), 400
        
        location = data.get("location")
        if location and len(location) > 100:
            return jsonify({"error": "Location is too long (max 100 characters)"}), 400
        
        password = data.get("password")
        if not password:
            return jsonify({"error": "Password is required"}), 400
        if len(password) > 200:
            return jsonify({"error": "Password is too long (max 200 characters)"}), 400
        
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return jsonify({"error": error_msg}), 400
        
        tenant_id = g.tenant_id
        manager_info = create_manager(tenant_id=tenant_id, name=name, username=username, password=password, location=location)
        return jsonify(manager_info), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check if it's a database unique constraint violation for username
        error_str = str(e)
        if ("UniqueViolation" in error_str or "duplicate key" in error_str.lower()) and ("username" in error_str.lower() or "ix_managers_username" in error_str.lower()):
            return jsonify({"error": f"Username with that name already exists"}), 409
        return jsonify({"error": f"Failed to create manager: {str(e)}"}), 500

@bp.put("/<username>")
@require_auth(roles=['super-admin'])
def edit_manager(username):
    """Update an existing manager (super-admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        new_username = data.get("username")
        location = data.get("location")
        password = data.get("password")
        
        # Validate inputs
        if name is not None and len(name) > 100:
            return jsonify({"error": "Manager name is too long (max 100 characters)"}), 400
        if new_username is not None and len(new_username) > 50:
            return jsonify({"error": "Username is too long (max 50 characters)"}), 400
        if location is not None and len(location) > 100:
            return jsonify({"error": "Location is too long (max 100 characters)"}), 400
        if password is not None:
            if len(password) > 200:
                return jsonify({"error": "Password is too long (max 200 characters)"}), 400
            # Validate password strength
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                return jsonify({"error": error_msg}), 400
        
        tenant_id = g.tenant_id
        updated_manager = update_manager(tenant_id=tenant_id, username=username, name=name, new_username=new_username, password=password, location=location)
        return jsonify(updated_manager), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check if it's a database unique constraint violation for username
        error_str = str(e)
        if ("UniqueViolation" in error_str or "duplicate key" in error_str.lower()) and ("username" in error_str.lower() or "ix_managers_username" in error_str.lower()):
            return jsonify({"error": f"Username with that name already exists"}), 409
        return jsonify({"error": f"Failed to update manager: {str(e)}"}), 500

@bp.get("/<username>")
@require_auth(roles=['super-admin'])
def get_manager(username):
    """Get a specific manager by username (super-admin only)"""
    tenant_id = g.tenant_id
    manager = get_manager_by_username(username, tenant_id=tenant_id)
    if not manager:
        return jsonify({"error": "Manager not found"}), 404
    # Don't return password
    manager.pop("password", None)
    return jsonify(manager)

@bp.post("/super-admin/login")
def super_admin_login():
    """
    Super-admin login endpoint.
    Note: This is for tenant super-admins. Use /api/tenants/login for tenant-level login.
    """
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Find manager by username (will need tenant_id from manager record)
    manager = get_manager_by_username(username)
    if not manager:
        return jsonify({"error": "Invalid credentials"}), 401
    
    stored_password = manager.get("password")
    if not stored_password or not verify_password(password, stored_password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    # Check if this is a super admin
    if not manager.get("is_super_admin"):
        return jsonify({"error": "Access denied. Super admin privileges required."}), 403
    
    tenant_id = manager.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": "Manager configuration error"}), 500
    
    # Check tenant status
    from ..models import Tenant
    tenant = Tenant.query.get(tenant_id)
    if tenant and tenant.status != 'active':
        return jsonify({"error": f"Account is {tenant.status}. Please contact support."}), 403
    
    # Generate JWT token
    token = generate_token({
        "role": "super-admin",
        "tenant_id": tenant_id,
        "name": manager.get("name", "Super Admin"),
        "username": username,
        "is_super_admin": True
    })
    
    return jsonify({
        "role": "super-admin",
        "tenant_id": tenant_id,
        "name": manager.get("name", "Super Admin"),
        "username": username,
        "token": token
    }), 200

