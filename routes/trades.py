"""
Trades management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, write_access_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_unassigned_inventory,
    get_inventory_by_trade,
    assign_inventory_to_trade,
    unassign_inventory_from_trade,
    create_serials_for_trade
)
from trades_data import get_trades_dataframe, get_trade_by_id, get_trade_headers

trades_bp = Blueprint('trades', __name__)


@trades_bp.route('/trades')
@login_required
def trades():
    """Display trades management page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'
    return render_template('trades.html', username=username, user_role=user_role)


@trades_bp.route('/api/trades/get', methods=['GET'])
@login_required
def get_trades():
    """Get all trades from external data source"""
    try:
        trades_list = get_trades_dataframe()
        headers = get_trade_headers()

        # Add assignment status to each trade
        for trade in trades_list:
            deal_number = trade.get('DealNumber', '')
            assigned_items = get_inventory_by_trade(deal_number)
            trade['_assigned_count'] = len(assigned_items)
            trade['_assigned_serials'] = [item['Serial'] for item in assigned_items]

        return jsonify({
            'headers': headers,
            'data': trades_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/<deal_number>', methods=['GET'])
@login_required
def get_trade_details(deal_number):
    """Get details for a specific trade"""
    try:
        # Try to convert to int if it's a numeric deal number
        try:
            deal_number = int(deal_number)
        except (ValueError, TypeError):
            pass

        trade = get_trade_by_id(deal_number)
        if not trade:
            return jsonify({'error': 'Trade not found'}), 404

        # Get assigned inventory
        assigned_items = get_inventory_by_trade(deal_number)

        return jsonify({
            'trade': trade,
            'assigned_inventory': assigned_items,
            'assigned_count': len(assigned_items)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/unassigned-inventory', methods=['GET'])
@login_required
def get_available_inventory():
    """Get inventory items available for assignment"""
    try:
        items = get_unassigned_inventory()
        return jsonify({'data': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/assigned-inventory/<deal_number>', methods=['GET'])
@login_required
def get_assigned_inventory(deal_number):
    """Get inventory items assigned to a specific trade"""
    try:
        items = get_inventory_by_trade(deal_number)
        return jsonify({'data': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/assign', methods=['POST'])
@login_required
@write_access_required
def assign_to_trade():
    """Assign inventory items to a trade"""
    try:
        data = request.json
        serials = data.get('serials', [])
        trade_id = data.get('trade_id')
        warranty_data = data.get('warranty_data')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400
        if not trade_id:
            return jsonify({'error': 'No trade_id provided'}), 400

        success, message, count = assign_inventory_to_trade(serials, trade_id, warranty_data)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'assigned_count': count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/unassign', methods=['POST'])
@login_required
@write_access_required
def unassign_from_trade():
    """Unassign inventory items from their trades"""
    try:
        data = request.json
        serials = data.get('serials', [])

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        success, message, count = unassign_inventory_from_trade(serials)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'unassigned_count': count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/bulk-assign', methods=['POST'])
@login_required
@write_access_required
def bulk_assign_to_trade():
    """
    Bulk assign inventory to a trade with warranty dates.
    This is the main endpoint for seamless trade assignment.
    """
    try:
        data = request.json
        deal_number = data.get('deal_number')
        serials = data.get('serials', [])

        # Warranty data to apply to all assigned items
        warranty_data = {
            'buy_start': data.get('buy_warranty_start'),
            'buy_end': data.get('buy_warranty_end'),
            'sell_start': data.get('sell_warranty_start'),
            'sell_end': data.get('sell_warranty_end'),
            'buy_client': data.get('buy_client'),
            'sell_client': data.get('sell_client'),
            'set_buy_tradeid': data.get('set_buy_tradeid', True),
            'set_sell_tradeid': data.get('set_sell_tradeid', False)
        }

        if not deal_number:
            return jsonify({'error': 'Deal Number is required'}), 400

        if not serials:
            return jsonify({'error': 'No inventory items selected'}), 400

        # Validate against trade notional (quantity)
        trade = get_trade_by_id(deal_number)
        if trade:
            trade_notional = trade.get('Notional', 0)
            already_assigned = len(get_inventory_by_trade(deal_number))
            remaining_quantity = trade_notional - already_assigned

            if len(serials) > remaining_quantity:
                return jsonify({
                    'error': f'Cannot assign {len(serials)} item(s). Only {remaining_quantity} remaining for this trade.'
                }), 400

        # Assign inventory with warranty data
        success, message, count = assign_inventory_to_trade(serials, deal_number, warranty_data)

        if success:
            # Get updated trade info
            trade = get_trade_by_id(deal_number)
            assigned_items = get_inventory_by_trade(deal_number)

            return jsonify({
                'success': True,
                'message': message,
                'assigned_count': count,
                'total_assigned': len(assigned_items),
                'trade': trade
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/create-serials', methods=['POST'])
@login_required
@write_access_required
def create_serials():
    """
    Create new inventory serials and assign them to a trade (BUY mode).
    Used when buying inventory from a counterparty.
    """
    try:
        data = request.json
        deal_number = data.get('deal_number')
        serials = data.get('serials', [])

        if not deal_number:
            return jsonify({'error': 'Deal Number is required'}), 400

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        # Validate against trade notional - must match exactly
        trade = get_trade_by_id(deal_number)
        if trade:
            trade_notional = trade.get('Notional', 0)
            already_assigned = len(get_inventory_by_trade(deal_number))
            remaining_quantity = trade_notional - already_assigned

            if len(serials) != remaining_quantity:
                return jsonify({
                    'error': f'Serial count ({len(serials)}) must match remaining trade quantity ({remaining_quantity}). Trade requires {trade_notional} total, {already_assigned} already assigned.'
                }), 400

        # Inventory metadata
        inventory_data = {
            'market': data.get('market', ''),
            'registry': data.get('registry', ''),
            'product': data.get('product', ''),
            'project_id': data.get('project_id', ''),
            'project_type': data.get('project_type', ''),
            'protocol': data.get('protocol', ''),
            'project_name': data.get('project_name', ''),
            'vintage': data.get('vintage', ''),
            'is_custody': data.get('is_custody', 'Yes')
        }

        # BUY warranty data
        warranty_data = {
            'buy_client': data.get('buy_client', ''),
            'buy_start': data.get('buy_start', ''),
            'buy_end': data.get('buy_end', '')
        }

        success, message, count = create_serials_for_trade(
            serials, deal_number, inventory_data, warranty_data
        )

        if success:
            # Get updated trade info
            trade = get_trade_by_id(deal_number)
            assigned_items = get_inventory_by_trade(deal_number)

            return jsonify({
                'success': True,
                'message': message,
                'created_count': count,
                'total_assigned': len(assigned_items),
                'trade': trade
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
