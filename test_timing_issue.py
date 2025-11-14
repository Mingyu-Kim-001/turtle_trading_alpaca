#!/usr/bin/env python3
"""
Investigate the N value discrepancy:
- Live system on Nov 13 at 6:36 AM: N = 0.1902
- Debug script now: N = 0.18475
"""

import os
import sys
sys.path.insert(0, '/Users/mingyukim/Desktop/turtle_trading_alpaca')

from system_long_short.core.data_provider import DataProvider
from system_long_short.core.indicators import IndicatorCalculator

print("="*80)
print("INVESTIGATING N VALUE DISCREPANCY")
print("="*80)
print()

data_provider = DataProvider(
    api_key=os.getenv('ALPACA_PAPER_KEY'), 
    api_secret=os.getenv('ALPACA_PAPER_SECRET')
)

# Fetch CURRENT data (what you're seeing now)
print("SCENARIO 1: Current data (what your debug script sees)")
print("="*80)
df_current = data_provider.get_historical_data('AMCR', days=100)
print(f"Total bars: {len(df_current)}")
print(f"Date range: {df_current.index[0].date()} to {df_current.index[-1].date()}")
print()

# Filter to only include data BEFORE Nov 13 (simulating what should be available)
df_before_nov13 = df_current[df_current.index < '2025-11-13']
print(f"After filtering < 2025-11-13:")
print(f"  Total bars: {len(df_before_nov13)}")
print(f"  Last date: {df_before_nov13.index[-1].date()}")
print()

df_before_nov13 = IndicatorCalculator.calculate_indicators(df_before_nov13)
n_before_nov13 = IndicatorCalculator.get_latest_completed_n(df_before_nov13)
print(f"  N value: {n_before_nov13}")
print()

# Now let's see what happens if we INCLUDE Nov 13
print("SCENARIO 2: Including Nov 13 data (what might have been available at 6:36 AM)")
print("="*80)
df_including_nov13 = df_current[df_current.index <= '2025-11-13']
print(f"After filtering <= 2025-11-13:")
print(f"  Total bars: {len(df_including_nov13)}")
print(f"  Last date: {df_including_nov13.index[-1].date()}")
print()

df_including_nov13 = IndicatorCalculator.calculate_indicators(df_including_nov13)
n_including_nov13 = IndicatorCalculator.get_latest_completed_n(df_including_nov13)
print(f"  N value: {n_including_nov13}")
print()

# Show last 5 bars of CURRENT data
print("="*80)
print("LAST 5 BARS FROM ALPACA (current)")
print("="*80)
df_with_indicators = IndicatorCalculator.calculate_indicators(df_current.copy())
last_5 = df_with_indicators[['close', 'TR', 'N']].tail(5)
print(last_5)
print()

# Check what N was on specific dates
print("="*80)
print("N VALUES BY DATE")
print("="*80)
for date_str in ['2025-11-11', '2025-11-12', '2025-11-13']:
    try:
        row = df_with_indicators.loc[df_with_indicators.index.date.astype(str) == date_str]
        if len(row) > 0:
            n_val = row['N'].iloc[0]
            close_val = row['close'].iloc[0]
            print(f"  {date_str}: N = {n_val:.5f}, Close = ${close_val:.2f}")
        else:
            print(f"  {date_str}: No data")
    except:
        pass
print()

# The key question: What was Nov 13's open/high/low/close at 6:36 AM?
print("="*80)
print("HYPOTHESIS: Why the live system got 0.1902")
print("="*80)
print()
print("At 6:36 AM ET on Nov 13, the Alpaca API would have returned:")
print("  1. Complete bars through Nov 12 (N = 0.18475)")
print("  2. PARTIAL bar for Nov 13 (pre-market data)")
print()
print("Since 6:36 AM is BEFORE market open (9:30 AM),")
print("get_latest_completed_n() would check:")
print("  - Is last bar from today? YES (Nov 13)")
print("  - Is market open (9:30-4:00)? NO (it's 6:36 AM)")
print("  - Therefore: Use LAST bar's N (Nov 13's partial N)")
print()
print("But Nov 13's bar at 6:36 AM would have had different OHLC")
print("than Nov 13's bar now (after market close).")
print()
print("The N value of 0.1902 suggests the TR on Nov 13 was calculated")
print("using the pre-market/early morning data, which may have been")
print("different from the final close.")
print()

# Let's calculate what TR would need to be for N = 0.1902
print("="*80)
print("REVERSE ENGINEERING: What TR gives N = 0.1902?")
print("="*80)
print()
print("N is a 20-day moving average of TR.")
print("If N = 0.1902 on Nov 13, we can calculate what TR must have been:")
print()

# Get the sum of last 19 TRs (Nov 11 back to Oct 14)
if len(df_with_indicators) >= 20:
    # Get last 19 completed TRs (excluding any Nov 13 data)
    tr_values = df_with_indicators['TR'].iloc[-20:-1] if len(df_with_indicators) > 20 else df_with_indicators['TR'].iloc[-19:]
    sum_19_trs = tr_values.sum()
    
    # N = (sum of 20 TRs) / 20
    # 0.1902 = (sum_19_trs + TR_nov13) / 20
    # TR_nov13 = (0.1902 * 20) - sum_19_trs
    
    target_n = 0.1902
    required_tr = (target_n * 20) - sum_19_trs
    
    print(f"  Sum of last 19 TRs: {sum_19_trs:.5f}")
    print(f"  For N = {target_n}, TR on Nov 13 must be: {required_tr:.5f}")
    print()
    
    # What's the actual TR for Nov 13 now?
    if '2025-11-13' in df_with_indicators.index.astype(str):
        actual_tr_nov13 = df_with_indicators[df_with_indicators.index.astype(str) == '2025-11-13']['TR'].iloc[0]
        print(f"  Actual TR on Nov 13 (final): {actual_tr_nov13:.5f}")
        print(f"  Difference: {required_tr - actual_tr_nov13:.5f}")
        print()
        print(f"  This means at 6:36 AM, the TR calculation used different")
        print(f"  high/low/close values than what ended up being final.")

print()
print("="*80)
print("CONCLUSION")
print("="*80)
print()
print("Your debug script gets 0.18475 because:")
print("  - It filters out Nov 13 entirely (< '2025-11-13')")
print("  - Uses only completed data through Nov 12")
print()
print("The live system got 0.1902 because:")
print("  - At 6:36 AM, it had a PARTIAL Nov 13 bar")
print("  - The market was closed (before 9:30 AM)")
print("  - So it used Nov 13's N based on pre-market data")
print("  - That early TR was different from the final TR")
print()
print("FIX: To match what the live system saw at 6:36 AM,")
print("you would need the EXACT snapshot of data as it existed")
print("at that time, which is no longer available.")

