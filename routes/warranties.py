"""
Warranty management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, write_access_required, page_access_required
from database import (
    get_user_by_username,
    get_all_warranty_items,
    get_warranty_headers,
    add_warranty_item,
    update_warranty_item,
    delete_warranty_item,
    get_user_page_settings
)

warranties_bp = Blueprint('warranties', __name__)


@warranties_bp.route('/warranties')
@login_required
@page_access_required('warranties')
def warranties():
    """Display warranty management page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    # Get user preferences with defaults
    view_mode = user['warranty_view_mode'] if user and user['warranty_view_mode'] else 'summarized'
    custody_view = user['warranty_custody_view'] if user and user['warranty_custody_view'] else 'all'
    rows_per_page = user['warranty_rows_per_page'] if user and user['warranty_rows_per_page'] else 'all'

    # Get saved filter settings
    page_settings = get_user_page_settings(username, 'warranties')
    saved_filters = page_settings.get('columnFilters', {})

    return render_template('warranties.html',
                         username=username,
                         user_role=user_role,
                         view_mode=view_mode,
                         custody_view=custody_view,
                         rows_per_page=rows_per_page,
                         saved_filters=saved_filters)


@warranties_bp.route('/api/warranties/get', methods=['GET'])
@login_required
def get_warranties():
    """Get all warranty items"""
    try:
        headers = get_warranty_headers()
        data = get_all_warranty_items()

        if not headers:
            headers = ['Serial', 'Market', 'Registry', 'Product', 'ProjectID', 'ProjectType',
                      'Protocol', 'ProjectName', 'IsCustody', 'Buy_Start', 'Buy_End', 'Buy_TradeID',
                      'Buy_Client', 'Sell_Start', 'Sell_End', 'Sell_TradeID', 'Sell_Client']

        return jsonify({'headers': headers, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@warranties_bp.route('/api/warranties/update', methods=['POST'])
@login_required
@write_access_required
def update_warranty():
    """Update a warranty item"""
    try:
        row_index = request.json.get('row_index')
        updates = request.json.get('updates')

        if row_index is None or not updates:
            return jsonify({'error': 'Missing row_index or updates'}), 400

        # Only allow updates to warranty fields
        warranty_updates = {
            'Buy_Start': updates.get('Buy_Start', ''),
            'Buy_End': updates.get('Buy_End', ''),
            'Sell_Start': updates.get('Sell_Start', ''),
            'Sell_End': updates.get('Sell_End', ''),
            'Buy_TradeID': updates.get('Buy_TradeID', ''),
            'Sell_TradeID': updates.get('Sell_TradeID', ''),
            'Buy_Client': updates.get('Buy_Client', ''),
            'Sell_Client': updates.get('Sell_Client', '')
        }

        success, message = update_warranty_item(row_index, warranty_updates)

        if success:
            return jsonify({'success': True, 'message': 'Warranty updated successfully'})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@warranties_bp.route('/api/warranties/add', methods=['POST'])
@login_required
@write_access_required
def add_warranty():
    """Add a new warranty item"""
    try:
        item_data = request.json.get('item')

        if not item_data:
            return jsonify({'error': 'Missing item data'}), 400

        success, item_id = add_warranty_item(item_data)

        if success:
            return jsonify({'success': True, 'item_id': item_id})
        else:
            return jsonify({'error': item_id}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@warranties_bp.route('/api/warranties/delete', methods=['POST'])
@login_required
@write_access_required
def delete_warranty():
    """Delete a warranty item"""
    try:
        row_index = request.json.get('row_index')

        if row_index is None:
            return jsonify({'error': 'Missing row_index'}), 400

        success, message = delete_warranty_item(row_index)

        if success:
            return jsonify({'success': True, 'message': 'Warranty deleted successfully'})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@warranties_bp.route('/api/warranties/commit-batch', methods=['POST'])
@login_required
@write_access_required
def commit_warranties_batch():
    """Commit a batch of warranty changes"""
    try:
        modified = request.json.get('modified', {})
        added = request.json.get('added', [])
        deleted = request.json.get('deleted', [])

        # Process deletions
        for row_index in deleted:
            delete_warranty_item(row_index)

        # Process modifications
        for row_index_str, updates in modified.items():
            row_index = int(row_index_str)
            warranty_updates = {
                'Buy_Start': updates.get('Buy_Start', ''),
                'Buy_End': updates.get('Buy_End', ''),
                'Sell_Start': updates.get('Sell_Start', ''),
                'Sell_End': updates.get('Sell_End', ''),
                'Buy_TradeID': updates.get('Buy_TradeID', ''),
                'Sell_TradeID': updates.get('Sell_TradeID', ''),
                'Buy_Client': updates.get('Buy_Client', ''),
                'Sell_Client': updates.get('Sell_Client', '')
            }
            update_warranty_item(row_index, warranty_updates)

        # Process additions
        for item_data in added:
            add_warranty_item(item_data)

        return jsonify({'success': True, 'message': 'Batch committed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
