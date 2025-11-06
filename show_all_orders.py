"""Show all open orders and recent orders"""
import os
import sys
import json
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime, timedelta

# Load credentials
api_key = os.environ.get('ALPACA_API_KEY')
api_secret = os.environ.get('ALPACA_SECRET_KEY')

if not api_key or not api_secret:
    print("Error: Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
    sys.exit(1)

trading_client = TradingClient(api_key, api_secret, paper=True)

# Load tracked orders from state
try:
    with open('system_long_short/trading_state_ls.json', 'r') as f:
        state = json.load(f)
        tracked_entry_orders = state.get('pending_entry_orders', {})
        tracked_pyramid_orders = state.get('pending_pyramid_orders', {})
except Exception as e:
    print(f"Could not load state: {e}")
    tracked_entry_orders = {}
    tracked_pyramid_orders = {}

print("=" * 140)
print("OPEN ORDERS IN ALPACA:")
print("=" * 140)

try:
    request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
    open_orders = trading_client.get_orders(filter=request)

    if not open_orders:
        print("No open orders.")
    else:
        print(f"{'Time':<20} {'Symbol':<8} {'Side':<6} {'Qty':<6} {'Status':<10} {'Stop':<10} {'Limit':<10} {'Order ID':<40} {'Tracked?':<10}")
        print("-" * 140)

        for order in open_orders:
            time_str = order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else 'N/A'
            symbol = order.symbol
            side = order.side.name
            qty = order.qty
            status = order.status.name
            stop = f"${float(order.stop_price):.2f}" if order.stop_price else "N/A"
            limit = f"${float(order.limit_price):.2f}" if order.limit_price else "N/A"
            order_id = str(order.id)

            # Check if tracked
            is_tracked = "YES" if (order_id in tracked_entry_orders.values() or
                                   order_id in tracked_pyramid_orders.values()) else "ZOMBIE"

            print(f"{time_str:<20} {symbol:<8} {side:<6} {qty:<6} {status:<10} {stop:<10} {limit:<10} {order_id:<40} {is_tracked:<10}")

except Exception as e:
    print(f"Error: {e}")

print()
print("=" * 140)
print("TRACKED ORDERS IN SYSTEM STATE:")
print("=" * 140)
print(f"Pending entry orders: {tracked_entry_orders}")
print(f"Pending pyramid orders: {tracked_pyramid_orders}")
print()
