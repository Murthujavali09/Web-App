# backend/auth.py
"""
Authentication and authorization utilities for server-side security.
"""
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime, timedelta
import jwt
import hashlib
import secrets
from .config import Config

# JWT secret key (use SECRET_KEY from config)
def get_jwt_secret():
    """Get JWT secret key from config"""
    return Config.SECRET_KEY

def generate_token(user_data, expires_in_hours=24):
    """
    Generate a JWT token for authenticated user.
    
    Args:
        user_data: Dict with user info (role, username, etc.)
        expires_in_hours: Token expiration time in hours
    
    Returns:
        JWT token string
    """
    payload = {
        **user_data,
        'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm='HS256')

def verify_token(token):
    """
    Verify and decode a JWT token.
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_auth_token():
    """
    Extract JWT token from request headers.
    Checks both 'Authorization: Bearer <token>' and 'X-Auth-Token' header.
    """
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Check custom header (for backward compatibility)
    return request.headers.get('X-Auth-Token', '')

def require_auth(roles=None):
    """
    Decorator to require authentication with tenant isolation.
    
    Args:
        roles: List of allowed roles (e.g., ['manager', 'super-admin', 'store'])
               If None, any authenticated user is allowed.
    
    Usage:
        @require_auth(roles=['manager'])
        def my_endpoint():
            # user info available in g.current_user
            # tenant_id available in g.tenant_id
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = get_auth_token()
            
            if not token:
                return jsonify({"error": "Authentication required. Please login."}), 401
            
            user_data = verify_token(token)
            if not user_data:
                return jsonify({"error": "Invalid or expired token. Please login again."}), 401
            
            # Check role if specified
            if roles and user_data.get('role') not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            
            # Extract tenant_id from token
            tenant_id = user_data.get('tenant_id')
            if not tenant_id:
                return jsonify({"error": "Invalid token: missing tenant_id"}), 401
            
            # Store user data and tenant_id in Flask's g object for use in route
            g.current_user = user_data
            g.tenant_id = tenant_id
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_password_strength(password):
    """
    Validate password strength.
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    
    Returns:
        (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    errors = []
    if not has_upper:
        errors.append("one uppercase letter")
    if not has_lower:
        errors.append("one lowercase letter")
    if not has_digit:
        errors.append("one number")
    if not has_special:
        errors.append("one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)")
    
    if errors:
        return False, f"Password must contain at least {', '.join(errors)}"
    
    return True, None

