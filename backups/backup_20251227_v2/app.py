from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import secrets
import os
import json
from datetime import datetime
import pytz
import requests
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
        group_by_param = request.args.get('group_by', 'Registry')

        # Valid grouping fields
        valid_fields = ['Registry', 'Market', 'Product', 'ProjectType', 'Protocol', 'Vintage', 'IsCustody']

        # Support multiple group_by fields separated by comma
        group_by_fields = [f.strip() for f in group_by_param.split(',') if f.strip() in valid_fields]
        if not group_by_fields:
            group_by_fields = ['Registry']

        # Get total count
        total_count = len(items)

        # For multi-level donut chart, we need hierarchical data
        if len(group_by_fields) > 1:
            # Build hierarchical structure for each level
            levels_data = []

            for level_idx, field in enumerate(group_by_fields):
                # For each level, group by all fields up to and including this one
                level_counts = {}
                for item in items:
                    key_parts = []
                    for i in range(level_idx + 1):
                        value = item.get(group_by_fields[i], 'Unknown') or 'Unknown'
                        key_parts.append(str(value).strip())
                    key = ' | '.join(key_parts)
                    level_counts[key] = level_counts.get(key, 0) + 1

                # Convert to list format
                level_labels = list(level_counts.keys())
                level_values = list(level_counts.values())

                # For inner levels, we need parent info
                parent_map = {}
                if level_idx > 0:
                    for label in level_labels:
                        parts = label.split(' | ')
                        parent_key = ' | '.join(parts[:-1])
                        parent_map[label] = parent_key

                levels_data.append({
                    'field': field,
                    'labels': level_labels,
                    'values': level_values,
                    'parent_map': parent_map
                })

            # Also return flat data for compatibility
            flat_counts = {}
            for item in items:
                key_parts = []
                for field in group_by_fields:
                    value = item.get(field, 'Unknown') or 'Unknown'
                    key_parts.append(str(value).strip())
                key = ' | '.join(key_parts)
                flat_counts[key] = flat_counts.get(key, 0) + 1

            return jsonify({
                'labels': list(flat_counts.keys()),
                'values': list(flat_counts.values()),
                'total': total_count,
                'group_by': group_by_fields,
                'available_fields': valid_fields,
                'hierarchical': True,
                'levels': levels_data
            })
        else:
            # Single field - simple aggregation
            counts = {}
            for item in items:
                value = item.get(group_by_fields[0], 'Unknown') or 'Unknown'
                key = str(value).strip()
                counts[key] = counts.get(key, 0) + 1

            return jsonify({
                'labels': list(counts.keys()),
                'values': list(counts.values()),
                'total': total_count,
                'group_by': group_by_fields,
                'available_fields': valid_fields,
                'hierarchical': False
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
        valid_fields = ['ProjectID', 'Registry', 'Market', 'Product', 'ProjectType', 'Protocol', 'Vintage', 'Buy_Client', 'Sell_Client', 'Buy_TradeID', 'Sell_TradeID']

        # Support multiple group_by fields separated by comma
        group_by_fields = [f.strip() for f in group_by_param.split(',') if f.strip() in valid_fields]
        if not group_by_fields:
            group_by_fields = ['ProjectID']

        today = datetime.now().date()

        # Filter warranties that have at least one set of dates (Buy or Sell)
        warranties = [w for w in warranties if (w.get('Buy_Start') and w.get('Buy_End')) or (w.get('Sell_Start') and w.get('Sell_End'))]

        # Helper function to parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                try:
                    return datetime.strptime(date_str, '%m/%d/%Y').date()
                except:
                    return None

        # Helper function to determine status
        def get_status(end_date):
            if not end_date:
                return 'no-warranty'
            days_until_expiry = (end_date - today).days
            if days_until_expiry < 0:
                return 'expired'
            elif days_until_expiry <= 30:
                return 'expiring-30'
            elif days_until_expiry <= 90:
                return 'expiring-90'
            else:
                return 'active'

        # Group warranties by the specified fields AND by serial_group (Buy+Sell date combination)
        # This ensures bars from the same warranty batch stay together
        grouped_data = {}

        for warranty in warranties:
            # Build composite group key from multiple fields
            key_parts = []
            for field in group_by_fields:
                value = warranty.get(field)
                if not value or str(value).strip() == '':
                    key_parts.append('(Unspecified)')
                else:
                    key_parts.append(str(value).strip())

            group_key = ' | '.join(key_parts)

            # Create serial_group key from Buy+Sell date combination
            buy_start = warranty.get('Buy_Start', '') or ''
            buy_end = warranty.get('Buy_End', '') or ''
            sell_start = warranty.get('Sell_Start', '') or ''
            sell_end = warranty.get('Sell_End', '') or ''
            serial_group = f"{buy_start}|{buy_end}|{sell_start}|{sell_end}"

            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    'serial_groups': {},  # Dictionary to track unique serial groups
                    'total_volume': 0
                }

            grouped_data[group_key]['total_volume'] += 1

            if serial_group not in grouped_data[group_key]['serial_groups']:
                grouped_data[group_key]['serial_groups'][serial_group] = {
                    'buy_start': buy_start,
                    'buy_end': buy_end,
                    'sell_start': sell_start,
                    'sell_end': sell_end,
                    'volume': 0
                }
            grouped_data[group_key]['serial_groups'][serial_group]['volume'] += 1

        # Convert to list format for frontend
        gantt_items = []

        for group_key, data in grouped_data.items():
            # Process each serial group - Buy and Sell bars share the same serial_group index
            for serial_group_idx, (serial_group_key, sg_data) in enumerate(data['serial_groups'].items()):
                # Add Buy period if exists
                if sg_data['buy_start'] and sg_data['buy_end']:
                    end_date = parse_date(sg_data['buy_end'])
                    gantt_items.append({
                        'label': group_key,
                        'start': sg_data['buy_start'],
                        'end': sg_data['buy_end'],
                        'volume': sg_data['volume'],
                        'total_group_volume': data['total_volume'],
                        'status': get_status(end_date),
                        'period_type': 'buy',
                        'serial_group': serial_group_idx  # Numeric index - same for Buy and Sell
                    })

                # Add Sell period if exists
                if sg_data['sell_start'] and sg_data['sell_end']:
                    end_date = parse_date(sg_data['sell_end'])
                    gantt_items.append({
                        'label': group_key,
                        'start': sg_data['sell_start'],
                        'end': sg_data['sell_end'],
                        'volume': sg_data['volume'],
                        'total_group_volume': data['total_volume'],
                        'status': get_status(end_date),
                        'period_type': 'sell',
                        'serial_group': serial_group_idx  # Numeric index - same for Buy and Sell
                    })

        # Sort by label and serial_group
        gantt_items.sort(key=lambda x: (x['label'], x.get('serial_group', 0), x['start'] or ''))

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

@app.route('/api/dashboard/warranty-alerts', methods=['GET'])
@login_required
def get_warranty_alerts():
    """Get warranty alerts for upcoming and expiring warranties"""
    try:
        warranties = get_all_warranty_items()
        today = datetime.now().date()

        # Helper function to parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                try:
                    return datetime.strptime(date_str, '%m/%d/%Y').date()
                except:
                    return None

        alerts = {
            'upcoming': [],      # Buy warranties starting within 30 days
            'buy_expiring': [],  # Buy warranties expiring within 30 days
            'sell_expiring': [], # Sell warranties expiring within 30 days
            'expired': []        # Any warranties already expired (within last 7 days)
        }

        # Group by ProjectID to aggregate counts
        upcoming_groups = {}
        buy_expiring_groups = {}
        sell_expiring_groups = {}
        expired_groups = {}

        for warranty in warranties:
            project_id = warranty.get('ProjectID', 'Unknown')
            project_name = warranty.get('ProjectName', '')

            # Check Buy_Start for upcoming warranties
            buy_start = parse_date(warranty.get('Buy_Start'))
            if buy_start:
                days_until_start = (buy_start - today).days
                if 0 < days_until_start <= 30:
                    if project_id not in upcoming_groups:
                        upcoming_groups[project_id] = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'date': buy_start,
                            'count': 0,
                            'type': 'buy_start'
                        }
                    upcoming_groups[project_id]['count'] += 1
                    if buy_start < upcoming_groups[project_id]['date']:
                        upcoming_groups[project_id]['date'] = buy_start

            # Check Buy_End for buy warranty expiring
            buy_end = parse_date(warranty.get('Buy_End'))
            if buy_end:
                days_until_expiry = (buy_end - today).days
                if days_until_expiry < 0 and days_until_expiry >= -7:
                    # Buy expired within last 7 days
                    key = f"{project_id}_buy"
                    if key not in expired_groups:
                        expired_groups[key] = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'date': buy_end,
                            'count': 0,
                            'type': 'buy_expired',
                            'period': 'Buy'
                        }
                    expired_groups[key]['count'] += 1
                elif 0 <= days_until_expiry <= 30:
                    # Buy expiring within 30 days
                    if project_id not in buy_expiring_groups:
                        buy_expiring_groups[project_id] = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'date': buy_end,
                            'count': 0,
                            'type': 'buy_expiring'
                        }
                    buy_expiring_groups[project_id]['count'] += 1
                    if buy_end < buy_expiring_groups[project_id]['date']:
                        buy_expiring_groups[project_id]['date'] = buy_end

            # Check Sell_End for sell warranty expiring/expired
            sell_end = parse_date(warranty.get('Sell_End'))
            if sell_end:
                days_until_expiry = (sell_end - today).days
                if days_until_expiry < 0 and days_until_expiry >= -7:
                    # Sell expired within last 7 days
                    key = f"{project_id}_sell"
                    if key not in expired_groups:
                        expired_groups[key] = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'date': sell_end,
                            'count': 0,
                            'type': 'sell_expired',
                            'period': 'Sell'
                        }
                    expired_groups[key]['count'] += 1
                elif 0 <= days_until_expiry <= 30:
                    # Sell expiring within 30 days
                    if project_id not in sell_expiring_groups:
                        sell_expiring_groups[project_id] = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'date': sell_end,
                            'count': 0,
                            'type': 'sell_expiring'
                        }
                    sell_expiring_groups[project_id]['count'] += 1
                    if sell_end < sell_expiring_groups[project_id]['date']:
                        sell_expiring_groups[project_id]['date'] = sell_end

        # Convert to lists and sort by date
        for group in upcoming_groups.values():
            alerts['upcoming'].append({
                'project_id': group['project_id'],
                'project_name': group['project_name'],
                'date': group['date'].isoformat(),
                'count': group['count'],
                'days': (group['date'] - today).days,
                'type': group['type']
            })

        for group in buy_expiring_groups.values():
            alerts['buy_expiring'].append({
                'project_id': group['project_id'],
                'project_name': group['project_name'],
                'date': group['date'].isoformat(),
                'count': group['count'],
                'days': (group['date'] - today).days,
                'type': group['type']
            })

        for group in sell_expiring_groups.values():
            alerts['sell_expiring'].append({
                'project_id': group['project_id'],
                'project_name': group['project_name'],
                'date': group['date'].isoformat(),
                'count': group['count'],
                'days': (group['date'] - today).days,
                'type': group['type']
            })

        for group in expired_groups.values():
            alerts['expired'].append({
                'project_id': group['project_id'],
                'project_name': group['project_name'],
                'date': group['date'].isoformat(),
                'count': group['count'],
                'days': (group['date'] - today).days,
                'type': group['type'],
                'period': group.get('period', '')
            })

        # Sort by date (ascending for upcoming/expiring, descending for expired)
        alerts['upcoming'].sort(key=lambda x: x['date'])
        alerts['buy_expiring'].sort(key=lambda x: x['date'])
        alerts['sell_expiring'].sort(key=lambda x: x['date'])
        alerts['expired'].sort(key=lambda x: x['date'], reverse=True)

        # Limit to top 5 each
        alerts['upcoming'] = alerts['upcoming'][:5]
        alerts['buy_expiring'] = alerts['buy_expiring'][:5]
        alerts['sell_expiring'] = alerts['sell_expiring'][:5]
        alerts['expired'] = alerts['expired'][:5]

        return jsonify({
            'alerts': alerts,
            'counts': {
                'upcoming': len(upcoming_groups),
                'buy_expiring': len(buy_expiring_groups),
                'sell_expiring': len(sell_expiring_groups),
                'expired': len(expired_groups)
            }
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

@app.route('/api/warranties/get', methods=['GET'])
@login_required
def get_warranties():
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

@app.route('/api/warranties/update', methods=['POST'])
@login_required
@write_access_required
def update_warranty():
    try:
        row_index = request.json.get('row_index')
        updates = request.json.get('updates')

        if row_index is None or not updates:
            return jsonify({'error': 'Missing row_index or updates'}), 400

        # Only allow updates to warranty fields (Buy_Start, Buy_End, Sell_Start, Sell_End, Buy_TradeID, Sell_TradeID, Buy_Client, Sell_Client)
        # Other fields come from inventory and cannot be edited here
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

# Registry Data Routes

@app.route('/registry-data')
@login_required
def registry_data():
    return render_template('registry_data.html')

@app.route('/api/registry/search', methods=['GET'])
@login_required
def search_registry():
    """Search a carbon credit registry for projects"""
    registry = request.args.get('registry', 'verra')
    search_type = request.args.get('type', 'id')
    query = request.args.get('query', '')

    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    try:
        if registry == 'verra':
            results = search_verra(query, search_type)
        elif registry == 'goldstandard':
            results = search_goldstandard(query, search_type)
        elif registry == 'acr':
            results = search_acr(query, search_type)
        elif registry == 'car':
            results = search_car(query, search_type)
        else:
            return jsonify({'error': 'Unknown registry'}), 400

        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/registry/project', methods=['GET'])
@login_required
def get_registry_project():
    """Get detailed project information from a registry"""
    registry = request.args.get('registry', 'verra')
    project_id = request.args.get('projectId', '')

    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400

    try:
        if registry == 'verra':
            project = get_verra_project(project_id)
        elif registry == 'goldstandard':
            project = get_goldstandard_project(project_id)
        elif registry == 'acr':
            project = get_acr_project(project_id)
        elif registry == 'car':
            project = get_car_project(project_id)
        else:
            return jsonify({'error': 'Unknown registry'}), 400

        return jsonify({'project': project})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Verra Registry Functions
def search_verra(query, search_type):
    """Search Verra VCS registry using POST API"""
    try:
        url = 'https://registry.verra.org/uiapi/resource/resource/search?$skip=0&$top=50&$count=true'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Build search payload
        if search_type == 'id':
            payload = {
                "program": "VCS",
                "resourceIdentifier": query
            }
        else:
            payload = {
                "program": "VCS",
                "resourceName": query
            }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = []

            items = data.get('value', data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                items = items.get('value', [])

            for item in items:
                results.append(extract_verra_fields(item))

            return results
        else:
            print(f"Verra API returned status {response.status_code}: {response.text[:200]}")
            return []
    except Exception as e:
        print(f"Verra search error: {e}")
        return []

def extract_verra_fields(item):
    """Extract all available fields from Verra API response"""
    project_id = str(item.get('resourceIdentifier', item.get('id', '')))
    return {
        # Basic Info
        'projectId': project_id,
        'name': item.get('resourceName', item.get('name', '')),
        'status': item.get('resourceStatus', item.get('status', '')),
        'program': item.get('program', 'VCS'),

        # Location
        'country': item.get('country', item.get('countryName', '')),
        'region': item.get('region', item.get('regionName', '')),

        # Project Details
        'projectType': item.get('projectType', item.get('type', '')),
        'methodology': item.get('methodology', item.get('protocolCategory', '')),
        'protocol': item.get('protocolCategory', item.get('protocol', '')),
        'sectorialScope': item.get('sectorialScope', item.get('sectoralScope', '')),

        # Proponent/Developer
        'proponent': item.get('proponent', item.get('proponentName', '')),
        'developer': item.get('projectDeveloper', item.get('developer', '')),

        # Credits
        'creditsIssued': item.get('totalVintageQuantity', item.get('issuedCredits', 0)),
        'creditsRetired': item.get('totalRetiredQuantity', item.get('retiredCredits', 0)),
        'creditsAvailable': item.get('totalAvailableQuantity', item.get('availableCredits', 0)),
        'creditsCancelled': item.get('totalCancelledQuantity', 0),
        'estimatedAnnualReductions': item.get('estimatedAnnualEmissionReductions', item.get('annualEmissionReductions', '')),

        # Dates
        'creditingPeriodStart': item.get('creditingPeriodStartDate', item.get('creditStartDate', '')),
        'creditingPeriodEnd': item.get('creditingPeriodEndDate', item.get('creditEndDate', '')),
        'registrationDate': item.get('registrationDate', ''),
        'validationDate': item.get('validationDate', ''),
        'verificationDate': item.get('verificationDate', ''),
        'firstIssuanceDate': item.get('firstIssuanceDate', ''),

        # Additional Info
        'additionalCertifications': item.get('additionalCertifications', item.get('ccbStandards', '')),
        'corsia': item.get('corsiaEligible', item.get('corsia', '')),
        'sdgGoals': item.get('sdgGoals', item.get('sustainableDevelopmentGoals', '')),
        'description': item.get('description', item.get('projectDescription', '')),

        # Registry URL
        'registryUrl': f"https://registry.verra.org/app/projectDetail/VCS/{project_id}"
    }

def get_verra_project(project_id):
    """Get detailed Verra project information"""
    try:
        # First try direct project lookup
        url = f'https://registry.verra.org/uiapi/resource/resource/search?$skip=0&$top=1&$count=true'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        payload = {
            "program": "VCS",
            "resourceIdentifier": str(project_id)
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            items = data.get('value', []) if isinstance(data, dict) else data

            if items and len(items) > 0:
                return extract_verra_fields(items[0])
            else:
                return {'error': 'Project not found', 'projectId': project_id}
        else:
            return {'error': f'API returned status {response.status_code}', 'projectId': project_id}
    except Exception as e:
        return {'error': str(e), 'projectId': project_id}

# Gold Standard Registry Functions
def search_goldstandard(query, search_type):
    """Search Gold Standard registry"""
    try:
        # Gold Standard API
        if search_type == 'id':
            url = f'https://registry.goldstandard.org/projects?q={query}&page=1'
        else:
            url = f'https://registry.goldstandard.org/projects?q={query}&page=1'

        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CarbonIMS/1.0'
        }

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = []

            items = data.get('data', [])
            for item in items:
                results.append({
                    'projectId': str(item.get('id', '')),
                    'name': item.get('name', ''),
                    'status': item.get('status', ''),
                    'country': item.get('country', {}).get('name', '') if isinstance(item.get('country'), dict) else '',
                    'type': item.get('type', {}).get('name', '') if isinstance(item.get('type'), dict) else '',
                    'creditsIssued': item.get('credits_issued', 0),
                    'registryUrl': f"https://registry.goldstandard.org/projects/details/{item.get('id', '')}"
                })

            return results
        else:
            return []
    except Exception as e:
        print(f"Gold Standard search error: {e}")
        return []

def get_goldstandard_project(project_id):
    """Get detailed Gold Standard project information"""
    try:
        url = f'https://registry.goldstandard.org/projects/details/{project_id}'
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'CarbonIMS/1.0'
        }

        # Try API endpoint first
        api_url = f'https://registry.goldstandard.org/projects/{project_id}'
        response = requests.get(api_url, headers=headers, timeout=30)

        if response.status_code == 200:
            item = response.json()
            data = item.get('data', item)
            return {
                'projectId': str(data.get('id', '')),
                'name': data.get('name', ''),
                'status': data.get('status', ''),
                'country': data.get('country', {}).get('name', '') if isinstance(data.get('country'), dict) else '',
                'region': data.get('region', ''),
                'protocol': data.get('methodology', {}).get('name', '') if isinstance(data.get('methodology'), dict) else '',
                'type': data.get('type', {}).get('name', '') if isinstance(data.get('type'), dict) else '',
                'developer': data.get('developer', {}).get('name', '') if isinstance(data.get('developer'), dict) else '',
                'creditsIssued': data.get('credits_issued', 0),
                'creditsRetired': data.get('credits_retired', 0),
                'creditsAvailable': data.get('credits_available', 0),
                'creditingPeriodStart': data.get('crediting_period_start', ''),
                'creditingPeriodEnd': data.get('crediting_period_end', ''),
                'registrationDate': data.get('registration_date', ''),
                'description': data.get('description', '')
            }
        else:
            return {'error': 'Project not found'}
    except Exception as e:
        return {'error': str(e)}

# ACR Registry Functions
def search_acr(query, search_type):
    """Search American Carbon Registry"""
    try:
        # ACR uses APX system - their API is not fully public
        # Provide direct link to their registry search
        results = [{
            'projectId': query,
            'name': f'Search "{query}" on ACR Registry',
            'status': 'See Registry',
            'developer': '',
            'protocol': '',
            'registryUrl': f'https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
        }]
        return results
    except Exception as e:
        print(f"ACR search error: {e}")
        return []

def get_acr_project(project_id):
    """Get ACR project - redirect to registry"""
    return {
        'projectId': project_id,
        'name': 'View on ACR Registry',
        'status': 'See registry for details',
        'registryUrl': f'https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
    }

# CAR Registry Functions
def search_car(query, search_type):
    """Search Climate Action Reserve"""
    try:
        # CAR also uses APX system
        results = [{
            'projectId': query,
            'name': f'Search "{query}" on CAR Registry',
            'status': 'See Registry',
            'developer': '',
            'protocol': '',
            'registryUrl': f'https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
        }]
        return results
    except Exception as e:
        print(f"CAR search error: {e}")
        return []

def get_car_project(project_id):
    """Get CAR project - redirect to registry"""
    return {
        'projectId': project_id,
        'name': 'View on CAR Registry',
        'status': 'See registry for details',
        'registryUrl': f'https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&TabName=Projects'
    }

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
