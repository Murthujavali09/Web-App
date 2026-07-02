# backend/routes/alerts.py
from flask import Blueprint, request, jsonify, g
from backend.database import db
from backend.models import get_alerts, mark_alert_read, create_alert
from backend.auth import require_auth

bp = Blueprint("alerts", __name__)


@bp.get("/")
@require_auth(roles=['manager'])
def list_alerts():
    """Get alerts for the current manager"""
    try:
        tenant_id = g.tenant_id
        user = g.current_user
        manager_username = user.get('username')
        
        if not manager_username:
            return jsonify({"error": "Manager authentication required"}), 401
        
        # Get query parameters
        store_id = request.args.get("store_id")
        is_read = request.args.get("is_read")
        limit = int(request.args.get("limit", 100))
        
        # Convert is_read string to boolean if provided
        is_read_bool = None
        if is_read is not None:
            is_read_bool = is_read.lower() in ('true', '1', 'yes')
        
        alerts = get_alerts(
            tenant_id=tenant_id,
            manager_username=manager_username,
            store_id=store_id,
            is_read=is_read_bool,
            limit=limit
        )
        
        return jsonify({
            "alerts": alerts,
            "total_count": len(alerts)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/<alert_id>/read")
@require_auth(roles=['manager'])
def mark_read(alert_id):
    """Mark an alert as read"""
    try:
        tenant_id = g.tenant_id
        success = mark_alert_read(alert_id, tenant_id)
        
        if success:
            return jsonify({"success": True, "message": "Alert marked as read"}), 200
        else:
            return jsonify({"error": "Alert not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/unread-count")
@require_auth(roles=['manager'])
def get_unread_count():
    """Get count of unread alerts for the current manager"""
    try:
        tenant_id = g.tenant_id
        user = g.current_user
        manager_username = user.get('username')
        
        if not manager_username:
            return jsonify({"error": "Manager authentication required"}), 401
        
        alerts = get_alerts(
            tenant_id=tenant_id,
            manager_username=manager_username,
            is_read=False,
            limit=1000  # Get all unread to count
        )
        
        return jsonify({
            "unread_count": len(alerts)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
