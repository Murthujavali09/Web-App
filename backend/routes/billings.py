# backend/routes/billings.py
from flask import Blueprint, request, jsonify, g
from ..models import get_billings_by_stores, update_billing_payment, get_stores, StoreBilling, get_all_managers, get_current_billing_month
from ..auth import require_auth

bp = Blueprint("billings", __name__)

@bp.get("/")
@require_auth(roles=['manager', 'super-admin', 'admin'])
def get_billings():
    """Get all billings grouped by store for managers (current month only)"""
    try:
        tenant_id = g.tenant_id
        user_role = g.current_user.get('role')
        current_month = get_current_billing_month()
        
        # Get stores for this tenant, filtered by admin regions if admin, or by manager username if manager
        if user_role == 'admin':
            admin_regions = g.current_user.get('regions', [])
            if not admin_regions:
                return jsonify({
                    'stores': [],
                    'billings': {},
                    'billing_month': current_month
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
                return jsonify({
                    'stores': [],
                    'billings': {},
                    'billing_month': current_month
                }), 200
            
            # Get stores for these managers
            from ..models import Store
            stores = Store.query.filter_by(tenant_id=tenant_id).filter(
                Store.manager_username.in_(manager_usernames)
            ).all()
            store_names = [store.name for store in stores]
        elif user_role == 'manager':
            # Manager sees only their own stores
            manager_username = g.current_user.get('username')
            if not manager_username:
                return jsonify({
                    'stores': [],
                    'billings': {},
                    'billing_month': current_month
                }), 200
            
            stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
            store_names = [store["name"] for store in stores]
        else:
            # Super-admin sees all stores
            stores = get_stores(tenant_id=tenant_id)
            store_names = [store["name"] for store in stores]
        
        # Get billings grouped by store (for current month)
        all_billings = get_billings_by_stores(tenant_id, billing_month=current_month)
        
        # Filter billings to only include stores the user has access to
        billings = {}
        for store_name in store_names:
            if store_name in all_billings:
                billings[store_name] = all_billings[store_name]
            else:
                # Ensure all stores have billing entries (even if empty)
                billings[store_name] = {
                    'electricity': {'paid': False, 'amount': 0},
                    'wifi': {'paid': False, 'amount': 0},
                    'gas': {'paid': False, 'amount': 0}
                }
        
        return jsonify({
            'stores': store_names,
            'billings': billings,
            'billing_month': current_month
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get billings: {str(e)}"}), 500


@bp.post("/pay")
@require_auth(roles=['manager', 'super-admin'])
def pay_billing():
    """Record a payment for a billing"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        store_id = data.get("store_id")
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
        
        bill_type = data.get("bill_type")
        if not bill_type:
            return jsonify({"error": "bill_type is required"}), 400
        
        if bill_type.lower() not in ['electricity', 'wifi', 'gas']:
            return jsonify({"error": "bill_type must be 'electricity', 'wifi', or 'gas'"}), 400
        
        amount = data.get("amount")
        if amount is None:
            return jsonify({"error": "amount is required"}), 400
        
        try:
            amount = float(amount)
            if amount < 0:
                return jsonify({"error": "amount must be positive"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "amount must be a valid number"}), 400
        
        tenant_id = g.tenant_id
        user_role = g.current_user.get('role')
        
        # Verify store belongs to tenant and manager (if manager)
        if user_role == 'manager':
            # Manager can only pay for their own stores
            manager_username = g.current_user.get('username')
            if not manager_username:
                return jsonify({"error": "Manager username not found"}), 400
            
            stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
            store_names = [store["name"] for store in stores]
            if store_id not in store_names:
                return jsonify({"error": f"Store '{store_id}' not found or access denied"}), 404
        else:
            # Super-admin can pay for any store in tenant
            stores = get_stores(tenant_id=tenant_id)
            store_names = [store["name"] for store in stores]
            if store_id not in store_names:
                return jsonify({"error": f"Store '{store_id}' not found"}), 404
        
        # Update billing payment
        billing = update_billing_payment(tenant_id, store_id, bill_type, amount)
        
        return jsonify(billing), 200
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to record payment: {str(e)}"}), 500


@bp.get("/managers")
@require_auth(roles=['super-admin', 'admin'])
def get_managers_billings():
    """Get all managers with their stores' billing information for super admin or admin"""
    try:
        tenant_id = g.tenant_id
        user_role = g.current_user.get('role')
        current_month = get_current_billing_month()
        
        # Get managers - filter by admin regions if admin
        if user_role == 'admin':
            admin_regions = g.current_user.get('regions', [])
            if not admin_regions:
                return jsonify({
                    'managers': [],
                    'billing_month': current_month
                }), 200
            
            # Get all managers in admin's assigned regions
            from ..models import Manager
            managers_query = Manager.query.filter_by(tenant_id=tenant_id).filter(
                Manager.is_super_admin == False,
                Manager.is_admin == False,
                Manager.location.in_(admin_regions)
            ).all()
            managers = [m.to_dict() for m in managers_query]
        else:
            # Super-admin sees all managers (exclude super admin and admins)
            all_managers = get_all_managers(tenant_id=tenant_id)
            managers = [m for m in all_managers if not m.get('is_super_admin', False) and not m.get('is_admin', False)]
        
        # Get billings for all stores
        all_billings = get_billings_by_stores(tenant_id, billing_month=current_month)
        
        # If admin, filter billings to only stores in their regions
        if user_role == 'admin':
            # Get all store names for managers in admin's regions
            from ..models import Store
            admin_store_names = set()
            for manager in managers:
                manager_stores = Store.query.filter_by(
                    tenant_id=tenant_id,
                    manager_username=manager['username']
                ).all()
                admin_store_names.update([s.name for s in manager_stores])
            
            # Filter billings to only include stores in admin's regions
            filtered_billings = {
                store_name: billing 
                for store_name, billing in all_billings.items() 
                if store_name in admin_store_names
            }
            all_billings = filtered_billings
        
        # Group stores by manager and attach billing info
        managers_with_billings = []
        for manager in managers:
            manager_username = manager['username']
            
            # Get stores for this manager
            stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
            
            # Get billing info for each store
            stores_with_billings = []
            total_paid = 0
            total_unpaid = 0
            
            for store in stores:
                store_name = store['name']
                store_billing = all_billings.get(store_name, {
                    'electricity': {'paid': False, 'amount': 0},
                    'wifi': {'paid': False, 'amount': 0},
                    'gas': {'paid': False, 'amount': 0}
                })
                
                # Calculate totals
                for bill_type in ['electricity', 'wifi', 'gas']:
                    bill = store_billing.get(bill_type, {'paid': False, 'amount': 0})
                    if bill['paid']:
                        total_paid += bill['amount']
                    else:
                        # Count unpaid bills
                        total_unpaid += 1
                
                stores_with_billings.append({
                    'name': store_name,
                    'billing': store_billing
                })
            
            managers_with_billings.append({
                'id': manager['id'],
                'name': manager['name'],
                'username': manager['username'],
                'location': manager.get('location'),
                'stores': stores_with_billings,
                'stores_count': len(stores_with_billings),
                'total_paid': total_paid,
                'unpaid_bills_count': total_unpaid
            })
        
        return jsonify({
            'managers': managers_with_billings,
            'billing_month': current_month
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get managers billings: {str(e)}"}), 500


@bp.get("/manager/<manager_username>")
@require_auth(roles=['super-admin', 'admin'])
def get_manager_billings(manager_username):
    """Get billing details for a specific manager's stores"""
    try:
        tenant_id = g.tenant_id
        user_role = g.current_user.get('role')
        current_month = get_current_billing_month()
        
        # If admin, verify manager is in their assigned regions
        if user_role == 'admin':
            admin_regions = g.current_user.get('regions', [])
            if not admin_regions:
                return jsonify({"error": "No regions assigned"}), 403
            
            # Get manager and check if their location is in admin's regions
            from ..models import get_manager_by_username
            manager = get_manager_by_username(manager_username, tenant_id=tenant_id)
            if not manager:
                return jsonify({"error": "Manager not found"}), 404
            
            manager_location = manager.get('location', '').strip()
            if not manager_location or manager_location not in admin_regions:
                return jsonify({"error": "Access denied. Manager not in your assigned regions."}), 403
        
        # Get stores for this manager
        stores = get_stores(tenant_id=tenant_id, manager_username=manager_username)
        
        if not stores:
            return jsonify({"error": "No stores found for this manager"}), 404
        
        # Get billings for these stores
        all_billings = get_billings_by_stores(tenant_id, billing_month=current_month)
        
        # Format store billings
        stores_with_billings = []
        for store in stores:
            store_name = store['name']
            store_billing = all_billings.get(store_name, {
                'electricity': {'paid': False, 'amount': 0},
                'wifi': {'paid': False, 'amount': 0},
                'gas': {'paid': False, 'amount': 0}
            })
            
            stores_with_billings.append({
                'name': store_name,
                'billing': store_billing
            })
        
        # Get manager info
        from ..models import get_manager_by_username
        manager = get_manager_by_username(manager_username, tenant_id=tenant_id)
        if not manager:
            return jsonify({"error": "Manager not found"}), 404
        
        return jsonify({
            'manager': {
                'name': manager['name'],
                'username': manager['username']
            },
            'stores': stores_with_billings,
            'billing_month': current_month
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to get manager billings: {str(e)}"}), 500

