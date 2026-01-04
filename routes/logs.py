"""
Activity Logs routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, admin_required, page_access_required
from database import (
    get_user_by_username,
    get_activity_logs,
    get_activity_log_by_id,
    get_activity_log_stats,
    get_distinct_log_values,
    mark_activity_reverted,
    clear_activity_reverted,
    log_activity,
    get_inventory_db_connection,
    get_all_inventory_items,
    add_inventory_item,
    delete_inventory_item,
    update_inventory_item
)

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/logs')
@login_required
@page_access_required('logs')
def logs_page():
    """Display activity logs page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    return render_template('logs.html',
                         username=username,
                         user_role=user_role)


@logs_bp.route('/api/logs', methods=['GET'])
@login_required
def get_logs():
    """Get activity logs with optional filters"""
    try:
        # Build filters from query params
        filters = {}

        if request.args.get('username'):
            filters['username'] = request.args.get('username')
        if request.args.get('action_type'):
            filters['action_type'] = request.args.get('action_type')
        if request.args.get('target_type'):
            filters['target_type'] = request.args.get('target_type')
        if request.args.get('date_from'):
            filters['date_from'] = request.args.get('date_from')
        if request.args.get('date_to'):
            filters['date_to'] = request.args.get('date_to')
        if request.args.get('serial'):
            filters['serial'] = request.args.get('serial')
        if request.args.get('is_reverted'):
            filters['is_reverted'] = request.args.get('is_reverted') == 'true'

        limit = int(request.args.get('limit', 500))
        offset = int(request.args.get('offset', 0))

        logs = get_activity_logs(filters if filters else None, limit, offset)

        return jsonify({
            'success': True,
            'logs': logs,
            'count': len(logs)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@logs_bp.route('/api/logs/stats', methods=['GET'])
@login_required
def get_logs_stats():
    """Get activity log statistics"""
    try:
        stats = get_activity_log_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@logs_bp.route('/api/logs/filters', methods=['GET'])
@login_required
def get_filter_options():
    """Get distinct values for filter dropdowns"""
    try:
        values = get_distinct_log_values()
        return jsonify({'success': True, 'filters': values})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@logs_bp.route('/api/logs/<int:log_id>', methods=['GET'])
@login_required
def get_log_detail(log_id):
    """Get details of a specific log entry"""
    try:
        log = get_activity_log_by_id(log_id)
        if not log:
            return jsonify({'error': 'Log entry not found'}), 404

        return jsonify({'success': True, 'log': log})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@logs_bp.route('/api/logs/revert/<int:log_id>', methods=['POST'])
@login_required
@admin_required
def revert_log(log_id):
    """Revert a specific action (admin only)"""
    try:
        username = session.get('user')
        log = get_activity_log_by_id(log_id)

        if not log:
            return jsonify({'error': 'Log entry not found'}), 404

        if log['is_reverted']:
            return jsonify({'error': 'This action has already been reverted'}), 400

        # Check if this action can be reverted
        action_type = log['action_type']
        target_type = log['target_type']

        revertable_actions = ['add', 'update', 'delete', 'import']
        if action_type not in revertable_actions:
            return jsonify({'error': f'Action type "{action_type}" cannot be reverted'}), 400

        # Perform the revert based on action type
        revert_success = False
        revert_message = ''

        if target_type == 'inventory':
            revert_success, revert_message = revert_inventory_action(log, username)
        elif target_type == 'warranty':
            revert_success, revert_message = revert_warranty_action(log, username)
        else:
            return jsonify({'error': f'Cannot revert actions on "{target_type}"'}), 400

        if revert_success:
            # Mark the log as reverted
            mark_activity_reverted(log_id, username)

            # Log the revert action
            log_activity(
                username=username,
                action_type='revert',
                target_type=target_type,
                target_id=log.get('target_id'),
                serial=log.get('serial'),
                details=f"Reverted action: {action_type} (Log ID: {log_id})"
            )

            return jsonify({
                'success': True,
                'message': revert_message
            })
        else:
            return jsonify({'error': revert_message}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def revert_inventory_action(log, username):
    """Revert an inventory action"""
    action_type = log['action_type']
    before_data = log.get('before_data')
    after_data = log.get('after_data')
    serial = log.get('serial')

    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        if action_type == 'add':
            # Revert add by deleting the item
            if serial:
                cursor.execute("DELETE FROM inventory WHERE serial = ?", (serial,))
                cursor.execute("DELETE FROM warranties WHERE serial = ?", (serial,))
                conn.commit()
                conn.close()
                return True, f"Reverted: Deleted added item with Serial {serial}"
            else:
                conn.close()
                return False, "Cannot revert: No serial number recorded"

        elif action_type == 'delete':
            # Revert delete by re-adding the item from before_data
            if before_data:
                # Re-insert the inventory item
                cursor.execute("""
                    INSERT INTO inventory (market, registry, product, project_id, project_type,
                                         protocol, project_name, vintage, serial, is_custody,
                                         is_assigned, trade_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    before_data.get('Market', ''),
                    before_data.get('Registry', ''),
                    before_data.get('Product', ''),
                    before_data.get('ProjectID', ''),
                    before_data.get('ProjectType', ''),
                    before_data.get('Protocol', ''),
                    before_data.get('ProjectName', ''),
                    before_data.get('Vintage', ''),
                    before_data.get('Serial', serial),
                    before_data.get('IsCustody', ''),
                    1 if before_data.get('IsAssigned') in ['True', 'true', '1', True] else 0,
                    before_data.get('TradeID', '')
                ))
                # Also create warranty record
                cursor.execute("INSERT OR IGNORE INTO warranties (serial) VALUES (?)",
                             (before_data.get('Serial', serial),))
                conn.commit()
                conn.close()
                return True, f"Reverted: Restored deleted item with Serial {serial}"
            else:
                conn.close()
                return False, "Cannot revert: No backup data recorded"

        elif action_type == 'update':
            # Revert update by restoring before_data
            if before_data and serial:
                cursor.execute("""
                    UPDATE inventory SET
                        market = ?, registry = ?, product = ?, project_id = ?,
                        project_type = ?, protocol = ?, project_name = ?, vintage = ?,
                        is_custody = ?, is_assigned = ?, trade_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE serial = ?
                """, (
                    before_data.get('Market', ''),
                    before_data.get('Registry', ''),
                    before_data.get('Product', ''),
                    before_data.get('ProjectID', ''),
                    before_data.get('ProjectType', ''),
                    before_data.get('Protocol', ''),
                    before_data.get('ProjectName', ''),
                    before_data.get('Vintage', ''),
                    before_data.get('IsCustody', ''),
                    1 if before_data.get('IsAssigned') in ['True', 'true', '1', True] else 0,
                    before_data.get('TradeID', ''),
                    serial
                ))
                conn.commit()
                conn.close()
                return True, f"Reverted: Restored previous values for Serial {serial}"
            else:
                conn.close()
                return False, "Cannot revert: No backup data or serial recorded"

        elif action_type == 'import':
            # Revert import - this is complex, suggest using backup restore instead
            conn.close()
            return False, "Import actions should be reverted using the Backup Restore feature"

        conn.close()
        return False, f"Unknown action type: {action_type}"

    except Exception as e:
        return False, str(e)


def revert_warranty_action(log, username):
    """Revert a warranty action"""
    action_type = log['action_type']
    before_data = log.get('before_data')
    serial = log.get('serial')

    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        if action_type == 'update' and before_data and serial:
            cursor.execute("""
                UPDATE warranties SET
                    buy_start = ?, buy_end = ?, sell_start = ?, sell_end = ?,
                    buy_tradeid = ?, sell_tradeid = ?, buy_client = ?, sell_client = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE serial = ?
            """, (
                before_data.get('buy_start', ''),
                before_data.get('buy_end', ''),
                before_data.get('sell_start', ''),
                before_data.get('sell_end', ''),
                before_data.get('buy_tradeid'),
                before_data.get('sell_tradeid'),
                before_data.get('buy_client', ''),
                before_data.get('sell_client', ''),
                serial
            ))
            conn.commit()
            conn.close()
            return True, f"Reverted: Restored warranty values for Serial {serial}"

        conn.close()
        return False, "Cannot revert warranty action: Missing data"

    except Exception as e:
        return False, str(e)


@logs_bp.route('/api/logs/redo/<int:log_id>', methods=['POST'])
@login_required
@admin_required
def redo_log(log_id):
    """Redo a previously undone action (admin only)"""
    try:
        username = session.get('user')
        log = get_activity_log_by_id(log_id)

        if not log:
            return jsonify({'error': 'Log entry not found'}), 404

        if not log['is_reverted']:
            return jsonify({'error': 'This action has not been undone'}), 400

        # Check if this action can be redone
        action_type = log['action_type']
        target_type = log['target_type']

        redoable_actions = ['add', 'update', 'delete']
        if action_type not in redoable_actions:
            return jsonify({'error': f'Action type "{action_type}" cannot be redone'}), 400

        # Perform the redo based on action type
        redo_success = False
        redo_message = ''

        if target_type == 'inventory':
            redo_success, redo_message = redo_inventory_action(log, username)
        elif target_type == 'warranty':
            redo_success, redo_message = redo_warranty_action(log, username)
        else:
            return jsonify({'error': f'Cannot redo actions on "{target_type}"'}), 400

        if redo_success:
            # Mark the log as no longer reverted (clear the reverted status)
            clear_activity_reverted(log_id)

            # Log the redo action
            log_activity(
                username=username,
                action_type='redo',
                target_type=target_type,
                target_id=log.get('target_id'),
                serial=log.get('serial'),
                details=f"Redone action: {action_type} (Log ID: {log_id})"
            )

            return jsonify({
                'success': True,
                'message': redo_message
            })
        else:
            return jsonify({'error': redo_message}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def redo_inventory_action(log, username):
    """Redo an inventory action (re-apply the original action)"""
    action_type = log['action_type']
    before_data = log.get('before_data')
    after_data = log.get('after_data')
    serial = log.get('serial')

    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        if action_type == 'add':
            # Redo add by re-inserting the item from after_data
            if after_data and serial:
                cursor.execute("""
                    INSERT INTO inventory (market, registry, product, project_id, project_type,
                                         protocol, project_name, vintage, serial, is_custody,
                                         is_assigned, trade_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    after_data.get('Market', after_data.get('market', '')),
                    after_data.get('Registry', after_data.get('registry', '')),
                    after_data.get('Product', after_data.get('product', '')),
                    after_data.get('ProjectID', after_data.get('project_id', '')),
                    after_data.get('ProjectType', after_data.get('project_type', '')),
                    after_data.get('Protocol', after_data.get('protocol', '')),
                    after_data.get('ProjectName', after_data.get('project_name', '')),
                    after_data.get('Vintage', after_data.get('vintage', '')),
                    serial,
                    after_data.get('IsCustody', after_data.get('is_custody', '')),
                    1 if after_data.get('IsAssigned', after_data.get('is_assigned')) in ['True', 'true', '1', True] else 0,
                    after_data.get('TradeID', after_data.get('trade_id', ''))
                ))
                cursor.execute("INSERT OR IGNORE INTO warranties (serial) VALUES (?)", (serial,))
                conn.commit()
                conn.close()
                return True, f"Redone: Re-added item with Serial {serial}"
            else:
                conn.close()
                return False, "Cannot redo: No data recorded"

        elif action_type == 'delete':
            # Redo delete by deleting the item again
            if serial:
                cursor.execute("DELETE FROM inventory WHERE serial = ?", (serial,))
                cursor.execute("DELETE FROM warranties WHERE serial = ?", (serial,))
                conn.commit()
                conn.close()
                return True, f"Redone: Deleted item with Serial {serial}"
            else:
                conn.close()
                return False, "Cannot redo: No serial number recorded"

        elif action_type == 'update':
            # Redo update by applying after_data
            if after_data and serial:
                cursor.execute("""
                    UPDATE inventory SET
                        market = ?, registry = ?, product = ?, project_id = ?,
                        project_type = ?, protocol = ?, project_name = ?, vintage = ?,
                        is_custody = ?, is_assigned = ?, trade_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE serial = ?
                """, (
                    after_data.get('Market', after_data.get('market', '')),
                    after_data.get('Registry', after_data.get('registry', '')),
                    after_data.get('Product', after_data.get('product', '')),
                    after_data.get('ProjectID', after_data.get('project_id', '')),
                    after_data.get('ProjectType', after_data.get('project_type', '')),
                    after_data.get('Protocol', after_data.get('protocol', '')),
                    after_data.get('ProjectName', after_data.get('project_name', '')),
                    after_data.get('Vintage', after_data.get('vintage', '')),
                    after_data.get('IsCustody', after_data.get('is_custody', '')),
                    1 if after_data.get('IsAssigned', after_data.get('is_assigned')) in ['True', 'true', '1', True] else 0,
                    after_data.get('TradeID', after_data.get('trade_id', '')),
                    serial
                ))
                conn.commit()
                conn.close()
                return True, f"Redone: Re-applied changes to Serial {serial}"
            else:
                conn.close()
                return False, "Cannot redo: No data or serial recorded"

        conn.close()
        return False, f"Unknown action type: {action_type}"

    except Exception as e:
        return False, str(e)


def redo_warranty_action(log, username):
    """Redo a warranty action (re-apply the original action)"""
    action_type = log['action_type']
    after_data = log.get('after_data')
    serial = log.get('serial')

    try:
        conn = get_inventory_db_connection()
        cursor = conn.cursor()

        if action_type == 'update' and after_data and serial:
            cursor.execute("""
                UPDATE warranties SET
                    buy_start = ?, buy_end = ?, sell_start = ?, sell_end = ?,
                    buy_tradeid = ?, sell_tradeid = ?, buy_client = ?, sell_client = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE serial = ?
            """, (
                after_data.get('Buy_Start', after_data.get('buy_start', '')),
                after_data.get('Buy_End', after_data.get('buy_end', '')),
                after_data.get('Sell_Start', after_data.get('sell_start', '')),
                after_data.get('Sell_End', after_data.get('sell_end', '')),
                after_data.get('Buy_TradeID', after_data.get('buy_tradeid')),
                after_data.get('Sell_TradeID', after_data.get('sell_tradeid')),
                after_data.get('Buy_Client', after_data.get('buy_client', '')),
                after_data.get('Sell_Client', after_data.get('sell_client', '')),
                serial
            ))
            conn.commit()
            conn.close()
            return True, f"Redone: Re-applied warranty changes for Serial {serial}"

        conn.close()
        return False, "Cannot redo warranty action: Missing data"

    except Exception as e:
        return False, str(e)
