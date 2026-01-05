"""
Trades management routes for Carbon IMS
"""

from flask import Blueprint, render_template, request, session, jsonify
from routes.auth import login_required, write_access_required, page_access_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_unassigned_inventory,
    get_inventory_by_trade,
    assign_inventory_to_trade,
    unassign_inventory_from_trade,
    create_serials_for_trade,
    log_activity,
    # Reservation functions
    get_inventory_by_criteria,
    reserve_inventory,
    release_reservation,
    get_reserved_inventory,
    mark_reservation_delivered,
    get_reservation_summary,
    # Trade criteria functions
    create_trade_criteria,
    get_trade_criteria,
    update_trade_criteria_fulfillment,
    cancel_trade_criteria,
    # Generic inventory functions
    create_generic_inventory,
    get_generic_inventory,
    fulfill_generic_inventory,
    get_pending_generic_positions,
    # Criteria allocation optimizer functions
    assign_criteria_only,
    get_criteria_allocation_status,
    get_trade_criteria_summary,
    remove_trade_criteria,
    remove_single_criteria,
    update_single_criteria,
    update_criteria_quantity,
    update_specific_criteria_quantity,
    get_trade_criteria_ids,
    get_available_after_criteria_claims
)
from trades_data import (
    get_trades_dataframe, get_trade_by_id, get_trade_headers,
    get_id_column_name, get_quantity_column_name, get_counterparty_column_name,
    _normalize_to_list
)

trades_bp = Blueprint('trades', __name__)


@trades_bp.route('/trades')
@login_required
@page_access_required('trades')
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
        raw_data = get_trades_dataframe()
        trades_list = _normalize_to_list(raw_data)
        headers = get_trade_headers()

        # Get the ID column name dynamically
        id_column = get_id_column_name()

        # Get allocation status for all criteria-only trades
        allocation_status = get_criteria_allocation_status()
        criteria_summary = get_trade_criteria_summary()

        # Add assignment status to each trade (includes both assigned and reserved)
        for trade in trades_list:
            deal_number = trade.get(id_column, '') if id_column else ''
            deal_number_str = str(deal_number)

            assigned_items = get_inventory_by_trade(deal_number)
            reserved_items = get_reserved_inventory(deal_number)

            # Combine assigned and reserved counts
            total_allocated = len(assigned_items) + len(reserved_items)
            all_serials = [item['Serial'] for item in assigned_items] + [item['Serial'] for item in reserved_items]

            trade['_assigned_count'] = total_allocated
            trade['_assigned_serials'] = all_serials
            trade['_reserved_count'] = len(reserved_items)

            # Add criteria-only allocation status
            if deal_number_str in criteria_summary:
                trade['_has_criteria'] = True
                criteria_list = criteria_summary[deal_number_str]

                # Merge per-criteria status into each criteria
                criteria_status = allocation_status.get('criteria_status', {})
                for crit in criteria_list:
                    crit_id = crit.get('criteria_id')
                    if crit_id and crit_id in criteria_status:
                        crit_status_info = criteria_status[crit_id]
                        crit['_status'] = crit_status_info.get('status', 'unknown')
                        crit['_available'] = crit_status_info.get('available', 0)
                        crit['_shortfall'] = crit_status_info.get('shortfall', 0)
                    else:
                        crit['_status'] = 'unknown'
                        crit['_available'] = 0
                        crit['_shortfall'] = 0

                trade['_criteria'] = criteria_list

                # Add optimizer status for this trade
                if deal_number_str in allocation_status.get('trade_status', {}):
                    status_info = allocation_status['trade_status'][deal_number_str]
                    trade['_allocation_status'] = status_info['status']
                    trade['_allocation_available'] = status_info.get('available', 0)
                    trade['_allocation_shortfall'] = status_info.get('shortfall', 0)
                    trade['_conflicts_with'] = status_info.get('conflicts_with', [])
                else:
                    trade['_allocation_status'] = 'unknown'
                    trade['_conflicts_with'] = []
            else:
                trade['_has_criteria'] = False
                trade['_allocation_status'] = None

        return jsonify({
            'headers': headers,
            'data': trades_list,
            'id_column': get_id_column_name(),
            'quantity_column': get_quantity_column_name(),
            'counterparty_column': get_counterparty_column_name(),
            'allocation_summary': {
                'total_available': allocation_status.get('total_available', 0),
                'total_required': allocation_status.get('total_required', 0),
                'allocation_possible': allocation_status.get('allocation_possible', True),
                'conflicts': allocation_status.get('conflicts', []),
                'allocated_serials': allocation_status.get('allocated_serials', [])
            }
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

        # Get assigned and reserved inventory
        assigned_items = get_inventory_by_trade(deal_number)
        reserved_items = get_reserved_inventory(deal_number)

        return jsonify({
            'trade': trade,
            'assigned_inventory': assigned_items,
            'reserved_inventory': reserved_items,
            'assigned_count': len(assigned_items) + len(reserved_items),
            'reserved_count': len(reserved_items)
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
        criteria_id = data.get('criteria_id')  # Optional: specific criteria to deduct from
        warranty_data = data.get('warranty_data')
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400
        if not trade_id:
            return jsonify({'error': 'No trade_id provided'}), 400

        success, message, count = assign_inventory_to_trade(serials, trade_id, warranty_data, criteria_id)

        if success:
            # Log the activity for each serial
            for serial in serials:
                log_activity(
                    username=username,
                    action_type='assign',
                    target_type='trade',
                    target_id=str(trade_id),
                    serial=serial,
                    details=f'Assigned serial {serial} to trade {trade_id}',
                    after_data={'trade_id': trade_id, 'serial': serial, 'warranty_data': warranty_data, 'criteria_id': criteria_id}
                )

            # Update criteria quantities if trade has criteria (reduce by assigned count)
            if count > 0 and get_trade_criteria_ids(trade_id):
                if criteria_id:
                    # Deduct from specific criteria
                    update_specific_criteria_quantity(criteria_id, -count, username)
                else:
                    # Use FIFO (first criteria)
                    update_criteria_quantity(trade_id, -count, username)

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
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        # Get current trade assignments before unassigning
        items = get_all_inventory_items()
        serial_trade_map = {}
        for item in items:
            if item.get('Serial') in serials:
                serial_trade_map[item.get('Serial')] = item.get('TradeID', item.get('trade_id', ''))

        success, message, count = unassign_inventory_from_trade(serials, username)

        if success:
            # Log the activity for each serial
            for serial in serials:
                previous_trade = serial_trade_map.get(serial, '')
                log_activity(
                    username=username,
                    action_type='unassign',
                    target_type='trade',
                    target_id=str(previous_trade) if previous_trade else '',
                    serial=serial,
                    details=f'Unassigned serial {serial} from trade {previous_trade}',
                    before_data={'trade_id': previous_trade, 'serial': serial}
                )

            # Note: Criteria quantity restoration is now handled in unassign_inventory_from_trade()
            # based on the stored criteria_id for each inventory item

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
        username = session.get('user')

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
            qty_column = get_quantity_column_name()
            trade_notional = trade.get(qty_column, 0) if qty_column else 0
            try:
                trade_notional = int(trade_notional) if trade_notional else 0
            except (ValueError, TypeError):
                trade_notional = 0

            already_assigned = len(get_inventory_by_trade(deal_number))
            remaining_quantity = trade_notional - already_assigned

            if remaining_quantity > 0 and len(serials) > remaining_quantity:
                return jsonify({
                    'error': f'Cannot assign {len(serials)} item(s). Only {remaining_quantity} remaining for this trade.'
                }), 400

        # Assign inventory with warranty data
        success, message, count = assign_inventory_to_trade(serials, deal_number, warranty_data)

        if success:
            # Log the bulk assignment activity
            log_activity(
                username=username,
                action_type='bulk_assign',
                target_type='trade',
                target_id=str(deal_number),
                details=f'Bulk assigned {count} item(s) to trade {deal_number}',
                after_data={
                    'trade_id': deal_number,
                    'serials': serials,
                    'warranty_data': warranty_data,
                    'count': count
                }
            )

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
        username = session.get('user')

        if not deal_number:
            return jsonify({'error': 'Deal Number is required'}), 400

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        # Validate against trade notional - must match exactly
        trade = get_trade_by_id(deal_number)
        if trade:
            qty_column = get_quantity_column_name()
            trade_notional = trade.get(qty_column, 0) if qty_column else 0
            try:
                trade_notional = int(trade_notional) if trade_notional else 0
            except (ValueError, TypeError):
                trade_notional = 0

            already_assigned = len(get_inventory_by_trade(deal_number))
            remaining_quantity = trade_notional - already_assigned

            if remaining_quantity > 0 and len(serials) != remaining_quantity:
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
            # Log the activity for each created serial
            for serial in serials:
                log_activity(
                    username=username,
                    action_type='create_serial',
                    target_type='trade',
                    target_id=str(deal_number),
                    serial=serial,
                    details=f'Created serial {serial} and assigned to trade {deal_number}',
                    after_data={
                        'trade_id': deal_number,
                        'serial': serial,
                        'inventory_data': inventory_data,
                        'warranty_data': warranty_data
                    }
                )

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


# =============================================================================
# RESERVATION ROUTES (for Sell Generic)
# =============================================================================

@trades_bp.route('/api/trades/query-inventory', methods=['POST'])
@login_required
def query_inventory_by_criteria():
    """
    Query inventory items matching specific criteria.
    Used to find inventory that can be reserved for a sell trade.
    """
    try:
        data = request.json
        criteria = {
            'market': data.get('market'),
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'vintage_from': data.get('vintage_from'),
            'vintage_to': data.get('vintage_to')
        }
        # Remove None values
        criteria = {k: v for k, v in criteria.items() if v}

        exclude_reserved = data.get('exclude_reserved', True)
        exclude_assigned = data.get('exclude_assigned', True)

        items = get_inventory_by_criteria(criteria, exclude_reserved, exclude_assigned)

        return jsonify({
            'success': True,
            'data': items,
            'count': len(items)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/check-availability', methods=['POST'])
@login_required
def check_inventory_availability():
    """
    Check inventory availability accounting for Generic Allocation claims.
    Returns the true available count after subtracting items claimed by
    existing criteria-only allocations.
    """
    try:
        data = request.json
        criteria = {
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'project_id': data.get('project_id'),
            'vintage_from': data.get('vintage_from'),
            'vintage_to': data.get('vintage_to')
        }
        # Remove None/empty values
        criteria = {k: v for k, v in criteria.items() if v}

        result = get_available_after_criteria_claims(criteria)

        return jsonify({
            'success': True,
            'total_matching': result.get('total_matching', 0),
            'claimed_by_criteria': result.get('claimed_by_criteria', 0),
            'available': result.get('available', 0),
            'criteria_claims': result.get('criteria_claims', []),
            'inventory_items': result.get('inventory_items', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/reserve', methods=['POST'])
@login_required
@write_access_required
def reserve_for_trade():
    """
    Reserve inventory items for a sell trade.
    Earmarks inventory so it cannot be sold to someone else.
    """
    try:
        data = request.json
        serials = data.get('serials', [])
        trade_id = data.get('trade_id')
        criteria_id = data.get('criteria_id')
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400
        if not trade_id:
            return jsonify({'error': 'Trade ID is required'}), 400

        success, message, count = reserve_inventory(serials, trade_id, username, criteria_id)

        if success:
            log_activity(
                username=username,
                action_type='reserve',
                target_type='trade',
                target_id=str(trade_id),
                details=f'Reserved {count} item(s) for trade {trade_id}',
                after_data={'trade_id': trade_id, 'serials': serials, 'criteria_id': criteria_id}
            )
            return jsonify({
                'success': True,
                'message': message,
                'reserved_count': count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/release-reservation', methods=['POST'])
@login_required
@write_access_required
def release_trade_reservation():
    """
    Release reservation on inventory items.
    Used when a sell trade is cancelled or modified.
    """
    try:
        data = request.json
        serials = data.get('serials', [])
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        # Get trade IDs for logging before releasing
        reserved_items = []
        for serial in serials:
            items = get_reserved_inventory(None)  # Get all reserved
            for item in items:
                if item.get('serial') == serial:
                    reserved_items.append(item)
                    break

        success, message, count = release_reservation(serials, username)

        if success:
            for item in reserved_items:
                log_activity(
                    username=username,
                    action_type='release_reservation',
                    target_type='trade',
                    target_id=str(item.get('trade_id', '')),
                    serial=item.get('serial'),
                    details=f'Released reservation on serial {item.get("serial")}',
                    before_data={'trade_id': item.get('trade_id'), 'serial': item.get('serial')}
                )
            return jsonify({
                'success': True,
                'message': message,
                'released_count': count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/reserved/<trade_id>', methods=['GET'])
@login_required
def get_trade_reserved_inventory(trade_id):
    """Get all inventory items reserved for a specific trade."""
    try:
        items = get_reserved_inventory(trade_id)
        return jsonify({
            'success': True,
            'data': items,
            'count': len(items)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/deliver-reserved', methods=['POST'])
@login_required
@write_access_required
def deliver_reserved_inventory():
    """
    Mark reserved inventory as delivered.
    Used when the sell trade is executed and inventory is transferred.
    """
    try:
        data = request.json
        serials = data.get('serials', [])
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        success, message, count = mark_reservation_delivered(serials, username)

        if success:
            log_activity(
                username=username,
                action_type='deliver',
                target_type='reservation',
                details=f'Delivered {count} reserved item(s)',
                after_data={'serials': serials}
            )
            return jsonify({
                'success': True,
                'message': message,
                'delivered_count': count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/reservation-summary', methods=['GET'])
@login_required
def get_reservation_summary_route():
    """Get summary of all reservations grouped by trade."""
    try:
        summary = get_reservation_summary()
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# TRADE CRITERIA ROUTES
# =============================================================================

@trades_bp.route('/api/trades/criteria', methods=['POST'])
@login_required
@write_access_required
def create_criteria():
    """
    Create trade criteria for a buy or sell generic trade.
    Defines the parameters that inventory must match.
    """
    try:
        data = request.json
        trade_id = data.get('trade_id')
        direction = data.get('direction')  # 'buy' or 'sell'
        quantity = data.get('quantity')
        username = session.get('user')

        if not trade_id:
            return jsonify({'error': 'Trade ID is required'}), 400
        if not direction or direction not in ['buy', 'sell']:
            return jsonify({'error': 'Direction must be "buy" or "sell"'}), 400
        if not quantity or int(quantity) <= 0:
            return jsonify({'error': 'Quantity must be a positive number'}), 400

        criteria = {
            'market': data.get('market'),
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'vintage_from': data.get('vintage_from'),
            'vintage_to': data.get('vintage_to')
        }
        # Remove None values
        criteria = {k: v for k, v in criteria.items() if v}

        success, message, criteria_id = create_trade_criteria(
            trade_id, direction, int(quantity), criteria, username
        )

        if success:
            log_activity(
                username=username,
                action_type='create_criteria',
                target_type='trade',
                target_id=str(trade_id),
                details=f'Created {direction} criteria for trade {trade_id}: {quantity} units',
                after_data={'trade_id': trade_id, 'direction': direction, 'quantity': quantity, 'criteria': criteria}
            )
            return jsonify({
                'success': True,
                'message': message,
                'criteria_id': criteria_id
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria/<trade_id>', methods=['GET'])
@login_required
def get_trade_criteria_route(trade_id):
    """Get all criteria for a specific trade."""
    try:
        direction = request.args.get('direction')
        status = request.args.get('status')

        criteria_list = get_trade_criteria(trade_id=trade_id, direction=direction, status=status)
        return jsonify({
            'success': True,
            'data': criteria_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria/<int:criteria_id>/cancel', methods=['POST'])
@login_required
@write_access_required
def cancel_criteria(criteria_id):
    """Cancel a trade criteria."""
    try:
        username = session.get('user')

        # Get criteria info before cancelling
        criteria_list = get_trade_criteria(criteria_id=criteria_id)
        criteria_info = criteria_list[0] if criteria_list else None

        success, message = cancel_trade_criteria(criteria_id, username)

        if success:
            log_activity(
                username=username,
                action_type='cancel_criteria',
                target_type='trade',
                target_id=str(criteria_info.get('trade_id', '')) if criteria_info else '',
                details=f'Cancelled criteria {criteria_id}',
                before_data=criteria_info
            )
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# GENERIC INVENTORY ROUTES (for Buy Generic)
# =============================================================================

@trades_bp.route('/api/trades/generic-position', methods=['POST'])
@login_required
@write_access_required
def create_generic_position():
    """
    Create a generic inventory position for a buy trade.
    Used when buying inventory that hasn't been delivered yet.
    """
    try:
        data = request.json
        trade_id = data.get('trade_id')
        quantity = data.get('quantity')
        criteria_id = data.get('criteria_id')
        username = session.get('user')

        if not trade_id:
            return jsonify({'error': 'Trade ID is required'}), 400
        if not quantity or int(quantity) <= 0:
            return jsonify({'error': 'Quantity must be a positive number'}), 400

        criteria = {
            'market': data.get('market'),
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'vintage': data.get('vintage')
        }
        # Remove None values
        criteria = {k: v for k, v in criteria.items() if v}

        success, message, generic_id = create_generic_inventory(
            trade_id, int(quantity), criteria, username, criteria_id
        )

        if success:
            log_activity(
                username=username,
                action_type='create_generic',
                target_type='trade',
                target_id=str(trade_id),
                details=f'Created generic position for trade {trade_id}: {quantity} units',
                after_data={'trade_id': trade_id, 'quantity': quantity, 'criteria': criteria}
            )
            return jsonify({
                'success': True,
                'message': message,
                'generic_id': generic_id
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/generic/<trade_id>', methods=['GET'])
@login_required
def get_trade_generic_inventory(trade_id):
    """Get all generic inventory positions for a specific trade."""
    try:
        status = request.args.get('status')
        positions = get_generic_inventory(trade_id, status)
        return jsonify({
            'success': True,
            'data': positions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/generic/<int:generic_id>/fulfill', methods=['POST'])
@login_required
@write_access_required
def fulfill_generic_position(generic_id):
    """
    Fulfill a generic inventory position with actual serials.
    Used when the bought inventory is delivered and serials are known.
    """
    try:
        data = request.json
        serials = data.get('serials', [])
        username = session.get('user')

        if not serials:
            return jsonify({'error': 'No serials provided'}), 400

        success, message, fulfilled_count = fulfill_generic_inventory(generic_id, serials, username)

        if success:
            log_activity(
                username=username,
                action_type='fulfill_generic',
                target_type='generic_position',
                target_id=str(generic_id),
                details=f'Fulfilled generic position {generic_id} with {fulfilled_count} serial(s)',
                after_data={'generic_id': generic_id, 'serials': serials}
            )
            return jsonify({
                'success': True,
                'message': message,
                'fulfilled_count': fulfilled_count
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/pending-generic', methods=['GET'])
@login_required
def get_pending_positions():
    """Get all pending generic inventory positions across all trades."""
    try:
        positions = get_pending_generic_positions()
        return jsonify({
            'success': True,
            'data': positions
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# CRITERIA-ONLY ALLOCATION ROUTES
# =============================================================================

@trades_bp.route('/api/trades/assign-criteria', methods=['POST'])
@login_required
@write_access_required
def assign_criteria_only_route():
    """
    Assign criteria to a trade without reserving specific inventory.
    The optimizer will check if sufficient inventory exists to satisfy
    all criteria-only trades collectively.
    """
    try:
        data = request.json
        trade_id = data.get('trade_id')
        quantity = data.get('quantity')
        username = session.get('user')

        if not trade_id:
            return jsonify({'error': 'Trade ID is required'}), 400
        if not quantity or int(quantity) <= 0:
            return jsonify({'error': 'Quantity must be a positive number'}), 400

        criteria = {
            'market': data.get('market'),
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'project_id': data.get('project_id'),
            'vintage_from': data.get('vintage_from'),
            'vintage_to': data.get('vintage_to')
        }
        # Remove None/empty values
        criteria = {k: v for k, v in criteria.items() if v}

        success, message, criteria_id = assign_criteria_only(
            trade_id, int(quantity), criteria, username
        )

        if success:
            # Get updated allocation status
            allocation_status = get_criteria_allocation_status()
            trade_status = allocation_status.get('trade_status', {}).get(str(trade_id), {})

            log_activity(
                username=username,
                action_type='assign_criteria_only',
                target_type='trade',
                target_id=str(trade_id),
                details=f'Assigned criteria-only to trade {trade_id}: {quantity} units',
                after_data={
                    'trade_id': trade_id,
                    'quantity': quantity,
                    'criteria': criteria,
                    'allocation_status': trade_status.get('status', 'unknown')
                }
            )
            return jsonify({
                'success': True,
                'message': message,
                'criteria_id': criteria_id,
                'allocation_status': trade_status.get('status', 'unknown'),
                'allocation_available': trade_status.get('available', 0),
                'allocation_shortfall': trade_status.get('shortfall', 0)
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/allocation-status', methods=['GET'])
@login_required
def get_allocation_status_route():
    """
    Get allocation status for all criteria-only trades.
    Returns optimizer results showing which trades can be satisfied
    and any conflicts between overlapping criteria.
    """
    try:
        status = get_criteria_allocation_status()
        summary = get_trade_criteria_summary()

        return jsonify({
            'success': True,
            'trade_status': status.get('trade_status', {}),
            'total_available': status.get('total_available', 0),
            'total_required': status.get('total_required', 0),
            'allocation_possible': status.get('allocation_possible', True),
            'conflicts': status.get('conflicts', []),
            'criteria_summary': summary
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria-only/<trade_id>', methods=['DELETE'])
@login_required
@write_access_required
def remove_criteria_only_route(trade_id):
    """
    Remove criteria-only assignment from a trade.
    This releases the criteria constraint without affecting reserved inventory.
    """
    try:
        username = session.get('user')

        # Get criteria info before removing
        summary = get_trade_criteria_summary()
        criteria_info = summary.get(str(trade_id), {})

        success, message = remove_trade_criteria(trade_id, username)

        if success:
            log_activity(
                username=username,
                action_type='remove_criteria_only',
                target_type='trade',
                target_id=str(trade_id),
                details=f'Removed criteria-only from trade {trade_id}',
                before_data=criteria_info
            )
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria/<int:criteria_id>', methods=['DELETE'])
@login_required
@write_access_required
def remove_single_criteria_route(criteria_id):
    """Remove a single criteria by its ID."""
    try:
        username = session.get('username', 'unknown')

        success, message = remove_single_criteria(criteria_id, username)

        if success:
            log_activity(
                username=username,
                action_type='remove_single_criteria',
                target_type='criteria',
                target_id=str(criteria_id),
                details=f'Removed criteria {criteria_id}'
            )
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria/<int:criteria_id>', methods=['PUT'])
@login_required
@write_access_required
def update_single_criteria_route(criteria_id):
    """Update a single criteria by its ID."""
    try:
        data = request.json
        username = session.get('username', 'unknown')

        quantity = data.get('quantity', 0)
        criteria = {
            'registry': data.get('registry'),
            'product': data.get('product'),
            'project_type': data.get('project_type'),
            'protocol': data.get('protocol'),
            'project_id': data.get('project_id'),
            'vintage_from': data.get('vintage_from'),
            'vintage_to': data.get('vintage_to')
        }

        success, message = update_single_criteria(criteria_id, quantity, criteria, username)

        if success:
            log_activity(
                username=username,
                action_type='update_criteria',
                target_type='criteria',
                target_id=str(criteria_id),
                details=f'Updated criteria {criteria_id}'
            )
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trades_bp.route('/api/trades/criteria-only/<trade_id>', methods=['GET'])
@login_required
def get_criteria_only_route(trade_id):
    """Get criteria-only assignment details for a specific trade."""
    try:
        summary = get_trade_criteria_summary()
        criteria_info = summary.get(str(trade_id), None)

        if not criteria_info:
            return jsonify({
                'success': True,
                'has_criteria': False,
                'data': None
            })

        # Get allocation status for this trade
        allocation_status = get_criteria_allocation_status()
        trade_status = allocation_status.get('trade_status', {}).get(str(trade_id), {})

        return jsonify({
            'success': True,
            'has_criteria': True,
            'data': criteria_info,
            'allocation_status': trade_status.get('status', 'unknown'),
            'allocation_available': trade_status.get('available', 0),
            'allocation_shortfall': trade_status.get('shortfall', 0)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
