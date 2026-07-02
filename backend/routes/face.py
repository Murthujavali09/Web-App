# backend/routes/face.py
from flask import Blueprint, request, jsonify, g
from datetime import datetime
from backend.database import db
from backend.models import Employee
from backend.auth import require_auth
from backend.services.face_service import (
    find_best_match, 
    validate_face_descriptor,
    compress_image,
    euclidean_distance
)

bp = Blueprint("face", __name__)


@bp.post("/add-appearance")
@require_auth()
def add_face_appearance():
    """
    Add a new face appearance to an existing employee (used when recognition fails).
    Allows employees to add new face variations without full re-registration.
    
    Request JSON:
    {
        "employee_name": "John Doe",  // or "employee_id": "123"
        "face_descriptor": [0.123, -0.456, ...],
        "face_image": "data:image/jpeg;base64,..."  // optional
    }
    """
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        employee_name = data.get("employee_name")
        employee_id = data.get("employee_id")
        face_descriptor = data.get("face_descriptor")
        face_image = data.get("face_image")
        
        # Get employee by name or ID (filter by tenant_id)
        if employee_name:
            # Search by name (case-insensitive) for this tenant
            employee = Employee.query.filter(
                Employee.tenant_id == tenant_id,
                Employee.name.ilike(employee_name.strip())
            ).first()
            if not employee:
                return jsonify({"error": f"Employee '{employee_name}' not found. Please check the spelling."}), 404
        elif employee_id:
            # Search by ID (filter by tenant_id)
            try:
                employee = Employee.query.filter_by(id=int(employee_id), tenant_id=tenant_id).first()
            except:
                return jsonify({"error": "Invalid employee_id format"}), 400
        else:
            return jsonify({"error": "Either employee_name or employee_id is required"}), 400
        
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        if not face_descriptor:
            return jsonify({"error": "face_descriptor is required"}), 400
        
        # Validate face descriptor format
        if not validate_face_descriptor(face_descriptor):
            return jsonify({"error": "Invalid face descriptor format. Must be 128-dimensional array"}), 400
        
        if not employee.face_registered:
            return jsonify({"error": "Employee does not have an initial face registration. Please register face first."}), 400
        
        # Compress face image if provided
        compressed_image = None
        if face_image:
            compressed_image = compress_image(face_image, max_size=400)
        
        # Get existing descriptors
        existing_descriptors = employee.get_face_descriptors()
        if not existing_descriptors and employee.get_face_descriptor():
            existing_descriptors = [employee.get_face_descriptor()]
        
        # Check if this new descriptor is too similar to existing ones (prevent duplicates)
        min_distance_to_existing = float('inf')
        for existing_desc in existing_descriptors:
            distance = euclidean_distance(face_descriptor, existing_desc)
            if distance < min_distance_to_existing:
                min_distance_to_existing = distance
        
        # Only add if it's different enough (distance > 0.3 means it's a different appearance)
        if min_distance_to_existing < 0.3:
            return jsonify({
                "success": True,
                "message": "Face already registered (very similar to existing registration)",
                "employee_id": str(employee.id),
                "employee_name": employee.name,
                "total_registrations": len(existing_descriptors)
            }), 200
        
        # Add new descriptor to the list
        existing_descriptors.append(face_descriptor)
        
        # Limit to last 5 registrations
        if len(existing_descriptors) > 5:
            existing_descriptors = existing_descriptors[-5:]
        
        # Update employee with face descriptors array
        employee.set_face_descriptors(existing_descriptors)
        employee.face_registered = True
        
        # Update face_image if provided
        if compressed_image:
            # Track storage usage
            from backend.utils.storage import calculate_base64_size, check_storage_limit, update_storage_usage
            
            old_image_size = calculate_base64_size(employee.face_image) if employee.face_image else 0
            new_image_size = calculate_base64_size(compressed_image)
            size_change = new_image_size - old_image_size
            
            # Check storage limit
            if size_change > 0:
                has_space, error_msg = check_storage_limit(tenant_id, size_change)
                if not has_space:
                    return jsonify({"error": error_msg}), 400
            
            # Store as text field
            employee.face_image = compressed_image
            
            # Update storage usage
            if size_change != 0:
                update_storage_usage(tenant_id, size_change)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "New face appearance added successfully",
            "employee_id": str(employee.id),
            "employee_name": employee.name,
            "total_registrations": len(existing_descriptors)
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.post("/register")
@require_auth()
def register_face():
    """
    Register a face descriptor for an employee.
    
    Request JSON:
    {
        "employee_id": "123",
        "face_descriptor": [0.123, -0.456, ...],  // 128-dimensional array
        "face_image": "data:image/jpeg;base64,..."  // optional
    }
    """
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        employee_id = data.get("employee_id")
        face_descriptor = data.get("face_descriptor")
        face_image = data.get("face_image")
        
        if not employee_id:
            return jsonify({"error": "employee_id is required"}), 400
        
        if not face_descriptor:
            return jsonify({"error": "face_descriptor is required"}), 400
        
        # Validate face descriptor format
        if not validate_face_descriptor(face_descriptor):
            return jsonify({"error": "Invalid face descriptor format. Must be 128-dimensional array"}), 400
        
        # Get employee (filter by tenant_id)
        try:
            employee = Employee.query.filter_by(id=int(employee_id), tenant_id=tenant_id).first()
        except:
            return jsonify({"error": "Invalid employee_id format"}), 400
        
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        # Check for duplicate face - search all registered employees for this tenant (only check against other employees)
        all_registered = Employee.query.filter(
            Employee.tenant_id == tenant_id,
            Employee.face_registered == True,
            Employee.id != int(employee_id)
        ).all()
        
        if all_registered:
            # Convert to dict format for find_best_match
            employee_dicts = []
            for emp in all_registered:
                emp_dict = emp.to_dict()
                emp_dict['_id'] = emp.id
                employee_dicts.append(emp_dict)
            
            # Find if this face matches any existing face from other employees
            match = find_best_match(face_descriptor, employee_dicts, threshold=0.6)
            if match:
                return jsonify({
                    "error": f"This face is already registered to {match['employee_name']}. Each employee must have a unique face.",
                    "duplicate_employee": match['employee_name'],
                    "confidence": match['confidence']
                }), 409  # 409 Conflict
        
        # Compress face image if provided
        compressed_image = None
        if face_image:
            compressed_image = compress_image(face_image, max_size=400)
        
        # Support multiple face descriptors per employee
        # Check if employee already has descriptors
        existing_descriptors = employee.get_face_descriptors()
        if not existing_descriptors and employee.get_face_descriptor():
            # Migrate old single descriptor to new format
            existing_descriptors = [employee.get_face_descriptor()]
        
        # Check if this new descriptor is too similar to existing ones (prevent duplicates)
        min_distance_to_existing = float('inf')
        for existing_desc in existing_descriptors:
            distance = euclidean_distance(face_descriptor, existing_desc)
            if distance < min_distance_to_existing:
                min_distance_to_existing = distance
        
        # Only add if it's different enough (distance > 0.3 means it's a different appearance)
        if min_distance_to_existing < 0.3:
            return jsonify({
                "success": True,
                "message": "Face already registered (very similar to existing registration)",
                "employee_id": str(employee.id),
                "employee_name": employee.name,
                "total_registrations": len(existing_descriptors)
            }), 200
        
        # Add new descriptor to the list
        existing_descriptors.append(face_descriptor)
        
        # Update employee with face descriptors array
        employee.set_face_descriptors(existing_descriptors)
        employee.face_registered = True
        
        # Update face_image (use latest image, or keep existing if not provided)
        if compressed_image:
            # Track storage usage
            from backend.utils.storage import calculate_base64_size, check_storage_limit, update_storage_usage
            
            old_image_size = calculate_base64_size(employee.face_image) if employee.face_image else 0
            new_image_size = calculate_base64_size(compressed_image)
            size_change = new_image_size - old_image_size
            
            # Check storage limit
            if size_change > 0:
                has_space, error_msg = check_storage_limit(tenant_id, size_change)
                if not has_space:
                    return jsonify({"error": error_msg}), 400
            
            # Store as text field
            employee.face_image = compressed_image
            
            # Update storage usage
            if size_change != 0:
                update_storage_usage(tenant_id, size_change)
        
        # Clear old single descriptor format
        employee.face_descriptor = None
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": "Face registered successfully",
            "employee_id": str(employee.id),
            "employee_name": employee.name
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.post("/recognize")
@require_auth()
def recognize_face():
    """
    Recognize a face and return matching employee.
    
    Request JSON:
    {
        "face_descriptor": [0.123, -0.456, ...],  // 128-dimensional array
        "store_id": "Lawrence"
    }
    """
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        face_descriptor = data.get("face_descriptor")
        store_id = data.get("store_id")
        
        if not face_descriptor:
            return jsonify({"error": "face_descriptor is required"}), 400
        
        # Note: store_id is optional now since employees are not tied to stores
        
        # Validate face descriptor format
        if not validate_face_descriptor(face_descriptor):
            return jsonify({"error": "Invalid face descriptor format. Must be 128-dimensional array"}), 400
        
        # Get all employees with registered faces for this tenant
        registered_employees = Employee.query.filter_by(tenant_id=tenant_id, face_registered=True).all()
        
        if not registered_employees:
            return jsonify({
                "success": False,
                "error": "No employees with registered faces found"
            }), 404
        
        # Convert to dict format for find_best_match
        employee_dicts = []
        for emp in registered_employees:
            emp_dict = emp.to_dict()
            emp_dict['_id'] = emp.id
            employee_dicts.append(emp_dict)
        
        # Find best match
        match = find_best_match(face_descriptor, employee_dicts, threshold=0.6)
        
        # Minimum confidence threshold (30%) - reject low-confidence matches
        MIN_CONFIDENCE = 0.3
        
        if match and match.get("confidence", 0) >= MIN_CONFIDENCE:
            return jsonify({
                "success": True,
                "employee_id": match["employee_id"],
                "employee_name": match["employee_name"],
                "confidence": match["confidence"],
                "distance": match["distance"]
            }), 200
        else:
            # If match exists but confidence is too low, or no match at all
            error_msg = "Face not recognized. "
            if match and match.get("confidence", 0) < MIN_CONFIDENCE:
                error_msg += f"Confidence too low ({match.get('confidence', 0)*100:.1f}%). "
            error_msg += "Please contact your manager to register or update your face."
            return jsonify({
                "success": False,
                "error": error_msg
            }), 404
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.get("/employees/<employee_id>")
@require_auth()
def get_employee_face(employee_id):
    """
    Get employee face registration status.
    """
    try:
        tenant_id = g.tenant_id
        try:
            employee = Employee.query.filter_by(id=int(employee_id), tenant_id=tenant_id).first()
        except:
            return jsonify({"error": "Invalid employee_id format"}), 400
        
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        # Count face descriptors
        descriptor_count = 0
        descriptors = employee.get_face_descriptors()
        if descriptors:
            descriptor_count = len(descriptors)
        elif employee.get_face_descriptor():
            descriptor_count = 1
        
        return jsonify({
            "employee_id": employee_id,
            "employee_name": employee.name,
            "face_registered": employee.face_registered,
            "has_face_image": hasattr(employee, 'face_image') and employee.face_image is not None,
            "face_registrations_count": descriptor_count
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
