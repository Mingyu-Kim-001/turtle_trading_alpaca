"""Test the new real-time price fetching implementation"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from system_long_short.core.data_provider import DataProvider

# Load API credentials
API_KEY = os.getenv('ALPACA_PAPER_LS_KEY') or os.getenv('ALPACA_API_KEY')
API_SECRET = os.getenv('ALPACA_PAPER_LS_SECRET') or os.getenv('ALPACA_SECRET_KEY')

if not API_KEY or not API_SECRET:
    print("ERROR: Missing API credentials")
    exit(1)

# Initialize DataProvider
data_provider = DataProvider(API_KEY, API_SECRET)

print("="*60)
print("TESTING NEW REAL-TIME PRICE FETCHING")
print("="*60)
print(f"Current time: {datetime.now()}")
print()

# Test 1: Single ticker
print("Test 1: get_current_price() for JPM")
print("-"*60)
jpm_price = data_provider.get_current_price('JPM')
print(f"JPM Price: ${jpm_price:.2f}" if jpm_price else "JPM Price: None")
print()

# Test 2: Batch of tickers
print("Test 2: get_current_prices_batch() for multiple tickers")
print("-"*60)
test_tickers = ['JPM', 'AAPL', 'MSFT', 'GOOGL', 'META']
prices = data_provider.get_current_prices_batch(test_tickers)

print(f"Fetched prices for {len(test_tickers)} tickers:")
for ticker in test_tickers:
    price = prices.get(ticker)
    if price:
        print(f"  {ticker}: ${price:.2f}")
    else:
        print(f"  {ticker}: None (no data)")

print()

# Test 3: Performance - larger batch
print("Test 3: Performance test with 16 tickers")
print("-"*60)
large_batch = ['JPM', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'NVDA', 'TSLA',
               'V', 'MA', 'WMT', 'JNJ', 'PG', 'XOM', 'BRK.B', 'UNH']

start_time = datetime.now()
batch_prices = data_provider.get_current_prices_batch(large_batch)
elapsed = (datetime.now() - start_time).total_seconds()

success_count = sum(1 for p in batch_prices.values() if p is not None)
print(f"Successfully fetched {success_count}/{len(large_batch)} prices")
print(f"Time elapsed: {elapsed:.3f} seconds")
print()

# Show a few sample prices
print("Sample prices from batch:")
for ticker in large_batch[:5]:
    price = batch_prices.get(ticker)
    if price:
        print(f"  {ticker}: ${price:.2f}")

print()
print("="*60)
print("✅ TESTING COMPLETE")
print("="*60)
print()
print("Key improvements:")
print("  • Uses latest trade data instead of delayed minute bars")
print("  • Real-time prices during market hours")
print("  • Faster API response (no historical data processing)")
print("  • More accurate for entry/exit decisions")
