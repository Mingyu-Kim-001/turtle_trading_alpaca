"""Check all MSFT orders today"""
import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime, timedelta

# Load credentials
api_key = os.environ.get('ALPACA_API_KEY')
api_secret = os.environ.get('ALPACA_SECRET_KEY')

if not api_key or not api_secret:
    print("Error: Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
    exit(1)

trading_client = TradingClient(api_key, api_secret, paper=True)

# Get all orders for today
today = datetime.now().date()
yesterday = today - timedelta(days=1)

request = GetOrdersRequest(
    status=QueryOrderStatus.ALL,
    after=yesterday,
    symbols=['MSFT']
)

orders = trading_client.get_orders(filter=request)

print(f"All MSFT orders from {yesterday}:")
print(f"{'Time':<20} {'Order ID':<40} {'Side':<8} {'Qty':<6} {'Type':<15} {'Status':<10} {'Stop':<10} {'Limit':<10} {'Filled Price':<12}")
print("=" * 140)

for order in orders:
    time_str = order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else 'N/A'
    order_id = str(order.id)[:36]
    side = order.side.name
    qty = order.qty
    order_type = order.type.name
    status = order.status.name
    stop_price = f"${float(order.stop_price):.2f}" if order.stop_price else "N/A"
    limit_price = f"${float(order.limit_price):.2f}" if order.limit_price else "N/A"
    filled_price = f"${float(order.filled_avg_price):.2f}" if order.filled_avg_price else "N/A"

    print(f"{time_str:<20} {order_id:<40} {side:<8} {qty:<6} {order_type:<15} {status:<10} {stop_price:<10} {limit_price:<10} {filled_price:<12}")

# Also check current positions
print("\n" + "=" * 140)
print("\nCurrent MSFT position:")
try:
    position = trading_client.get_open_position('MSFT')
    print(f"  Qty: {position.qty} ({position.side})")
    print(f"  Avg entry price: ${float(position.avg_entry_price):.2f}")
    print(f"  Current price: ${float(position.current_price):.2f}")
    print(f"  Market value: ${float(position.market_value):.2f}")
    print(f"  P/L: ${float(position.unrealized_pl):.2f}")
except Exception as e:
    print(f"  No open position or error: {e}")
