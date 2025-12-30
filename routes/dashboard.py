"""
Dashboard and analytics routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from datetime import datetime, timedelta
from routes.auth import login_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_all_warranty_items
)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Display analytics dashboard"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'
    display_name = user['display_name'] if user and user['display_name'] else username
    return render_template('dashboard.html', username=username, display_name=display_name, user_role=user_role)


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Get aggregated statistics for the dashboard"""
    try:
        items = get_all_inventory_items()
        group_by_param = request.args.get('group_by', 'Registry')

        valid_fields = ['Registry', 'Market', 'Product', 'ProjectType', 'Protocol', 'Vintage', 'IsCustody']

        group_by_fields = [f.strip() for f in group_by_param.split(',') if f.strip() in valid_fields]
        if not group_by_fields:
            group_by_fields = ['Registry']

        total_count = len(items)

        if len(group_by_fields) > 1:
            # Build hierarchical structure for multi-level donut chart
            levels_data = []

            for level_idx, field in enumerate(group_by_fields):
                level_counts = {}
                for item in items:
                    key_parts = []
                    for i in range(level_idx + 1):
                        value = item.get(group_by_fields[i], 'Unknown') or 'Unknown'
                        key_parts.append(str(value).strip())
                    key = ' | '.join(key_parts)
                    level_counts[key] = level_counts.get(key, 0) + 1

                level_labels = list(level_counts.keys())
                level_values = list(level_counts.values())

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


def parse_date(date_str):
    """Helper function to parse dates in multiple formats"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        try:
            return datetime.strptime(date_str, '%m/%d/%Y').date()
        except:
            return None


def get_warranty_status(end_date, today):
    """Helper function to determine warranty status"""
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


@dashboard_bp.route('/api/dashboard/warranty-gantt', methods=['GET'])
@login_required
def get_warranty_gantt_data():
    """Get warranty timeline data for Gantt chart visualization"""
    try:
        warranties = get_all_warranty_items()
        group_by_param = request.args.get('group_by', 'ProjectID')

        valid_fields = ['ProjectID', 'Registry', 'Market', 'Product', 'ProjectType', 'Protocol',
                       'Vintage', 'Buy_Client', 'Sell_Client', 'Buy_TradeID', 'Sell_TradeID']

        group_by_fields = [f.strip() for f in group_by_param.split(',') if f.strip() in valid_fields]
        if not group_by_fields:
            group_by_fields = ['ProjectID']

        today = datetime.now().date()

        # Filter warranties that have at least one set of dates
        warranties = [w for w in warranties if (w.get('Buy_Start') and w.get('Buy_End')) or
                     (w.get('Sell_Start') and w.get('Sell_End'))]

        # Group warranties by the specified fields AND by serial_group
        grouped_data = {}

        for warranty in warranties:
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
                    'serial_groups': {},
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
                        'status': get_warranty_status(end_date, today),
                        'period_type': 'buy',
                        'serial_group': serial_group_idx
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
                        'status': get_warranty_status(end_date, today),
                        'period_type': 'sell',
                        'serial_group': serial_group_idx
                    })

        # Sort by label and serial_group
        gantt_items.sort(key=lambda x: (x['label'], x.get('serial_group', 0), x['start'] or ''))

        # Calculate date range for timeline
        all_dates = []
        for item in gantt_items:
            if item['start']:
                d = parse_date(item['start'])
                if d:
                    all_dates.append(d)
            if item['end']:
                d = parse_date(item['end'])
                if d:
                    all_dates.append(d)

        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
        else:
            min_date = today
            max_date = today

        # Extend range by 1 month on each side
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


@dashboard_bp.route('/api/dashboard/warranty-alerts', methods=['GET'])
@login_required
def get_warranty_alerts():
    """Get warranty alerts for upcoming and expiring warranties"""
    try:
        warranties = get_all_warranty_items()
        today = datetime.now().date()

        alerts = {
            'upcoming': [],
            'buy_expiring': [],
            'sell_expiring': [],
            'expired': []
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

        # Sort by date
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
