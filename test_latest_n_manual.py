#!/usr/bin/env python3
"""
Manual test to verify get_latest_completed_n() logic with today's data
Shows step-by-step what the function does
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
df_original = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)

# Create a copy and ADD TODAY'S INCOMPLETE BAR (November 13, 2025)
df = df_original.copy()
eastern = pytz.timezone('US/Eastern')
today_date = datetime(2025, 11, 13, 0, 0, 0)
today_date = eastern.localize(today_date)

last_close = df.iloc[-1]['close']
new_row = pd.DataFrame({
    'open': [last_close + 0.05],
    'high': [last_close + 0.15],
    'low': [last_close - 0.05],
    'close': [last_close + 0.10],
    'volume': [500000]
}, index=[today_date])

df = pd.concat([df, new_row])
df = IndicatorCalculator.calculate_atr(df, period=20)

print("="*80)
print("MANUAL WALKTHROUGH: get_latest_completed_n() Logic")
print("="*80)
print()
print(f"Data loaded with {len(df)} bars")
print()

# Show last 3 bars
print("Last 3 bars:")
last_3 = df[['close', 'N']].tail(3)
for i, (idx, row) in enumerate(last_3.iterrows()):
    bar_num = len(df) - len(last_3) + i + 1
    date_str = idx.strftime('%Y-%m-%d')
    is_today = " ← TODAY (11/13/2025)" if idx.date() == today_date.date() else ""
    print(f"  Bar {bar_num}: {date_str}, N=${row['N']:.4f}{is_today}")

print()
print("-"*80)
print("MANUAL LOGIC WALKTHROUGH")
print("-"*80)
print()

# Extract the values we'll use
last_bar_date = df.index[-1]
last_bar_date_only = last_bar_date.date() if hasattr(last_bar_date, 'date') else last_bar_date.to_pydatetime().date()
last_n = df.iloc[-1]['N']
second_last_n = df.iloc[-2]['N']

print(f"Step 1: Get last bar's date")
print(f"  last_bar_date = {last_bar_date_only}")
print()

print(f"Step 2: Get today's date in ET timezone")
now_eastern = datetime.now(eastern)
today = now_eastern.date()
print(f"  today = {today}")
print(f"  current time (ET) = {now_eastern.strftime('%H:%M:%S')}")
print()

print(f"Step 3: Check if last_bar_date == today")
print(f"  {last_bar_date_only} == {today} ?")
if last_bar_date_only == today:
    print(f"  → YES, last bar is from TODAY")
    print()
    
    print(f"Step 4: Since last bar is today, check if market is open")
    market_time = now_eastern.time()
    market_open = time(9, 30)
    market_close = time(16, 0)
    
    print(f"  market_time = {market_time}")
    print(f"  market_open = {market_open}")
    print(f"  market_close = {market_close}")
    print(f"  Is {market_open} <= {market_time} <= {market_close} ?")
    
    if market_open <= market_time <= market_close:
        print(f"  → YES, market IS OPEN")
        print()
        print(f"Step 5: Market is open, last bar is incomplete")
        print(f"  → Return SECOND-TO-LAST bar's N")
        print(f"  → return df.iloc[-2]['N'] = ${second_last_n:.4f}")
        expected_result = second_last_n
        reason = "Market OPEN, excluding today's incomplete bar"
    else:
        print(f"  → NO, market is CLOSED")
        print()
        print(f"Step 5: Market is closed, today's bar is complete")
        print(f"  → Return LAST bar's N")
        print(f"  → return df.iloc[-1]['N'] = ${last_n:.4f}")
        expected_result = last_n
        reason = "Market CLOSED, today's bar is complete"
else:
    print(f"  → NO, last bar is from a previous day")
    print()
    print(f"Step 4: Last bar is from a previous day (already complete)")
    print(f"  → Return LAST bar's N")
    print(f"  → return df.iloc[-1]['N'] = ${last_n:.4f}")
    expected_result = last_n
    reason = "Last bar is from a previous day"

print()
print("="*80)
print("ACTUAL FUNCTION CALL")
print("="*80)
actual_result = IndicatorCalculator.get_latest_completed_n(df)
print(f"get_latest_completed_n() returned: ${actual_result:.4f}")
print(f"Expected: ${expected_result:.4f}")
print(f"Reason: {reason}")
print()

if abs(actual_result - expected_result) < 0.0001:
    print("✅ CORRECT! Function works as expected")
else:
    print(f"❌ MISMATCH! Got ${actual_result:.4f}, expected ${expected_result:.4f}")

print()
print("="*80)
print("KEY FINDINGS")
print("="*80)
print()
print(f"Last bar date: {last_bar_date_only}")
print(f"Today's date: {today}")
print(f"Current time (ET): {now_eastern.strftime('%H:%M:%S')}")
print(f"Market hours: 09:30:00 - 16:00:00")
print()

if last_bar_date_only == today:
    print("✓ Last bar IS from today (11/13/2025)")
    market_time = now_eastern.time()
    if time(9, 30) <= market_time <= time(16, 0):
        print("✓ Market IS OPEN - Function returns YESTERDAY's N")
        print(f"  → N = ${second_last_n:.4f} (from bar on {df.index[-2].date()})")
        print()
        print("This EXCLUDES today's incomplete bar, preventing N from")
        print("changing throughout the trading day.")
    else:
        print("✓ Market is CLOSED - Function returns TODAY's N")
        print(f"  → N = ${last_n:.4f} (from bar on {df.index[-1].date()})")
        print()
        print("After market close, today's bar is considered complete.")
else:
    print(f"✗ Last bar is NOT from today (it's from {last_bar_date_only})")
    print("  Function returns the LAST available bar's N")
    print(f"  → N = ${last_n:.4f}")
    print()
    print("To test the 'exclude today' logic, you would need:")
    print("1. Data that includes 11/13/2025 as the last bar")
    print("2. Run this test during market hours (9:30 AM - 4:00 PM ET)")

print()
print("="*80)
print("ANSWER TO YOUR QUESTION")
print("="*80)
print()
print("Q: Does get_latest_completed_n() truly exclude today's date?")
print()
print("A: YES, but ONLY during market hours (9:30 AM - 4:00 PM ET).")
print()
print("   The function checks:")
print("   1. Is the last bar from today?")
print("   2. Is the current time between 9:30 AM and 4:00 PM ET?")
print()
print("   If BOTH are true → Returns SECOND-TO-LAST bar (excludes today)")
print("   If EITHER is false → Returns LAST bar")
print()
print("   This ensures:")
print("   - N doesn't change while actively trading")
print("   - Position sizing stays consistent throughout the day")
print("   - Stop losses are calculated with stable N values")
print()

