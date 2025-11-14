"""
Parameter Grid Search for Turtle Trading Strategy

This script runs backtests across all combinations of parameters to find optimal settings.
Results are automatically saved to backtest_results_cache_v3.csv with full configuration details.

Parameter Grid:
- Seeds: 1-100 (for statistical significance)
- Risk per unit: [0.01, 0.03, 0.05, 0.08, 0.1] (1%, 3%, 5%, 8%, 10%)
- Enable System 2: [True, False] (System 1 always enabled)
- Stop Loss ATR Multiplier: [2, 2.5, 3, 3.5]
- Pyramid ATR Multiplier: [0.5, 0.75, 1]

Total combinations per seed: 5 × 2 × 4 × 3 = 120 parameter configurations
Total backtests: 120 × 100 seeds = 12,000 backtests

Results are saved to:
  backtesting/backtest_results_cache_v3.csv

This allows analysis of:
- Which parameter combinations work best
- How sensitive performance is to each parameter
- Statistical distribution of outcomes across seeds
- Optimal risk management settings

Usage:
    python run_parameter_grid_search.py [options]

Examples:
    # Run full grid search (12,000 backtests)
    python run_parameter_grid_search.py

    # Test with fewer seeds (1,200 backtests)
    python run_parameter_grid_search.py --start-seed 1 --end-seed 10

    # Limit CPU usage
    python run_parameter_grid_search.py --workers 4
"""

import sys
import os
import pandas as pd
import numpy as np
import random
import argparse
from datetime import datetime
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import itertools

# Add the project root and backtesting directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backtesting_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, backtesting_dir)

from turtle_unified_backtester import TurtleUnifiedBacktester

# Global variable to hold data in each worker process
_worker_data = None


def _init_worker():
    """Initialize worker process by loading data once per worker (not per task)."""
    global _worker_data

    data_dir = os.path.join(project_root, "data/alpaca_daily")
    all_files = os.listdir(data_dir)
    csv_files = sorted([f for f in all_files if f.endswith('_alpaca_daily.csv')])

    _worker_data = {}
    for file_name in csv_files:
        ticker = file_name.split('_')[0]
        data_path = os.path.join(data_dir, file_name)
        if os.path.exists(data_path):
            _worker_data[ticker] = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)


def run_single_backtest(args):
    """Run a single backtest with the given configuration."""
    import io
    import contextlib

    (seed, risk_per_unit_pct, enable_system2, stop_loss_atr_multiplier, pyramid_atr_multiplier) = args

    # Use the data loaded in worker initialization
    global _worker_data
    all_data = _worker_data

    # Set random seed
    random.seed(seed)

    # Create backtester with save_results=False (we only care about the cache)
    backtester = TurtleUnifiedBacktester(
        initial_equity=10000,
        risk_per_unit_pct=risk_per_unit_pct,
        max_positions=100,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,  # Always enabled
        enable_system2=enable_system2,
        check_shortability=False,
        shortable_tickers=None,
        enable_logging=False,
        seed=seed,
        save_results=False,  # Don't save detailed logs/charts to save disk space
        balance_long_short_units=False,  # Not varying this parameter in grid search
        stop_loss_atr_multiplier=stop_loss_atr_multiplier,
        pyramid_atr_multiplier=pyramid_atr_multiplier,
        use_margin=True,  # Use margin (consistent with live trading)
        margin_multiplier=2.0  # Standard 2x margin
    )

    try:
        # Suppress all print output from the backtester
        with contextlib.redirect_stdout(io.StringIO()):
            # Use run_with_cache to avoid re-running existing configurations
            results = backtester.run_with_cache(all_data)
            (final_equity, _, _, _, _, _, _, _, from_cache) = results

        # Return summary
        return {
            'seed': seed,
            'risk_per_unit_pct': risk_per_unit_pct,
            'enable_system2': enable_system2,
            'stop_loss_atr_multiplier': stop_loss_atr_multiplier,
            'pyramid_atr_multiplier': pyramid_atr_multiplier,
            'success': True,
            'from_cache': from_cache,
            'final_equity': final_equity,
            'config_id': backtester._get_config_id()
        }
    except Exception as e:
        return {
            'seed': seed,
            'risk_per_unit_pct': risk_per_unit_pct,
            'enable_system2': enable_system2,
            'stop_loss_atr_multiplier': stop_loss_atr_multiplier,
            'pyramid_atr_multiplier': pyramid_atr_multiplier,
            'success': False,
            'from_cache': False,
            'error': str(e)
        }


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Run parameter grid search for Turtle Trading strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full grid search (12,000 backtests)
  python run_parameter_grid_search.py

  # Test with fewer seeds
  python run_parameter_grid_search.py --start-seed 1 --end-seed 10

  # Limit CPU usage
  python run_parameter_grid_search.py --workers 4

  # Dry run (just show what would be run)
  python run_parameter_grid_search.py --dry-run
        """
    )

    parser.add_argument(
        '--start-seed',
        type=int,
        default=1,
        help='Starting seed number (default: 1)'
    )
    parser.add_argument(
        '--end-seed',
        type=int,
        default=100,
        help='Ending seed number (default: 100)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of worker processes (default: use all CPU cores)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be run without actually running backtests'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.start_seed > args.end_seed:
        print(f"Error: start-seed ({args.start_seed}) must be <= end-seed ({args.end_seed})")
        sys.exit(1)

    # Parameter grid
    # Note: risk_per_unit is % of equity risked per unit
    # Default working value is 0.005 (0.5%), so grid ranges from 0.2% to 1.0%
    risk_per_unit_values = [0.002, 0.003, 0.005, 0.008, 0.01]  # 0.2%, 0.3%, 0.5%, 0.8%, 1.0%
    enable_system2_values = [True, False]
    stop_loss_atr_multiplier_values = [2, 2.5, 3, 3.5]
    pyramid_atr_multiplier_values = [0.5, 0.75, 1]
    seed_values = list(range(args.start_seed, args.end_seed + 1))

    # Generate all combinations
    all_combinations = list(itertools.product(
        seed_values,
        risk_per_unit_values,
        enable_system2_values,
        stop_loss_atr_multiplier_values,
        pyramid_atr_multiplier_values
    ))

    num_workers = args.workers if args.workers else cpu_count()
    num_combinations = len(all_combinations)
    num_seeds = len(seed_values)
    num_param_configs = num_combinations // num_seeds

    print("="*80)
    print("PARAMETER GRID SEARCH - TURTLE TRADING STRATEGY")
    print("="*80)
    print(f"\nParameter Grid:")
    print(f"  Seeds: {args.start_seed}-{args.end_seed} ({num_seeds} seeds)")
    print(f"  Risk per unit: {risk_per_unit_values}")
    print(f"  Enable System 2: {enable_system2_values}")
    print(f"  Stop Loss ATR Multiplier: {stop_loss_atr_multiplier_values}")
    print(f"  Pyramid ATR Multiplier: {pyramid_atr_multiplier_values}")

    print(f"\nGrid Statistics:")
    print(f"  Parameter configurations: {num_param_configs}")
    print(f"  Seeds per configuration: {num_seeds}")
    print(f"  Total backtests: {num_combinations}")

    print(f"\nExecution Settings:")
    print(f"  Workers: {num_workers}")
    print(f"  Dry run: {args.dry_run}")

    print(f"\nResults will be saved to:")
    print(f"  {os.path.join(backtesting_dir, 'backtest_results_cache_v3.csv')}")

    if args.dry_run:
        print(f"\n{'='*80}")
        print("DRY RUN - Showing first 10 combinations:")
        print(f"{'='*80}")
        for i, combo in enumerate(all_combinations[:10]):
            seed, risk, sys2, stop, pyr = combo
            print(f"{i+1}. Seed={seed}, Risk={risk}, Sys2={sys2}, Stop={stop}N, Pyr={pyr}N")
        print(f"\n... and {len(all_combinations) - 10} more")
        print(f"\n{'='*80}")
        print("DRY RUN COMPLETE - Use without --dry-run to execute")
        print(f"{'='*80}")
        return

    print(f"\n{'='*80}")
    print("STARTING GRID SEARCH")
    print(f"{'='*80}\n")

    # Run grid search
    start_time = datetime.now()

    print("Initializing worker processes...")
    print("(Each worker will load data once - this takes ~10-30 seconds)")

    # Use initializer to load data once per worker process
    with Pool(processes=num_workers, initializer=_init_worker) as pool:
        init_time = (datetime.now() - start_time).total_seconds()
        print(f"✓ Worker processes initialized in {init_time:.1f} seconds\n")
        print("Starting backtests...")

        backtest_start = datetime.now()

        # Use imap_unordered with tqdm for progress tracking
        results = list(tqdm(
            pool.imap_unordered(run_single_backtest, all_combinations, chunksize=1),
            total=len(all_combinations),
            desc="Running grid search",
            unit="backtest",
            ncols=100,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        ))

        backtest_time = (datetime.now() - backtest_start).total_seconds()

    end_time = datetime.now()
    elapsed_total = (end_time - start_time).total_seconds()

    # Summary
    print(f"\n{'='*80}")
    print("GRID SEARCH SUMMARY")
    print(f"{'='*80}\n")

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    from_cache = [r for r in successful if r['from_cache']]
    newly_computed = [r for r in successful if not r['from_cache']]

    print(f"Completed: {len(successful)}/{num_combinations} successful")
    print(f"  - From cache: {len(from_cache)}")
    print(f"  - Newly computed: {len(newly_computed)}")

    if failed:
        print(f"Failed: {len(failed)}/{num_combinations}")
        print(f"\nSample errors (first 5):")
        for i, r in enumerate(failed[:5]):
            print(f"  {i+1}. Seed={r['seed']}, Risk={r['risk_per_unit_pct']}, Sys2={r['enable_system2']}")
            print(f"     Error: {r.get('error', 'Unknown error')}")

    print(f"\nTotal runtime: {elapsed_total:.1f}s ({elapsed_total/60:.1f} minutes)")
    print(f"  - Worker init: {init_time:.1f}s")
    print(f"  - Backtests: {backtest_time:.1f}s")
    print(f"  - Avg per backtest: {backtest_time/num_combinations:.2f}s")

    if len(newly_computed) > 0:
        print(f"  - Avg per new backtest: {backtest_time/len(newly_computed):.2f}s")

    # Load and analyze cache results
    cache_file = os.path.join(backtesting_dir, 'backtest_results_cache_v3.csv')
    if os.path.exists(cache_file):
        print(f"\nAnalyzing results from cache...")
        cache_df = pd.read_csv(cache_file)

        print(f"\nCache Statistics:")
        print(f"  Total entries in cache: {len(cache_df)}")
        print(f"  Unique configurations: {cache_df['config_id'].nunique()}")

        # Group by parameter combinations (excluding seed)
        param_cols = ['risk_per_unit_pct', 'enable_system2', 'stop_loss_atr_multiplier', 'pyramid_atr_multiplier']

        print(f"\nTop 10 Parameter Combinations by Average Return:")
        print(f"{'='*80}")

        # Group by parameters and calculate average metrics
        grouped = cache_df.groupby(param_cols).agg({
            'total_return_pct': ['mean', 'std', 'min', 'max', 'count'],
            'win_rate': 'mean',
            'num_trades': 'mean'
        }).round(2)

        # Sort by mean return
        grouped = grouped.sort_values(('total_return_pct', 'mean'), ascending=False)

        # Display top 10
        for i, (params, row) in enumerate(grouped.head(10).iterrows()):
            risk, sys2, stop, pyr = params
            sys2_str = "Sys1+2" if sys2 else "Sys1"
            print(f"\n{i+1}. Risk={risk:.0%} {sys2_str} Stop={stop}N Pyr={pyr}N")
            print(f"   Return: {row[('total_return_pct', 'mean')]:.1f}% ± {row[('total_return_pct', 'std')]:.1f}%")
            print(f"   Range: [{row[('total_return_pct', 'min')]:.1f}%, {row[('total_return_pct', 'max')]:.1f}%]")
            print(f"   Win Rate: {row[('win_rate', 'mean')]:.1f}%")
            print(f"   Avg Trades: {row[('num_trades', 'mean')]:.0f}")
            print(f"   Seeds: {int(row[('total_return_pct', 'count')])}")

        print(f"\n{'='*80}")
        print(f"Full results saved to: {cache_file}")
        print(f"Use pandas to analyze: pd.read_csv('{cache_file}')")

    print(f"\n{'='*80}")
    print("GRID SEARCH COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
