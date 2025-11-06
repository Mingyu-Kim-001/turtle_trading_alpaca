"""
Analyze differences between Long-Only and Long-Short strategies

This script compares:
1. Total returns and trade counts
2. Pyramid vs non-pyramid performance
3. Long vs short trade breakdown
4. Top winning/losing trades
5. Performance over time
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from backtesting.turtle_backtester import TurtleBacktester
from backtesting.turtle_long_short_backtester import TurtleLongShortBacktester


def run_both_strategies(all_data):
    """Run both strategies and return results"""

    print("="*70)
    print("RUNNING LONG-ONLY STRATEGY")
    print("="*70)

    long_only = TurtleBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.01,
        max_positions=10,
        enable_logging=False
    )

    long_only_results = long_only.run(all_data)
    long_only_final_equity, long_only_trades = long_only_results[0], long_only_results[1]

    print(f"\nLong-Only Results:")
    print(f"  Final Equity: ${long_only_final_equity:,.2f}")
    print(f"  Total Trades: {len(long_only_trades)}")

    print("\n" + "="*70)
    print("RUNNING LONG-SHORT STRATEGY")
    print("="*70)

    long_short = TurtleLongShortBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.01,
        max_positions=10,
        enable_shorts=True,
        check_shortability=False,
        enable_logging=False
    )

    long_short_results = long_short.run(all_data)
    long_short_final_equity, long_short_trades = long_short_results[0], long_short_results[1]

    print(f"\nLong-Short Results:")
    print(f"  Final Equity: ${long_short_final_equity:,.2f}")
    print(f"  Total Trades: {len(long_short_trades)}")

    return {
        'long_only': {
            'final_equity': long_only_final_equity,
            'trades': long_only_trades,
            'initial': 10_000
        },
        'long_short': {
            'final_equity': long_short_final_equity,
            'trades': long_short_trades,
            'initial': 10_000
        }
    }


def analyze_pyramid_performance(trades_df, strategy_name):
    """Analyze performance of pyramided vs non-pyramided trades"""

    print(f"\n{'='*70}")
    print(f"{strategy_name}: PYRAMID ANALYSIS")
    print(f"{'='*70}")

    # Add pyramid flag
    trades_df['is_pyramided'] = trades_df['pyramid_count'] > 1

    # Overall stats
    pyramided = trades_df[trades_df['is_pyramided']]
    non_pyramided = trades_df[~trades_df['is_pyramided']]

    print(f"\nTrade Counts:")
    print(f"  Non-pyramided (1 unit): {len(non_pyramided)} trades")
    print(f"  Pyramided (2-4 units):  {len(pyramided)} trades")
    print(f"  Pyramid Rate: {len(pyramided)/len(trades_df)*100:.1f}%")

    # P&L breakdown
    print(f"\nP&L Breakdown:")
    print(f"  Non-pyramided P&L: ${non_pyramided['pnl'].sum():,.2f}")
    print(f"  Pyramided P&L:     ${pyramided['pnl'].sum():,.2f}")
    print(f"  Total P&L:         ${trades_df['pnl'].sum():,.2f}")

    # Win rates
    non_pyr_wins = (non_pyramided['pnl'] > 0).sum()
    pyr_wins = (pyramided['pnl'] > 0).sum()

    print(f"\nWin Rates:")
    if len(non_pyramided) > 0:
        print(f"  Non-pyramided: {non_pyr_wins/len(non_pyramided)*100:.1f}%")
    if len(pyramided) > 0:
        print(f"  Pyramided:     {pyr_wins/len(pyramided)*100:.1f}%")

    # Average P&L
    print(f"\nAverage P&L per Trade:")
    if len(non_pyramided) > 0:
        print(f"  Non-pyramided: ${non_pyramided['pnl'].mean():,.2f}")
    if len(pyramided) > 0:
        print(f"  Pyramided:     ${pyramided['pnl'].mean():,.2f}")

    # Pyramid level breakdown
    if len(pyramided) > 0:
        print(f"\nPyramid Level Distribution:")
        for level in sorted(pyramided['pyramid_count'].unique()):
            level_trades = pyramided[pyramided['pyramid_count'] == level]
            level_pnl = level_trades['pnl'].sum()
            print(f"  {level} units: {len(level_trades)} trades, P&L: ${level_pnl:,.2f}")


def analyze_long_vs_short(long_short_trades_df):
    """Analyze long vs short performance"""

    print(f"\n{'='*70}")
    print(f"LONG vs SHORT COMPARISON")
    print(f"{'='*70}")

    longs = long_short_trades_df[long_short_trades_df['side'] == 'long']
    shorts = long_short_trades_df[long_short_trades_df['side'] == 'short']

    print(f"\nTrade Counts:")
    print(f"  Long trades:  {len(longs)}")
    print(f"  Short trades: {len(shorts)}")

    # P&L breakdown
    long_pnl = longs['pnl'].sum()
    short_pnl = shorts['pnl'].sum()

    print(f"\nTotal P&L:")
    print(f"  Long P&L:  ${long_pnl:,.2f} ({long_pnl/(long_pnl+short_pnl)*100:.1f}% of total)")
    print(f"  Short P&L: ${short_pnl:,.2f} ({short_pnl/(long_pnl+short_pnl)*100:.1f}% of total)")
    print(f"  Total P&L: ${long_pnl + short_pnl:,.2f}")

    # Win rates
    long_wins = (longs['pnl'] > 0).sum()
    short_wins = (shorts['pnl'] > 0).sum()

    print(f"\nWin Rates:")
    print(f"  Long:  {long_wins/len(longs)*100:.1f}% ({long_wins}/{len(longs)})")
    print(f"  Short: {short_wins/len(shorts)*100:.1f}% ({short_wins}/{len(shorts)})")

    # Average P&L
    print(f"\nAverage P&L per Trade:")
    print(f"  Long:  ${longs['pnl'].mean():,.2f}")
    print(f"  Short: ${shorts['pnl'].mean():,.2f}")

    # Pyramid breakdown by side
    print(f"\nPyramid Usage:")
    long_pyramided = longs[longs['pyramid_count'] > 1]
    short_pyramided = shorts[shorts['pyramid_count'] > 1]

    print(f"  Long pyramided:  {len(long_pyramided)}/{len(longs)} ({len(long_pyramided)/len(longs)*100:.1f}%)")
    print(f"  Short pyramided: {len(short_pyramided)}/{len(shorts)} ({len(short_pyramided)/len(shorts)*100:.1f}%)")

    # Top winning and losing trades
    print(f"\nTop 5 Long Winners:")
    top_long_wins = longs.nlargest(5, 'pnl')[['ticker', 'entry_date', 'exit_date', 'pnl', 'pyramid_count']]
    for idx, trade in top_long_wins.iterrows():
        print(f"  {trade['ticker']}: ${trade['pnl']:,.2f} ({trade['pyramid_count']} units)")

    print(f"\nTop 5 Short Winners:")
    top_short_wins = shorts.nlargest(5, 'pnl')[['ticker', 'entry_date', 'exit_date', 'pnl', 'pyramid_count']]
    for idx, trade in top_short_wins.iterrows():
        print(f"  {trade['ticker']}: ${trade['pnl']:,.2f} ({trade['pyramid_count']} units)")


def analyze_top_trades(trades_df, strategy_name, top_n=10):
    """Show top winning and losing trades"""

    print(f"\n{'='*70}")
    print(f"{strategy_name}: TOP TRADES")
    print(f"{'='*70}")

    print(f"\nTop {top_n} Winners:")
    top_winners = trades_df.nlargest(top_n, 'pnl')
    for idx, trade in top_winners.iterrows():
        side = trade.get('side', 'long')
        duration = (pd.to_datetime(trade['exit_date']) - pd.to_datetime(trade['entry_date'])).days
        print(f"  {trade['ticker']:6s} ({side:5s}): ${trade['pnl']:10,.2f} | "
              f"{trade['pyramid_count']} units | {duration:3d} days | "
              f"Entry: {pd.to_datetime(trade['entry_date']).strftime('%Y-%m-%d')}")

    print(f"\nTop {top_n} Losers:")
    top_losers = trades_df.nsmallest(top_n, 'pnl')
    for idx, trade in top_losers.iterrows():
        side = trade.get('side', 'long')
        duration = (pd.to_datetime(trade['exit_date']) - pd.to_datetime(trade['entry_date'])).days
        print(f"  {trade['ticker']:6s} ({side:5s}): ${trade['pnl']:10,.2f} | "
              f"{trade['pyramid_count']} units | {duration:3d} days | "
              f"Entry: {pd.to_datetime(trade['entry_date']).strftime('%Y-%m-%d')}")


def compare_strategies(results):
    """Compare overall strategy performance"""

    print(f"\n{'='*70}")
    print(f"OVERALL STRATEGY COMPARISON")
    print(f"{'='*70}")

    long_only = results['long_only']
    long_short = results['long_short']

    lo_return = (long_only['final_equity'] - long_only['initial']) / long_only['initial'] * 100
    ls_return = (long_short['final_equity'] - long_short['initial']) / long_short['initial'] * 100

    print(f"\nReturns:")
    print(f"  Long-Only:  ${long_only['final_equity']:,.2f} ({lo_return:.1f}% return)")
    print(f"  Long-Short: ${long_short['final_equity']:,.2f} ({ls_return:.1f}% return)")
    print(f"  Difference: ${long_short['final_equity'] - long_only['final_equity']:,.2f}")
    print(f"  Long-Short outperformed by: {ls_return - lo_return:.1f} percentage points")

    print(f"\nTrade Counts:")
    print(f"  Long-Only:  {len(long_only['trades'])} trades")
    print(f"  Long-Short: {len(long_short['trades'])} trades")

    lo_pnl = sum(t['pnl'] for t in long_only['trades'])
    ls_pnl = sum(t['pnl'] for t in long_short['trades'])

    print(f"\nTotal P&L:")
    print(f"  Long-Only:  ${lo_pnl:,.2f}")
    print(f"  Long-Short: ${ls_pnl:,.2f}")

    print(f"\nAverage P&L per Trade:")
    print(f"  Long-Only:  ${lo_pnl/len(long_only['trades']):,.2f}")
    print(f"  Long-Short: ${ls_pnl/len(long_short['trades']):,.2f}")


def create_comparison_plots(results, plot_dir):
    """Create visualization comparing strategies"""

    lo_trades = pd.DataFrame(results['long_only']['trades'])
    ls_trades = pd.DataFrame(results['long_short']['trades'])

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. P&L Distribution
    ax = axes[0, 0]
    lo_trades['pnl'].hist(bins=50, alpha=0.5, label='Long-Only', ax=ax, color='blue')
    ls_trades['pnl'].hist(bins=50, alpha=0.5, label='Long-Short', ax=ax, color='green')
    ax.set_xlabel('P&L ($)')
    ax.set_ylabel('Frequency')
    ax.set_title('P&L Distribution Comparison')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. Pyramid Count Distribution
    ax = axes[0, 1]
    lo_pyramid_counts = lo_trades['pyramid_count'].value_counts().sort_index()
    ls_pyramid_counts = ls_trades['pyramid_count'].value_counts().sort_index()

    x = np.arange(1, 5)
    width = 0.35
    ax.bar(x - width/2, [lo_pyramid_counts.get(i, 0) for i in x], width, label='Long-Only', alpha=0.7)
    ax.bar(x + width/2, [ls_pyramid_counts.get(i, 0) for i in x], width, label='Long-Short', alpha=0.7)
    ax.set_xlabel('Pyramid Units')
    ax.set_ylabel('Number of Trades')
    ax.set_title('Pyramid Usage Comparison')
    ax.set_xticks(x)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 3. Long-Short Breakdown
    ax = axes[1, 0]
    longs = ls_trades[ls_trades['side'] == 'long']
    shorts = ls_trades[ls_trades['side'] == 'short']

    categories = ['Long Trades', 'Short Trades']
    pnl_values = [longs['pnl'].sum(), shorts['pnl'].sum()]
    colors = ['green' if v > 0 else 'red' for v in pnl_values]

    ax.bar(categories, pnl_values, color=colors, alpha=0.7)
    ax.set_ylabel('Total P&L ($)')
    ax.set_title('Long vs Short P&L (Long-Short Strategy)')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(True, alpha=0.3, axis='y')

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))

    # 4. Cumulative P&L Over Time
    ax = axes[1, 1]

    lo_trades_sorted = lo_trades.sort_values('exit_date')
    lo_trades_sorted['cumulative_pnl'] = lo_trades_sorted['pnl'].cumsum()

    ls_trades_sorted = ls_trades.sort_values('exit_date')
    ls_trades_sorted['cumulative_pnl'] = ls_trades_sorted['pnl'].cumsum()

    ax.plot(lo_trades_sorted['exit_date'], lo_trades_sorted['cumulative_pnl'],
            label='Long-Only', linewidth=2, alpha=0.7)
    ax.plot(ls_trades_sorted['exit_date'], ls_trades_sorted['cumulative_pnl'],
            label='Long-Short', linewidth=2, alpha=0.7)
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative P&L ($)')
    ax.set_title('Cumulative P&L Over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.0f}K'))

    plt.tight_layout()
    plot_path = os.path.join(plot_dir, 'strategy_comparison.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\n{'='*70}")
    print(f"Comparison plots saved to: {plot_path}")
    print(f"{'='*70}")


if __name__ == "__main__":
    # Load data
    data_dir = os.path.join(project_root, "data/alpaca_daily")
    all_files = os.listdir(data_dir)
    csv_files = [f for f in all_files if f.endswith('_alpaca_daily.csv')]

    all_data = {}
    for file_name in csv_files:
        ticker = file_name.split('_')[0]
        data_path = os.path.join(data_dir, file_name)
        if os.path.exists(data_path):
            all_data[ticker] = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)

    print(f"Loaded data for {len(all_data)} tickers\n")

    # Run both strategies
    results = run_both_strategies(all_data)

    # Compare overall
    compare_strategies(results)

    # Analyze Long-Only
    lo_trades_df = pd.DataFrame(results['long_only']['trades'])
    analyze_pyramid_performance(lo_trades_df, "LONG-ONLY")
    analyze_top_trades(lo_trades_df, "LONG-ONLY")

    # Analyze Long-Short
    ls_trades_df = pd.DataFrame(results['long_short']['trades'])
    analyze_pyramid_performance(ls_trades_df, "LONG-SHORT")
    analyze_long_vs_short(ls_trades_df)
    analyze_top_trades(ls_trades_df, "LONG-SHORT")

    # Create comparison plots
    plot_dir = os.path.join(project_root, 'backtesting', 'turtle_long_short_plots')
    os.makedirs(plot_dir, exist_ok=True)
    create_comparison_plots(results, plot_dir)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
