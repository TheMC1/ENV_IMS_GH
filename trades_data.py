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
    Core schema fields:
        - DealNumber (int): Unique deal identifier
        - Counterparty (str): Trading counterparty name
        - Portfolio (str): Portfolio/book name
        - Notional (int): Notional amount
        - TradeType (str): Type of trade (Spot, Forward, Option, etc.)
        - SettleDate (date): Settlement date
        - Underlier (str): Underlying asset/instrument
        - DealCurrency (str): Currency code (USD, EUR, GBP, etc.)

    Additional metadata fields can be added as needed.
    The schema is flexible and will be displayed dynamically.

    TODO: Replace this dummy implementation with actual data source
          (e.g., database query, API call, file read, etc.)
    """
    # =========================================================================
    # DUMMY DATA - Replace this section with your actual data fetching logic
    # =========================================================================

    # Generate sample trades for demonstration
    # Schema: DealNumber(int), Counterparty(str), Portfolio(str), Notional(int),
    #         TradeType(str), SettleDate(date), Underlier(str), DealCurrency(str)
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


def get_trade_by_id(deal_number):
    """
    Get a specific trade by its DealNumber.

    Args:
        deal_number: The unique deal number identifier

    Returns:
        Trade dictionary or None if not found
    """
    trades = get_trades_dataframe()
    for trade in trades:
        if trade.get('DealNumber') == deal_number:
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
        'DealNumber',
        'Counterparty',
        'Portfolio',
        'Notional',
        'TradeType',
        'SettleDate',
        'Underlier',
        'DealCurrency',
        'status',
        'trader',
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
