# backend/routes/admins.py
from flask import Blueprint, request, jsonify, g
from ..models import get_all_managers, create_manager, update_manager, get_manager_by_username, verify_password
from ..config import Config
from ..auth import generate_token, validate_password_strength, require_auth

bp = Blueprint("admins", __name__)

@bp.get("/")
@require_auth(roles=['super-admin'])
def list_admins():
    """List all admins for the current tenant (super-admin only)"""
    tenant_id = g.tenant_id
    managers = get_all_managers(tenant_id=tenant_id)
    # Filter to only admins
    admins = [m for m in managers if m.get('is_admin', False)]
    return jsonify(admins)

@bp.get("/available-regions")
@require_auth(roles=['super-admin'])
def get_available_regions():
    """Get all unique locations from managers (super-admin only)"""
    tenant_id = g.tenant_id
    from ..models import Manager
    
    # Get all unique locations from managers (excluding super admins and admins)
    managers = Manager.query.filter_by(tenant_id=tenant_id).filter(
        Manager.location.isnot(None),
        Manager.is_super_admin == False,
        Manager.is_admin == False
    ).all()
    
    locations_set = set()
    for manager in managers:
        if manager.location and manager.location.strip():
            locations_set.add(manager.location.strip())
    
    # Also include locations from existing admins' regions (in case they were assigned custom regions)
    admins = Manager.query.filter_by(tenant_id=tenant_id, is_admin=True).all()
    for admin in admins:
        admin_regions = admin.get_regions()
        if admin_regions:
            for region in admin_regions:
                if region and region.strip():
                    locations_set.add(region.strip())
    
    # Convert to sorted list
    locations = sorted(list(locations_set))
    
    return jsonify(locations)

@bp.post("/")
@require_auth(roles=['super-admin'])
def add_admin():
    """Create a new admin (super-admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "Admin name is required"}), 400
        if len(name) > 100:
            return jsonify({"error": "Admin name is too long (max 100 characters)"}), 400
        
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
        
        regions = data.get("regions", [])
        if not isinstance(regions, list):
            return jsonify({"error": "Regions must be an array"}), 400
        
        tenant_id = g.tenant_id
        admin_info = create_manager(
            tenant_id=tenant_id, 
            name=name, 
            username=username, 
            password=password, 
            location=location,
            is_admin=True,
            regions=regions
        )
        return jsonify(admin_info), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check if it's a database unique constraint violation for username
        error_str = str(e)
        if ("UniqueViolation" in error_str or "duplicate key" in error_str.lower()) and ("username" in error_str.lower() or "ix_managers_username" in error_str.lower()):
            return jsonify({"error": f"Username with that name already exists"}), 409
        return jsonify({"error": f"Failed to create admin: {str(e)}"}), 500

@bp.put("/<username>")
@require_auth(roles=['super-admin'])
def edit_admin(username):
    """Update an existing admin (super-admin only)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        new_username = data.get("username")
        location = data.get("location")
        password = data.get("password")
        regions = data.get("regions")
        
        # Validate inputs
        if name is not None and len(name) > 100:
            return jsonify({"error": "Admin name is too long (max 100 characters)"}), 400
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
        if regions is not None and not isinstance(regions, list):
            return jsonify({"error": "Regions must be an array"}), 400
        
        tenant_id = g.tenant_id
        updated_admin = update_manager(
            tenant_id=tenant_id, 
            username=username, 
            name=name, 
            new_username=new_username, 
            password=password, 
            location=location,
            is_admin=True,
            regions=regions
        )
        return jsonify(updated_admin), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check if it's a database unique constraint violation for username
        error_str = str(e)
        if ("UniqueViolation" in error_str or "duplicate key" in error_str.lower()) and ("username" in error_str.lower() or "ix_managers_username" in error_str.lower()):
            return jsonify({"error": f"Username with that name already exists"}), 409
        return jsonify({"error": f"Failed to update admin: {str(e)}"}), 500

@bp.get("/<username>")
@require_auth(roles=['super-admin'])
def get_admin(username):
    """Get a specific admin by username (super-admin only)"""
    tenant_id = g.tenant_id
    admin = get_manager_by_username(username, tenant_id=tenant_id)
    if not admin:
        return jsonify({"error": "Admin not found"}), 404
    if not admin.get("is_admin"):
        return jsonify({"error": "User is not an admin"}), 404
    # Don't return password
    admin.pop("password", None)
    return jsonify(admin)

@bp.post("/login")
def admin_login():
    """
    Admin login endpoint.
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
    
    # Check if this is an admin
    if not manager.get("is_admin"):
        return jsonify({"error": "Access denied. Admin privileges required."}), 403
    
    tenant_id = manager.get("tenant_id")
    if not tenant_id:
        return jsonify({"error": "Manager configuration error"}), 500
    
    # Check tenant status
    from ..models import Tenant
    tenant = Tenant.query.get(tenant_id)
    if tenant and tenant.status != 'active':
        return jsonify({"error": f"Account is {tenant.status}. Please contact support."}), 403
    
    # Get regions
    regions = manager.get("regions", [])
    
    # Generate JWT token
    token = generate_token({
        "role": "admin",
        "tenant_id": tenant_id,
        "name": manager.get("name", "Admin"),
        "username": username,
        "is_admin": True,
        "regions": regions
    })
    
    return jsonify({
        "role": "admin",
        "tenant_id": tenant_id,
        "name": manager.get("name", "Admin"),
        "username": username,
        "regions": regions,
        "token": token
    }), 200

