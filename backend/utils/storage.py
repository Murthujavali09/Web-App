# backend/utils/storage.py
"""
Storage tracking and file upload utilities for multi-tenant system.
"""
import os
import base64
from pathlib import Path
from flask import g
from backend.models import Tenant, update_tenant_storage
from backend.database import db


def get_tenant_upload_path(tenant_id, subdirectory="files"):
    """
    Get tenant-specific upload directory path.
    
    Args:
        tenant_id: Tenant ID
        subdirectory: Subdirectory name (e.g., "faces", "inventory", "files")
    
    Returns:
        Path object for tenant's upload directory
    """
    from backend.config import Config
    
    base_uploads = Config.BASE_DIR / "uploads"
    tenant_dir = base_uploads / f"tenant_{tenant_id}" / subdirectory
    
    # Create directory if it doesn't exist
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    return tenant_dir


def calculate_base64_size(base64_string):
    """
    Calculate the size in bytes of a base64 encoded string.
    
    Args:
        base64_string: Base64 encoded string (may include data URI prefix)
    
    Returns:
        Size in bytes
    """
    try:
        # Remove data URI prefix if present
        if ',' in base64_string:
            base64_string = base64_string.split(',', 1)[1]
        
        # Decode base64 and get size
        decoded = base64.b64decode(base64_string)
        return len(decoded)
    except Exception as e:
        print(f"Error calculating base64 size: {e}")
        return 0


def check_storage_limit(tenant_id, additional_bytes):
    """
    Check if tenant has enough storage space.
    
    Args:
        tenant_id: Tenant ID
        additional_bytes: Bytes to add
    
    Returns:
        (has_space, error_message)
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return False, "Tenant not found"
    
    if not tenant.check_storage_limit(additional_bytes):
        used_gb = tenant.used_storage_bytes / (1024 ** 3)
        max_gb = tenant.max_storage_bytes / (1024 ** 3)
        return False, f"Storage limit exceeded. Used {used_gb:.2f}GB / {max_gb:.2f}GB. Please upgrade your plan."
    
    return True, None


def update_storage_usage(tenant_id, additional_bytes):
    """
    Update tenant storage usage.
    
    Args:
        tenant_id: Tenant ID
        additional_bytes: Bytes to add (can be negative for deletion)
    
    Returns:
        Updated tenant dict or None if failed
    """
    try:
        # Check storage limit before adding
        if additional_bytes > 0:
            has_space, error_msg = check_storage_limit(tenant_id, additional_bytes)
            if not has_space:
                raise ValueError(error_msg)
        
        return update_tenant_storage(tenant_id, additional_bytes)
    except Exception as e:
        print(f"Error updating storage: {e}")
        raise


def save_file_to_tenant_directory(tenant_id, file_data, filename, subdirectory="files"):
    """
    Save a file to tenant-specific directory and track storage.
    
    Args:
        tenant_id: Tenant ID
        file_data: File data (bytes or base64 string)
        filename: Filename to save
        subdirectory: Subdirectory name (e.g., "faces", "inventory")
    
    Returns:
        Relative path to saved file
    """
    # Get tenant upload path
    upload_dir = get_tenant_upload_path(tenant_id, subdirectory)
    file_path = upload_dir / filename
    
    # Determine if file_data is base64 or bytes
    if isinstance(file_data, str):
        # Base64 encoded
        if ',' in file_data:
            # Remove data URI prefix
            file_data = file_data.split(',', 1)[1]
        file_bytes = base64.b64decode(file_data)
        file_size = len(file_bytes)
    else:
        # Already bytes
        file_bytes = file_data
        file_size = len(file_bytes)
    
    # Check storage limit
    has_space, error_msg = check_storage_limit(tenant_id, file_size)
    if not has_space:
        raise ValueError(error_msg)
    
    # Save file
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    # Update storage usage
    update_storage_usage(tenant_id, file_size)
    
    # Return relative path from project root
    return f"uploads/tenant_{tenant_id}/{subdirectory}/{filename}"


def delete_file_from_tenant_directory(tenant_id, file_path):
    """
    Delete a file from tenant directory and update storage.
    
    Args:
        tenant_id: Tenant ID
        file_path: Relative or absolute path to file
    """
    from backend.config import Config
    
    # Convert to absolute path if relative
    if not Path(file_path).is_absolute():
        file_path = Config.BASE_DIR / file_path
    
    file_path = Path(file_path)
    
    # Check if file exists and belongs to tenant
    if not file_path.exists():
        return
    
    # Verify it's in tenant directory
    expected_prefix = str(Config.BASE_DIR / "uploads" / f"tenant_{tenant_id}")
    if not str(file_path).startswith(expected_prefix):
        raise ValueError("File does not belong to this tenant")
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Delete file
    file_path.unlink()
    
    # Update storage (subtract)
    update_storage_usage(tenant_id, -file_size)


def get_storage_usage_info(tenant_id):
    """
    Get storage usage information for a tenant.
    
    Args:
        tenant_id: Tenant ID
    
    Returns:
        Dict with storage info
    """
    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        return None
    
    used_gb = tenant.used_storage_bytes / (1024 ** 3)
    max_gb = tenant.max_storage_bytes / (1024 ** 3)
    used_percent = tenant.get_storage_usage_percent()
    
    return {
        "tenant_id": tenant_id,
        "plan": tenant.plan,
        "used_bytes": tenant.used_storage_bytes,
        "max_bytes": tenant.max_storage_bytes,
        "used_gb": round(used_gb, 2),
        "max_gb": round(max_gb, 2),
        "used_percent": round(used_percent, 2),
        "available_gb": round(max_gb - used_gb, 2)
    }


def calculate_database_storage(tenant_id):
    """
    Calculate storage used by base64 images in database for a tenant.
    This can be used to initialize storage tracking or recalculate.
    
    Args:
        tenant_id: Tenant ID
    
    Returns:
        Total bytes used in database
    """
    from backend.models import Employee, TimeClock
    
    total_bytes = 0
    
    # Count employee face images
    employees = Employee.query.filter_by(tenant_id=tenant_id).all()
    for emp in employees:
        if emp.face_image:
            total_bytes += calculate_base64_size(emp.face_image)
    
    # Count timeclock face images
    entries = TimeClock.query.filter_by(tenant_id=tenant_id).all()
    for entry in entries:
        if entry.clock_in_face_image:
            total_bytes += calculate_base64_size(entry.clock_in_face_image)
        if entry.clock_out_face_image:
            total_bytes += calculate_base64_size(entry.clock_out_face_image)
    
    return total_bytes


def initialize_tenant_storage(tenant_id):
    """
    Initialize tenant storage by calculating existing database storage.
    
    Args:
        tenant_id: Tenant ID
    """
    current_storage = calculate_database_storage(tenant_id)
    tenant = Tenant.query.get(tenant_id)
    if tenant:
        tenant.used_storage_bytes = current_storage
        db.session.commit()
        return current_storage
    return 0

