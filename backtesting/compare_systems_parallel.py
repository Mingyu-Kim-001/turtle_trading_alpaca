"""
Parallel System Comparison Script

Compares System 1 vs Dual System (System 1 + System 2) across multiple seeds
using multiprocessing for faster execution.

Features:
- Parallel execution using all CPU cores
- Real-time progress bars for data loading and backtest execution
- Statistical significance testing (t-test for PnL and Max Drawdown)
- Comprehensive metrics comparison including Max Drawdown
- Configurable risk per unit parameter

Metrics Compared:
- Total PnL and Return %
- Win Rate and Avg Win/Loss
- Maximum Drawdown (lower is better)
- Number of Trades
- Head-to-Head Performance by Seed

Configuration:
- Seeds: 1-100
- Risk per unit: Configurable via --risk-per-unit (default: 0.001 = 0.1%)
- Long + Short enabled
- No saving of results (fast mode)

Usage:
    python compare_systems_parallel.py [--risk-per-unit 0.001]
"""

import sys
import os
import pandas as pd
import numpy as np
import random
from multiprocessing import Pool, cpu_count
from datetime import datetime
import json
from tqdm import tqdm

# Add the project root and backtesting directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backtesting_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, backtesting_dir)

from turtle_unified_backtester import TurtleUnifiedBacktester


def load_all_data():
    """Load all historical data once (shared across processes via serialization)."""
    data_dir = os.path.join(project_root, "data/alpaca_daily")
    all_files = os.listdir(data_dir)
    csv_files = sorted([f for f in all_files if f.endswith('_alpaca_daily.csv')])
    
    all_data = {}
    for file_name in tqdm(csv_files, desc="Loading ticker data", unit="file", ncols=100):
        ticker = file_name.split('_')[0]
        data_path = os.path.join(data_dir, file_name)
        if os.path.exists(data_path):
            all_data[ticker] = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)
    
    return all_data


def run_single_backtest(args):
    """Run a single backtest with given parameters."""
    seed, system_config, all_data, risk_per_unit_pct = args
    
    # Set random seed
    random.seed(seed)
    
    # Determine which systems to enable
    enable_system1 = system_config in ['system1', 'dual']
    enable_system2 = system_config == 'dual'
    
    # Create backtester
    backtester = TurtleUnifiedBacktester(
        initial_equity=10000,
        risk_per_unit_pct=risk_per_unit_pct,
        max_positions=100,
        enable_longs=True,
        enable_shorts=True,
        enable_system1=enable_system1,
        enable_system2=enable_system2,
        check_shortability=False,
        shortable_tickers=None,
        enable_logging=False,  # Disable detailed logging for speed
        seed=seed,
        save_results=False  # Don't save results
    )
    
    # Run backtest
    try:
        results = backtester.run(all_data)
        final_equity, all_trades, final_cash, _, equity_history, _, _, _ = results
        
        # Calculate metrics
        initial_equity = backtester.initial_equity
        total_pnl = final_equity - initial_equity
        total_return_pct = (total_pnl / initial_equity) * 100
        
        num_trades = len(all_trades)
        winning_trades = [t for t in all_trades if t['pnl'] > 0]
        losing_trades = [t for t in all_trades if t['pnl'] <= 0]
        
        win_rate = (len(winning_trades) / num_trades * 100) if num_trades > 0 else 0
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Calculate maximum drawdown
        max_drawdown_pct = 0
        if equity_history:
            equity_values = [eq for _, eq in equity_history]
            peak = equity_values[0]
            max_drawdown = 0
            
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak * 100
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            max_drawdown_pct = max_drawdown
        
        return {
            'seed': seed,
            'system': system_config,
            'final_equity': final_equity,
            'total_pnl': total_pnl,
            'return_pct': total_return_pct,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown_pct': max_drawdown_pct,
            'success': True
        }
    except Exception as e:
        return {
            'seed': seed,
            'system': system_config,
            'success': False,
            'error': str(e)
        }


def main():
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Compare System 1 vs Dual System across multiple seeds',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default risk (0.001 = 0.1%)
  python compare_systems_parallel.py
  
  # Run with higher risk (0.005 = 0.5%)
  python compare_systems_parallel.py --risk-per-unit 0.005
  
  # Run with lower risk (0.0005 = 0.05%)
  python compare_systems_parallel.py --risk-per-unit 0.0005
  
  # Run with 1% risk
  python compare_systems_parallel.py --risk-per-unit 0.01
        """
    )
    
    parser.add_argument(
        '--risk-per-unit',
        type=float,
        default=0.001,
        help='Risk per unit as percentage of equity (default: 0.001 = 0.1%%)'
    )
    
    args = parser.parse_args()
    risk_per_unit_pct = args.risk_per_unit
    
    # Convert to basis points for display
    risk_bp = int(risk_per_unit_pct * 10000)
    
    print("="*80)
    print("PARALLEL SYSTEM COMPARISON: System 1 vs Dual System")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Seeds: 1-100")
    print(f"  Risk per unit: {risk_per_unit_pct} ({risk_per_unit_pct*100:.2f}% / {risk_bp}bp)")
    print(f"  Initial equity: $10,000")
    print(f"  Long + Short: Enabled")
    print(f"  System 1: 20-10 (entry/exit)")
    print(f"  Dual System: 20-10 + 55-20")
    print(f"  Saving results: Disabled (fast mode)")
    
    # Load data once
    print(f"\nLoading historical data...")
    all_data = load_all_data()
    print(f"\n✓ Loaded data for {len(all_data)} tickers")
    
    # Prepare task list
    seeds = range(1, 101)
    tasks = []
    
    # System 1 only tasks
    for seed in seeds:
        tasks.append((seed, 'system1', all_data, risk_per_unit_pct))
    
    # Dual system tasks
    for seed in seeds:
        tasks.append((seed, 'dual', all_data, risk_per_unit_pct))
    
    print(f"\nTotal backtests to run: {len(tasks)}")
    print(f"Using {cpu_count()} CPU cores")
    print(f"\nStarting parallel execution...")
    print("(This may take several minutes...)\n")
    
    # Run in parallel with progress bar
    start_time = datetime.now()
    
    with Pool(processes=cpu_count()) as pool:
        # Use imap_unordered with tqdm for progress tracking
        results = list(tqdm(
            pool.imap_unordered(run_single_backtest, tasks),
            total=len(tasks),
            desc="Running backtests",
            unit="backtest",
            ncols=100,
            bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
        ))
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"\n✓ Completed in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    
    # Separate results by system
    system1_results = [r for r in results if r['system'] == 'system1' and r['success']]
    dual_results = [r for r in results if r['system'] == 'dual' and r['success']]
    
    failed = [r for r in results if not r['success']]
    if failed:
        print(f"\n⚠️ Warning: {len(failed)} backtests failed")
    
    # Calculate statistics
    print("\n" + "="*80)
    print("RESULTS COMPARISON")
    print("="*80)
    
    def print_stats(results, system_name):
        pnls = [r['total_pnl'] for r in results]
        returns = [r['return_pct'] for r in results]
        trades = [r['num_trades'] for r in results]
        win_rates = [r['win_rate'] for r in results]
        max_drawdowns = [r['max_drawdown_pct'] for r in results]
        
        positive_pnl = [p for p in pnls if p > 0]
        negative_pnl = [p for p in pnls if p <= 0]
        
        print(f"\n{system_name}:")
        print(f"  Seeds tested: {len(results)}")
        print(f"  Average PnL: ${np.mean(pnls):,.2f}")
        print(f"  Median PnL: ${np.median(pnls):,.2f}")
        print(f"  Std Dev PnL: ${np.std(pnls):,.2f}")
        print(f"  Min PnL: ${np.min(pnls):,.2f} (seed {results[np.argmin(pnls)]['seed']})")
        print(f"  Max PnL: ${np.max(pnls):,.2f} (seed {results[np.argmax(pnls)]['seed']})")
        print(f"  Positive seeds: {len(positive_pnl)}/{len(results)} ({len(positive_pnl)/len(results)*100:.1f}%)")
        print(f"  Negative seeds: {len(negative_pnl)}/{len(results)} ({len(negative_pnl)/len(results)*100:.1f}%)")
        print(f"\n  Average Return: {np.mean(returns):.2f}%")
        print(f"  Median Return: {np.median(returns):.2f}%")
        print(f"  Std Dev Return: {np.std(returns):.2f}%")
        print(f"  Min Return: {np.min(returns):.2f}%")
        print(f"  Max Return: {np.max(returns):.2f}%")
        print(f"\n  Average Max Drawdown: {np.mean(max_drawdowns):.2f}%")
        print(f"  Median Max Drawdown: {np.median(max_drawdowns):.2f}%")
        print(f"  Std Dev Max Drawdown: {np.std(max_drawdowns):.2f}%")
        print(f"  Min Max Drawdown: {np.min(max_drawdowns):.2f}% (seed {results[np.argmin(max_drawdowns)]['seed']})")
        print(f"  Max Max Drawdown: {np.max(max_drawdowns):.2f}% (seed {results[np.argmax(max_drawdowns)]['seed']})")
        print(f"\n  Average Trades: {np.mean(trades):.0f}")
        print(f"  Average Win Rate: {np.mean(win_rates):.2f}%")
        
        return pnls, returns, max_drawdowns
    
    system1_pnls, system1_returns, system1_mdds = print_stats(system1_results, "SYSTEM 1 (20-10)")
    dual_pnls, dual_returns, dual_mdds = print_stats(dual_results, "DUAL SYSTEM (20-10 + 55-20)")
    
    # Comparison
    print("\n" + "="*80)
    print("DIRECT COMPARISON")
    print("="*80)
    
    pnl_diff = np.mean(dual_pnls) - np.mean(system1_pnls)
    pnl_diff_pct = (pnl_diff / abs(np.mean(system1_pnls))) * 100 if np.mean(system1_pnls) != 0 else 0
    
    return_diff = np.mean(dual_returns) - np.mean(system1_returns)
    
    mdd_diff = np.mean(dual_mdds) - np.mean(system1_mdds)
    
    print(f"\nAverage PnL Difference (Dual - System1):")
    print(f"  ${pnl_diff:,.2f} ({pnl_diff_pct:+.1f}%)")
    
    print(f"\nAverage Return Difference (Dual - System1):")
    print(f"  {return_diff:+.2f} percentage points")
    
    print(f"\nAverage Max Drawdown Difference (Dual - System1):")
    print(f"  {mdd_diff:+.2f} percentage points")
    if mdd_diff < 0:
        print(f"  (Dual System has {abs(mdd_diff):.2f}% lower drawdown - BETTER)")
    elif mdd_diff > 0:
        print(f"  (Dual System has {mdd_diff:.2f}% higher drawdown - WORSE)")
    else:
        print(f"  (Same drawdown)")
    
    # Winner count
    system1_better = 0
    dual_better = 0
    tie = 0
    
    for s1_result, dual_result in zip(system1_results, dual_results):
        if s1_result['seed'] == dual_result['seed']:
            if s1_result['total_pnl'] > dual_result['total_pnl']:
                system1_better += 1
            elif dual_result['total_pnl'] > s1_result['total_pnl']:
                dual_better += 1
            else:
                tie += 1
    
    print(f"\nHead-to-Head (by seed):")
    print(f"  System 1 wins: {system1_better}/{len(system1_results)} ({system1_better/len(system1_results)*100:.1f}%)")
    print(f"  Dual System wins: {dual_better}/{len(dual_results)} ({dual_better/len(dual_results)*100:.1f}%)")
    print(f"  Ties: {tie}/{len(system1_results)} ({tie/len(system1_results)*100:.1f}%)")
    
    # Statistical significance (t-test)
    from scipy import stats
    t_stat_pnl, p_value_pnl = stats.ttest_rel(dual_pnls, system1_pnls)
    t_stat_mdd, p_value_mdd = stats.ttest_rel(system1_mdds, dual_mdds)  # Inverted: lower MDD is better
    
    print(f"\nStatistical Significance (Paired t-test):")
    print(f"  PnL Comparison:")
    print(f"    t-statistic: {t_stat_pnl:.4f}")
    print(f"    p-value: {p_value_pnl:.6f}")
    if p_value_pnl < 0.01:
        print(f"    Result: Highly significant (p < 0.01) ✓✓")
    elif p_value_pnl < 0.05:
        print(f"    Result: Significant (p < 0.05) ✓")
    else:
        print(f"    Result: Not significant (p >= 0.05)")
    
    print(f"\n  Max Drawdown Comparison:")
    print(f"    t-statistic: {t_stat_mdd:.4f}")
    print(f"    p-value: {p_value_mdd:.6f}")
    if p_value_mdd < 0.01:
        print(f"    Result: Highly significant (p < 0.01) ✓✓")
    elif p_value_mdd < 0.05:
        print(f"    Result: Significant (p < 0.05) ✓")
    else:
        print(f"    Result: Not significant (p >= 0.05)")
    
    # Save detailed results to CSV
    output_file = os.path.join(os.path.dirname(__file__), 'system_comparison_results.csv')
    
    # Combine results
    all_results = []
    for result in system1_results + dual_results:
        all_results.append({
            'seed': result['seed'],
            'system': result['system'],
            'final_equity': result['final_equity'],
            'total_pnl': result['total_pnl'],
            'return_pct': result['return_pct'],
            'num_trades': result['num_trades'],
            'win_rate': result['win_rate'],
            'avg_win': result['avg_win'],
            'avg_loss': result['avg_loss'],
            'max_drawdown_pct': result['max_drawdown_pct']
        })
    
    df = pd.DataFrame(all_results)
    df = df.sort_values(['seed', 'system'])
    df.to_csv(output_file, index=False)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    # Recommendation
    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    
    if pnl_diff > 0 and p_value_pnl < 0.05:
        print(f"\n✓ DUAL SYSTEM is recommended")
        print(f"  - Average PnL is ${pnl_diff:,.2f} higher ({pnl_diff_pct:+.1f}%)")
        print(f"  - Wins in {dual_better}/{len(dual_results)} seeds ({dual_better/len(dual_results)*100:.1f}%)")
        print(f"  - Average Max Drawdown: {np.mean(dual_mdds):.2f}% vs {np.mean(system1_mdds):.2f}% ({mdd_diff:+.2f}%)")
        print(f"  - PnL difference is statistically significant (p={p_value_pnl:.6f})")
    elif pnl_diff < 0 and p_value_pnl < 0.05:
        print(f"\n✓ SYSTEM 1 is recommended")
        print(f"  - Average PnL is ${-pnl_diff:,.2f} higher ({-pnl_diff_pct:+.1f}%)")
        print(f"  - Wins in {system1_better}/{len(system1_results)} seeds ({system1_better/len(system1_results)*100:.1f}%)")
        print(f"  - Average Max Drawdown: {np.mean(system1_mdds):.2f}% vs {np.mean(dual_mdds):.2f}% ({-mdd_diff:+.2f}%)")
        print(f"  - PnL difference is statistically significant (p={p_value_pnl:.6f})")
    else:
        print(f"\n→ No clear winner")
        print(f"  - Average PnL difference: ${pnl_diff:,.2f} ({pnl_diff_pct:+.1f}%)")
        print(f"  - Average MDD difference: {mdd_diff:+.2f} percentage points")
        print(f"  - PnL difference is not statistically significant (p={p_value_pnl:.6f})")
        print(f"  - Consider other factors (simplicity, trade frequency, drawdown tolerance, etc.)")
    
    print("\n" + "="*80)
    print("COMPARISON COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()

