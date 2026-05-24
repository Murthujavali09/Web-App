# backend/routes/eod.py
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta
from ..models import get_eods, create_eod, get_stores, EOD
from ..database import db
from ..auth import require_auth

bp = Blueprint("eod", __name__)

@bp.get("/")
@require_auth()
def list_eod():
    tenant_id = g.tenant_id
    store_id = request.args.get("store_id")
    reports = get_eods(tenant_id=tenant_id, store_id=store_id)
    return jsonify(reports)

@bp.post("/")
@require_auth()
def add_eod():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        store_id = data.get("store_id")
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
        
        report_date = data.get("report_date")
        if not report_date:
            return jsonify({"error": "report_date is required"}), 400
        
        # Extract values with explicit defaults and validation
        def safe_float(value, default=0):
            try:
                return float(value or default)
            except (ValueError, TypeError):
                return 0
        
        def safe_int(value, default=0):
            try:
                return int(value or default)
            except (ValueError, TypeError):
                return default
        
        try:
            cash_amount = safe_float(data.get("cash_amount", 0))
            credit_amount = safe_float(data.get("credit_amount", 0))
            card1_amount = safe_float(data.get("card1_amount", 0))
            qpay_amount = safe_float(data.get("qpay_amount", 0))
            boxes_count = safe_int(data.get("boxes_count", 0))
            accessories_amount = safe_float(data.get("accessories_amount", 0))
            magenta_amount = safe_float(data.get("magenta_amount", 0))
            inventory_sold = safe_int(data.get("inventory_sold", 0))
            over_short = safe_float(data.get("over_short", 0))  # Can be negative
            total1 = safe_float(data.get("total1", 0))
            
            # Denominations
            denom_100_count = safe_int(data.get("denom_100_count", 0))
            denom_100_total = safe_float(data.get("denom_100_total", 0))
            denom_50_count = safe_int(data.get("denom_50_count", 0))
            denom_50_total = safe_float(data.get("denom_50_total", 0))
            denom_20_count = safe_int(data.get("denom_20_count", 0))
            denom_20_total = safe_float(data.get("denom_20_total", 0))
            denom_10_count = safe_int(data.get("denom_10_count", 0))
            denom_10_total = safe_float(data.get("denom_10_total", 0))
            denom_5_count = safe_int(data.get("denom_5_count", 0))
            denom_5_total = safe_float(data.get("denom_5_total", 0))
            denom_1_count = safe_int(data.get("denom_1_count", 0))
            denom_1_total = safe_float(data.get("denom_1_total", 0))
            total_bills = safe_float(data.get("total_bills", 0))
            
            # Validate non-negative values (except over_short which can be negative)
            if cash_amount < 0 or credit_amount < 0 or card1_amount < 0 or qpay_amount < 0 or boxes_count < 0 or accessories_amount < 0 or magenta_amount < 0 or inventory_sold < 0 or total1 < 0:
                return jsonify({"error": "All amounts and counts must be non-negative (except Over/Short)"}), 400
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid numeric value: {str(e)}"}), 400
        
        # Debug logging
        print(f"EOD Submission received: cash={cash_amount}, credit={credit_amount}, card1={card1_amount}, "
              f"qpay={qpay_amount}, boxes={boxes_count}, accessories={accessories_amount}, "
              f"magenta={magenta_amount}, inventory_sold={inventory_sold}, over_short={over_short}, total1={total1}")
        
        tenant_id = g.tenant_id
        eod_id = create_eod(
            tenant_id=tenant_id,
            store_id=store_id,
            report_date=report_date,
            notes=data.get("notes"),
            cash_amount=cash_amount,
            credit_amount=credit_amount,
            card1_amount=card1_amount,
            qpay_amount=qpay_amount,
            boxes_count=boxes_count,
            accessories_amount=accessories_amount,
            magenta_amount=magenta_amount,
            inventory_sold=inventory_sold,
            over_short=over_short,
            total1=total1,
            denom_100_count=denom_100_count,
            denom_100_total=denom_100_total,
            denom_50_count=denom_50_count,
            denom_50_total=denom_50_total,
            denom_20_count=denom_20_count,
            denom_20_total=denom_20_total,
            denom_10_count=denom_10_count,
            denom_10_total=denom_10_total,
            denom_5_count=denom_5_count,
            denom_5_total=denom_5_total,
            denom_1_count=denom_1_count,
            denom_1_total=denom_1_total,
            total_bills=total_bills,
            submitted_by=data.get("submitted_by")
        )
        
        return jsonify({"id": eod_id}), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to create EOD report: {str(e)}"}), 500

@bp.get("/cash-report")
@require_auth(roles=['super-admin', 'admin'])
def get_cash_report():
    """
    Get cash report data for all stores for a date range (7 days).
    Returns data grouped by date and store.
    
    Query params:
    - start_date: Start date (YYYY-MM-DD), defaults to 7 days ago
    - end_date: End date (YYYY-MM-DD), defaults to today
    """
    try:
        tenant_id = g.tenant_id
        
        # Get date range from query params
        start_date_param = request.args.get("start_date")
        end_date_param = request.args.get("end_date")
        
        if start_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
        else:
            start_date = (datetime.now() - timedelta(days=6)).date()  # 7 days including today
        
        if end_date_param:
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        else:
            end_date = datetime.now().date()
        
        # Get stores for this tenant, optionally filtered by manager or admin regions
        user_role = g.current_user.get('role')
        manager_username = request.args.get("manager_username")
        
        # If admin, filter stores by managers in assigned regions
        if user_role == 'admin':
            admin_regions = g.current_user.get('regions', [])
            if not admin_regions:
                # Admin with no regions sees no stores
                return jsonify({
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "stores": [],
                    "data": {}
                }), 200
            
            # Get all managers in admin's assigned regions
            from ..models import Manager
            managers = Manager.query.filter_by(tenant_id=tenant_id).filter(
                Manager.is_super_admin == False,
                Manager.is_admin == False,
                Manager.location.in_(admin_regions)
            ).all()
            
            manager_usernames = [m.username for m in managers]
            if not manager_usernames:
                # No managers in assigned regions
                return jsonify({
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "stores": [],
                    "data": {}
                }), 200
            
            # Get stores for these managers
            from ..models import Store
            stores = Store.query.filter_by(tenant_id=tenant_id).filter(
                Store.manager_username.in_(manager_usernames)
            ).all()
            store_names = [store.name for store in stores]
        elif manager_username:
            # Filter by specific manager
            stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
            store_names = [store["name"] for store in stores]
        else:
            # Super-admin sees all stores
            stores = get_stores(tenant_id=tenant_id)
            store_names = [store["name"] for store in stores]
        
        # Get EOD reports for the date range, filtered by store names if admin
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        eod_query = EOD.query.filter(
            EOD.tenant_id == tenant_id,
            EOD.report_date >= start_date_str,
            EOD.report_date <= end_date_str
        )
        
        # If admin, only show EODs for stores in their regions
        if user_role == 'admin' and store_names:
            eod_query = eod_query.filter(EOD.store_id.in_(store_names))
        
        eods = eod_query.all()
        
        # Group data by date and store
        report_data = {}
        
        # Initialize all dates in range with empty data
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            report_data[date_str] = {}
            for store_name in store_names:
                report_data[date_str][store_name] = {
                    "cash_amount": 0,
                    "credit_amount": 0,
                    "qpay_amount": 0,
                    "total": 0
                }
            current_date += timedelta(days=1)
        
        # Fill in actual EOD data
        for eod in eods:
            date_str = eod.report_date
            store_name = eod.store_id
            
            if date_str in report_data and store_name in report_data[date_str]:
                report_data[date_str][store_name] = {
                    "cash_amount": float(eod.cash_amount or 0),
                    "credit_amount": float(eod.credit_amount or 0),
                    "qpay_amount": float(eod.qpay_amount or 0),
                    "total": float(eod.cash_amount or 0) + float(eod.credit_amount or 0) + float(eod.qpay_amount or 0)
                }
        
        # Format response
        result = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "stores": store_names,
            "data": report_data
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get cash report: {str(e)}"}), 500

@bp.get("/card-report")
@require_auth(roles=['super-admin', 'admin'])
def get_card_report():
    """
    Get card report data for all stores for a date range (7 days).
    Returns data grouped by date and store.
    Card report uses credit_amount + card1_amount from EOD.
    
    Query params:
    - start_date: Start date (YYYY-MM-DD), defaults to 7 days ago
    - end_date: End date (YYYY-MM-DD), defaults to today
    """
    try:
        tenant_id = g.tenant_id
        
        # Get date range from query params
        start_date_param = request.args.get("start_date")
        end_date_param = request.args.get("end_date")
        
        if start_date_param:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
        else:
            start_date = (datetime.now() - timedelta(days=6)).date()  # 7 days including today
        
        if end_date_param:
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        else:
            end_date = datetime.now().date()
        
        # Get stores for this tenant, optionally filtered by manager or admin regions
        user_role = g.current_user.get('role')
        manager_username = request.args.get("manager_username")
        
        # If admin, filter stores by managers in assigned regions
        if user_role == 'admin':
            admin_regions = g.current_user.get('regions', [])
            if not admin_regions:
                # Admin with no regions sees no stores
                return jsonify({
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "stores": [],
                    "data": {}
                }), 200
            
            # Get all managers in admin's assigned regions
            from ..models import Manager
            managers = Manager.query.filter_by(tenant_id=tenant_id).filter(
                Manager.is_super_admin == False,
                Manager.is_admin == False,
                Manager.location.in_(admin_regions)
            ).all()
            
            manager_usernames = [m.username for m in managers]
            if not manager_usernames:
                # No managers in assigned regions
                return jsonify({
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "stores": [],
                    "data": {}
                }), 200
            
            # Get stores for these managers
            from ..models import Store
            stores = Store.query.filter_by(tenant_id=tenant_id).filter(
                Store.manager_username.in_(manager_usernames)
            ).all()
            store_names = [store.name for store in stores]
        elif manager_username:
            # Filter by specific manager
            stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
            store_names = [store["name"] for store in stores]
        else:
            # Super-admin sees all stores
            stores = get_stores(tenant_id=tenant_id)
            store_names = [store["name"] for store in stores]
        
        # Get EOD reports for the date range, filtered by store names if admin
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()
        
        eod_query = EOD.query.filter(
            EOD.tenant_id == tenant_id,
            EOD.report_date >= start_date_str,
            EOD.report_date <= end_date_str
        )
        
        # If admin, only show EODs for stores in their regions
        if user_role == 'admin' and store_names:
            eod_query = eod_query.filter(EOD.store_id.in_(store_names))
        
        eods = eod_query.all()
        
        # Group data by date and store
        report_data = {}
        
        # Initialize all dates in range with empty data
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            report_data[date_str] = {}
            for store_name in store_names:
                report_data[date_str][store_name] = {
                    "credit_amount": 0,
                    "card1_amount": 0,
                    "card_total": 0
                }
            current_date += timedelta(days=1)
        
        # Fill in actual EOD data
        for eod in eods:
            date_str = eod.report_date
            store_name = eod.store_id
            
            if date_str in report_data and store_name in report_data[date_str]:
                credit_amount = float(eod.credit_amount or 0)
                card1_amount = float(eod.card1_amount or 0)
                card_total = credit_amount + card1_amount
                
                report_data[date_str][store_name] = {
                    "credit_amount": credit_amount,
                    "card1_amount": card1_amount,
                    "card_total": card_total
                }
        
        # Format response
        result = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "stores": store_names,
            "data": report_data
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get card report: {str(e)}"}), 500
