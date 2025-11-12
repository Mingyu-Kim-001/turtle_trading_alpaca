"""
Test script for parameterized stop loss and pyramiding backtester

This script demonstrates how to use the new stop_loss_atr_multiplier and
pyramid_atr_multiplier parameters in the unified backtester.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtesting.turtle_unified_backtester import TurtleUnifiedBacktester


def test_default_parameters():
    """Test with default parameters (2N stop, 0.5N pyramid)"""
    print("="*70)
    print("TEST 1: Default Parameters (2N stop, 0.5N pyramid)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=2.0,    # Default
        pyramid_atr_multiplier=0.5,      # Default
        seed=42,
        save_results=False  # Don't save for testing
    )

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Win Rate: {metrics['win_rate']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_wider_stops():
    """Test with wider stops (3N) and default pyramiding"""
    print("\n" + "="*70)
    print("TEST 2: Wider Stops (3N stop, 0.5N pyramid)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=3.0,    # Wider stops
        pyramid_atr_multiplier=0.5,      # Default
        seed=42,
        save_results=False
    )

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Win Rate: {metrics['win_rate']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_less_frequent_pyramiding():
    """Test with default stops and less frequent pyramiding (0.75N)"""
    print("\n" + "="*70)
    print("TEST 3: Less Frequent Pyramiding (2N stop, 0.75N pyramid)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=2.0,    # Default
        pyramid_atr_multiplier=0.75,     # Less frequent pyramiding
        seed=42,
        save_results=False
    )

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Win Rate: {metrics['win_rate']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_aggressive_parameters():
    """Test with tighter stops and more frequent pyramiding"""
    print("\n" + "="*70)
    print("TEST 4: Aggressive Parameters (1.5N stop, 0.25N pyramid)")
    print("="*70)

    backtester = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=1.5,    # Tighter stops
        pyramid_atr_multiplier=0.25,     # More frequent pyramiding
        seed=42,
        save_results=False
    )

    metrics = backtester.run('2016-01-01', '2016-12-31')

    print(f"\nResults:")
    print(f"  Final Equity: ${metrics['final_equity']:,.2f}")
    print(f"  Total Return: {metrics['total_return_pct']:.2f}%")
    print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Win Rate: {metrics['win_rate']:.2f}%")
    print(f"  Number of Trades: {metrics['num_trades']}")


def test_cache_usage():
    """Test cache functionality with v3 parameters"""
    print("\n" + "="*70)
    print("TEST 5: Cache Usage (saves to cache_v3.csv)")
    print("="*70)

    # First run - should calculate
    print("\nFirst run (should calculate)...")
    backtester1 = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=2.5,
        pyramid_atr_multiplier=0.6,
        seed=99,
        save_results=True  # Enable caching
    )

    metrics1 = backtester1.run('2016-01-01', '2016-03-31')
    print(f"  Result: ${metrics1['final_equity']:,.2f}")

    # Second run with SAME parameters - should load from cache
    print("\nSecond run with same parameters (should load from cache)...")
    backtester2 = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=2.5,
        pyramid_atr_multiplier=0.6,
        seed=99,
        save_results=True
    )

    metrics2 = backtester2.run('2016-01-01', '2016-03-31')
    print(f"  Result: ${metrics2['final_equity']:,.2f}")
    print(f"  Match: {metrics1['final_equity'] == metrics2['final_equity']}")

    # Third run with DIFFERENT parameter - should calculate
    print("\nThird run with different stop loss (should calculate)...")
    backtester3 = TurtleUnifiedBacktester(
        initial_equity=10_000,
        risk_per_unit_pct=0.005,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,
        enable_system2=False,
        stop_loss_atr_multiplier=3.0,  # Different!
        pyramid_atr_multiplier=0.6,
        seed=99,
        save_results=True
    )

    metrics3 = backtester3.run('2016-01-01', '2016-03-31')
    print(f"  Result: ${metrics3['final_equity']:,.2f}")
    print(f"  Different from first: {metrics1['final_equity'] != metrics3['final_equity']}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PARAMETERIZED BACKTESTER TEST SUITE")
    print("="*70)
    print("\nTesting new parameters:")
    print("  - stop_loss_atr_multiplier (default: 2.0)")
    print("  - pyramid_atr_multiplier (default: 0.5)")
    print("\n")

    test_default_parameters()
    test_wider_stops()
    test_less_frequent_pyramiding()
    test_aggressive_parameters()
    test_cache_usage()

    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)
    print("\nCache file location: backtesting/backtest_results_cache_v3.csv")
    print("Documentation: backtesting/CACHE_V3_README.md")


if __name__ == '__main__':
    main()
