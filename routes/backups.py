"""
Backup and restore routes for Carbon IMS
"""

from flask import Blueprint, request, session, jsonify
from datetime import datetime
import pytz
from routes.auth import admin_required
from database import (
    get_all_inventory_backups,
    restore_inventory_backup,
    delete_inventory_backup,
    create_inventory_backup
)

backups_bp = Blueprint('backups', __name__)


@backups_bp.route('/api/inventory/backups', methods=['GET'])
@admin_required
def list_backups():
    """List all inventory backups grouped by date"""
    try:
        backups_data = get_all_inventory_backups()
        grouped_backups = {}

        for backup in backups_data:
            created_at = backup['created_at']
            try:
                # Parse the UTC timestamp from database
                dt_utc = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                dt_utc = pytz.utc.localize(dt_utc)
                # Convert to Eastern Time
                eastern = pytz.timezone('US/Eastern')
                dt_eastern = dt_utc.astimezone(eastern)
                # Format in 12-hour format
                date_only = dt_eastern.strftime('%Y-%m-%d')
                time_only = dt_eastern.strftime('%I:%M:%S %p')
            except:
                date_only = 'Unknown'
                time_only = created_at

            backup_info = {
                'id': backup['id'],
                'filename': str(backup['id']),
                'date': created_at,
                'date_only': date_only,
                'time_only': time_only,
                'size': 0,
                'username': backup['username'],
                'action': backup['action'],
                'summary': backup.get('summary', None)
            }

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


@backups_bp.route('/api/inventory/restore', methods=['POST'])
@admin_required
def restore_backup():
    """Restore inventory from a backup"""
    try:
        backup_id = request.json.get('filename')
        username = session.get('user')

        if not backup_id:
            return jsonify({'error': 'Backup ID is required'}), 400

        try:
            backup_id = int(backup_id)
        except:
            return jsonify({'error': 'Invalid backup ID'}), 400

        success, message = restore_inventory_backup(backup_id)

        if not success:
            return jsonify({'error': message}), 404

        # Create a backup of the restored state
        create_inventory_backup(username, f'Restored from backup ID: {backup_id}')

        return jsonify({'success': True, 'message': 'Inventory restored successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@backups_bp.route('/api/inventory/backup/delete', methods=['POST'])
@admin_required
def delete_backup():
    """Delete a specific backup"""
    try:
        backup_id = request.json.get('filename')

        if not backup_id:
            return jsonify({'error': 'Backup ID is required'}), 400

        try:
            backup_id = int(backup_id)
        except:
            return jsonify({'error': 'Invalid backup ID'}), 400

        success, message = delete_inventory_backup(backup_id)

        if not success:
            return jsonify({'error': message}), 404

        return jsonify({'success': True, 'message': 'Backup deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@backups_bp.route('/api/inventory/backup/delete-date', methods=['POST'])
@admin_required
def delete_backups_by_date():
    """Delete all backups from a specific date"""
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
