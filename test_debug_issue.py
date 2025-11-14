#!/usr/bin/env python3
"""
Demonstrate the index issue in the debug.py code
"""

import os
import sys
sys.path.insert(0, '/Users/mingyukim/Desktop/turtle_trading_alpaca')

from system_long_short.core.data_provider import DataProvider
from system_long_short.core.indicators import IndicatorCalculator

print("="*80)
print("DEMONSTRATING THE INDEX ISSUE")
print("="*80)
print()

data_provider = DataProvider(
    api_key=os.getenv('ALPACA_PAPER_KEY'), 
    api_secret=os.getenv('ALPACA_PAPER_SECRET')
)

# Fetch data
print("1. Fetching data...")
df_original = data_provider.get_historical_data('AMCR', days=100)
print(f"   Type of index: {type(df_original.index)}")
print(f"   Last index value: {df_original.index[-1]}")
print(f"   Last date: {df_original.index[-1].date() if hasattr(df_original.index[-1], 'date') else df_original.index[-1]}")
print()

# WRONG WAY (Your current code)
print("="*80)
print("WRONG WAY: Using .reset_index() without .set_index()")
print("="*80)
df_wrong = df_original.copy().reset_index()
print(f"2a. After .reset_index():")
print(f"    Columns: {df_wrong.columns.tolist()}")
print(f"    Type of index: {type(df_wrong.index)}")
print(f"    Last index value: {df_wrong.index[-1]} (numeric!)")
print()

df_wrong = df_wrong.loc[df_wrong['date'] < '2025-11-13']
print(f"2b. After filtering date < '2025-11-13':")
print(f"    Last index value: {df_wrong.index[-1]} (still numeric!)")
print(f"    Last date in 'date' column: {df_wrong['date'].iloc[-1]}")
print()

df_wrong_indicators = IndicatorCalculator.calculate_indicators(df_wrong)
print(f"2c. After calculate_indicators:")
print(f"    Index is: {type(df_wrong_indicators.index)}")
print(f"    Last index value: {df_wrong_indicators.index[-1]}")
print()

latest_n_wrong = IndicatorCalculator.get_latest_completed_n(df_wrong_indicators)
print(f"2d. get_latest_completed_n() returned: {latest_n_wrong}")
print(f"    ❌ This might be WRONG because index isn't a date!")
print()

# RIGHT WAY
print("="*80)
print("RIGHT WAY #1: Don't use .reset_index() at all")
print("="*80)
df_right1 = df_original.copy()
# Filter using index directly
df_right1 = df_right1[df_right1.index < '2025-11-13']
print(f"3a. After filtering index < '2025-11-13':")
print(f"    Type of index: {type(df_right1.index)}")
print(f"    Last index value: {df_right1.index[-1]}")
print(f"    Last date: {df_right1.index[-1].date()}")
print()

df_right1_indicators = IndicatorCalculator.calculate_indicators(df_right1)
latest_n_right1 = IndicatorCalculator.get_latest_completed_n(df_right1_indicators)
print(f"3b. get_latest_completed_n() returned: {latest_n_right1}")
print(f"    ✅ This is CORRECT - index is a date!")
print()

# RIGHT WAY #2
print("="*80)
print("RIGHT WAY #2: Use .reset_index() but then .set_index('date')")
print("="*80)
df_right2 = df_original.copy().reset_index()
df_right2 = df_right2.loc[df_right2['date'] < '2025-11-13']
df_right2 = df_right2.set_index('date')  # PUT IT BACK!
print(f"4a. After .set_index('date'):")
print(f"    Type of index: {type(df_right2.index)}")
print(f"    Last index value: {df_right2.index[-1]}")
print()

df_right2_indicators = IndicatorCalculator.calculate_indicators(df_right2)
latest_n_right2 = IndicatorCalculator.get_latest_completed_n(df_right2_indicators)
print(f"4b. get_latest_completed_n() returned: {latest_n_right2}")
print(f"    ✅ This is CORRECT - index is a date!")
print()

# Show last few rows
print("="*80)
print("LAST 3 ROWS OF DATA (RIGHT WAY)")
print("="*80)
print(df_right1_indicators[['close', 'N']].tail(3))
print()

print("="*80)
print("COMPARISON")
print("="*80)
print(f"Wrong way result: {latest_n_wrong}")
print(f"Right way result: {latest_n_right1}")
print(f"Difference: {abs(latest_n_wrong - latest_n_right1) if latest_n_wrong and latest_n_right1 else 'N/A'}")
print()

print("="*80)
print("WHAT THE LIVE SYSTEM DOES")
print("="*80)
print("The live trading system does NOT use .reset_index()")
print("It uses the data directly with date as index, like RIGHT WAY #1")
print()
print("That's why the live system got 0.1902 (using proper date index)")
print("But your debug code got 0.18475 (using numeric index)")

