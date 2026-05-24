# backend/routes/timeclock.py
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from backend.database import db
from backend.models import Employee, TimeClock
from backend.auth import require_auth
from backend.services.face_service import (
    find_best_match,
    validate_face_descriptor,
    compress_image,
    euclidean_distance
)

bp = Blueprint("timeclock", __name__)


@bp.post("/clock-in")
@require_auth()
def clock_in_route():
    """Legacy clock-in endpoint (kept for compatibility)"""
    data = request.get_json()
    employee_id = data.get("employee_id")
    tenant_id = g.tenant_id
    
    # Verify employee belongs to this tenant
    employee = Employee.query.filter_by(id=int(employee_id), tenant_id=tenant_id).first()
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    
    entry = TimeClock(
        tenant_id=tenant_id,
        employee_id=int(employee_id),
        clock_in=datetime.utcnow(),
        clock_out=None
    )
    db.session.add(entry)
    db.session.commit()
    
    return jsonify({"entry_id": str(entry.id)}), 201


@bp.post("/clock-out")
@require_auth()
def clock_out_route():
    """Legacy clock-out endpoint (kept for compatibility)"""
    data = request.get_json()
    entry_id = data.get("entry_id")
    tenant_id = g.tenant_id
    
    try:
        entry = TimeClock.query.filter_by(id=int(entry_id), tenant_id=tenant_id).first()
        if entry:
            entry.clock_out = datetime.utcnow()
            db.session.commit()
            return jsonify({"ok": True})
        else:
            return jsonify({"error": "Invalid or already clocked out entry"}), 400
    except:
        return jsonify({"error": "Invalid entry_id format"}), 400


@bp.post("/clock-in-face")
@require_auth()
def clock_in_face():
    """
    Clock in using face recognition.
    
    Request JSON:
    {
        "face_descriptor": [0.123, -0.456, ...],
        "face_image": "data:image/jpeg;base64,...",
        "store_id": "Lawrence"
    }
    """
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        face_descriptor = data.get("face_descriptor")
        face_image = data.get("face_image")
        store_id = data.get("store_id")
        
        if not face_descriptor:
            return jsonify({"error": "face_descriptor is required"}), 400
        
        # Validate face descriptor
        if not validate_face_descriptor(face_descriptor):
            return jsonify({"error": "Invalid face descriptor format"}), 400
        
        # Get all employees with registered faces for this tenant
        registered_employees = Employee.query.filter_by(tenant_id=tenant_id, face_registered=True).all()
        
        if not registered_employees:
            return jsonify({
                "success": False,
                "error": "No employees with registered faces found. Please register your face first."
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
        
        if not match or match.get("confidence", 0) < MIN_CONFIDENCE:
            error_msg = "Face not recognized. "
            if match and match.get("confidence", 0) < MIN_CONFIDENCE:
                error_msg += f"Confidence too low ({match.get('confidence', 0)*100:.1f}%). "
            error_msg += "Please contact your manager to register or update your face."
            return jsonify({
                "success": False,
                "error": error_msg
            }), 404
        
        employee_id = int(match["employee_id"])
        employee_name = match["employee_name"]
        confidence = match["confidence"]
        # Convert numpy types to Python float for database compatibility
        confidence = float(confidence) if confidence is not None else None
        
        # Get employee object (verify tenant_id)
        employee = Employee.query.filter_by(id=employee_id, tenant_id=tenant_id).first()
        
        if not employee:
            return jsonify({"error": "Employee not found or does not belong to this tenant"}), 404
        
        if employee:
            # Get existing descriptors
            existing_descriptors = employee.get_face_descriptors()
            if not existing_descriptors and employee.get_face_descriptor():
                existing_descriptors = [employee.get_face_descriptor()]
            
            # Check if this new face is different enough from existing ones
            min_distance = float('inf')
            for existing_desc in existing_descriptors:
                distance = euclidean_distance(face_descriptor, existing_desc)
                if distance < min_distance:
                    min_distance = distance
            
            # If distance > 0.3, it's a different appearance - add it to learn
            if min_distance > 0.3 and confidence > 0.7:
                existing_descriptors.append(face_descriptor)
                # Limit to last 5 registrations
                if len(existing_descriptors) > 5:
                    existing_descriptors = existing_descriptors[-5:]
                
                employee.set_face_descriptors(existing_descriptors)
                db.session.commit()
        
        # Check if employee is already clocked in today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        existing_entry = TimeClock.query.filter(
            TimeClock.tenant_id == tenant_id,
            TimeClock.employee_id == employee_id,
            TimeClock.clock_in >= today_start,
            TimeClock.clock_out == None
        ).first()
        
        if existing_entry:
            clock_in_iso = existing_entry.clock_in.isoformat()
            if not clock_in_iso.endswith('Z') and existing_entry.clock_in.tzinfo is None:
                clock_in_iso += 'Z'
            
            return jsonify({
                "success": False,
                "error": f"{employee_name} is already clocked in today.",
                "employee_name": employee_name,
                "clock_in_time": clock_in_iso
            }), 400
        
        # Check store timings if store_id is provided
        if store_id:
            from backend.models import Store
            store = Store.query.filter_by(tenant_id=tenant_id, name=store_id).first()
            if store and store.opening_time:
                # Parse opening time (format: "HH:MM")
                try:
                    opening_hour, opening_minute = map(int, store.opening_time.split(':'))
                    now = datetime.utcnow()
                    opening_time_today = now.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
                    earliest_clock_in = opening_time_today - timedelta(minutes=30)
                    
                    # Check if current time is before 30 minutes before opening
                    if now < earliest_clock_in:
                        opening_time_str = store.opening_time
                        earliest_time_str = earliest_clock_in.strftime('%H:%M')
                        return jsonify({
                            "success": False,
                            "error": f"Cannot clock in yet. Store opens at {opening_time_str}. You can clock in starting at {earliest_time_str} (30 minutes before opening)."
                        }), 400
                except (ValueError, AttributeError):
                    # If time parsing fails, skip the check
                    pass
        
        # Compress face image
        compressed_image = compress_image(face_image, max_size=400) if face_image else None
        
        # Track storage usage for face image
        if compressed_image:
            from backend.utils.storage import calculate_base64_size, check_storage_limit, update_storage_usage
            
            image_size = calculate_base64_size(compressed_image)
            
            # Check storage limit
            has_space, error_msg = check_storage_limit(tenant_id, image_size)
            if not has_space:
                return jsonify({"error": error_msg}), 400
            
            # Update storage usage
            update_storage_usage(tenant_id, image_size)
        
        # Create clock-in entry
        clock_in_time = datetime.utcnow()
        entry = TimeClock(
            tenant_id=tenant_id,
            employee_id=employee_id,
            employee_name=employee_name,
            store_id=store_id,
            clock_in=clock_in_time,
            clock_out=None,
            clock_in_face_image=compressed_image,
            clock_in_confidence=confidence
        )
        
        db.session.add(entry)
        db.session.commit()
        
        # Check if employee clocked in late (after opening time) and create alert
        if store_id:
            from backend.models import Store, create_alert
            try:
                store = Store.query.filter_by(tenant_id=tenant_id, name=store_id).first()
                if store and store.opening_time and store.manager_username:
                    try:
                        opening_hour, opening_minute = map(int, store.opening_time.split(':'))
                        opening_time_today = clock_in_time.replace(hour=opening_hour, minute=opening_minute, second=0, microsecond=0)
                        
                        # Check if clock-in is after opening time
                        if clock_in_time > opening_time_today:
                            # Calculate how many minutes late
                            minutes_late = int((clock_in_time - opening_time_today).total_seconds() / 60)
                            
                            # Create alert for manager
                            create_alert(
                                tenant_id=tenant_id,
                                store_id=store_id,
                                manager_username=store.manager_username,
                                alert_type='late_clock_in',
                                title=f'Late Clock-In: {employee_name}',
                                message=f'{employee_name} clocked in {minutes_late} minute{"s" if minutes_late != 1 else ""} late at {clock_in_time.strftime("%H:%M")}. Store opening time is {store.opening_time}.',
                                employee_id=employee_id,
                                employee_name=employee_name
                            )
                    except (ValueError, AttributeError) as e:
                        # If time parsing fails, skip alert creation
                        print(f"Warning: Could not create late clock-in alert: {e}")
            except Exception as e:
                # Don't fail clock-in if alert creation fails
                print(f"Warning: Error creating alert: {e}")
        
        clock_in_iso = entry.clock_in.isoformat()
        if not clock_in_iso.endswith('Z') and entry.clock_in.tzinfo is None:
            clock_in_iso += 'Z'
        
        return jsonify({
            "success": True,
            "entry_id": str(entry.id),
            "employee_id": str(employee_id),
            "employee_name": employee_name,
            "clock_in_time": clock_in_iso,
            "confidence": confidence
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/clock-out-face")
@require_auth()
def clock_out_face():
    """
    Clock out using face recognition.
    
    Request JSON:
    {
        "face_descriptor": [0.123, -0.456, ...],
        "face_image": "data:image/jpeg;base64,...",
        "store_id": "Lawrence"
    }
    """
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        face_descriptor = data.get("face_descriptor")
        face_image = data.get("face_image")
        store_id = data.get("store_id")
        
        if not face_descriptor:
            return jsonify({"error": "face_descriptor is required"}), 400
        
        # Validate face descriptor
        if not validate_face_descriptor(face_descriptor):
            return jsonify({"error": "Invalid face descriptor format"}), 400
        
        # Get all employees with registered faces for this tenant
        registered_employees = Employee.query.filter_by(tenant_id=tenant_id, face_registered=True).all()
        
        if not registered_employees:
            return jsonify({
                "success": False,
                "error": "No employees with registered faces found."
            }), 404
        
        # Convert to dict format for find_best_match
        employee_dicts = []
        for emp in registered_employees:
            emp_dict = emp.to_dict()
            emp_dict['_id'] = emp.id
            employee_dicts.append(emp_dict)
        
        # Find best match
        match = find_best_match(face_descriptor, employee_dicts, threshold=0.6)
        
        if not match:
            return jsonify({
                "success": False,
                "error": "Face not recognized. Please try again or contact your manager."
            }), 404
        
        employee_id = int(match["employee_id"])
        employee_name = match["employee_name"]
        confidence = match["confidence"]
        # Convert numpy types to Python float for database compatibility
        confidence = float(confidence) if confidence is not None else None
        
        # Get employee object (verify tenant_id)
        employee = Employee.query.filter_by(id=employee_id, tenant_id=tenant_id).first()
        
        if not employee:
            return jsonify({"error": "Employee not found or does not belong to this tenant"}), 404
        
        if employee:
            # Get existing descriptors
            existing_descriptors = employee.get_face_descriptors()
            if not existing_descriptors and employee.get_face_descriptor():
                existing_descriptors = [employee.get_face_descriptor()]
            
            # Check if this new face is different enough from existing ones
            min_distance = float('inf')
            for existing_desc in existing_descriptors:
                distance = euclidean_distance(face_descriptor, existing_desc)
                if distance < min_distance:
                    min_distance = distance
            
            # If distance > 0.3, it's a different appearance - add it to learn
            if min_distance > 0.3 and confidence > 0.7:
                existing_descriptors.append(face_descriptor)
                # Limit to last 5 registrations
                if len(existing_descriptors) > 5:
                    existing_descriptors = existing_descriptors[-5:]
                
                employee.set_face_descriptors(existing_descriptors)
                db.session.commit()
        
        # Find active clock-in entry for today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        active_entry = TimeClock.query.filter(
            TimeClock.tenant_id == tenant_id,
            TimeClock.employee_id == employee_id,
            TimeClock.clock_in >= today_start,
            TimeClock.clock_out == None
        ).first()
        
        if not active_entry:
            return jsonify({
                "success": False,
                "error": f"{employee_name} is not clocked in today. Please clock in first.",
                "employee_name": employee_name
            }), 400
        
        # Check if employee should have been auto clocked out (15 minutes after closing)
        if store_id:
            from backend.models import Store
            store = Store.query.filter_by(tenant_id=tenant_id, name=store_id).first()
            if store and store.closing_time:
                try:
                    closing_hour, closing_minute = map(int, store.closing_time.split(':'))
                    now = datetime.utcnow()
                    closing_time_today = now.replace(hour=closing_hour, minute=closing_minute, second=0, microsecond=0)
                    auto_clockout_time = closing_time_today + timedelta(minutes=15)
                    
                    # If it's past auto clock-out time, auto clock out
                    if now >= auto_clockout_time:
                        clock_out_time = auto_clockout_time  # Use the auto clock-out time, not current time
                        clock_in_time = active_entry.clock_in
                        hours_worked = (clock_out_time - clock_in_time).total_seconds() / 3600
                        
                        active_entry.clock_out = clock_out_time
                        active_entry.hours_worked = round(hours_worked, 2)
                        db.session.commit()
                        
                        clock_in_iso = clock_in_time.isoformat()
                        if not clock_in_iso.endswith('Z') and clock_in_time.tzinfo is None:
                            clock_in_iso += 'Z'
                        
                        clock_out_iso = clock_out_time.isoformat()
                        if not clock_out_iso.endswith('Z') and clock_out_time.tzinfo is None:
                            clock_out_iso += 'Z'
                        
                        return jsonify({
                            "success": True,
                            "auto_clockout": True,
                            "entry_id": str(active_entry.id),
                            "employee_id": str(employee_id),
                            "employee_name": employee_name,
                            "clock_in_time": clock_in_iso,
                            "clock_out_time": clock_out_iso,
                            "hours_worked": round(hours_worked, 2),
                            "message": f"Auto clocked out at {auto_clockout_time.strftime('%H:%M')} (15 minutes after closing time {store.closing_time})"
                        }), 200
                except (ValueError, AttributeError):
                    # If time parsing fails, skip the check
                    pass
        
        # Compress face image
        compressed_image = compress_image(face_image, max_size=400) if face_image else None
        
        # Track storage usage for face image
        if compressed_image:
            from backend.utils.storage import calculate_base64_size, check_storage_limit, update_storage_usage
            
            old_image_size = calculate_base64_size(active_entry.clock_out_face_image) if active_entry.clock_out_face_image else 0
            new_image_size = calculate_base64_size(compressed_image)
            size_change = new_image_size - old_image_size
            
            # Check storage limit
            if size_change > 0:
                has_space, error_msg = check_storage_limit(tenant_id, size_change)
                if not has_space:
                    return jsonify({"error": error_msg}), 400
            
            # Update storage usage
            if size_change != 0:
                update_storage_usage(tenant_id, size_change)
        
        # Update entry with clock-out time
        clock_out_time = datetime.utcnow()
        clock_in_time = active_entry.clock_in
        hours_worked = (clock_out_time - clock_in_time).total_seconds() / 3600
        
        active_entry.clock_out = clock_out_time
        active_entry.clock_out_face_image = compressed_image
        active_entry.clock_out_confidence = confidence
        active_entry.hours_worked = round(hours_worked, 2)
        
        db.session.commit()
        
        clock_in_iso = clock_in_time.isoformat()
        if not clock_in_iso.endswith('Z') and clock_in_time.tzinfo is None:
            clock_in_iso += 'Z'
        
        clock_out_iso = clock_out_time.isoformat()
        if not clock_out_iso.endswith('Z') and clock_out_time.tzinfo is None:
            clock_out_iso += 'Z'
        
        return jsonify({
            "success": True,
            "entry_id": str(active_entry.id),
            "employee_id": str(employee_id),
            "employee_name": employee_name,
            "clock_in_time": clock_in_iso,
            "clock_out_time": clock_out_iso,
            "hours_worked": round(hours_worked, 2),
            "confidence": confidence
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/today")
@require_auth()
def get_today_entries():
    """
    Get all timeclock entries for today for a specific store.
    
    Query params:
    - store_id: Store identifier
    """
    try:
        tenant_id = g.tenant_id
        store_id = request.args.get("store_id")
        
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        
        entries = TimeClock.query.filter(
            TimeClock.tenant_id == tenant_id,
            TimeClock.store_id == store_id,
            TimeClock.clock_in >= today_start,
            TimeClock.clock_in < tomorrow_start
        ).order_by(TimeClock.clock_in.desc()).all()
        
        # Format entries for response
        formatted_entries = [entry.to_dict() for entry in entries]
        
        return jsonify({
            "date": today_start.date().isoformat(),
            "store_id": store_id,
            "employees": formatted_entries,
            "total_count": len(formatted_entries)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/history")
@require_auth()
def get_history():
    """
    Get timeclock history for a store.
    
    Query params:
    - store_id: Store identifier
    - days: Number of days to look back (default 30)
    """
    try:
        tenant_id = g.tenant_id
        store_id = request.args.get("store_id")
        days = int(request.args.get("days", 30))
        
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        entries = TimeClock.query.filter(
            TimeClock.tenant_id == tenant_id,
            TimeClock.store_id == store_id,
            TimeClock.clock_in >= start_date
        ).order_by(TimeClock.clock_in.desc()).all()
        
        # Format entries for response
        formatted_entries = [entry.to_dict() for entry in entries]
        
        return jsonify({
            "store_id": store_id,
            "entries": formatted_entries,
            "total_count": len(formatted_entries),
            "days": days
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/employee/<employee_id>/history")
@require_auth()
def get_employee_history(employee_id):
    """
    Get timeclock history for a specific employee.
    
    Path params:
    - employee_id: Employee identifier
    
    Query params:
    - days: Number of days to look back (default 90)
    """
    try:
        tenant_id = g.tenant_id
        days = int(request.args.get("days", 90))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Verify employee belongs to this tenant
        employee = Employee.query.filter_by(id=int(employee_id), tenant_id=tenant_id).first()
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        # Find all entries for this employee
        entries = TimeClock.query.filter(
            TimeClock.tenant_id == tenant_id,
            TimeClock.employee_id == int(employee_id),
            TimeClock.clock_in >= start_date
        ).order_by(TimeClock.clock_in.desc()).all()
        
        # Format entries for response
        formatted_entries = [entry.to_dict() for entry in entries]
        
        return jsonify({
            "employee_id": employee_id,
            "entries": formatted_entries,
            "total_count": len(formatted_entries),
            "days": days
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
