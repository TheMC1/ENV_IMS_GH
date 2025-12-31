"""
Inventory management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, write_access_required, page_access_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_inventory_headers,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    create_inventory_backup,
    get_user_page_settings
)

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/inventory')
@login_required
@page_access_required('inventory')
def inventory():
    """Display inventory management page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    # Get user preferences with defaults
    view_mode = user['view_mode'] if user and user['view_mode'] else 'summarized'
    custody_view = user['custody_view'] if user and user['custody_view'] else 'all'
    rows_per_page = user['rows_per_page'] if user and user['rows_per_page'] else 'all'

    # Get saved filter settings
    page_settings = get_user_page_settings(username, 'inventory')
    saved_filters = page_settings.get('columnFilters', {})

    return render_template('inventory.html',
                         username=username,
                         user_role=user_role,
                         view_mode=view_mode,
                         custody_view=custody_view,
                         rows_per_page=rows_per_page,
                         saved_filters=saved_filters)


@inventory_bp.route('/api/inventory/get', methods=['GET'])
@login_required
def get_inventory():
    """Get all inventory items"""
    try:
        headers = get_inventory_headers()
        data = get_all_inventory_items()

        if not headers:
            return jsonify({'headers': [], 'data': []})

        return jsonify({'headers': headers, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/update', methods=['POST'])
@login_required
@write_access_required
def update_inventory():
    """Update an inventory item"""
    try:
        row_index = request.json.get('row_index')
        row_data = request.json.get('data')
        username = session.get('user')

        success, message = update_inventory_item(row_index, row_data)

        if not success:
            return jsonify({'error': message}), 404

        # Create backup after update
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'
        item_identifier = row_data.get(first_col, 'Unknown')
        create_inventory_backup(username, f'Updated item: {item_identifier}')

        return jsonify({'success': True, 'message': 'Inventory updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/add', methods=['POST'])
@login_required
@write_access_required
def add_inventory():
    """Add a new inventory item"""
    try:
        row_data = request.json.get('data')
        username = session.get('user')

        success, item_id = add_inventory_item(row_data)

        if not success:
            return jsonify({'error': item_id}), 500

        # Create backup after adding
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'
        item_identifier = row_data.get(first_col, 'N/A')
        create_inventory_backup(username, f'Added item: {item_identifier}')

        return jsonify({'success': True, 'message': 'Item added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/delete', methods=['POST'])
@login_required
@write_access_required
def delete_inventory():
    """Delete an inventory item"""
    try:
        row_index = request.json.get('row_index')
        username = session.get('user')

        # Get item data before deleting for backup description
        items = get_all_inventory_items()
        deleted_item = None
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'

        for item in items:
            if item.get('_row_index') == row_index:
                deleted_item = item.get(first_col, 'N/A')
                break

        success, message = delete_inventory_item(row_index)

        if not success:
            return jsonify({'error': message}), 404

        # Create backup after delete
        create_inventory_backup(username, f'Deleted item: {deleted_item}')

        return jsonify({'success': True, 'message': 'Item deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/bulk-delete', methods=['POST'])
@login_required
@write_access_required
def bulk_delete_inventory():
    """Bulk delete inventory items by serial numbers"""
    try:
        serials = request.json.get('serials', [])
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        items = get_all_inventory_items()

        # Find items to delete by serial
        items_to_delete = []
        for item in items:
            if item.get('Serial') in serials:
                items_to_delete.append(item)

        if not items_to_delete:
            return jsonify({'error': 'No matching items found'}), 404

        # Delete each item
        deleted_count = 0
        deleted_serials = []

        for item in items_to_delete:
            row_index = item.get('_row_index')
            serial = item.get('Serial')
            success, message = delete_inventory_item(row_index)

            if success:
                deleted_count += 1
                deleted_serials.append(serial)

        # Create backup after bulk delete
        summary = f'Bulk deleted {deleted_count} item(s): {", ".join(deleted_serials[:10])}'
        if len(deleted_serials) > 10:
            summary += f' and {len(deleted_serials) - 10} more'

        create_inventory_backup(username, summary)

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'deleted_serials': deleted_serials
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/commit-batch', methods=['POST'])
@login_required
@write_access_required
def commit_batch():
    """Commit a batch of changes and create a single backup with summary"""
    try:
        username = session.get('user')
        changes_summary = request.json.get('summary', {})
        modifications = request.json.get('modifications', {})
        additions = request.json.get('additions', [])
        deletions = request.json.get('deletions', [])

        # Process deletions
        for row_index in deletions:
            delete_inventory_item(row_index)

        # Process modifications
        for row_index_str, changes in modifications.items():
            row_index = int(row_index_str)
            update_inventory_item(row_index, changes)

        # Process additions
        for new_row in additions:
            add_inventory_item(new_row)

        # Create backup with summary
        total_changes = len(modifications) + len(additions) + len(deletions)
        action_desc = f'Batch commit: {total_changes} change(s)'
        create_inventory_backup(username, action_desc, changes_summary)

        return jsonify({'success': True, 'message': 'Batch committed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
