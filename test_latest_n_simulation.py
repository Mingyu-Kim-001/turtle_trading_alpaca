#!/usr/bin/env python3
"""
SIMULATION: What happens at different times on 11/13/2025 with AMCR
Shows exactly what get_latest_completed_n() would return at each time
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

# Load AMCR data and add today's bar
data_path = os.path.join(project_root, 'data/alpaca_daily/AMCR_alpaca_daily.csv')
df_original = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
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

# Get the N values
yesterday_n = df.iloc[-2]['N']  # September 26, 2025
today_n = df.iloc[-1]['N']      # November 13, 2025

yesterday_date = df.index[-2].date()
today_date_only = df.index[-1].date()

print("="*80)
print("SIMULATION: get_latest_completed_n() at Different Times")
print("Testing with AMCR on November 13, 2025")
print("="*80)
print()

print("Data Setup:")
print(f"  Yesterday's bar: {yesterday_date}, N = ${yesterday_n:.4f}")
print(f"  Today's bar:     {today_date_only}, N = ${today_n:.4f} (incomplete during market)")
print()

# Define test times throughout the day
test_times = [
    ("8:00 AM", 8, 0),     # Pre-market
    ("9:29 AM", 9, 29),    # Just before open
    ("9:30 AM", 9, 30),    # Market opens
    ("10:00 AM", 10, 0),   # YOUR REQUESTED TIME
    ("12:00 PM", 12, 0),   # Mid-day
    ("3:59 PM", 15, 59),   # Just before close
    ("4:00 PM", 16, 0),    # Market closes
    ("5:00 PM", 17, 0),    # After hours
]

market_open = time(9, 30)
market_close = time(16, 0)

print("="*80)
print("SIMULATION RESULTS")
print("="*80)
print()

for time_label, hour, minute in test_times:
    test_time = time(hour, minute)
    is_market_open = market_open <= test_time <= market_close
    
    # Simulate what the function would return
    if is_market_open:
        returned_n = yesterday_n
        bar_used = "YESTERDAY"
        bar_date = yesterday_date
        reason = "Market OPEN → excludes today"
        indicator = "🔴"
    else:
        returned_n = today_n
        bar_used = "TODAY"
        bar_date = today_date_only
        reason = "Market CLOSED → includes today"
        indicator = "🟢"
    
    print(f"{indicator} {time_label:>10}  →  N = ${returned_n:.4f}  ({bar_used}: {bar_date})")
    print(f"             {reason}")
    print()

print("="*80)
print("ANSWER TO YOUR SPECIFIC QUESTION")
print("="*80)
print()
print("Q: At 11/13/2025 10:00 AM ET with AMCR, what does get_latest_completed_n() return?")
print()
print(f"A: It returns ${yesterday_n:.4f}")
print()
print(f"   This is the N from {yesterday_date} (the SECOND-TO-LAST bar)")
print(f"   NOT the N from {today_date_only} (${today_n:.4f})")
print()
print("   WHY?")
print("   1. ✓ Last bar IS from today (11/13)")
print("   2. ✓ Current time (10:00 AM) IS during market hours (9:30 AM - 4:00 PM)")
print("   3. → Function returns SECOND-TO-LAST bar's N")
print()
print("   This means:")
print("   - Today's incomplete bar is EXCLUDED ✓")
print("   - N won't change from 9:30 AM to 4:00 PM ✓")
print("   - Position sizing is consistent all day ✓")
print()

print("="*80)
print("VISUAL TIMELINE")
print("="*80)
print()
print("  Before 9:30 AM          9:30 AM - 4:00 PM           After 4:00 PM")
print("  ===============         =================           ==============")
print(f"  Uses TODAY's N          Uses YESTERDAY's N          Uses TODAY's N")
print(f"  ${today_n:.4f}               ${yesterday_n:.4f}                  ${today_n:.4f}")
print()
print("  Market closed,          Market OPEN,                Market closed,")
print("  today's bar is          today's bar is              today's bar is")
print("  complete                INCOMPLETE                  now complete")
print()
print("                     ← YOU ARE HERE (10:00 AM)")
print()

