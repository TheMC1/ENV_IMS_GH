"""
Reports routes for Carbon IMS
Provides high-level statistics and reporting functionality
"""

from flask import Blueprint, render_template, request, session, jsonify, Response
from routes.auth import login_required, page_access_required
from database import (
    get_user_by_username,
    get_all_inventory_items,
    get_all_warranty_items,
    get_inventory_db_connection,
    get_user_page_settings,
    save_user_page_settings
)
from trades_data import get_trades_dataframe
from datetime import datetime, timedelta
import json
import csv
import io

reports_bp = Blueprint('reports', __name__)


def get_inventory_statistics(filters=None):
    """Calculate inventory statistics with optional filters"""
    items = get_all_inventory_items()

    if not items:
        return {
            'total_items': 0,
            'in_custody': 0,
            'not_in_custody': 0,
            'assigned': 0,
            'unassigned': 0,
            'by_registry': {},
            'by_vintage': {},
            'by_portfolio': {},
            'by_product': {}
        }

    # Apply filters if provided
    if filters:
        if filters.get('registry'):
            items = [i for i in items if i.get('Registry') == filters['registry']]
        if filters.get('vintage'):
            items = [i for i in items if i.get('Vintage') == filters['vintage']]
        if filters.get('product'):
            items = [i for i in items if i.get('Product') == filters['product']]

    total = len(items)
    in_custody = sum(1 for i in items if str(i.get('IsCustody', '')).lower() in ['yes', 'true', '1'])
    not_in_custody = total - in_custody
    assigned = sum(1 for i in items if str(i.get('IsAssigned', '')).lower() in ['yes', 'true', '1'])
    unassigned = total - assigned

    # Group by registry
    by_registry = {}
    for item in items:
        registry = item.get('Registry') or 'Unknown'
        by_registry[registry] = by_registry.get(registry, 0) + 1

    # Group by vintage
    by_vintage = {}
    for item in items:
        vintage = item.get('Vintage') or 'Unknown'
        by_vintage[vintage] = by_vintage.get(vintage, 0) + 1

    # Group by product
    by_product = {}
    for item in items:
        product = item.get('Product') or 'Unknown'
        by_product[product] = by_product.get(product, 0) + 1

    # Group by project type
    by_project_type = {}
    for item in items:
        project_type = item.get('ProjectType') or 'Unknown'
        by_project_type[project_type] = by_project_type.get(project_type, 0) + 1

    return {
        'total_items': total,
        'in_custody': in_custody,
        'not_in_custody': not_in_custody,
        'assigned': assigned,
        'unassigned': unassigned,
        'by_registry': by_registry,
        'by_vintage': by_vintage,
        'by_product': by_product,
        'by_project_type': by_project_type
    }


def get_warranty_statistics(filters=None):
    """Calculate warranty statistics with optional filters"""
    items = get_all_warranty_items()
    today = datetime.now().date()

    if not items:
        return {
            'total_warranties': 0,
            'with_buy_warranty': 0,
            'with_sell_warranty': 0,
            'buy_expiring_30_days': 0,
            'buy_expiring_60_days': 0,
            'buy_expiring_90_days': 0,
            'sell_expiring_30_days': 0,
            'sell_expiring_60_days': 0,
            'sell_expiring_90_days': 0,
            'buy_expired': 0,
            'sell_expired': 0,
            'expiring_soon': []
        }

    # Apply filters if provided
    if filters:
        if filters.get('registry'):
            items = [i for i in items if i.get('Registry') == filters['registry']]
        if filters.get('vintage'):
            items = [i for i in items if i.get('Vintage') == filters['vintage']]

    total = len(items)
    with_buy = sum(1 for i in items if i.get('Buy_End'))
    with_sell = sum(1 for i in items if i.get('Sell_End'))

    buy_expiring_30 = 0
    buy_expiring_60 = 0
    buy_expiring_90 = 0
    sell_expiring_30 = 0
    sell_expiring_60 = 0
    sell_expiring_90 = 0
    buy_expired = 0
    sell_expired = 0
    expiring_soon = []

    for item in items:
        # Check buy warranty
        buy_end_str = item.get('Buy_End', '')
        if buy_end_str:
            try:
                buy_end = datetime.strptime(buy_end_str, '%Y-%m-%d').date()
                days_until = (buy_end - today).days

                if days_until < 0:
                    buy_expired += 1
                elif days_until <= 30:
                    buy_expiring_30 += 1
                    expiring_soon.append({
                        'serial': item.get('Serial'),
                        'type': 'Buy',
                        'end_date': buy_end_str,
                        'days_remaining': days_until,
                        'registry': item.get('Registry'),
                        'client': item.get('Buy_Client')
                    })
                elif days_until <= 60:
                    buy_expiring_60 += 1
                elif days_until <= 90:
                    buy_expiring_90 += 1
            except:
                pass

        # Check sell warranty
        sell_end_str = item.get('Sell_End', '')
        if sell_end_str:
            try:
                sell_end = datetime.strptime(sell_end_str, '%Y-%m-%d').date()
                days_until = (sell_end - today).days

                if days_until < 0:
                    sell_expired += 1
                elif days_until <= 30:
                    sell_expiring_30 += 1
                    expiring_soon.append({
                        'serial': item.get('Serial'),
                        'type': 'Sell',
                        'end_date': sell_end_str,
                        'days_remaining': days_until,
                        'registry': item.get('Registry'),
                        'client': item.get('Sell_Client')
                    })
                elif days_until <= 60:
                    sell_expiring_60 += 1
                elif days_until <= 90:
                    sell_expiring_90 += 1
            except:
                pass

    # Sort expiring soon by days remaining
    expiring_soon.sort(key=lambda x: x['days_remaining'])

    return {
        'total_warranties': total,
        'with_buy_warranty': with_buy,
        'with_sell_warranty': with_sell,
        'buy_expiring_30_days': buy_expiring_30,
        'buy_expiring_60_days': buy_expiring_60,
        'buy_expiring_90_days': buy_expiring_90,
        'sell_expiring_30_days': sell_expiring_30,
        'sell_expiring_60_days': sell_expiring_60,
        'sell_expiring_90_days': sell_expiring_90,
        'buy_expired': buy_expired,
        'sell_expired': sell_expired,
        'expiring_soon': expiring_soon[:20]  # Limit to top 20
    }


def get_trade_statistics(filters=None):
    """Calculate trade statistics"""
    trades = get_trades_dataframe()

    if not trades:
        return {
            'total_trades': 0,
            'pending_trades': 0,
            'confirmed_trades': 0,
            'allocated_trades': 0,
            'completed_trades': 0,
            'total_notional': 0,
            'by_status': {},
            'by_portfolio': {},
            'by_counterparty': {},
            'by_trade_type': {},
            'by_currency': {}
        }

    total = len(trades)

    # Count by status
    by_status = {}
    for trade in trades:
        status = trade.get('status', 'Unknown')
        by_status[status] = by_status.get(status, 0) + 1

    pending = by_status.get('Pending', 0)
    confirmed = by_status.get('Confirmed', 0)
    allocated = by_status.get('Allocated', 0)
    completed = by_status.get('Completed', 0)

    # Total notional
    total_notional = sum(trade.get('Notional', 0) for trade in trades)

    # Group by portfolio
    by_portfolio = {}
    for trade in trades:
        portfolio = trade.get('Portfolio') or 'Unknown'
        by_portfolio[portfolio] = by_portfolio.get(portfolio, 0) + 1

    # Group by counterparty
    by_counterparty = {}
    for trade in trades:
        counterparty = trade.get('Counterparty') or 'Unknown'
        by_counterparty[counterparty] = by_counterparty.get(counterparty, 0) + 1

    # Group by trade type
    by_trade_type = {}
    for trade in trades:
        trade_type = trade.get('TradeType') or 'Unknown'
        by_trade_type[trade_type] = by_trade_type.get(trade_type, 0) + 1

    # Group by currency
    by_currency = {}
    for trade in trades:
        currency = trade.get('DealCurrency') or 'Unknown'
        by_currency[currency] = by_currency.get(currency, 0) + 1

    # Pending trades details
    pending_trades_list = [t for t in trades if t.get('status') == 'Pending']

    return {
        'total_trades': total,
        'pending_trades': pending,
        'confirmed_trades': confirmed,
        'allocated_trades': allocated,
        'completed_trades': completed,
        'total_notional': total_notional,
        'by_status': by_status,
        'by_portfolio': by_portfolio,
        'by_counterparty': by_counterparty,
        'by_trade_type': by_trade_type,
        'by_currency': by_currency,
        'pending_trades_list': pending_trades_list[:10]  # Top 10 pending
    }


def get_filter_options():
    """Get available filter options from inventory data"""
    items = get_all_inventory_items()

    registries = sorted(set(i.get('Registry') for i in items if i.get('Registry')))
    vintages = sorted(set(i.get('Vintage') for i in items if i.get('Vintage')))
    products = sorted(set(i.get('Product') for i in items if i.get('Product')))
    project_types = sorted(set(i.get('ProjectType') for i in items if i.get('ProjectType')))

    return {
        'registries': registries,
        'vintages': vintages,
        'products': products,
        'project_types': project_types
    }


@reports_bp.route('/reports')
@login_required
@page_access_required('reports')
def reports():
    """Display reports page"""
    username = session.get('user')
    user = get_user_by_username(username)
    user_role = user['role'] if user else 'user'

    # Get saved report settings
    settings = get_user_page_settings(username, 'reports')

    return render_template('reports.html',
                         username=username,
                         user_role=user_role,
                         saved_settings=json.dumps(settings))


@reports_bp.route('/api/reports/data', methods=['GET', 'POST'])
@login_required
def get_report_data():
    """Get report data with optional filters"""
    try:
        filters = None
        if request.method == 'POST':
            filters = request.json or {}

        inventory_stats = get_inventory_statistics(filters)
        warranty_stats = get_warranty_statistics(filters)
        trade_stats = get_trade_statistics(filters)
        filter_options = get_filter_options()

        return jsonify({
            'inventory': inventory_stats,
            'warranties': warranty_stats,
            'trades': trade_stats,
            'filter_options': filter_options,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/api/reports/settings', methods=['POST'])
@login_required
def save_report_settings():
    """Save user's report settings"""
    try:
        username = session.get('user')
        settings = request.json

        success, message = save_user_page_settings(username, 'reports', settings)

        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/api/reports/export', methods=['POST'])
@login_required
def export_report():
    """Export report data to CSV"""
    try:
        data = request.json
        export_format = data.get('format', 'csv')
        sections = data.get('sections', ['inventory', 'warranties', 'trades'])
        filters = data.get('filters', {})

        # Get report data
        inventory_stats = get_inventory_statistics(filters)
        warranty_stats = get_warranty_statistics(filters)
        trade_stats = get_trade_statistics(filters)

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Report header
        writer.writerow(['Carbon IMS Report'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])

        if 'inventory' in sections:
            writer.writerow(['=== INVENTORY SUMMARY ==='])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Items', inventory_stats['total_items']])
            writer.writerow(['In Custody', inventory_stats['in_custody']])
            writer.writerow(['Not In Custody', inventory_stats['not_in_custody']])
            writer.writerow(['Assigned to Trades', inventory_stats['assigned']])
            writer.writerow(['Unassigned', inventory_stats['unassigned']])
            writer.writerow([])

            writer.writerow(['By Registry'])
            for registry, count in inventory_stats['by_registry'].items():
                writer.writerow([registry, count])
            writer.writerow([])

            writer.writerow(['By Vintage'])
            for vintage, count in sorted(inventory_stats['by_vintage'].items()):
                writer.writerow([vintage, count])
            writer.writerow([])

        if 'warranties' in sections:
            writer.writerow(['=== WARRANTY SUMMARY ==='])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Warranties', warranty_stats['total_warranties']])
            writer.writerow(['With Buy Warranty', warranty_stats['with_buy_warranty']])
            writer.writerow(['With Sell Warranty', warranty_stats['with_sell_warranty']])
            writer.writerow(['Buy Expired', warranty_stats['buy_expired']])
            writer.writerow(['Sell Expired', warranty_stats['sell_expired']])
            writer.writerow(['Buy Expiring (30 days)', warranty_stats['buy_expiring_30_days']])
            writer.writerow(['Sell Expiring (30 days)', warranty_stats['sell_expiring_30_days']])
            writer.writerow([])

            if warranty_stats['expiring_soon']:
                writer.writerow(['Warranties Expiring Soon'])
                writer.writerow(['Serial', 'Type', 'End Date', 'Days Remaining', 'Registry', 'Client'])
                for item in warranty_stats['expiring_soon']:
                    writer.writerow([
                        item['serial'],
                        item['type'],
                        item['end_date'],
                        item['days_remaining'],
                        item['registry'],
                        item['client']
                    ])
                writer.writerow([])

        if 'trades' in sections:
            writer.writerow(['=== TRADES SUMMARY ==='])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Trades', trade_stats['total_trades']])
            writer.writerow(['Pending', trade_stats['pending_trades']])
            writer.writerow(['Confirmed', trade_stats['confirmed_trades']])
            writer.writerow(['Allocated', trade_stats['allocated_trades']])
            writer.writerow(['Total Notional', f"{trade_stats['total_notional']:,}"])
            writer.writerow([])

            writer.writerow(['By Portfolio'])
            for portfolio, count in trade_stats['by_portfolio'].items():
                writer.writerow([portfolio, count])
            writer.writerow([])

            writer.writerow(['By Trade Type'])
            for trade_type, count in trade_stats['by_trade_type'].items():
                writer.writerow([trade_type, count])
            writer.writerow([])

        # Get CSV content
        csv_content = output.getvalue()
        output.close()

        # Return as downloadable file
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=ims_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/api/reports/email', methods=['POST'])
@login_required
def email_report():
    """Send report via email (placeholder - needs SMTP configuration)"""
    try:
        data = request.json
        email_to = data.get('email')
        sections = data.get('sections', ['inventory', 'warranties', 'trades'])
        filters = data.get('filters', {})

        if not email_to:
            return jsonify({'error': 'Email address is required'}), 400

        # Get report data
        inventory_stats = get_inventory_statistics(filters)
        warranty_stats = get_warranty_statistics(filters)
        trade_stats = get_trade_statistics(filters)

        # Build email body
        email_body = f"""
Carbon IMS Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

        if 'inventory' in sections:
            email_body += f"""
=== INVENTORY SUMMARY ===
Total Items: {inventory_stats['total_items']:,}
In Custody: {inventory_stats['in_custody']:,}
Not In Custody: {inventory_stats['not_in_custody']:,}
Assigned to Trades: {inventory_stats['assigned']:,}
Unassigned: {inventory_stats['unassigned']:,}

"""

        if 'warranties' in sections:
            email_body += f"""
=== WARRANTY SUMMARY ===
Total Warranties: {warranty_stats['total_warranties']:,}
Buy Expired: {warranty_stats['buy_expired']:,}
Sell Expired: {warranty_stats['sell_expired']:,}
Buy Expiring (30 days): {warranty_stats['buy_expiring_30_days']:,}
Sell Expiring (30 days): {warranty_stats['sell_expiring_30_days']:,}

"""

        if 'trades' in sections:
            email_body += f"""
=== TRADES SUMMARY ===
Total Trades: {trade_stats['total_trades']:,}
Pending: {trade_stats['pending_trades']:,}
Confirmed: {trade_stats['confirmed_trades']:,}
Total Notional: {trade_stats['total_notional']:,}

"""

        # In a real implementation, you would send the email here using smtplib
        # For now, we'll return success with a note about configuration

        # Example SMTP implementation (commented out):
        # import smtplib
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        #
        # msg = MIMEMultipart()
        # msg['From'] = 'ims@company.com'
        # msg['To'] = email_to
        # msg['Subject'] = f'Carbon IMS Report - {datetime.now().strftime("%Y-%m-%d")}'
        # msg.attach(MIMEText(email_body, 'plain'))
        #
        # with smtplib.SMTP('smtp.company.com', 587) as server:
        #     server.starttls()
        #     server.login('username', 'password')
        #     server.send_message(msg)

        return jsonify({
            'success': True,
            'message': f'Report prepared for {email_to}. Note: Email sending requires SMTP configuration.',
            'preview': email_body
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
