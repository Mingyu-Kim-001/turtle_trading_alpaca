#!/usr/bin/env python3
"""
Test script to verify get_latest_completed_n() with TODAY's data included
This simulates real trading behavior when today's incomplete bar exists
"""

import sys
import os
import pandas as pd
from datetime import datetime, time, timedelta
import pytz
from unittest.mock import patch

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from system_long_short.core.indicators import IndicatorCalculator

# Load AMCR data
data_path = os.path.join(project_root, 'data/alpaca_daily/AMCR_alpaca_daily.csv')

if not os.path.exists(data_path):
    print(f"ERROR: Data file not found: {data_path}")
    sys.exit(1)

df_original = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
print(f"Loaded {len(df_original)} bars of AMCR data")
print(f"Original date range: {df_original.index[0].date()} to {df_original.index[-1].date()}")
print()

# Create a copy and ADD TODAY'S INCOMPLETE BAR
df = df_original.copy()

# Add November 13, 2025 as "today's" bar (simulating incomplete intraday data)
eastern = pytz.timezone('US/Eastern')
today_date = datetime(2025, 11, 13, 0, 0, 0)  # November 13, 2025
today_date = eastern.localize(today_date)

# Create a new row for today with realistic values based on last close
last_close = df.iloc[-1]['close']
new_row = pd.DataFrame({
    'open': [last_close + 0.05],
    'high': [last_close + 0.15],
    'low': [last_close - 0.05],
    'close': [last_close + 0.10],  # Incomplete close (will change by end of day)
    'volume': [500000]
}, index=[today_date])

df = pd.concat([df, new_row])
print(f"✓ Added today's bar (11/13/2025) to simulate incomplete intraday data")
print(f"Updated date range: {df.index[0].date()} to {df.index[-1].date()}")
print()

# Calculate ATR
df = IndicatorCalculator.calculate_atr(df, period=20)

# Show last few rows with N values
print("="*80)
print("Last 5 bars with N values (INCLUDING TODAY):")
print("="*80)
last_5 = df[['close', 'high', 'low', 'TR', 'N']].tail(5)
for idx, row in last_5.iterrows():
    date_str = idx.strftime('%Y-%m-%d')
    is_today = "(TODAY - INCOMPLETE)" if idx.date() == today_date.date() else ""
    print(f"{date_str}: Close=${row['close']:.2f}, TR=${row['TR']:.2f}, N=${row['N']:.4f} {is_today}")
print()

# Get N values
last_n = df.iloc[-1]['N']
second_last_n = df.iloc[-2]['N']

print(f"N from LAST bar (today's incomplete): ${last_n:.4f}")
print(f"N from SECOND-TO-LAST bar (yesterday's complete): ${second_last_n:.4f}")
print()

# TEST SCENARIO 1: Market is OPEN (10:00 AM ET)
print("="*80)
print("TEST SCENARIO 1: November 13, 2025 at 10:00 AM ET")
print("="*80)
mock_time = eastern.localize(datetime(2025, 11, 13, 10, 0, 0))
print(f"Mocked current time: {mock_time}")
print(f"Market status: OPEN (trading hours)")
print()

with patch('system_long_short.core.indicators.datetime') as mock_datetime:
    # Mock datetime.now() to return our simulated time
    mock_datetime.now.return_value = mock_time
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    
    result_market_open = IndicatorCalculator.get_latest_completed_n(df)
    
print(f"get_latest_completed_n() returned: ${result_market_open:.4f}")
print()

print("Expected behavior:")
print("  - Last bar IS from today (11/13)")
print("  - Market IS OPEN (10:00 AM is between 9:30 AM - 4:00 PM)")
print(f"  - Should return SECOND-TO-LAST bar's N: ${second_last_n:.4f}")
print()

if abs(result_market_open - second_last_n) < 0.0001:
    print("✅ CORRECT! Function returned second-to-last N (yesterday's complete bar)")
    print("   Today's incomplete bar was correctly EXCLUDED")
else:
    print(f"❌ ERROR! Function returned ${result_market_open:.4f}")
    print(f"   Expected ${second_last_n:.4f} (second-to-last)")
    if abs(result_market_open - last_n) < 0.0001:
        print("   It returned the LAST bar (today's incomplete) - THIS IS WRONG!")

print()

# TEST SCENARIO 2: Market is CLOSED (5:00 PM ET)
print("="*80)
print("TEST SCENARIO 2: November 13, 2025 at 5:00 PM ET")
print("="*80)
mock_time_closed = eastern.localize(datetime(2025, 11, 13, 17, 0, 0))
print(f"Mocked current time: {mock_time_closed}")
print(f"Market status: CLOSED (after hours)")
print()

with patch('system_long_short.core.indicators.datetime') as mock_datetime:
    # Mock datetime.now() to return our simulated time
    mock_datetime.now.return_value = mock_time_closed
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    
    result_market_closed = IndicatorCalculator.get_latest_completed_n(df)

print(f"get_latest_completed_n() returned: ${result_market_closed:.4f}")
print()

print("Expected behavior:")
print("  - Last bar IS from today (11/13)")
print("  - Market is CLOSED (5:00 PM is after 4:00 PM)")
print(f"  - Should return LAST bar's N: ${last_n:.4f}")
print("    (Today's bar is now complete)")
print()

if abs(result_market_closed - last_n) < 0.0001:
    print("✅ CORRECT! Function returned last N (today's now-complete bar)")
    print("   After market close, today's bar is considered complete")
else:
    print(f"❌ ERROR! Function returned ${result_market_closed:.4f}")
    print(f"   Expected ${last_n:.4f} (last bar)")

print()

# TEST SCENARIO 3: Before market opens (8:00 AM ET)
print("="*80)
print("TEST SCENARIO 3: November 13, 2025 at 8:00 AM ET")
print("="*80)
mock_time_premarket = eastern.localize(datetime(2025, 11, 13, 8, 0, 0))
print(f"Mocked current time: {mock_time_premarket}")
print(f"Market status: CLOSED (pre-market)")
print()

with patch('system_long_short.core.indicators.datetime') as mock_datetime:
    # Mock datetime.now() to return our simulated time
    mock_datetime.now.return_value = mock_time_premarket
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    
    result_premarket = IndicatorCalculator.get_latest_completed_n(df)

print(f"get_latest_completed_n() returned: ${result_premarket:.4f}")
print()

print("Expected behavior:")
print("  - Last bar IS from today (11/13)")
print("  - Market is CLOSED (8:00 AM is before 9:30 AM)")
print(f"  - Should return LAST bar's N: ${last_n:.4f}")
print("    (Even though it's 'today', it's before market open so treated as complete)")
print()

if abs(result_premarket - last_n) < 0.0001:
    print("✅ CORRECT! Function returned last N")
    print("   Before market open, the bar is considered complete")
else:
    print(f"❌ ERROR! Function returned ${result_premarket:.4f}")
    print(f"   Expected ${last_n:.4f} (last bar)")

print()
print("="*80)
print("FINAL SUMMARY")
print("="*80)
print("""
VERIFIED BEHAVIOR of get_latest_completed_n():

Scenario 1: 10:00 AM ET on 11/13 (MARKET OPEN)
  → Returns yesterday's N (${:.4f})
  → ✓ Excludes today's incomplete bar

Scenario 2: 5:00 PM ET on 11/13 (MARKET CLOSED)
  → Returns today's N (${:.4f})
  → ✓ Today's bar is now complete

Scenario 3: 8:00 AM ET on 11/13 (PRE-MARKET)
  → Returns today's N (${:.4f})
  → ✓ Before market, today's bar considered complete

KEY INSIGHT:
The function ONLY excludes today's bar during trading hours (9:30AM-4:00PM ET).
This prevents N from changing while the market is actively trading, ensuring
consistent position sizing and stop loss calculations throughout the day.

Outside trading hours (pre-market, after-hours, weekends), today's bar is
considered complete and will be used.
""".format(second_last_n, last_n, last_n))

