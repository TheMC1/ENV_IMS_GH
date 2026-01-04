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
    get_user_page_settings,
    log_activity
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
        username = session.get('user')

        if row_index is None or not updates:
            return jsonify({'error': 'Missing row_index or updates'}), 400

        # Get before data for logging
        items = get_all_warranty_items()
        before_item = next((item for item in items if item.get('_row_index') == row_index), None)
        serial = before_item.get('Serial', '') if before_item else updates.get('Serial', '')

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
            # Log the activity
            log_activity(
                username=username,
                action_type='update',
                target_type='warranty',
                target_id=str(row_index),
                serial=serial,
                details=f'Updated warranty: Serial {serial}',
                before_data=dict(before_item) if before_item else None,
                after_data=warranty_updates
            )
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
        username = session.get('user')

        if not item_data:
            return jsonify({'error': 'Missing item data'}), 400

        serial = item_data.get('Serial', '')

        success, item_id = add_warranty_item(item_data)

        if success:
            # Log the activity
            log_activity(
                username=username,
                action_type='add',
                target_type='warranty',
                target_id=str(item_id),
                serial=serial,
                details=f'Added new warranty: Serial {serial}',
                after_data=item_data
            )
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
        username = session.get('user')

        if row_index is None:
            return jsonify({'error': 'Missing row_index'}), 400

        # Get before data for logging
        items = get_all_warranty_items()
        before_item = next((item for item in items if item.get('_row_index') == row_index), None)
        serial = before_item.get('Serial', '') if before_item else ''

        success, message = delete_warranty_item(row_index)

        if success:
            # Log the activity
            log_activity(
                username=username,
                action_type='delete',
                target_type='warranty',
                target_id=str(row_index),
                serial=serial,
                details=f'Deleted warranty: Serial {serial}',
                before_data=dict(before_item) if before_item else None
            )
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
        username = session.get('user')
        modified = request.json.get('modified', {})
        added = request.json.get('added', [])
        deleted = request.json.get('deleted', [])

        # Get all items for logging before changes
        all_items = get_all_warranty_items()

        # Process deletions
        for row_index in deleted:
            before_item = next((item for item in all_items if item.get('_row_index') == row_index), None)
            serial = before_item.get('Serial', '') if before_item else ''
            delete_warranty_item(row_index)
            log_activity(
                username=username,
                action_type='delete',
                target_type='warranty',
                target_id=str(row_index),
                serial=serial,
                details=f'Deleted warranty (batch): Serial {serial}',
                before_data=dict(before_item) if before_item else None
            )

        # Process modifications
        for row_index_str, updates in modified.items():
            row_index = int(row_index_str)
            before_item = next((item for item in all_items if item.get('_row_index') == row_index), None)
            serial = before_item.get('Serial', '') if before_item else ''
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
            log_activity(
                username=username,
                action_type='update',
                target_type='warranty',
                target_id=str(row_index),
                serial=serial,
                details=f'Updated warranty (batch): Serial {serial}',
                before_data=dict(before_item) if before_item else None,
                after_data=warranty_updates
            )

        # Process additions
        for item_data in added:
            serial = item_data.get('Serial', '')
            success, item_id = add_warranty_item(item_data)
            if success:
                log_activity(
                    username=username,
                    action_type='add',
                    target_type='warranty',
                    target_id=str(item_id),
                    serial=serial,
                    details=f'Added warranty (batch): Serial {serial}',
                    after_data=item_data
                )

        return jsonify({'success': True, 'message': 'Batch committed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
