#!/usr/bin/env python3
"""
Test script to verify get_latest_completed_n() behavior
Tests with AMCR ticker at 11/13 10:00AM ET
"""

import sys
import os
import pandas as pd
from datetime import datetime, time
import pytz

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from system_long_short.core.indicators import IndicatorCalculator

# Load AMCR data
data_path = os.path.join(project_root, 'data/alpaca_daily/AMCR_alpaca_daily.csv')

if not os.path.exists(data_path):
    print(f"ERROR: Data file not found: {data_path}")
    sys.exit(1)

df = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
print(f"Loaded {len(df)} bars of AMCR data")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print()

# Calculate ATR
df = IndicatorCalculator.calculate_atr(df, period=20)

# Show last few rows with N values
print("="*80)
print("Last 5 bars with N values:")
print("="*80)
last_5 = df[['close', 'high', 'low', 'TR', 'N']].tail(5)
for idx, row in last_5.iterrows():
    date_str = idx.strftime('%Y-%m-%d')
    print(f"{date_str}: Close=${row['close']:.2f}, TR=${row['TR']:.2f}, N=${row['N']:.2f}")
print()

# Test the function behavior
print("="*80)
print("Testing get_latest_completed_n() behavior")
print("="*80)
print()

# Create a mock scenario - we'll temporarily mock the datetime to simulate 11/13 10:00AM ET
# First, let's see what the actual last date in the data is
last_date = df.index[-1]
second_last_date = df.index[-2] if len(df) >= 2 else None

print(f"Last bar date: {last_date.strftime('%Y-%m-%d')}")
if second_last_date:
    print(f"Second-to-last bar date: {second_last_date.strftime('%Y-%m-%d')}")
print()

# Get actual N values
last_n = df.iloc[-1]['N']
second_last_n = df.iloc[-2]['N'] if len(df) >= 2 else None

print(f"N from last bar: ${last_n:.4f}")
if second_last_n is not None:
    print(f"N from second-to-last bar: ${second_last_n:.4f}")
print()

# Now let's manually check the logic
eastern = pytz.timezone('US/Eastern')

# Scenario 1: Current time is 11/13/2025 10:00AM ET (during market hours)
print("="*80)
print("SCENARIO 1: November 13, 2025 at 10:00 AM ET (Market Open)")
print("="*80)
simulated_time = eastern.localize(datetime(2025, 11, 13, 10, 0, 0))
print(f"Simulated current time: {simulated_time}")

# Check if last bar is from "today"
last_bar_date = df.index[-1]
if hasattr(last_bar_date, 'date'):
    last_bar_date_only = last_bar_date.date()
elif hasattr(last_bar_date, 'to_pydatetime'):
    last_bar_date_only = last_bar_date.to_pydatetime().date()
else:
    last_bar_date_only = last_bar_date

simulated_today = simulated_time.date()
print(f"Last bar date: {last_bar_date_only}")
print(f"Simulated today: {simulated_today}")

market_open = time(9, 30)
market_close = time(16, 0)
market_time = simulated_time.time()

print(f"Market time: {market_time}")
print(f"Market hours: {market_open} to {market_close}")
print(f"Is market open? {market_open <= market_time <= market_close}")

if last_bar_date_only == simulated_today:
    print("✓ Last bar is from TODAY")
    if market_open <= market_time <= market_close:
        print("✓ Market IS OPEN - Should use SECOND-TO-LAST bar's N")
        expected_n = second_last_n
        print(f"Expected N: ${expected_n:.4f} (from second-to-last bar)")
    else:
        print("✗ Market is CLOSED - Should use LAST bar's N")
        expected_n = last_n
        print(f"Expected N: ${expected_n:.4f} (from last bar)")
else:
    print("✗ Last bar is NOT from today")
    print("Should use LAST bar's N")
    expected_n = last_n
    print(f"Expected N: ${expected_n:.4f} (from last bar)")

print()

# Scenario 2: Current time is 11/13/2025 5:00PM ET (after market close)
print("="*80)
print("SCENARIO 2: November 13, 2025 at 5:00 PM ET (After Market Close)")
print("="*80)
simulated_time_2 = eastern.localize(datetime(2025, 11, 13, 17, 0, 0))
print(f"Simulated current time: {simulated_time_2}")

market_time_2 = simulated_time_2.time()
print(f"Market time: {market_time_2}")
print(f"Is market open? {market_open <= market_time_2 <= market_close}")

if last_bar_date_only == simulated_today:
    print("✓ Last bar is from TODAY")
    if market_open <= market_time_2 <= market_close:
        print("✗ Market IS OPEN - Should use SECOND-TO-LAST bar's N")
        expected_n_2 = second_last_n
        print(f"Expected N: ${expected_n_2:.4f} (from second-to-last bar)")
    else:
        print("✓ Market is CLOSED - Should use LAST bar's N")
        expected_n_2 = last_n
        print(f"Expected N: ${expected_n_2:.4f} (from last bar)")
else:
    print("✗ Last bar is NOT from today")
    print("Should use LAST bar's N")
    expected_n_2 = last_n
    print(f"Expected N: ${expected_n_2:.4f} (from last bar)")

print()

# Now let's actually call the function and see what it returns
# Note: This will use the ACTUAL current time, not simulated
print("="*80)
print("ACTUAL FUNCTION CALL (using real current time)")
print("="*80)
now_actual = datetime.now(eastern)
print(f"Actual current time: {now_actual}")
print(f"Actual current date: {now_actual.date()}")

actual_result = IndicatorCalculator.get_latest_completed_n(df)
print(f"get_latest_completed_n() returned: ${actual_result:.4f}")

# Determine which N it should have returned
actual_market_time = now_actual.time()
actual_is_market_open = market_open <= actual_market_time <= market_close

if last_bar_date_only == now_actual.date():
    print(f"Last bar IS from today ({now_actual.date()})")
    if actual_is_market_open:
        print(f"Market IS OPEN (time is {actual_market_time})")
        print(f"Should return N from SECOND-TO-LAST bar: ${second_last_n:.4f}")
        if abs(actual_result - second_last_n) < 0.0001:
            print("✅ CORRECT! Function returned second-to-last N")
        else:
            print(f"❌ ERROR! Function returned {actual_result:.4f}, expected {second_last_n:.4f}")
    else:
        print(f"Market is CLOSED (time is {actual_market_time})")
        print(f"Should return N from LAST bar: ${last_n:.4f}")
        if abs(actual_result - last_n) < 0.0001:
            print("✅ CORRECT! Function returned last N")
        else:
            print(f"❌ ERROR! Function returned {actual_result:.4f}, expected {last_n:.4f}")
else:
    print(f"Last bar is NOT from today (last bar: {last_bar_date_only}, today: {now_actual.date()})")
    print(f"Should return N from LAST bar: ${last_n:.4f}")
    if abs(actual_result - last_n) < 0.0001:
        print("✅ CORRECT! Function returned last N")
    else:
        print(f"❌ ERROR! Function returned {actual_result:.4f}, expected {last_n:.4f}")

print()
print("="*80)
print("SUMMARY")
print("="*80)
print("""
The get_latest_completed_n() function works as follows:

1. If last bar is from TODAY and market is OPEN (9:30AM-4:00PM ET):
   → Returns SECOND-TO-LAST bar's N (excludes today's incomplete bar)

2. If last bar is from TODAY but market is CLOSED:
   → Returns LAST bar's N (today's bar is complete)

3. If last bar is from a PREVIOUS day:
   → Returns LAST bar's N (it's already complete)

This ensures N doesn't change throughout the trading day, providing consistent
values for position sizing and stop loss calculations.
""")

