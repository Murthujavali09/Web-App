# backend/routes/inventory.py
from flask import Blueprint, request, jsonify, g
from ..models import get_inventory, add_inventory_item, update_inventory_item, delete_inventory_item
from ..auth import require_auth

bp = Blueprint("inventory", __name__)

@bp.route("/", methods=["GET"])
@require_auth()
def list_inventory():
    tenant_id = g.tenant_id
    store_id = request.args.get("store_id")
    device_type = request.args.get("device_type")  # Optional filter by device type
    # Only use device_type if it's a valid value
    if device_type and device_type.strip() and device_type.strip() in ['metro', 'discontinued', 'unlocked']:
        device_type = device_type.strip()
    else:
        device_type = None  # Don't filter if invalid or not provided
    items = get_inventory(tenant_id=tenant_id, store_id=store_id, device_type=device_type)
    return jsonify(items)

@bp.route("/", methods=["POST"])
@require_auth()
def add_item():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        store_id = data.get("store_id")
        sku = data.get("sku")
        name = data.get("name")
        
        if not store_id:
            return jsonify({"error": "store_id is required"}), 400
        if not sku or not sku.strip():
            return jsonify({"error": "SKU is required"}), 400
        if not name or not name.strip():
            return jsonify({"error": "Item name is required"}), 400
        
        quantity = data.get("quantity", 0)
        try:
            quantity = int(quantity) if quantity is not None else 0
            if quantity < 0:
                return jsonify({"error": "Quantity must be non-negative"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Quantity must be a valid integer"}), 400
        
        device_type = data.get("device_type", "metro")  # Default to metro
        # Validate device_type
        valid_types = ['metro', 'discontinued', 'unlocked']
        if device_type not in valid_types:
            device_type = 'metro'
        
        tenant_id = g.tenant_id
        try:
            item_id = add_inventory_item(
                tenant_id=tenant_id,
                store_id=store_id,
                sku=sku.strip(),
                name=name.strip(),
                quantity=quantity,
                device_type=device_type
            )
            return jsonify({"id": item_id}), 201
        except ValueError as ve:
            # Handle duplicate item error (user-friendly message)
            return jsonify({"error": str(ve)}), 409
        except Exception as e:
            # Check if it's a database unique constraint violation (fallback)
            error_str = str(e)
            if "UniqueViolation" in error_str or "duplicate key" in error_str.lower() or "uq_" in error_str.lower():
                name_value = data.get("name", "").strip() if 'data' in locals() else ""
                return jsonify({"error": f"An item with SKU '{sku.strip()}' and name '{name_value}' already exists for this store. Please use a different name or update the existing item."}), 409
            raise  # Re-raise if it's a different error
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 409
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Check if it's a database unique constraint violation (fallback)
        error_str = str(e)
        if "UniqueViolation" in error_str or "duplicate key" in error_str.lower() or "uq_" in error_str.lower():
            sku_value = data.get("sku", "").strip() if 'data' in locals() else "this SKU"
            name_value = data.get("name", "").strip() if 'data' in locals() else ""
            return jsonify({"error": f"An item with SKU '{sku_value}' and name '{name_value}' already exists for this store. Please use a different name or update the existing item."}), 409
        return jsonify({"error": f"Failed to add inventory item: {str(e)}"}), 500

@bp.route("/", methods=["PUT"], strict_slashes=False)
@require_auth()
def update_item():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        tenant_id = g.tenant_id
        store_id = data.get("store_id")
        item_id = data.get("_id") or data.get("id")  # Support both _id and id
        sku = data.get("sku")  # Old SKU for finding the item (used if item_id not provided)
        quantity = data.get("quantity")
        name = data.get("name")
        new_sku = data.get("new_sku")
        device_type = data.get("device_type")  # Optional device_type update
        
        # Require either item_id OR (store_id and sku)
        if not item_id and (not store_id or not sku):
            return jsonify({"error": "Either _id or both store_id and sku are required"}), 400
        
        success = update_inventory_item(tenant_id=tenant_id, store_id=store_id, sku=sku, item_id=item_id, quantity=quantity, name=name, new_sku=new_sku, device_type=device_type)
        if success:
            return jsonify({"message": "Inventory item updated successfully"}), 200
        else:
            # Check if it's because new SKU already exists
            if new_sku:
                from ..models import Inventory
                query = Inventory.query.filter_by(tenant_id=tenant_id, store_id=store_id, sku=new_sku)
                if item_id:
                    try:
                        query = query.filter(Inventory.id != int(item_id))
                    except (ValueError, TypeError):
                        return jsonify({"error": "Invalid item_id format"}), 400
                existing = query.first()
                if existing:
                    return jsonify({"error": f"SKU '{new_sku}' already exists for this store"}), 409
            return jsonify({"error": "Inventory item not found or update failed"}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to update inventory item: {str(e)}"}), 500

@bp.route("/", methods=["DELETE"])
@require_auth()
def remove_item():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        tenant_id = g.tenant_id
        store_id = data.get("store_id")
        sku = data.get("sku")
        
        if not store_id or not sku:
            return jsonify({"error": "store_id and sku are required"}), 400
        
        success = delete_inventory_item(tenant_id=tenant_id, store_id=store_id, sku=sku)
        if success:
            return jsonify({"message": "Inventory item deleted successfully"}), 200
        else:
            return jsonify({"error": "Inventory item not found"}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to delete inventory item: {str(e)}"}), 500
