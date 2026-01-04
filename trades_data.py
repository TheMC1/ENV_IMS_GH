"""
Trades Data Source Module

This module provides the interface for fetching trade data.
Currently uses dummy data - replace get_trades_dataframe() with your actual implementation.

The functions are schema-agnostic and will work with any DataFrame/list structure.
"""

from datetime import datetime, timedelta
import random


# =============================================================================
# COLUMN NAME OVERRIDES
# Set these to explicitly specify column names, or leave as None for auto-detect
# =============================================================================
TRADE_ID_COLUMN = None          # e.g., 'DealNumber', 'TradeID', 'ID'
TRADE_QUANTITY_COLUMN = None    # e.g., 'Notional', 'Quantity', 'Amount'
TRADE_COUNTERPARTY_COLUMN = None  # e.g., 'Counterparty', 'Client', 'Party'
# =============================================================================

# =============================================================================
# DISPLAY COLUMNS OVERRIDE
# Set this list to manually specify which columns to display in the trades table.
# If set, ONLY these columns will be shown in the specified order.
# Leave as None to auto-detect and display all columns.
# =============================================================================
DISPLAY_COLUMNS = None
# Example:
# DISPLAY_COLUMNS = ['DealNumber', 'Counterparty', 'Notional', 'TradeType', 'status']
# =============================================================================


def _normalize_to_list(data):
    """
    Normalize data to a list of dictionaries.
    Handles pandas DataFrame, list of dicts, or None.

    Args:
        data: DataFrame, list of dicts, or None

    Returns:
        List of dictionaries
    """
    if data is None:
        return []

    # Check if it's a pandas DataFrame
    try:
        import pandas as pd
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return []
            return data.to_dict('records')
    except ImportError:
        pass

    # If it's already a list, return as-is
    if isinstance(data, list):
        return data

    # If it's a dict (single record), wrap in list
    if isinstance(data, dict):
        return [data]

    return []


def _get_id_column(trade_record):
    """
    Dynamically determine the ID column from a trade record.
    Uses TRADE_ID_COLUMN override if set, otherwise auto-detects.

    Args:
        trade_record: A dictionary representing a trade

    Returns:
        The name of the ID column, or None if not found
    """
    # Use override if specified
    if TRADE_ID_COLUMN:
        return TRADE_ID_COLUMN

    if not trade_record:
        return None

    # Common ID column patterns (case-insensitive search)
    id_patterns = [
        'DealNumber', 'deal_number', 'dealnumber',
        'TradeID', 'trade_id', 'tradeid',
        'ID', 'Id', 'id',
        'DealID', 'deal_id', 'dealid',
        'TransactionID', 'transaction_id',
        'OrderID', 'order_id'
    ]

    keys = list(trade_record.keys())

    # First try exact match
    for pattern in id_patterns:
        if pattern in keys:
            return pattern

    # Then try case-insensitive match
    keys_lower = {k.lower(): k for k in keys}
    for pattern in id_patterns:
        if pattern.lower() in keys_lower:
            return keys_lower[pattern.lower()]

    # Fallback to first column
    return keys[0] if keys else None


def _get_quantity_column(trade_record):
    """
    Dynamically determine the quantity/notional column from a trade record.
    Uses TRADE_QUANTITY_COLUMN override if set, otherwise auto-detects.

    Args:
        trade_record: A dictionary representing a trade

    Returns:
        The name of the quantity column, or None if not found
    """
    # Use override if specified
    if TRADE_QUANTITY_COLUMN:
        return TRADE_QUANTITY_COLUMN

    if not trade_record:
        return None

    # Common quantity column patterns
    qty_patterns = [
        'Notional', 'notional',
        'Quantity', 'quantity', 'Qty', 'qty',
        'Amount', 'amount',
        'Volume', 'volume',
        'Size', 'size',
        'Units', 'units'
    ]

    keys = list(trade_record.keys())

    for pattern in qty_patterns:
        if pattern in keys:
            return pattern

    # Case-insensitive fallback
    keys_lower = {k.lower(): k for k in keys}
    for pattern in qty_patterns:
        if pattern.lower() in keys_lower:
            return keys_lower[pattern.lower()]

    return None


def _get_counterparty_column(trade_record):
    """
    Dynamically determine the counterparty/client column from a trade record.
    Uses TRADE_COUNTERPARTY_COLUMN override if set, otherwise auto-detects.

    Args:
        trade_record: A dictionary representing a trade

    Returns:
        The name of the counterparty column, or None if not found
    """
    # Use override if specified
    if TRADE_COUNTERPARTY_COLUMN:
        return TRADE_COUNTERPARTY_COLUMN

    if not trade_record:
        return None

    # Common counterparty column patterns
    cpty_patterns = [
        'Counterparty', 'counterparty',
        'Client', 'client',
        'Party', 'party',
        'Customer', 'customer',
        'Account', 'account',
        'Trader', 'trader',
        'CounterpartyName', 'counterparty_name',
        'ClientName', 'client_name'
    ]

    keys = list(trade_record.keys())

    for pattern in cpty_patterns:
        if pattern in keys:
            return pattern

    # Case-insensitive fallback
    keys_lower = {k.lower(): k for k in keys}
    for pattern in cpty_patterns:
        if pattern.lower() in keys_lower:
            return keys_lower[pattern.lower()]

    return None


def get_trades_dataframe():
    """
    Fetch trades data from external source.

    Returns a list of dictionaries with trade information.
    The schema is flexible and will be displayed dynamically.

    TODO: Replace this dummy implementation with actual data source
          (e.g., database query, API call, file read, etc.)
    """
    # =========================================================================
    # DUMMY DATA - Replace this section with your actual data fetching logic
    # =========================================================================

    dummy_trades = [
        {
            'DealNumber': 1001,
            'Counterparty': 'Green Energy Ltd',
            'Portfolio': 'Carbon Trading',
            'Notional': 125000,
            'TradeType': 'Spot',
            'SettleDate': '2024-12-20',
            'Underlier': 'VCU-2023',
            'DealCurrency': 'USD',
            'status': 'Pending',
            'trader': 'John Smith',
            'notes': 'Q4 carbon offset purchase'
        },
        {
            'DealNumber': 1002,
            'Counterparty': 'Carbon Solutions Inc',
            'Portfolio': 'Renewables',
            'Notional': 75000,
            'TradeType': 'Forward',
            'SettleDate': '2024-12-23',
            'Underlier': 'REC-SOLAR',
            'DealCurrency': 'EUR',
            'status': 'Confirmed',
            'trader': 'Jane Doe',
            'notes': 'Renewable energy credits'
        },
        {
            'DealNumber': 1003,
            'Counterparty': 'EcoCredits LLC',
            'Portfolio': 'Carbon Trading',
            'Notional': 218750,
            'TradeType': 'Spot',
            'SettleDate': '2024-12-27',
            'Underlier': 'ACR-FOREST',
            'DealCurrency': 'USD',
            'status': 'Pending',
            'trader': 'Mike Johnson',
            'notes': 'Forest conservation project'
        },
        {
            'DealNumber': 1004,
            'Counterparty': 'Sustainability Partners',
            'Portfolio': 'Biodiversity',
            'Notional': 84375,
            'TradeType': 'Option',
            'SettleDate': '2024-12-29',
            'Underlier': 'VCU-BIO',
            'DealCurrency': 'GBP',
            'status': 'Allocated',
            'trader': 'Sarah Wilson',
            'notes': 'Biodiversity project credits'
        },
        {
            'DealNumber': 1005,
            'Counterparty': 'Net Zero Trading',
            'Portfolio': 'Methane',
            'Notional': 285000,
            'TradeType': 'Forward',
            'SettleDate': '2025-01-05',
            'Underlier': 'CER-METHANE',
            'DealCurrency': 'USD',
            'status': 'Pending',
            'trader': 'Tom Brown',
            'notes': 'Methane capture project'
        }
    ]

    return dummy_trades

    # =========================================================================
    # Example implementations (uncomment and modify as needed):
    #
    # import pandas as pd
    #
    # # Option 1: From API - returns DataFrame or list
    # import requests
    # response = requests.get('https://your-api.com/trades')
    # return response.json()  # Works with list of dicts
    #
    # # Option 2: From database - returns DataFrame
    # import sqlite3
    # conn = sqlite3.connect('trades.db')
    # df = pd.read_sql_query("SELECT * FROM trades", conn)
    # return df  # DataFrame is automatically normalized
    #
    # # Option 3: From CSV/Excel - returns DataFrame
    # df = pd.read_excel('trades.xlsx')
    # return df  # DataFrame is automatically normalized
    # =========================================================================


def get_trade_by_id(trade_id):
    """
    Get a specific trade by its ID (schema-agnostic).
    Automatically detects the ID column from the data.

    Args:
        trade_id: The unique trade identifier (will be compared as-is and as int/str)

    Returns:
        Trade dictionary or None if not found
    """
    raw_data = get_trades_dataframe()
    trades = _normalize_to_list(raw_data)

    if not trades:
        return None

    # Determine the ID column dynamically
    id_column = _get_id_column(trades[0])

    if not id_column:
        return None

    # Search for the trade, handling type mismatches
    for trade in trades:
        trade_value = trade.get(id_column)

        # Direct comparison
        if trade_value == trade_id:
            return dict(trade)  # Return a copy as dict

        # Try numeric comparison (handle string vs int mismatches)
        try:
            if int(trade_value) == int(trade_id):
                return dict(trade)
        except (ValueError, TypeError):
            pass

        # Try string comparison
        if str(trade_value) == str(trade_id):
            return dict(trade)

    return None


def get_trade_headers():
    """
    Get the column headers for trades display (schema-agnostic).
    Dynamically extracts headers from the data.

    Returns:
        List of column names in display order
    """
    # Use manual override if specified
    if DISPLAY_COLUMNS:
        return DISPLAY_COLUMNS

    raw_data = get_trades_dataframe()
    trades = _normalize_to_list(raw_data)

    if not trades:
        return []

    # Get all unique keys from all trades
    all_keys = set()
    for trade in trades:
        all_keys.update(trade.keys())

    # Define preferred column patterns for ordering (generic patterns)
    preferred_patterns = [
        # ID columns first
        'id', 'deal', 'trade', 'transaction', 'order',
        # Then counterparty/client
        'counterparty', 'client', 'party', 'customer',
        # Portfolio/book
        'portfolio', 'book', 'account',
        # Quantity/amount
        'notional', 'quantity', 'qty', 'amount', 'volume', 'size',
        # Type
        'type', 'tradetype', 'deal_type',
        # Dates
        'date', 'settle', 'trade_date', 'value_date',
        # Product/asset
        'underlier', 'product', 'asset', 'instrument', 'security',
        # Currency
        'currency', 'ccy',
        # Status
        'status', 'state',
    ]

    def get_sort_key(col):
        """Generate sort key based on preferred patterns."""
        col_lower = col.lower()
        for i, pattern in enumerate(preferred_patterns):
            if pattern in col_lower:
                return (i, col)
        return (len(preferred_patterns), col)

    # Sort columns by preference, then alphabetically
    ordered = sorted(all_keys, key=get_sort_key)

    return ordered


def get_id_column_name():
    """
    Get the name of the ID column in the trades data.
    Useful for external code that needs to know the ID field name.

    Returns:
        String name of the ID column, or None if no data
    """
    raw_data = get_trades_dataframe()
    trades = _normalize_to_list(raw_data)

    if not trades:
        return None

    return _get_id_column(trades[0])


def get_quantity_column_name():
    """
    Get the name of the quantity/notional column in the trades data.
    Useful for external code that needs to know the quantity field name.

    Returns:
        String name of the quantity column, or None if not found
    """
    raw_data = get_trades_dataframe()
    trades = _normalize_to_list(raw_data)

    if not trades:
        return None

    return _get_quantity_column(trades[0])


def get_counterparty_column_name():
    """
    Get the name of the counterparty/client column in the trades data.
    Useful for external code that needs to know the counterparty field name.

    Returns:
        String name of the counterparty column, or None if not found
    """
    raw_data = get_trades_dataframe()
    trades = _normalize_to_list(raw_data)

    if not trades:
        return None

    return _get_counterparty_column(trades[0])
