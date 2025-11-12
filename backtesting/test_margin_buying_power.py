"""
Test script for margin buying power functionality

This script demonstrates how the backtester now uses Alpaca's margin system
with 2x buying power for longs and proper margin requirements for shorts.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.turtle_unified_backtester import TurtleUnifiedBacktester


def test_with_margin():
    """Test with 2x margin enabled (default, matches Alpaca)"""
    print("="*70)
    print("TEST 1: With 2x Margin (Alpaca Default)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        use_margin=True,           # Enable margin
        margin_multiplier=2.0,     # 2x buying power
        seed=42,
        save_results=False
    )

    print(f"Initial Settings:")
    print(f"  Initial Equity: ${backtester.initial_equity:,.2f}")
    print(f"  Use Margin: {backtester.use_margin}")
    print(f"  Margin Multiplier: {backtester.margin_multiplier}x")
    print(f"  Initial Buying Power: ${backtester.initial_equity * backtester.margin_multiplier:,.2f}")

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_without_margin():
    """Test without margin (cash account only)"""
    print("\n" + "="*70)
    print("TEST 2: Without Margin (Cash Account)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        use_margin=False,          # Disable margin
        margin_multiplier=1.0,     # 1x (no leverage)
        seed=42,
        save_results=False
    )

    print(f"Initial Settings:")
    print(f"  Initial Equity: ${backtester.initial_equity:,.2f}")
    print(f"  Use Margin: {backtester.use_margin}")
    print(f"  Margin Multiplier: {backtester.margin_multiplier}x")
    print(f"  Initial Buying Power: ${backtester.initial_equity * backtester.margin_multiplier:,.2f}")

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")
    print(f"\nNote: Cash account typically has fewer trades due to limited buying power")


def test_higher_margin():
    """Test with higher margin (3x) - hypothetical"""
    print("\n" + "="*70)
    print("TEST 3: With 3x Margin (Hypothetical)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        use_margin=True,
        margin_multiplier=3.0,     # 3x buying power (portfolio margin)
        seed=42,
        save_results=False
    )

    print(f"Initial Settings:")
    print(f"  Initial Equity: ${backtester.initial_equity:,.2f}")
    print(f"  Use Margin: {backtester.use_margin}")
    print(f"  Margin Multiplier: {backtester.margin_multiplier}x")
    print(f"  Initial Buying Power: ${backtester.initial_equity * backtester.margin_multiplier:,.2f}")

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_comparison():
    """Compare margin vs cash accounts side by side"""
    print("\n" + "="*70)
    print("TEST 4: Direct Comparison (Margin vs Cash)")
    print("="*70)

    # Run with margin
    bt_margin = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        use_margin=True,
        margin_multiplier=2.0,
        seed=99,
        save_results=False
    )
    metrics_margin = bt_margin.run('2016-01-01', '2016-03-31')

    # Run without margin
    bt_cash = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        use_margin=False,
        seed=99,
        save_results=False
    )
    metrics_cash = bt_cash.run('2016-01-01', '2016-03-31')

    print("\nComparison:")
    print(f"{'Metric':<20} {'With Margin':<20} {'Cash Only':<20}")
    print("-" * 60)
    print(f"{'Final Equity':<20} ${metrics_margin['final_equity']:<19,.2f} ${metrics_cash['final_equity']:<19,.2f}")
    print(f"{'Return %':<20} {metrics_margin['total_return_pct']:<19.2f}% {metrics_cash['total_return_pct']:<19.2f}%")
    print(f"{'Num Trades':<20} {metrics_margin['num_trades']:<19} {metrics_cash['num_trades']:<19}")
    print(f"{'Max Drawdown %':<20} {metrics_margin['max_drawdown_pct']:<19.2f}% {metrics_cash['max_drawdown_pct']:<19.2f}%")


def explain_buying_power():
    """Explain how buying power works"""
    print("\n" + "="*70)
    print("BUYING POWER EXPLANATION")
    print("="*70)

    print("""
For Margin Accounts (use_margin=True, margin_multiplier=2.0):
----------------------------------------------------------
• Buying Power = Equity × 2
• Example: $10,000 equity → $20,000 buying power

Long Positions:
• Cost: Full position value
• Example: Buy $5,000 of stock → Uses $5,000 buying power
• Remaining: $15,000 buying power

Short Positions:
• Buying Power Use: 100% of short value (same as longs)
• Example: Short $5,000 of stock → Uses $5,000 buying power
• Note: While maintenance requirement is 150%,
  buying power consumption is 1x (same as longs)

Cash Tracking:
• For longs: Deduct full cost from cash
• For shorts: Deduct 50% margin held from cash
• Cash can go negative in margin accounts (that's the leverage)

For Cash Accounts (use_margin=False):
--------------------------------------
• Buying Power = Cash only
• No leverage available
• More conservative, fewer trades
• Shorts still possible but use more buying power

Real Alpaca Behavior:
--------------------
• Short-enabled accounts use 2x margin (margin_multiplier=2.0)
• This is Reg T margin (Federal Reserve regulation)
• Some accounts qualify for portfolio margin (up to 6x)
• The backtester defaults match Alpaca's standard margin account
""")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("MARGIN BUYING POWER TEST SUITE")
    print("="*70)
    print("\nTesting Alpaca's margin buying power system:")
    print("  - 2x buying power for margin accounts (default)")
    print("  - Both longs and shorts use 1x buying power")
    print("  - Cash account option for comparison\n")

    test_with_margin()
    test_without_margin()
    test_higher_margin()
    test_comparison()
    explain_buying_power()

    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)
    print("\nKey Findings:")
    print("  • Margin accounts (2x) can take more positions")
    print("  • Cash accounts are more conservative")
    print("  • Both longs and shorts use 1x buying power (same consumption)")
    print("  • Results are now more realistic for Alpaca trading")


if __name__ == '__main__':
    main()
