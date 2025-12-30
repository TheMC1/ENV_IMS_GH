"""
Trades Data Source Module

This module provides the interface for fetching trade data.
Currently uses dummy data - replace get_trades_dataframe() with your actual implementation.

The function should return a list of dictionaries, each representing a trade.
"""

from datetime import datetime, timedelta
import random


def get_trades_dataframe():
    """
    Fetch trades data from external source.

    Returns a list of dictionaries with trade information.
    Each trade should have at minimum:
        - trade_id: Unique identifier for the trade
        - client: Client name
        - price: Price per unit
        - quantity: Number of units

    Additional metadata fields can be added as needed.
    The schema is flexible and will be displayed dynamically.

    TODO: Replace this dummy implementation with actual data source
          (e.g., database query, API call, file read, etc.)
    """
    # =========================================================================
    # DUMMY DATA - Replace this section with your actual data fetching logic
    # =========================================================================

    # Generate sample trades for demonstration
    dummy_trades = [
        {
            'trade_id': 'TRD-2024-001',
            'client': 'Acme Corporation',
            'counterparty': 'Green Energy Ltd',
            'trade_date': '2024-12-15',
            'settlement_date': '2024-12-20',
            'product_type': 'VCU',
            'registry': 'Verra',
            'vintage': '2023',
            'quantity': 1000,
            'price': 12.50,
            'total_value': 12500.00,
            'status': 'Pending',
            'buy_warranty_start': '2024-12-20',
            'buy_warranty_end': '2025-12-20',
            'notes': 'Q4 carbon offset purchase'
        },
        {
            'trade_id': 'TRD-2024-002',
            'client': 'Beta Industries',
            'counterparty': 'Carbon Solutions Inc',
            'trade_date': '2024-12-18',
            'settlement_date': '2024-12-23',
            'product_type': 'VCU',
            'registry': 'Gold Standard',
            'vintage': '2022',
            'quantity': 500,
            'price': 15.00,
            'total_value': 7500.00,
            'status': 'Confirmed',
            'buy_warranty_start': '2024-12-23',
            'buy_warranty_end': '2025-06-23',
            'notes': 'Renewable energy credits'
        },
        {
            'trade_id': 'TRD-2024-003',
            'client': 'Gamma Holdings',
            'counterparty': 'EcoCredits LLC',
            'trade_date': '2024-12-20',
            'settlement_date': '2024-12-27',
            'product_type': 'REC',
            'registry': 'ACR',
            'vintage': '2024',
            'quantity': 2500,
            'price': 8.75,
            'total_value': 21875.00,
            'status': 'Pending',
            'buy_warranty_start': '2024-12-27',
            'buy_warranty_end': '2025-12-27',
            'notes': 'Forest conservation project'
        },
        {
            'trade_id': 'TRD-2024-004',
            'client': 'Delta Corp',
            'counterparty': 'Sustainability Partners',
            'trade_date': '2024-12-22',
            'settlement_date': '2024-12-29',
            'product_type': 'VCU',
            'registry': 'Verra',
            'vintage': '2023',
            'quantity': 750,
            'price': 11.25,
            'total_value': 8437.50,
            'status': 'Allocated',
            'buy_warranty_start': '2024-12-29',
            'buy_warranty_end': '2025-06-29',
            'notes': 'Biodiversity project credits'
        },
        {
            'trade_id': 'TRD-2024-005',
            'client': 'Epsilon Energy',
            'counterparty': 'Net Zero Trading',
            'trade_date': '2024-12-28',
            'settlement_date': '2025-01-05',
            'product_type': 'CER',
            'registry': 'CAR',
            'vintage': '2024',
            'quantity': 3000,
            'price': 9.50,
            'total_value': 28500.00,
            'status': 'Pending',
            'buy_warranty_start': '2025-01-05',
            'buy_warranty_end': '2026-01-05',
            'notes': 'Methane capture project'
        }
    ]

    return dummy_trades

    # =========================================================================
    # Example of how to replace with actual implementation:
    #
    # import pandas as pd
    # import requests
    #
    # # Option 1: From API
    # response = requests.get('https://your-api.com/trades')
    # trades = response.json()
    # return trades
    #
    # # Option 2: From database
    # import sqlite3
    # conn = sqlite3.connect('trades.db')
    # df = pd.read_sql_query("SELECT * FROM trades", conn)
    # return df.to_dict('records')
    #
    # # Option 3: From CSV/Excel
    # df = pd.read_excel('trades.xlsx')
    # return df.to_dict('records')
    # =========================================================================


def get_trade_by_id(trade_id):
    """
    Get a specific trade by its ID.

    Args:
        trade_id: The unique trade identifier

    Returns:
        Trade dictionary or None if not found
    """
    trades = get_trades_dataframe()
    for trade in trades:
        if trade.get('trade_id') == trade_id:
            return trade
    return None


def get_trade_headers():
    """
    Get the column headers for trades display.

    Returns:
        List of column names in preferred display order
    """
    # Define preferred column order
    preferred_order = [
        'trade_id',
        'client',
        'counterparty',
        'trade_date',
        'settlement_date',
        'product_type',
        'registry',
        'vintage',
        'quantity',
        'price',
        'total_value',
        'status',
        'buy_warranty_start',
        'buy_warranty_end',
        'notes'
    ]

    trades = get_trades_dataframe()
    if not trades:
        return preferred_order

    # Get all unique keys
    all_keys = set()
    for trade in trades:
        all_keys.update(trade.keys())

    # Order by preferred, then alphabetically for remaining
    ordered = [h for h in preferred_order if h in all_keys]
    remaining = sorted([h for h in all_keys if h not in preferred_order])
    ordered.extend(remaining)

    return ordered
