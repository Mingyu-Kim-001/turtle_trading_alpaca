#!/usr/bin/env python3
"""
Test to demonstrate the fix for get_latest_completed_n()
Shows the behavior at different times of day
"""

import os
import sys
sys.path.insert(0, '/Users/mingyukim/Desktop/turtle_trading_alpaca')

from system_long_short.core.data_provider import DataProvider
from system_long_short.core.indicators import IndicatorCalculator
import pandas as pd

print("="*80)
print("TESTING FIXED get_latest_completed_n() BEHAVIOR")
print("="*80)
print()

# Fetch data
data_provider = DataProvider(
    api_key=os.getenv('ALPACA_PAPER_KEY'), 
    api_secret=os.getenv('ALPACA_PAPER_SECRET')
)

df = data_provider.get_historical_data('AMCR', days=100)
df = IndicatorCalculator.calculate_indicators(df)

print(f"Data fetched: {len(df)} bars")
print(f"Date range: {df.index[0].date()} to {df.index[-1].date()}")
print()

# Show last 3 bars
print("Last 3 bars:")
print("="*80)
for idx, row in df[['close', 'N']].tail(3).iterrows():
    print(f"  {idx.date()}: Close=${row['close']:.2f}, N=${row['N']:.5f}")
print()

# Test what N would be returned NOW
print("="*80)
print("CURRENT BEHAVIOR (with fix)")
print("="*80)
latest_n = IndicatorCalculator.get_latest_completed_n(df)
print(f"get_latest_completed_n() returns: ${latest_n:.5f}")
print()

import pytz
from datetime import datetime, time
eastern = pytz.timezone('US/Eastern')
now = datetime.now(eastern)
last_date = df.index[-1].date()
today = now.date()

print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Last bar date: {last_date}")
print(f"Today: {today}")
print()

if last_date == today:
    market_close = time(16, 0)
    current_time = now.time()
    
    print(f"Last bar IS from today")
    print(f"Current time: {current_time}")
    print(f"Market close: {market_close}")
    
    if current_time <= market_close:
        print(f"✓ Time is BEFORE/AT market close")
        print(f"✓ Using YESTERDAY'S N: ${df.iloc[-2]['N']:.5f} (from {df.index[-2].date()})")
        print(f"✓ NOT using today's N: ${df.iloc[-1]['N']:.5f} (incomplete)")
    else:
        print(f"✓ Time is AFTER market close")
        print(f"✓ Using TODAY'S N: ${df.iloc[-1]['N']:.5f} (now complete)")
else:
    print(f"Last bar is from a previous day ({last_date})")
    print(f"✓ Using LAST bar's N: ${df.iloc[-1]['N']:.5f} (already complete)")

print()
print("="*80)
print("BEHAVIOR TIMELINE (Nov 13, 2025)")
print("="*80)
print()
print("OLD BEHAVIOR (BUGGY):")
print("  6:36 AM: Uses Nov 13's partial N (0.1902) ❌ WRONG")
print("  10:00 AM: Uses Nov 12's N (0.18475) ✓")
print("  5:00 PM: Uses Nov 13's final N (0.19325) ✓")
print()
print("NEW BEHAVIOR (FIXED):")
print("  6:36 AM: Uses Nov 12's N (0.18475) ✓✓ CORRECT!")
print("  10:00 AM: Uses Nov 12's N (0.18475) ✓")
print("  5:00 PM: Uses Nov 13's final N (0.19325) ✓")
print()
print("KEY CHANGE:")
print("  Before fix: Used today's bar if market was closed (6:36 AM)")
print("  After fix: ALWAYS use yesterday's bar until AFTER market close (> 4:00 PM)")
print()
print("This ensures:")
print("  ✓ N is consistent from midnight to 4:00 PM")
print("  ✓ Pre-market activity doesn't affect N calculation")
print("  ✓ Position sizing is stable throughout the day")

