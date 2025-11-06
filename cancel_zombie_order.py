"""Cancel the zombie MSFT order"""
import os
import sys
from alpaca.trading.client import TradingClient

# The zombie order ID
ZOMBIE_ORDER_ID = "bdf234d3-624c-4e85-8592-75a39e5eb23a"

# Load credentials
api_key = os.environ.get('ALPACA_API_KEY')
api_secret = os.environ.get('ALPACA_SECRET_KEY')

if not api_key or not api_secret:
    print("Error: Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
    print("\nUsage:")
    print("  export ALPACA_API_KEY='your_key'")
    print("  export ALPACA_SECRET_KEY='your_secret'")
    print("  python cancel_zombie_order.py")
    sys.exit(1)

trading_client = TradingClient(api_key, api_secret, paper=True)

print(f"Attempting to cancel zombie order: {ZOMBIE_ORDER_ID}")
print()

try:
    # Check order status first
    order = trading_client.get_order_by_id(ZOMBIE_ORDER_ID)
    print(f"Order found!")
    print(f"  Symbol: {order.symbol}")
    print(f"  Side: {order.side.name}")
    print(f"  Qty: {order.qty}")
    print(f"  Status: {order.status.name}")
    print(f"  Stop: ${order.stop_price}")
    print(f"  Limit: ${order.limit_price}")
    print()

    if order.status.name in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
        print(f"Order is already {order.status.name}. No action needed.")
    else:
        print("Order is still open. Canceling...")
        trading_client.cancel_order_by_id(ZOMBIE_ORDER_ID)
        print("✓ Order successfully canceled!")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
