# backend/routes/inventory_history.py
from flask import Blueprint, request, jsonify, g
from datetime import datetime, date, timedelta
from sqlalchemy import func, cast, Date
from backend.database import db
from backend.models import Inventory, InventoryHistory, EOD, Store, create_alert
from backend.auth import require_auth

bp = Blueprint("inventory_history", __name__)

@bp.get("/")
@require_auth()
def list_inventory_history():
    """Get inventory history snapshots for a store"""
    tenant_id = g.tenant_id
    store_id = request.args.get("store_id")
    
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400
    
    # Get all snapshots for this tenant/store, sorted by date (newest first)
    snapshots = InventoryHistory.query.filter_by(tenant_id=tenant_id, store_id=store_id).order_by(InventoryHistory.snapshot_date.desc()).all()
    
    print(f"Loading inventory history for store_id={store_id}, found {len(snapshots)} snapshots")
    if snapshots:
        latest_date = snapshots[0].snapshot_date.date() if snapshots[0].snapshot_date else None
        print(f"Latest snapshot date: {latest_date}")
        # Print all snapshot dates for debugging
        all_dates = [s.snapshot_date.date() for s in snapshots if s.snapshot_date]
        print(f"All snapshot dates: {all_dates}")
    
    return jsonify([snapshot.to_dict() for snapshot in snapshots])

@bp.post("/snapshot")
@require_auth()
def create_inventory_snapshot():
    """Create a new inventory snapshot for a store"""
    data = request.get_json()
    tenant_id = g.tenant_id
    
    store_id = data.get("store_id")
    snapshot_date = data.get("snapshot_date")  # Should be YYYY-MM-DD format (device's local date)
    today_date = data.get("today_date")  # Today's date from device's local time
    
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400
    
    # Get current inventory for this tenant/store
    items = Inventory.query.filter_by(tenant_id=tenant_id, store_id=store_id).all()
    
    # Parse snapshot date - use the date string directly (no timezone conversion)
    if snapshot_date:
        try:
            # If snapshot_date is just YYYY-MM-DD, parse it directly
            if len(snapshot_date) == 10:  # YYYY-MM-DD format
                date_parts = snapshot_date.split('-')
                snapshot_dt = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 0, 0, 0)
            else:
                snapshot_dt = datetime.fromisoformat(snapshot_date.replace('Z', '+00:00'))
                # Normalize to midnight
                snapshot_dt = datetime(snapshot_dt.year, snapshot_dt.month, snapshot_dt.day, 0, 0, 0)
        except Exception as parse_err:
            print(f"Error parsing snapshot_date '{snapshot_date}': {parse_err}")
            # Fallback: use today_date if provided, otherwise use current date
            if today_date and len(today_date) == 10:
                date_parts = today_date.split('-')
                snapshot_dt = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 0, 0, 0)
            else:
                snapshot_dt = datetime.now()  # Use local server time as fallback
                snapshot_dt = datetime(snapshot_dt.year, snapshot_dt.month, snapshot_dt.day, 0, 0, 0)
    else:
        # Use today_date if provided, otherwise use current date
        if today_date and len(today_date) == 10:
            date_parts = today_date.split('-')
            snapshot_dt = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 0, 0, 0)
        else:
            snapshot_dt = datetime.now()  # Use local server time as fallback
            snapshot_dt = datetime(snapshot_dt.year, snapshot_dt.month, snapshot_dt.day, 0, 0, 0)
    
    # Normalize item field names for consistency
    normalized_items = []
    for item in items:
        normalized = {
            "sku": item.sku,
            "name": item.name,
            "quantity": item.quantity,
            "price": 0,
            "device_type": item.device_type if hasattr(item, 'device_type') else 'metro'
        }
        normalized_items.append(normalized)
    
    # Get today's date from device's local time for comparison
    if today_date and len(today_date) == 10:
        try:
            date_parts = today_date.split('-')
            today_dt = datetime(int(date_parts[0]), int(date_parts[1]), int(date_parts[2]), 0, 0, 0)
        except:
            # Fallback to server local time
            today_dt = datetime.now()
            today_dt = datetime(today_dt.year, today_dt.month, today_dt.day, 0, 0, 0)
    else:
        # Fallback to server local time if today_date not provided
        today_dt = datetime.now()
        today_dt = datetime(today_dt.year, today_dt.month, today_dt.day, 0, 0, 0)
    
    # Debug logging
    print(f"Creating snapshot: store_id={store_id}, snapshot_date={snapshot_dt.date()}, today_date={today_dt.date()}")
    print(f"Number of items to snapshot: {len(normalized_items)}")
    
    # Check if snapshot already exists for this tenant/store/date
    # Compare by date only (ignore time component) to handle timezone differences
    snapshot_date_only = snapshot_dt.date()
    existing = InventoryHistory.query.filter(
        InventoryHistory.tenant_id == tenant_id,
        InventoryHistory.store_id == store_id,
        func.date(InventoryHistory.snapshot_date) == snapshot_date_only
    ).first()
    
    if existing:
        # Only allow updating today's snapshot - prevent editing past days
        if snapshot_dt < today_dt:
            error_msg = f"Cannot update inventory history for past dates. Snapshot date ({snapshot_dt.date()}) is before today ({today_dt.date()})."
            print(f"ERROR: {error_msg}")
            return jsonify({"error": error_msg}), 403
        
        # Update existing snapshot (only allowed for today)
        existing.set_items(normalized_items)
        existing.updated_at = datetime.now()
        db.session.commit()
        
        # Validate inventory against yesterday's data (same validation as create)
        warning_message = None
        if snapshot_dt.date() == today_dt.date():  # Only validate for today's snapshot
            try:
                # Get yesterday's date
                yesterday = snapshot_dt.date() - timedelta(days=1)
                
                # Get yesterday's inventory snapshot
                yesterday_snapshot = InventoryHistory.query.filter(
                    InventoryHistory.tenant_id == tenant_id,
                    InventoryHistory.store_id == store_id,
                    func.date(InventoryHistory.snapshot_date) == yesterday
                ).first()
                
                # Get yesterday's EOD inventory_sold
                yesterday_date_str = yesterday.strftime('%Y-%m-%d')
                yesterday_eod = EOD.query.filter_by(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    report_date=yesterday_date_str
                ).first()
                
                if yesterday_snapshot and yesterday_eod:
                    # Calculate yesterday's total inventory
                    yesterday_items = yesterday_snapshot.get_items()
                    yesterday_total = sum(item.get('quantity', 0) for item in yesterday_items)
                    
                    # Get inventory sold from yesterday's EOD
                    inventory_sold = yesterday_eod.inventory_sold or 0
                    
                    # Calculate expected inventory: yesterday_total - inventory_sold
                    expected_total = yesterday_total - inventory_sold
                    
                    # Calculate current total inventory
                    current_total = sum(item.get('quantity', 0) for item in normalized_items)
                    
                    # Check for mismatch
                    if current_total != expected_total:
                        difference = current_total - expected_total
                        warning_message = f"Inventory mismatch detected! Expected: {expected_total} (Yesterday: {yesterday_total} - Sold: {inventory_sold}), Actual: {current_total}, Difference: {difference:+d}"
                        
                        # Get store to find manager_username
                        store = Store.query.filter_by(tenant_id=tenant_id, name=store_id).first()
                        manager_username = store.manager_username if store else None
                        
                        if manager_username:
                            # Create alert for the manager
                            alert_title = f"Inventory Mismatch - {store_id}"
                            alert_message = (
                                f"Inventory mismatch detected for {store_id} on {snapshot_dt.date().isoformat()}.\n\n"
                                f"Expected Total: {expected_total} items\n"
                                f"(Yesterday's Total: {yesterday_total} - Inventory Sold: {inventory_sold})\n"
                                f"Actual Total: {current_total} items\n"
                                f"Difference: {difference:+d} items\n\n"
                                f"Please verify the inventory counts."
                            )
                            
                            create_alert(
                                tenant_id=tenant_id,
                                store_id=store_id,
                                manager_username=manager_username,
                                alert_type='inventory_mismatch',
                                title=alert_title,
                                message=alert_message
                            )
                            print(f"Alert created for manager {manager_username} about inventory mismatch")
                        else:
                            print(f"Warning: No manager found for store {store_id}, cannot create alert")
                        
                        print(f"INVENTORY MISMATCH: {warning_message}")
            except Exception as validation_error:
                # Don't fail the snapshot update if validation fails
                print(f"Error during inventory validation: {validation_error}")
                import traceback
                traceback.print_exc()
        
        print(f"Snapshot updated: id={existing.id}, store_id={store_id}, date={snapshot_dt.date()}, items_count={len(normalized_items)}")
        
        response_data = {
            "message": "Snapshot updated",
            "id": str(existing.id),
            "snapshot_date": snapshot_dt.date().isoformat()
        }
        
        if warning_message:
            response_data["warning"] = warning_message
        
        return jsonify(response_data), 200
    else:
        # Prevent creating snapshots for past dates
        if snapshot_dt < today_dt:
            error_msg = f"Cannot create inventory snapshot for past dates. Snapshot date ({snapshot_dt.date()}) is before today ({today_dt.date()})."
            print(f"ERROR: {error_msg}")
            return jsonify({"error": error_msg}), 403
        
        # Create new snapshot (only for today or future dates)
        snapshot = InventoryHistory(
            tenant_id=tenant_id,
            store_id=store_id,
            snapshot_date=snapshot_dt
        )
        snapshot.set_items(normalized_items)
        
        db.session.add(snapshot)
        db.session.commit()
        
        # Refresh to get the committed snapshot
        db.session.refresh(snapshot)
        
        # Validate inventory against yesterday's data
        warning_message = None
        if snapshot_dt.date() == today_dt.date():  # Only validate for today's snapshot
            try:
                # Get yesterday's date
                yesterday = snapshot_dt.date() - timedelta(days=1)
                
                # Get yesterday's inventory snapshot
                yesterday_snapshot = InventoryHistory.query.filter(
                    InventoryHistory.tenant_id == tenant_id,
                    InventoryHistory.store_id == store_id,
                    func.date(InventoryHistory.snapshot_date) == yesterday
                ).first()
                
                # Get yesterday's EOD inventory_sold
                yesterday_date_str = yesterday.strftime('%Y-%m-%d')
                yesterday_eod = EOD.query.filter_by(
                    tenant_id=tenant_id,
                    store_id=store_id,
                    report_date=yesterday_date_str
                ).first()
                
                if yesterday_snapshot and yesterday_eod:
                    # Calculate yesterday's total inventory
                    yesterday_items = yesterday_snapshot.get_items()
                    yesterday_total = sum(item.get('quantity', 0) for item in yesterday_items)
                    
                    # Get inventory sold from yesterday's EOD
                    inventory_sold = yesterday_eod.inventory_sold or 0
                    
                    # Calculate expected inventory: yesterday_total - inventory_sold
                    expected_total = yesterday_total - inventory_sold
                    
                    # Calculate current total inventory
                    current_total = sum(item.get('quantity', 0) for item in normalized_items)
                    
                    # Check for mismatch
                    if current_total != expected_total:
                        difference = current_total - expected_total
                        warning_message = f"Inventory mismatch detected! Expected: {expected_total} (Yesterday: {yesterday_total} - Sold: {inventory_sold}), Actual: {current_total}, Difference: {difference:+d}"
                        
                        # Get store to find manager_username
                        store = Store.query.filter_by(tenant_id=tenant_id, name=store_id).first()
                        manager_username = store.manager_username if store else None
                        
                        if manager_username:
                            # Create alert for the manager
                            alert_title = f"Inventory Mismatch - {store_id}"
                            alert_message = (
                                f"Inventory mismatch detected for {store_id} on {snapshot_dt.date().isoformat()}.\n\n"
                                f"Expected Total: {expected_total} items\n"
                                f"(Yesterday's Total: {yesterday_total} - Inventory Sold: {inventory_sold})\n"
                                f"Actual Total: {current_total} items\n"
                                f"Difference: {difference:+d} items\n\n"
                                f"Please verify the inventory counts."
                            )
                            
                            create_alert(
                                tenant_id=tenant_id,
                                store_id=store_id,
                                manager_username=manager_username,
                                alert_type='inventory_mismatch',
                                title=alert_title,
                                message=alert_message
                            )
                            print(f"Alert created for manager {manager_username} about inventory mismatch")
                        else:
                            print(f"Warning: No manager found for store {store_id}, cannot create alert")
                        
                        print(f"INVENTORY MISMATCH: {warning_message}")
            except Exception as validation_error:
                # Don't fail the snapshot creation if validation fails
                print(f"Error during inventory validation: {validation_error}")
                import traceback
                traceback.print_exc()
        
        print(f"Snapshot created: id={snapshot.id}, store_id={store_id}, date={snapshot_dt.date()}, stored_date={snapshot.snapshot_date.date() if snapshot.snapshot_date else 'None'}, items_count={len(normalized_items)}")
        
        response_data = {
            "message": "Snapshot created",
            "id": str(snapshot.id),
            "snapshot_date": snapshot_dt.date().isoformat()
        }
        
        if warning_message:
            response_data["warning"] = warning_message
        
        return jsonify(response_data), 201
