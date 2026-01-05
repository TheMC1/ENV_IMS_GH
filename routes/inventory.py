"""
Inventory management routes for Carbon IMS
"""

import csv
import io
from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, write_access_required, page_access_required, admin_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_inventory_headers,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    create_inventory_backup,
    get_user_page_settings,
    verify_user_password,
    get_inventory_db_connection,
    log_activity,
    get_criteria_allocation_status
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
            return jsonify({'headers': [], 'data': [], 'generic_reserved_serials': []})

        # Get serials allocated to criteria-only trades (generic reservations)
        allocation_status = get_criteria_allocation_status()
        generic_reserved_serials = allocation_status.get('allocated_serials', [])

        return jsonify({
            'headers': headers,
            'data': data,
            'generic_reserved_serials': generic_reserved_serials,
            'generic_reserved_count': len(generic_reserved_serials)
        })
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

        # Get before data for logging
        items = get_all_inventory_items()
        before_item = next((item for item in items if item.get('_row_index') == row_index), None)
        serial = row_data.get('Serial', before_item.get('Serial') if before_item else None)

        success, message = update_inventory_item(row_index, row_data)

        if not success:
            return jsonify({'error': message}), 404

        # Create backup after update
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'
        item_identifier = row_data.get(first_col, 'Unknown')
        create_inventory_backup(username, f'Updated item: {item_identifier}')

        # Log the activity
        log_activity(
            username=username,
            action_type='update',
            target_type='inventory',
            target_id=str(row_index),
            serial=serial,
            details=f'Updated inventory item: Serial {serial}',
            before_data=dict(before_item) if before_item else None,
            after_data=row_data
        )

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
        serial = row_data.get('Serial', row_data.get('serial', ''))

        success, item_id = add_inventory_item(row_data)

        if not success:
            return jsonify({'error': item_id}), 500

        # Create backup after adding
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'
        item_identifier = row_data.get(first_col, 'N/A')
        create_inventory_backup(username, f'Added item: {item_identifier}')

        # Log the activity
        log_activity(
            username=username,
            action_type='add',
            target_type='inventory',
            target_id=str(item_id),
            serial=serial,
            details=f'Added new inventory item: Serial {serial}',
            after_data=row_data
        )

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

        # Get item data before deleting for backup description and logging
        items = get_all_inventory_items()
        deleted_item_data = None
        headers = get_inventory_headers()
        first_col = headers[0] if headers else 'Unknown'

        for item in items:
            if item.get('_row_index') == row_index:
                deleted_item_data = dict(item)
                break

        deleted_item = deleted_item_data.get(first_col, 'N/A') if deleted_item_data else 'N/A'
        serial = deleted_item_data.get('Serial', '') if deleted_item_data else ''

        success, message = delete_inventory_item(row_index)

        if not success:
            return jsonify({'error': message}), 404

        # Create backup after delete
        create_inventory_backup(username, f'Deleted item: {deleted_item}')

        # Log the activity
        log_activity(
            username=username,
            action_type='delete',
            target_type='inventory',
            target_id=str(row_index),
            serial=serial,
            details=f'Deleted inventory item: Serial {serial}',
            before_data=deleted_item_data
        )

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
        deleted_items_data = []

        for item in items_to_delete:
            row_index = item.get('_row_index')
            serial = item.get('Serial')
            success, message = delete_inventory_item(row_index)

            if success:
                deleted_count += 1
                deleted_serials.append(serial)
                deleted_items_data.append(dict(item))

        # Create backup after bulk delete
        summary = f'Bulk deleted {deleted_count} item(s): {", ".join(deleted_serials[:10])}'
        if len(deleted_serials) > 10:
            summary += f' and {len(deleted_serials) - 10} more'

        create_inventory_backup(username, summary)

        # Log each deleted item
        for i, serial in enumerate(deleted_serials):
            log_activity(
                username=username,
                action_type='delete',
                target_type='inventory',
                serial=serial,
                details=f'Bulk deleted inventory item: Serial {serial}',
                before_data=deleted_items_data[i] if i < len(deleted_items_data) else None
            )

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

        # Get all items before changes for logging
        all_items = get_all_inventory_items()
        items_by_index = {item.get('_row_index'): item for item in all_items}

        # Process deletions
        for row_index in deletions:
            before_item = items_by_index.get(row_index)
            serial = before_item.get('Serial', '') if before_item else ''
            delete_inventory_item(row_index)
            log_activity(
                username=username,
                action_type='delete',
                target_type='inventory',
                target_id=str(row_index),
                serial=serial,
                details=f'Deleted inventory item (batch): Serial {serial}',
                before_data=dict(before_item) if before_item else None
            )

        # Process modifications
        for row_index_str, changes in modifications.items():
            row_index = int(row_index_str)
            before_item = items_by_index.get(row_index)
            serial = changes.get('Serial', before_item.get('Serial', '') if before_item else '')
            update_inventory_item(row_index, changes)
            log_activity(
                username=username,
                action_type='update',
                target_type='inventory',
                target_id=str(row_index),
                serial=serial,
                details=f'Updated inventory item (batch): Serial {serial}',
                before_data=dict(before_item) if before_item else None,
                after_data=changes
            )

        # Process additions
        for new_row in additions:
            serial = new_row.get('Serial', new_row.get('serial', ''))
            success, item_id = add_inventory_item(new_row)
            if success:
                log_activity(
                    username=username,
                    action_type='add',
                    target_type='inventory',
                    target_id=str(item_id),
                    serial=serial,
                    details=f'Added inventory item (batch): Serial {serial}',
                    after_data=new_row
                )

        # Create backup with summary
        total_changes = len(modifications) + len(additions) + len(deletions)
        action_desc = f'Batch commit: {total_changes} change(s)'
        create_inventory_backup(username, action_desc, changes_summary)

        return jsonify({'success': True, 'message': 'Batch committed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@inventory_bp.route('/api/inventory/import-csv', methods=['POST'])
@login_required
@admin_required
def import_csv():
    """Import inventory and warranty data from CSV file (admin only)"""
    try:
        username = session.get('user')
        password = request.form.get('password')
        mode = request.form.get('mode', 'append')  # 'append' or 'replace'

        # Verify password
        if not password:
            return jsonify({'error': 'Password is required'}), 400

        success, message = verify_user_password(username, password)
        if not success:
            return jsonify({'error': 'Invalid password'}), 401

        # Check for file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV'}), 400

        # Read and parse CSV
        try:
            content = file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(content))
            rows = list(csv_reader)
        except Exception as e:
            return jsonify({'error': f'Failed to parse CSV: {str(e)}'}), 400

        if not rows:
            return jsonify({'error': 'CSV file is empty'}), 400

        # Define valid inventory and warranty columns
        inventory_columns = [
            'market', 'registry', 'product', 'project_id', 'project_type',
            'protocol', 'project_name', 'vintage', 'serial', 'is_custody',
            'is_assigned', 'trade_id'
        ]
        warranty_columns = [
            'buy_start', 'buy_end', 'sell_start', 'sell_end',
            'buy_tradeid', 'sell_tradeid', 'buy_client', 'sell_client'
        ]

        # Normalize CSV headers (case-insensitive matching)
        csv_headers = [h.strip() for h in csv_reader.fieldnames] if csv_reader.fieldnames else []
        header_map = {}
        for h in csv_headers:
            h_lower = h.lower().replace(' ', '_')
            # Check inventory columns
            for col in inventory_columns:
                if h_lower == col.lower():
                    header_map[h] = col
                    break
            # Check warranty columns
            for col in warranty_columns:
                if h_lower == col.lower():
                    header_map[h] = col
                    break
            # If no match, keep original (will be ignored for inventory)
            if h not in header_map:
                header_map[h] = h

        # Create backup before import
        create_inventory_backup(username, f'Pre-import backup (mode: {mode})')

        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        # If replace mode, clear existing data
        if mode == 'replace':
            cursor.execute('DELETE FROM warranties')
            cursor.execute('DELETE FROM inventory')
            conn.commit()

        imported_count = 0
        skipped_count = 0
        errors = []
        imported_serials = []
        skipped_serials = []

        for i, row in enumerate(rows, start=2):  # Start at 2 to account for header row
            try:
                # Normalize row keys
                normalized_row = {}
                for key, value in row.items():
                    if key in header_map:
                        normalized_row[header_map[key]] = value.strip() if value else ''

                # Check if serial exists (required field)
                serial = normalized_row.get('serial', '')
                if not serial:
                    skipped_count += 1
                    errors.append(f'Row {i}: Missing serial number')
                    continue

                # Build inventory data
                inventory_data = {col: normalized_row.get(col, '') for col in inventory_columns if col in normalized_row}

                # Check for existing serial in append mode
                if mode == 'append':
                    cursor.execute('SELECT id FROM inventory WHERE serial = ?', (serial,))
                    existing = cursor.fetchone()
                    if existing:
                        skipped_count += 1
                        skipped_serials.append(serial)
                        errors.append(f'Row {i}: Serial {serial} already exists')
                        continue

                # Insert inventory record
                inv_cols = list(inventory_data.keys())
                inv_vals = [inventory_data[c] for c in inv_cols]

                if inv_cols:
                    placeholders = ', '.join(['?' for _ in inv_cols])
                    cursor.execute(
                        f'INSERT INTO inventory ({", ".join(inv_cols)}) VALUES ({placeholders})',
                        inv_vals
                    )

                # Build and insert warranty data if any warranty columns present
                warranty_data = {col: normalized_row.get(col, '') for col in warranty_columns if col in normalized_row and normalized_row.get(col, '')}

                if warranty_data or serial:
                    # Always create a warranty record for each inventory item
                    warranty_data['serial'] = serial
                    war_cols = list(warranty_data.keys())
                    war_vals = [warranty_data[c] for c in war_cols]

                    placeholders = ', '.join(['?' for _ in war_cols])
                    cursor.execute(
                        f'INSERT OR REPLACE INTO warranties ({", ".join(war_cols)}) VALUES ({placeholders})',
                        war_vals
                    )

                imported_count += 1
                imported_serials.append(serial)

            except Exception as e:
                skipped_count += 1
                errors.append(f'Row {i}: {str(e)}')

        conn.commit()
        conn.close()

        # Create post-import backup with detailed summary including serials
        import_summary = {
            'added': [{'Serial': s} for s in imported_serials],
            'modified': [],
            'deleted': [] if mode == 'append' else [{'Serial': 'All previous records replaced'}]
        }
        action_desc = f'CSV Import ({mode}): {imported_count} imported, {skipped_count} skipped'
        create_inventory_backup(username, action_desc, import_summary)

        # Log the import activity
        log_activity(
            username=username,
            action_type='import',
            target_type='inventory',
            details=f'CSV Import ({mode}): {imported_count} items imported, {skipped_count} skipped',
            after_data={'imported_serials': imported_serials[:50], 'total_imported': imported_count}
        )

        return jsonify({
            'success': True,
            'imported': imported_count,
            'skipped': skipped_count,
            'errors': errors[:20] if errors else [],  # Return first 20 errors
            'total_errors': len(errors)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
