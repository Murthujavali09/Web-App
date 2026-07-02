# backend/routes/employees.py
from flask import Blueprint, request, jsonify, g
from ..models import get_employees, create_employee, delete_employee, update_employee
from ..auth import require_auth

bp = Blueprint("employees", __name__)

@bp.get("/")
@require_auth()
def list_employees():
    tenant_id = g.tenant_id
    store_id = request.args.get("store_id")
    employees = get_employees(tenant_id=tenant_id, store_id=store_id)
    return jsonify(employees)


@bp.get("/active-count")
@require_auth()
def get_active_count():
    """Get count of employees currently clocked in (active)"""
    from datetime import datetime
    from ..models import TimeClock
    
    tenant_id = g.tenant_id
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get all employees clocked in today who haven't clocked out
    active_entries = TimeClock.query.filter(
        TimeClock.tenant_id == tenant_id,
        TimeClock.clock_in >= today_start,
        TimeClock.clock_out == None
    ).all()
    
    # Get unique employee IDs
    active_employee_ids = set(entry.employee_id for entry in active_entries)
    
    return jsonify({
        "active_count": len(active_employee_ids),
        "active_employee_ids": list(active_employee_ids)
    }), 200

@bp.post("/")
@require_auth()
def add_employee():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        name = data.get("name")
        if not name or not name.strip():
            return jsonify({"error": "Employee name is required"}), 400
        
        tenant_id = g.tenant_id
        phone_number = data.get("phone_number")
        
        # Check for duplicate phone number if provided
        if phone_number and phone_number.strip():
            from ..models import Employee
            existing_employee = Employee.query.filter_by(
                tenant_id=tenant_id,
                phone_number=phone_number.strip()
            ).first()
            if existing_employee:
                return jsonify({"error": f"An employee with phone number {phone_number.strip()} already exists."}), 400
        
        emp_id = create_employee(
            tenant_id=tenant_id,
            store_id=data.get("store_id"),
            name=name.strip(),
            role=data.get("role"),
            phone_number=phone_number,
            hourly_pay=data.get("hourly_pay")
        )
        return jsonify({"id": emp_id}), 201
    except ValueError as e:
        # Handle duplicate phone number error from create_employee
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to create employee: {str(e)}"}), 500

@bp.put("/<employee_id>")
@require_auth()
def edit_employee(employee_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        tenant_id = g.tenant_id
        
        # Verify employee belongs to this tenant
        from ..models import Employee
        employee = Employee.query.get(int(employee_id)) if employee_id.isdigit() else None
        if not employee or employee.tenant_id != tenant_id:
            return jsonify({"error": "Employee not found"}), 404
        
        phone_number = data.get("phone_number")
        hourly_pay = data.get("hourly_pay")
        
        # Check for duplicate phone number if phone_number is being updated and is different
        if phone_number and phone_number.strip():
            from ..models import Employee
            existing_employee = Employee.query.filter_by(
                tenant_id=tenant_id,
                phone_number=phone_number.strip()
            ).first()
            if existing_employee and str(existing_employee.id) != str(employee_id):
                return jsonify({"error": f"An employee with phone number {phone_number.strip()} already exists."}), 400
        
        # Validate hourly_pay if provided
        if hourly_pay is not None:
            try:
                hourly_pay = float(hourly_pay) if hourly_pay else None
                if hourly_pay is not None and hourly_pay < 0:
                    return jsonify({"error": "Hourly pay cannot be negative"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid hourly pay value"}), 400
        
        success = update_employee(
            employee_id=employee_id,
            tenant_id=tenant_id,
            phone_number=phone_number,
            hourly_pay=hourly_pay
        )
        
        if success:
            # Return updated employee data
            employee = Employee.query.get(int(employee_id))
            return jsonify({"success": True, "employee": employee.to_dict()}), 200
        else:
            return jsonify({"error": "Failed to update employee"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to update employee: {str(e)}"}), 500

@bp.delete("/<employee_id>")
@require_auth()
def remove_employee(employee_id):
    tenant_id = g.tenant_id
    # Verify employee belongs to this tenant before deletion
    from ..models import Employee
    employee = Employee.query.get(int(employee_id)) if employee_id.isdigit() else None
    if not employee or employee.tenant_id != tenant_id:
        return jsonify({"success": False, "error": "Employee not found"}), 404
    
    success = delete_employee(employee_id)
    if success:
        return jsonify({"success": True, "message": "Employee deleted successfully"}), 200
    else:
        return jsonify({"success": False, "error": "Employee not found"}), 404
