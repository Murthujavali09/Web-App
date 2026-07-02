# backend/routes/auto_clockout.py
"""
Auto clock-out endpoint to clock out employees who forgot to clock out
15 minutes after store closing time.
"""
from flask import Blueprint, jsonify, g
from datetime import datetime, timedelta
from backend.database import db
from backend.models import Store, TimeClock
from backend.auth import require_auth

bp = Blueprint("auto_clockout", __name__)


@bp.post("/auto-clockout")
@require_auth(roles=['manager', 'admin', 'super-admin'])
def auto_clockout():
    """
    Auto clock out employees who forgot to clock out 15 minutes after closing time.
    This endpoint should be called periodically (e.g., via cron job or scheduled task).
    """
    try:
        tenant_id = g.tenant_id
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get all stores for this tenant
        stores = Store.query.filter_by(tenant_id=tenant_id).all()
        
        auto_clocked_out = []
        
        for store in stores:
            if not store.closing_time:
                continue
            
            try:
                # Parse closing time (format: "HH:MM")
                closing_hour, closing_minute = map(int, store.closing_time.split(':'))
                closing_time_today = now.replace(hour=closing_hour, minute=closing_minute, second=0, microsecond=0)
                auto_clockout_time = closing_time_today + timedelta(minutes=15)
                
                # Only auto clock out if current time is past the auto clock-out time
                # and it's still today (not past midnight)
                if now >= auto_clockout_time and now.date() == closing_time_today.date():
                    # Find all employees clocked in today at this store who haven't clocked out
                    active_entries = TimeClock.query.filter(
                        TimeClock.tenant_id == tenant_id,
                        TimeClock.store_id == store.name,
                        TimeClock.clock_in >= today_start,
                        TimeClock.clock_out == None
                    ).all()
                    
                    for entry in active_entries:
                        # Auto clock out
                        clock_in_time = entry.clock_in
                        hours_worked = (auto_clockout_time - clock_in_time).total_seconds() / 3600
                        
                        entry.clock_out = auto_clockout_time
                        entry.hours_worked = round(hours_worked, 2)
                        
                        auto_clocked_out.append({
                            "employee_id": str(entry.employee_id),
                            "employee_name": entry.employee_name,
                            "store_id": store.name,
                            "clock_in_time": clock_in_time.isoformat(),
                            "clock_out_time": auto_clockout_time.isoformat(),
                            "hours_worked": round(hours_worked, 2)
                        })
            except (ValueError, AttributeError) as e:
                # Skip stores with invalid closing time format
                continue
        
        if auto_clocked_out:
            db.session.commit()
            return jsonify({
                "success": True,
                "auto_clocked_out_count": len(auto_clocked_out),
                "auto_clocked_out": auto_clocked_out
            }), 200
        else:
            return jsonify({
                "success": True,
                "auto_clocked_out_count": 0,
                "message": "No employees needed auto clock-out"
            }), 200
            
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
