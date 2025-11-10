"""
Run Multiple Seed Backtests - PARALLEL VERSION

This script runs backtests for multiple seeds in parallel using multiprocessing,
saving detailed results (JSONL logs and PNG charts) for each seed.

Configuration:
- Seeds: 1-100 (configurable)
- Long + Short: Enabled (always)
- System 1 (20-10): Enabled by default
- System 2 (55-20): Disabled by default (use --enable-system2)
- Balance mode: Disabled by default (use --balance-long-short-units)
- Risk per unit: Configurable (default: 0.005 = 0.5%)
- Parallel execution: Uses all CPU cores

Results are saved to:
  backtesting/results/turtle_unified_{config_name}_results/

Each seed gets its own directory with:
- config.json - Configuration parameters
- daily_backtest_log_{config_name}.jsonl - Daily position and trade log
- equity_over_time.png - Equity curve chart
- cash_over_time.png - Cash level chart
- units_over_time.png - Position units chart

Usage:
    python run_multiple_seeds.py [options]
    
Examples:
    # System 1 only (default)
    python run_multiple_seeds.py
    
    # Dual system (System 1 + System 2)
    python run_multiple_seeds.py --enable-system2
    
    # With balance mode
    python run_multiple_seeds.py --balance-long-short-units
    
    # All options
    python run_multiple_seeds.py --start-seed 1 --end-seed 50 --risk-per-unit 0.01 --enable-system2 --balance-long-short-units
"""

import sys
import os
import pandas as pd
import numpy as np
import random
from datetime import datetime
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

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


def run_backtest_for_seed(args):
    """Run a single backtest for the given seed."""
    seed, risk_per_unit_pct, enable_system2, balance_long_short_units = args
    
    # Use the data loaded in worker initialization
    global _worker_data
    all_data = _worker_data
    
    # Set random seed
    random.seed(seed)
    
    # Create backtester with save_results=True for detailed output
    backtester = TurtleUnifiedBacktester(
        initial_equity=10000,
        risk_per_unit_pct=risk_per_unit_pct,
        max_positions=100,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=True,  # Always enabled
        enable_system2=enable_system2,  # Configurable
        check_shortability=False,
        shortable_tickers=None,
        enable_logging=False,  # Disable console logging for cleaner output
        seed=seed,
        save_results=True,  # Enable detailed result saving
        balance_long_short_units=balance_long_short_units  # Configurable
    )
    
    try:
        # Run backtest (will also save to cache)
        results = backtester.run(all_data)
        (final_equity, all_trades, final_cash, cash_history, equity_history,
         long_unit_history, short_unit_history, net_unit_history) = results
        
        # Calculate summary metrics
        initial_equity = backtester.initial_equity
        total_pnl = final_equity - initial_equity
        total_return_pct = (total_pnl / initial_equity) * 100
        
        num_trades = len(all_trades)
        winning_trades = [t for t in all_trades if t['pnl'] > 0]
        
        win_rate = (len(winning_trades) / num_trades * 100) if num_trades > 0 else 0
        
        # Return summary
        return {
            'seed': seed,
            'success': True,
            'final_equity': final_equity,
            'total_pnl': total_pnl,
            'return_pct': total_return_pct,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'result_dir': backtester.result_dir
        }
    except Exception as e:
        return {
            'seed': seed,
            'success': False,
            'error': str(e)
        }


def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Run backtests for multiple seeds with detailed results in parallel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run seeds 1-100 with default (System 1 only, no balance)
  python run_multiple_seeds.py
  
  # Run with Dual System (System 1 + System 2)
  python run_multiple_seeds.py --enable-system2
  
  # Run with balance mode
  python run_multiple_seeds.py --balance-long-short-units
  
  # Run with all options
  python run_multiple_seeds.py --start-seed 1 --end-seed 50 --risk-per-unit 0.01 --enable-system2 --balance-long-short-units
  
  # Limit CPU usage
  python run_multiple_seeds.py --workers 4
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
        '--risk-per-unit',
        type=float,
        default=0.005,
        help='Risk per unit as percentage of equity (default: 0.005 = 0.5%%)'
    )
    parser.add_argument(
        '--enable-system2',
        action='store_true',
        help='Enable System 2 (55-20) in addition to System 1 (default: System 1 only)'
    )
    parser.add_argument(
        '--balance-long-short-units',
        action='store_true',
        help='Maintain equal total long and short units including pyramiding (default: disabled)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of worker processes (default: use all CPU cores)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.start_seed > args.end_seed:
        print(f"Error: start-seed ({args.start_seed}) must be <= end-seed ({args.end_seed})")
        sys.exit(1)
    
    if args.risk_per_unit <= 0 or args.risk_per_unit > 0.1:
        print(f"Warning: risk-per-unit {args.risk_per_unit} is unusual (typical: 0.001-0.01)")
    
    # Configuration
    start_seed = args.start_seed
    end_seed = args.end_seed
    risk_per_unit_pct = args.risk_per_unit
    enable_system2 = args.enable_system2
    balance_long_short_units = args.balance_long_short_units
    num_workers = args.workers if args.workers else cpu_count()
    num_seeds = end_seed - start_seed + 1
    
    # Convert to basis points for display
    risk_bp = int(risk_per_unit_pct * 10000)
    
    # Determine system configuration for display
    if enable_system2:
        system_desc = "Dual System (System 1 + System 2)"
    else:
        system_desc = "System 1 (20-10) only"
    
    print("="*80)
    print("MULTIPLE SEED BACKTEST RUNNER - PARALLEL")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Seeds: {start_seed}-{end_seed} ({num_seeds} total)")
    print(f"  Risk per unit: {risk_per_unit_pct} ({risk_per_unit_pct*100:.2f}% / {risk_bp}bp)")
    print(f"  Initial equity: $10,000")
    print(f"  Long + Short: Enabled")
    print(f"  System: {system_desc}")
    print(f"  Balance mode: {'Enabled' if balance_long_short_units else 'Disabled'}")
    print(f"  Max positions: 100")
    print(f"  Workers: {num_workers}")
    print(f"\nResults will be saved to:")
    print(f"  backtesting/results/turtle_unified_*_results/")
    print(f"    - config.json (configuration)")
    print(f"    - daily_backtest_log_*.jsonl (daily logs)")
    print(f"    - *.png (charts)")
    
    # Prepare task list
    tasks = []
    for seed in range(start_seed, end_seed + 1):
        tasks.append((seed, risk_per_unit_pct, enable_system2, balance_long_short_units))
    
    print(f"\nTotal backtests to run: {len(tasks)}")
    print(f"\nInitializing worker processes...")
    print("(Each worker will load data once - this takes ~10-30 seconds)")
    
    # Run in parallel with progress bar
    start_time = datetime.now()
    
    # Use initializer to load data once per worker process
    with Pool(processes=num_workers, initializer=_init_worker) as pool:
        init_time = (datetime.now() - start_time).total_seconds()
        print(f"✓ Worker processes initialized in {init_time:.1f} seconds\n")
        print("Starting backtests...")
        
        backtest_start = datetime.now()
        
        # Use imap_unordered with tqdm for progress tracking
        results = list(tqdm(
            pool.imap_unordered(run_backtest_for_seed, tasks, chunksize=1),
            total=len(tasks),
            desc="Running backtests",
            unit="seed",
            ncols=100,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        ))
        
        backtest_time = (datetime.now() - backtest_start).total_seconds()
    
    end_time = datetime.now()
    elapsed_total = (end_time - start_time).total_seconds()
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"Completed: {len(successful)}/{num_seeds} successful")
    if failed:
        print(f"Failed: {len(failed)}/{num_seeds}")
        print(f"  Failed seeds: {[r['seed'] for r in failed]}")
    
    print(f"\nTotal runtime: {elapsed_total:.1f}s ({elapsed_total/60:.1f} minutes)")
    print(f"  - Worker init: {init_time:.1f}s")
    print(f"  - Backtests: {backtest_time:.1f}s")
    print(f"  - Avg per seed: {backtest_time/num_seeds:.1f}s")
    
    if successful:
        # Calculate statistics
        pnls = [r['total_pnl'] for r in successful]
        returns = [r['return_pct'] for r in successful]
        
        print(f"\nPerformance Statistics:")
        print(f"  Average PnL: ${np.mean(pnls):,.2f}")
        print(f"  Median PnL: ${np.median(pnls):,.2f}")
        print(f"  Std Dev PnL: ${np.std(pnls):,.2f}")
        print(f"  Min PnL: ${np.min(pnls):,.2f} (seed {successful[np.argmin(pnls)]['seed']})")
        print(f"  Max PnL: ${np.max(pnls):,.2f} (seed {successful[np.argmax(pnls)]['seed']})")
        
        print(f"\n  Average Return: {np.mean(returns):.2f}%")
        print(f"  Median Return: {np.median(returns):.2f}%")
        print(f"  Min Return: {np.min(returns):.2f}% (seed {successful[np.argmin(returns)]['seed']})")
        print(f"  Max Return: {np.max(returns):.2f}% (seed {successful[np.argmax(returns)]['seed']})")
        
        positive_returns = [r for r in successful if r['total_pnl'] > 0]
        print(f"\n  Positive seeds: {len(positive_returns)}/{len(successful)} ({len(positive_returns)/len(successful)*100:.1f}%)")
    
    # Save summary to CSV
    summary_file = os.path.join(backtesting_dir, 'results', f'summary_seeds_{start_seed}_{end_seed}.csv')
    os.makedirs(os.path.dirname(summary_file), exist_ok=True)
    
    summary_data = []
    for r in successful:
        summary_data.append({
            'seed': r['seed'],
            'final_equity': r['final_equity'],
            'total_pnl': r['total_pnl'],
            'return_pct': r['return_pct'],
            'num_trades': r['num_trades'],
            'win_rate': r['win_rate'],
            'result_dir': r['result_dir']
        })
    
    if summary_data:
        df = pd.DataFrame(summary_data)
        # Sort by seed for easier reading
        df = df.sort_values('seed')
        df.to_csv(summary_file, index=False)
        print(f"\nSummary saved to: {summary_file}")
    
    print(f"\nDetailed results (JSONL + PNG) saved to:")
    print(f"  backtesting/results/turtle_unified_*_results/")
    
    print(f"\n{'='*80}")
    print("COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()

