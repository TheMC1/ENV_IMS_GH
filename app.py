from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import secrets
import os
import json
from datetime import datetime
import pytz
from database import (
    init_database,
    init_inventory_database,
    get_user_by_username,
    verify_user_password,
    get_all_users,
    add_user as db_add_user,
    update_user as db_update_user,
    delete_user as db_delete_user,
    reset_user_password as db_reset_password,
    suspend_user as db_suspend_user,
    unsuspend_user as db_unsuspend_user,
    update_user_settings,
    update_user_preferences,
    get_all_inventory_items,
    get_inventory_headers,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    create_inventory_backup,
    get_all_inventory_backups,
    restore_inventory_backup,
    delete_inventory_backup,
    migrate_csv_to_database,
    get_all_warranty_items,
    get_warranty_headers,
    add_warranty_item,
    update_warranty_item,
    delete_warranty_item,
    get_user_page_settings,
    save_user_page_settings
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

init_database()
init_inventory_database()

# Migrate CSV data to database if CSV exists and database is empty
CSV_FILE = 'inventory.csv'
if os.path.exists(CSV_FILE):
    items = get_all_inventory_items()
    if len(items) == 0:
        print("Migrating CSV data to database...")
        success, message = migrate_csv_to_database(CSV_FILE)
        if success:
            print("CSV migration completed successfully!")
            # Rename CSV to mark as migrated
            os.rename(CSV_FILE, CSV_FILE + '.migrated')
        else:
            print(f"CSV migration failed: {message}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        user = get_user_by_username(session['user'])
        if not user or user['role'] != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def write_access_required(f):
    """Decorator to ensure user has write access (admin or trader roles only)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = get_user_by_username(session['user'])
        if not user:
            return jsonify({'error': 'User not found'}), 401
        # Only admin and trader have write access, ops is read-only
        if user['role'] not in ['admin', 'trader']:
            return jsonify({'error': 'You do not have permission to modify the inventory. Your role is read-only.'}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('login.html')

        success, message = verify_user_password(username, password)
        if success:
            session['user'] = username
            session.permanent = False
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('home'))
        else:
            flash(message, 'danger')
            return render_template('login.html')

    return render_template('login.html')

@app.route('/home')
@login_required
def home():
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'
    display_name = user['display_name'] if user and user['display_name'] else username
    return render_template('home.html', username=username, display_name=display_name, user_role=user_role)

@app.route('/dashboard')
@login_required
def dashboard():
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'
    display_name = user['display_name'] if user and user['display_name'] else username
    return render_template('dashboard.html', username=username, display_name=display_name, user_role=user_role)

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Get aggregated statistics for the dashboard"""
    try:
        items = get_all_inventory_items()
        group_by = request.args.get('group_by', 'Registry')

        # Valid grouping fields
        valid_fields = ['Registry', 'Market', 'Product', 'ProjectType', 'Protocol', 'IsCustody']
        if group_by not in valid_fields:
            group_by = 'Registry'

        # Aggregate counts by the specified field
        counts = {}
        for item in items:
            key = item.get(group_by, 'Unknown') or 'Unknown'
            counts[key] = counts.get(key, 0) + 1

        # Convert to chart-friendly format
        labels = list(counts.keys())
        values = list(counts.values())

        # Get total count
        total_count = len(items)

        return jsonify({
            'labels': labels,
            'values': values,
            'total': total_count,
            'group_by': group_by,
            'available_fields': valid_fields
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/warranty-gantt', methods=['GET'])
@login_required
def get_warranty_gantt_data():
    """Get warranty timeline data for Gantt chart visualization"""
    try:
        warranties = get_all_warranty_items()
        group_by_param = request.args.get('group_by', 'ProjectID')

        # Valid grouping fields for Gantt chart
        valid_fields = ['ProjectID', 'Registry', 'Market', 'Product', 'ProjectType', 'Protocol', 'Client', 'Side', 'OPL_TradeID']

        # Support multiple group_by fields separated by comma
        group_by_fields = [f.strip() for f in group_by_param.split(',') if f.strip() in valid_fields]
        if not group_by_fields:
            group_by_fields = ['ProjectID']

        today = datetime.now().date()

        # Filter out warranties without dates
        warranties = [w for w in warranties if w.get('Warranty_Start') and w.get('Warranty_End')]

        # Group warranties by the specified fields and aggregate volumes
        grouped_data = {}

        for warranty in warranties:
            # Build composite group key from multiple fields
            key_parts = []
            skip_item = False
            for field in group_by_fields:
                value = warranty.get(field)
                if not value or str(value).strip() == '':
                    skip_item = True
                    break
                key_parts.append(str(value).strip())

            if skip_item:
                continue

            group_key = ' | '.join(key_parts)
            warranty_start = warranty.get('Warranty_Start', '')
            warranty_end = warranty.get('Warranty_End', '')

            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    'periods': {},  # Dictionary to track unique warranty periods
                    'total_volume': 0
                }

            grouped_data[group_key]['total_volume'] += 1

            # Create a unique key for this warranty period
            period_key = f"{warranty_start}_{warranty_end}"

            if period_key not in grouped_data[group_key]['periods']:
                grouped_data[group_key]['periods'][period_key] = {
                    'start': warranty_start,
                    'end': warranty_end,
                    'volume': 0
                }

            grouped_data[group_key]['periods'][period_key]['volume'] += 1

        # Convert to list format for frontend
        gantt_items = []

        for group_key, data in grouped_data.items():
            for period_key, period_data in data['periods'].items():
                start_str = period_data['start']
                end_str = period_data['end']
                volume = period_data['volume']

                # Parse dates
                start_date = None
                end_date = None

                if start_str:
                    try:
                        start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
                    except:
                        try:
                            start_date = datetime.strptime(start_str, '%m/%d/%Y').date()
                        except:
                            pass

                if end_str:
                    try:
                        end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
                    except:
                        try:
                            end_date = datetime.strptime(end_str, '%m/%d/%Y').date()
                        except:
                            pass

                # Determine status based on warranty end date
                status = 'no-warranty'
                if start_date and end_date:
                    days_until_expiry = (end_date - today).days
                    if days_until_expiry < 0:
                        status = 'expired'
                    elif days_until_expiry <= 30:
                        status = 'expiring-30'
                    elif days_until_expiry <= 90:
                        status = 'expiring-90'
                    else:
                        status = 'active'

                gantt_items.append({
                    'label': group_key,
                    'start': start_str,
                    'end': end_str,
                    'volume': volume,
                    'total_group_volume': data['total_volume'],
                    'status': status
                })

        # Sort by label
        gantt_items.sort(key=lambda x: (x['label'], x['start'] or ''))

        # Calculate date range for timeline
        all_dates = []
        for item in gantt_items:
            if item['start']:
                try:
                    d = datetime.strptime(item['start'], '%Y-%m-%d').date()
                    all_dates.append(d)
                except:
                    try:
                        d = datetime.strptime(item['start'], '%m/%d/%Y').date()
                        all_dates.append(d)
                    except:
                        pass
            if item['end']:
                try:
                    d = datetime.strptime(item['end'], '%Y-%m-%d').date()
                    all_dates.append(d)
                except:
                    try:
                        d = datetime.strptime(item['end'], '%m/%d/%Y').date()
                        all_dates.append(d)
                    except:
                        pass

        # Default range if no dates found
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
        else:
            min_date = today
            max_date = today

        # Extend range by 1 month on each side
        from datetime import timedelta
        min_date = min_date.replace(day=1)
        max_date = (max_date.replace(day=1) + timedelta(days=32)).replace(day=1)

        return jsonify({
            'items': gantt_items,
            'min_date': min_date.isoformat(),
            'max_date': max_date.isoformat(),
            'today': today.isoformat(),
            'group_by': group_by_fields,
            'available_fields': valid_fields
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users')
@admin_required
def manage_users():
    username = session.get('user')
    users_from_db = get_all_users()
    user_list = []
    for user in users_from_db:
        user_list.append({
            'username': user['username'],
            'first_name': user['first_name'] or '',
            'last_name': user['last_name'] or '',
            'email': user['email'] or '',
            'display_name': user['display_name'] or '',
            'role': user['role'],
            'is_suspended': user['is_suspended']
        })
    return render_template('users.html', username=username, users=user_list)

@app.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    display_name = request.form.get('display_name', '').strip()
    role = request.form.get('role', 'user')

    if not username or not password:
        flash('Username and password are required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_add_user(username, password, first_name, last_name, email, display_name, role)
    if success:
        flash(f'User "{username}" has been created successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))

@app.route('/users/edit', methods=['POST'])
@admin_required
def edit_user():
    old_username = request.form.get('old_username', '').strip()
    new_username = request.form.get('username', '').strip()
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    display_name = request.form.get('display_name', '').strip()
    role = request.form.get('role', 'user')

    if not old_username or not new_username:
        flash('Username is required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_update_user(old_username, new_username, first_name, last_name, email, display_name, role)
    if success:
        flash(f'User "{new_username}" has been updated successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))

@app.route('/users/delete', methods=['POST'])
@admin_required
def delete_user():
    username = request.form.get('username', '').strip()
    current_user = session.get('user')

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_delete_user(username, current_user)
    if success:
        flash(f'User "{username}" has been deleted successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))

@app.route('/users/reset-password', methods=['POST'])
@admin_required
def reset_password():
    username = request.form.get('username', '').strip()
    new_password = request.form.get('new_password', '')

    if not username or not new_password:
        flash('Username and new password are required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_reset_password(username, new_password)
    if success:
        flash(f'Password for "{username}" has been reset successfully.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))

@app.route('/users/suspend', methods=['POST'])
@admin_required
def suspend_user():
    username = request.form.get('username', '').strip()
    current_user = session.get('user')

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_suspend_user(username, current_user)
    if success:
        flash(f'User "{username}" has been suspended.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))

@app.route('/users/unsuspend', methods=['POST'])
@admin_required
def unsuspend_user():
    username = request.form.get('username', '').strip()

    if not username:
        flash('Username is required.', 'danger')
        return redirect(url_for('manage_users'))

    success, message = db_unsuspend_user(username)
    if success:
        flash(f'User "{username}" has been unsuspended.', 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('manage_users'))


@app.route('/inventory')
@login_required
def inventory():
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    # Get user preferences with defaults
    view_mode = user['view_mode'] if user and user['view_mode'] else 'summarized'
    custody_view = user['custody_view'] if user and user['custody_view'] else 'all'
    rows_per_page = user['rows_per_page'] if user and user['rows_per_page'] else 'all'

    return render_template('inventory.html',
                         username=username,
                         user_role=user_role,
                         view_mode=view_mode,
                         custody_view=custody_view,
                         rows_per_page=rows_per_page)

@app.route('/api/inventory/get', methods=['GET'])
@login_required
def get_inventory():
    try:
        headers = get_inventory_headers()
        data = get_all_inventory_items()

        if not headers:
            # Return empty structure if no data
            return jsonify({'headers': [], 'data': []})

        return jsonify({'headers': headers, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/update', methods=['POST'])
@login_required
@write_access_required
def update_inventory():
    try:
        row_index = request.json.get('row_index')
        row_data = request.json.get('data')
        username = session.get('user')

        # Update item in database
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

@app.route('/api/inventory/add', methods=['POST'])
@login_required
@write_access_required
def add_inventory():
    try:
        row_data = request.json.get('data')
        username = session.get('user')

        # Add item to database
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

@app.route('/api/inventory/delete', methods=['POST'])
@login_required
@write_access_required
def delete_inventory():
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

        # Delete item from database
        success, message = delete_inventory_item(row_index)

        if not success:
            return jsonify({'error': message}), 404

        # Create backup after delete
        create_inventory_backup(username, f'Deleted item: {deleted_item}')

        return jsonify({'success': True, 'message': 'Item deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/validate-password', methods=['POST'])
@login_required
def validate_password():
    """Validate user password for sensitive operations"""
    try:
        username = session.get('user')
        password = request.json.get('password')

        if not password:
            return jsonify({'valid': False, 'error': 'Password is required'}), 400

        success, message = verify_user_password(username, password)

        if success:
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False, 'error': message}), 401
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500

@app.route('/api/verify-password', methods=['POST'])
@login_required
def verify_password_endpoint():
    """Verify user password for delete operations"""
    try:
        username = session.get('user')
        password = request.json.get('password')

        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        success, message = verify_user_password(username, password)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': message}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/bulk-delete', methods=['POST'])
@login_required
@write_access_required
def bulk_delete_inventory():
    """Bulk delete inventory items by serial numbers"""
    try:
        serials = request.json.get('serials', [])
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        # Get all inventory items
        items = get_all_inventory_items()

        # Find items to delete by serial
        items_to_delete = []
        for item in items:
            if item.get('Serial') in serials:
                items_to_delete.append(item)

        if not items_to_delete:
            return jsonify({'error': 'No matching items found'}), 404

        # Delete each item (this will also delete corresponding warranties)
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

@app.route('/api/inventory/commit-batch', methods=['POST'])
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

@app.route('/api/inventory/backups', methods=['GET'])
@admin_required
def list_backups():
    try:
        backups_data = get_all_inventory_backups()
        grouped_backups = {}

        for backup in backups_data:
            # Parse created_at timestamp
            created_at = backup['created_at']
            try:
                # Parse the UTC timestamp from database
                dt_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                # Make it timezone-aware (UTC)
                dt_utc = pytz.utc.localize(dt_utc)
                # Convert to Eastern Time
                eastern = pytz.timezone('US/Eastern')
                dt_eastern = dt_utc.astimezone(eastern)
                # Format in 12-hour format
                date_only = dt_eastern.strftime('%Y-%m-%d')
                time_only = dt_eastern.strftime('%I:%M:%S %p')  # 12-hour format with AM/PM
            except:
                date_only = 'Unknown'
                time_only = created_at

            backup_info = {
                'id': backup['id'],
                'filename': str(backup['id']),  # Frontend expects 'filename', use ID as string
                'date': created_at,
                'date_only': date_only,
                'time_only': time_only,
                'size': 0,  # Database backups don't have file size
                'username': backup['username'],
                'action': backup['action'],
                'summary': backup.get('summary', None)
            }

            # Group by date
            if date_only not in grouped_backups:
                grouped_backups[date_only] = []
            grouped_backups[date_only].append(backup_info)

        # Sort backups within each group by ID (newest first)
        for date in grouped_backups:
            grouped_backups[date].sort(key=lambda x: x['id'], reverse=True)

        # Sort dates (newest first)
        sorted_dates = sorted(grouped_backups.keys(), reverse=True)
        sorted_grouped = {date: grouped_backups[date] for date in sorted_dates}

        return jsonify({'backups': backups_data, 'grouped': sorted_grouped})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/restore', methods=['POST'])
@admin_required
def restore_backup():
    try:
        backup_id = request.json.get('filename')  # Frontend sends 'filename' but it's actually the ID
        username = session.get('user')

        if not backup_id:
            return jsonify({'error': 'Backup ID is required'}), 400

        # Try to parse as integer
        try:
            backup_id = int(backup_id)
        except:
            return jsonify({'error': 'Invalid backup ID'}), 400

        # Restore the backup
        success, message = restore_inventory_backup(backup_id)

        if not success:
            return jsonify({'error': message}), 404

        # Create a backup of the restored state
        create_inventory_backup(username, f'Restored from backup ID: {backup_id}')

        return jsonify({'success': True, 'message': 'Inventory restored successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/backup/delete', methods=['POST'])
@admin_required
def delete_backup():
    try:
        backup_id = request.json.get('filename')  # Frontend sends 'filename' but it's actually the ID

        if not backup_id:
            return jsonify({'error': 'Backup ID is required'}), 400

        # Try to parse as integer
        try:
            backup_id = int(backup_id)
        except:
            return jsonify({'error': 'Invalid backup ID'}), 400

        # Delete the backup
        success, message = delete_inventory_backup(backup_id)

        if not success:
            return jsonify({'error': message}), 404

        return jsonify({'success': True, 'message': 'Backup deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/backup/delete-date', methods=['POST'])
@admin_required
def delete_backups_by_date():
    try:
        date_to_delete = request.json.get('date')

        if not date_to_delete:
            return jsonify({'error': 'Date is required'}), 400

        backups = get_all_inventory_backups()
        deleted_count = 0

        for backup in backups:
            created_at = backup['created_at']
            try:
                dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                backup_date = dt.strftime('%Y-%m-%d')

                if backup_date == date_to_delete:
                    delete_inventory_backup(backup['id'])
                    deleted_count += 1
            except:
                continue

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} backup(s) from {date_to_delete}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Warranties Routes

@app.route('/warranties')
@login_required
def warranties():
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    # Get user preferences with defaults
    view_mode = user['warranty_view_mode'] if user and user['warranty_view_mode'] else 'summarized'
    custody_view = user['warranty_custody_view'] if user and user['warranty_custody_view'] else 'all'
    rows_per_page = user['warranty_rows_per_page'] if user and user['warranty_rows_per_page'] else 'all'

    return render_template('warranties.html',
                         username=username,
                         user_role=user_role,
                         view_mode=view_mode,
                         custody_view=custody_view,
                         rows_per_page=rows_per_page)

@app.route('/api/warranties/get', methods=['GET'])
@login_required
def get_warranties():
    try:
        headers = get_warranty_headers()
        data = get_all_warranty_items()

        if not headers:
            headers = ['Serial', 'Market', 'Registry', 'Product', 'ProjectID', 'ProjectType',
                      'Protocol', 'ProjectName', 'IsCustody', 'Warranty_Start', 'Warranty_End']

        return jsonify({'headers': headers, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/warranties/update', methods=['POST'])
@login_required
@write_access_required
def update_warranty():
    try:
        row_index = request.json.get('row_index')
        updates = request.json.get('updates')

        if row_index is None or not updates:
            return jsonify({'error': 'Missing row_index or updates'}), 400

        # Only allow updates to warranty fields (Warranty_Start, Warranty_End, OPL_TradeID, Client, Side)
        # Other fields come from inventory and cannot be edited here
        warranty_updates = {
            'Warranty_Start': updates.get('Warranty_Start', ''),
            'Warranty_End': updates.get('Warranty_End', ''),
            'OPL_TradeID': updates.get('OPL_TradeID', ''),
            'Client': updates.get('Client', ''),
            'Side': updates.get('Side', '')
        }

        success, message = update_warranty_item(row_index, warranty_updates)

        if success:
            return jsonify({'success': True, 'message': 'Warranty updated successfully'})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/warranties/add', methods=['POST'])
@login_required
@write_access_required
def add_warranty():
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

@app.route('/api/warranties/delete', methods=['POST'])
@login_required
@write_access_required
def delete_warranty():
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

@app.route('/api/warranties/commit-batch', methods=['POST'])
@login_required
@write_access_required
def commit_warranties_batch():
    try:
        modified = request.json.get('modified', {})
        added = request.json.get('added', [])
        deleted = request.json.get('deleted', [])

        # Process deletions
        for row_index in deleted:
            delete_warranty_item(row_index)

        # Process modifications (only warranty fields can be updated)
        for row_index_str, updates in modified.items():
            row_index = int(row_index_str)
            # Only extract warranty fields from updates
            warranty_updates = {
                'Warranty_Start': updates.get('Warranty_Start', ''),
                'Warranty_End': updates.get('Warranty_End', ''),
                'OPL_TradeID': updates.get('OPL_TradeID', ''),
                'Client': updates.get('Client', ''),
                'Side': updates.get('Side', '')
            }
            update_warranty_item(row_index, warranty_updates)

        # Process additions
        for item_data in added:
            add_warranty_item(item_data)

        return jsonify({'success': True, 'message': 'Batch committed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    username = session.get('user')
    user = get_user_by_username(username)

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        display_name = request.form.get('display_name', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        view_mode = request.form.get('view_mode', '')
        custody_view = request.form.get('custody_view', '')
        rows_per_page = request.form.get('rows_per_page', '')
        warranty_view_mode = request.form.get('warranty_view_mode', '')
        warranty_custody_view = request.form.get('warranty_custody_view', '')
        warranty_rows_per_page = request.form.get('warranty_rows_per_page', '')

        # Verify current password if trying to change password
        if new_password or confirm_password:
            if not current_password:
                flash('Please enter your current password to change your password.', 'danger')
                return render_template('settings.html', user=user)

            success, message = verify_user_password(username, current_password)
            if not success:
                flash('Current password is incorrect.', 'danger')
                return render_template('settings.html', user=user)

            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return render_template('settings.html', user=user)

            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return render_template('settings.html', user=user)

        # Update settings
        update_display_name = display_name if display_name else None
        update_password = new_password if new_password else None
        update_view_mode = view_mode if view_mode else None
        update_custody_view = custody_view if custody_view else None
        update_rows_per_page = rows_per_page if rows_per_page else None
        update_warranty_view_mode = warranty_view_mode if warranty_view_mode else None
        update_warranty_custody_view = warranty_custody_view if warranty_custody_view else None
        update_warranty_rows_per_page = warranty_rows_per_page if warranty_rows_per_page else None

        # Check if there are any changes
        has_changes = (update_display_name is not None or
                      update_password is not None or
                      update_view_mode is not None or
                      update_custody_view is not None or
                      update_rows_per_page is not None or
                      update_warranty_view_mode is not None or
                      update_warranty_custody_view is not None or
                      update_warranty_rows_per_page is not None)

        if not has_changes:
            flash('No changes to save.', 'warning')
            return render_template('settings.html', user=user)

        # Update user settings (display name and password)
        if update_display_name is not None or update_password is not None:
            success, message = update_user_settings(username, update_display_name, update_password)
            if not success:
                flash(f'Error: {message}', 'danger')
                return render_template('settings.html', user=user)

        # Update user preferences
        if (update_view_mode is not None or update_custody_view is not None or
            update_rows_per_page is not None or update_warranty_view_mode is not None or
            update_warranty_custody_view is not None or update_warranty_rows_per_page is not None):
            success, message = update_user_preferences(username, update_view_mode, update_custody_view,
                                                      update_rows_per_page, update_warranty_view_mode,
                                                      update_warranty_custody_view, update_warranty_rows_per_page)
            if not success:
                flash(f'Error: {message}', 'danger')
                return render_template('settings.html', user=user)

        flash('Settings updated successfully', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# User Page Settings API
@app.route('/api/settings/<page>', methods=['GET'])
@login_required
def get_page_settings(page):
    """Get user settings for a specific page"""
    try:
        username = session.get('user')
        settings = get_user_page_settings(username, page)
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/<page>', methods=['POST'])
@login_required
def save_page_settings(page):
    """Save user settings for a specific page"""
    try:
        username = session.get('user')
        settings = request.json

        if settings is None:
            return jsonify({'error': 'No settings provided'}), 400

        success, message = save_user_page_settings(username, page, settings)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
