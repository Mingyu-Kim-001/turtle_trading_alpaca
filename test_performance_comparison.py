"""Compare performance: old minute bars vs new latest trades"""

import os
import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

# Load API credentials
API_KEY = os.getenv('ALPACA_PAPER_LS_KEY') or os.getenv('ALPACA_API_KEY')
API_SECRET = os.getenv('ALPACA_PAPER_LS_SECRET') or os.getenv('ALPACA_SECRET_KEY')

if not API_KEY or not API_SECRET:
    print("ERROR: Missing API credentials")
    exit(1)

data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

# Typical tickers from your system
test_tickers = ['JPM', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA',
                'V', 'MA', 'WMT', 'JNJ', 'PG', 'XOM', 'BRK.B', 'UNH']

print("="*70)
print("PERFORMANCE COMPARISON: Old Method vs New Method")
print("="*70)
print(f"Testing with {len(test_tickers)} tickers")
print()

# OLD METHOD: 1-minute bars (24 hour lookback)
print("🐌 OLD METHOD: 1-Minute Bars (24-hour lookback)")
print("-"*70)

start = time.time()
try:
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    request_params = StockBarsRequest(
        symbol_or_symbols=test_tickers,
        timeframe=TimeFrame.Minute,
        start=start_time,
        end=end_time
    )

    bars = data_client.get_stock_bars(request_params)
    df = bars.df

    # Extract latest price for each ticker (simulate actual usage)
    old_prices = {}
    for ticker in test_tickers:
        try:
            if isinstance(df.index, pd.MultiIndex):
                ticker_data = df.loc[ticker]
                if not ticker_data.empty:
                    latest_price = ticker_data['close'].iloc[-1]
                    old_prices[ticker] = float(latest_price)
        except:
            pass

    old_elapsed = time.time() - start

    print(f"  Time: {old_elapsed:.3f} seconds")
    print(f"  Prices fetched: {len(old_prices)}/{len(test_tickers)}")
    print(f"  Data points received: {len(df)} minute bars")
    print(f"  Sample: JPM = ${old_prices.get('JPM', 0):.2f}")

except Exception as e:
    print(f"  ERROR: {e}")
    old_elapsed = 999

print()

# NEW METHOD: Latest trade
print("🚀 NEW METHOD: Latest Trade (real-time)")
print("-"*70)

start = time.time()
try:
    request = StockLatestTradeRequest(symbol_or_symbols=test_tickers)
    latest_trades = data_client.get_stock_latest_trade(request)

    new_prices = {}
    for ticker in test_tickers:
        if ticker in latest_trades:
            new_prices[ticker] = float(latest_trades[ticker].price)

    new_elapsed = time.time() - start

    print(f"  Time: {new_elapsed:.3f} seconds")
    print(f"  Prices fetched: {len(new_prices)}/{len(test_tickers)}")
    print(f"  Data points received: {len(test_tickers)} trades (1 per ticker)")
    print(f"  Sample: JPM = ${new_prices.get('JPM', 0):.2f}")

except Exception as e:
    print(f"  ERROR: {e}")
    new_elapsed = 999

print()

# COMPARISON
print("="*70)
print("RESULTS")
print("="*70)
print(f"Old Method: {old_elapsed:.3f}s")
print(f"New Method: {new_elapsed:.3f}s")

if new_elapsed < old_elapsed:
    speedup = old_elapsed / new_elapsed
    savings = old_elapsed - new_elapsed
    print(f"⚡ Speedup: {speedup:.1f}x FASTER")
    print(f"⚡ Time Saved: {savings:.3f} seconds per batch fetch")
else:
    print(f"⚠️  New method is slower by {new_elapsed - old_elapsed:.3f}s")

print()

# Simulate typical intraday cycle
print("="*70)
print("SIMULATED INTRADAY CYCLE (every 5 minutes)")
print("="*70)
print("Typical operations per cycle:")
print("  1. Entry queue: batch fetch (~16 tickers)")
print("  2. Long positions: batch fetch (~5 tickers)")
print("  3. Short positions: batch fetch (~5 tickers)")
print("  4. Pyramid checks: batch fetch (~10 tickers)")
print()

# Estimate total time per cycle
num_batches = 4  # Typical number of batch fetches per cycle
tickers_per_batch = 12  # Average

old_total = old_elapsed * num_batches * (tickers_per_batch / len(test_tickers))
new_total = new_elapsed * num_batches * (tickers_per_batch / len(test_tickers))

print(f"OLD Method Total Time per Cycle: ~{old_total:.2f} seconds")
print(f"NEW Method Total Time per Cycle: ~{new_total:.2f} seconds")
print()

if new_total < 300:  # 5 minutes = 300 seconds
    print(f"✅ SAFE: Total cycle time ({new_total:.2f}s) << 5 minutes (300s)")
    print(f"   Margin: {300 - new_total:.1f} seconds remaining")
else:
    print(f"⚠️  WARNING: Cycle time ({new_total:.2f}s) approaching 5-minute limit")

print()
print("="*70)
