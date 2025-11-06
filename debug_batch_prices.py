"""Debug script to test get_current_prices_batch"""

import os
from datetime import datetime
from system_long_short.core.data_provider import DataProvider

# Load credentials (same pattern as scheduler)
api_key = os.environ.get('ALPACA_PAPER_LS_KEY')
api_secret = os.environ.get('ALPACA_PAPER_LS_SECRET')

if not api_key or not api_secret:
    print("ERROR: API credentials not found in environment")
    print("Please set ALPACA_PAPER_LS_KEY and ALPACA_PAPER_LS_SECRET")
    exit(1)

# Initialize data provider
data_provider = DataProvider(api_key, api_secret)

# Test with a single ticker
test_tickers = ['AAPL', 'MSFT', 'GOOGL']

print(f"Current time: {datetime.now()}")
print(f"\nTesting get_current_prices_batch with tickers: {test_tickers}")
print("-" * 60)

# Try to fetch prices
current_prices = data_provider.get_current_prices_batch(test_tickers)

print(f"\nResult: {current_prices}")
print("-" * 60)

# Check if all are None
all_none = all(price is None for price in current_prices.values())
if all_none:
    print("\n⚠️  ALL PRICES ARE NONE!")
    print("This typically means:")
    print("  1. Market is currently closed")
    print("  2. No minute-level data available in the last 15 minutes")
    print("\nTrying single ticker with fallback...")

    # Try fetching with a longer timeframe
    from datetime import timedelta
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    try:
        end = datetime.now()
        start = end - timedelta(hours=24)  # Look back 24 hours

        request_params = StockBarsRequest(
            symbol_or_symbols=['AAPL'],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end
        )

        bars = data_provider.data_client.get_stock_bars(request_params)
        df = bars.df

        print(f"\n24-hour lookback results:")
        print(f"  DataFrame empty: {df.empty}")
        if not df.empty:
            print(f"  Rows: {len(df)}")
            print(f"  Latest timestamp: {df.index[-1]}")
            print(f"  Latest close: {df['close'].iloc[-1]}")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("\n✓ Prices fetched successfully!")
    for ticker, price in current_prices.items():
        print(f"  {ticker}: ${price}")
