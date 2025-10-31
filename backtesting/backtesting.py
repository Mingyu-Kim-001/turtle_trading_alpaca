# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import timedelta
import warnings
warnings.filterwarnings('ignore')

def log_trade(trades_log, date, ticker, action, units, N, balance, price, value, reason, 
        system=None, pnl=None, entry_value=None, risk_pot=None, overall_stop=None, pyramid_level=None):
  """
  Generate a trade log entry and append it to trades_log list.
  
  Parameters:
  -----------
  trades_log : list
    List to append the trade log to
  date : datetime
    Trade date
  ticker : str
    Stock ticker symbol
  action : str
    'BUY' or 'SELL'
  units : float
    Number of units traded
  N : float
    ATR value at time of trade
  balance : float
    Account balance after trade
  price : float
    Trade execution price
  value : float
    Total value of the trade
  reason : str
    Reason for the trade (e.g., 'System 1 entry', 'Stop loss')
  system : int, optional
    Trading system (1 or 2)
  pnl : float, optional
    Profit/loss for sell trades
  entry_value : float, optional
    Entry value for tracking
  risk_pot : float, optional
    Risk potential after trade
  overall_stop : float, optional
    Overall stop price for the position
  pyramid_level : int, optional
    Pyramid level (1=initial entry, 2-4=pyramid additions)
  """
  trade_entry = {
    'date': date,
    'ticker': ticker,
    'action': action,
    'units': units,
    'N': N,
    'balance': balance,
    'price': price,
    'value': value,
    'reason': reason
  }
  
  # Add optional fields only if they're provided
  if system is not None:
    trade_entry['system'] = system
  if pnl is not None:
    trade_entry['pnl'] = pnl
  if entry_value is not None:
    trade_entry['entry_value'] = entry_value
  if risk_pot is not None:
    trade_entry['risk_pot'] = risk_pot
  if overall_stop is not None:
    trade_entry['overall_stop'] = overall_stop
  if pyramid_level is not None:
    trade_entry['pyramid_level'] = pyramid_level
  
  trades_log.append(trade_entry)

def prepare_ticker_data(filepath):
  """Load and prepare a single ticker's data with all indicators pre-calculated"""
  ticker = os.path.basename(filepath).replace('_alpaca_daily.csv', '')
  
  try:
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    df = df.set_index('timestamp').sort_index()
    
    # Calculate ATR (N) - vectorized
    df['prev_close'] = df['close'].shift(1)
    df['TR'] = np.maximum(
      df['high'] - df['low'],
      np.maximum(
        np.abs(df['high'] - df['prev_close']),
        np.abs(df['low'] - df['prev_close'])
      )
    )
    df['N'] = df['TR'].rolling(window=20).mean().shift(1) # yesterday's ATR
    
    # Pre-calculate all rolling windows needed - vectorized
    df['high_20'] = df['high'].rolling(window=20).max().shift(1)  # Yesterday's 20-day high
    df['high_55'] = df['high'].rolling(window=55).max().shift(1)  # Yesterday's 55-day high
    df['low_10'] = df['low'].rolling(window=10).min().shift(1)   # Yesterday's 10-day low
    df['low_20'] = df['low'].rolling(window=20).min().shift(1)   # Yesterday's 20-day low
    
    # Entry signals
    df['signal_1_entry'] = df['high'] > df['high_20']  # System 1 entry
    df['signal_2_entry'] = df['high'] > df['high_55']  # System 2 entry
    
    # Exit signals
    df['signal_1_exit'] = df['low'] < df['low_10']   # System 1 exit
    df['signal_2_exit'] = df['low'] < df['low_20']   # System 2 exit
    
    return ticker, df
  except Exception as e:
    print(f"Error loading {filepath}: {e}")
    return None, None

def load_all_tickers_parallel(data_dir='./data/alpaca_daily', max_workers=8):
  """Load all tickers in parallel with pre-calculated indicators"""
  filepaths = [
    os.path.join(data_dir, f) for f in os.listdir(data_dir) 
    if f.endswith('_alpaca_daily.csv')
  ]
  
  tickers_data = {}
  
  with ThreadPoolExecutor(max_workers=max_workers) as executor:
    results = executor.map(prepare_ticker_data, filepaths)
    
    for ticker, df in results:
      if ticker and df is not None and len(df) > 55:
        tickers_data[ticker] = df
  
  return tickers_data

def calculate_overall_stop(pyramid_units):
  """Calculate the overall stop price for the entire position"""
  if not pyramid_units:
    return None
  
  # Find the highest entry price among all pyramid units
  highest_entry = max(unit['entry_price'] for unit in pyramid_units)
  highest_entry_n = next(unit['entry_n'] for unit in pyramid_units if unit['entry_price'] == highest_entry)
  
  # Overall stop is 2N below the highest entry price
  return highest_entry - 2 * highest_entry_n

def vectorized_backtest_with_filter(tickers_data, initial_balance=1e6):
  """Optimized backtest using vectorized operations with System 1 filter rules"""
  
  # Get all unique dates
  all_dates = sorted(set(date for df in tickers_data.values() for date in df.index))
  
  # Initialize tracking arrays
  results = pd.DataFrame(index=all_dates)
  results['balance'] = initial_balance
  results['positions_value'] = 0.0
  results['equity'] = initial_balance
  results['num_positions'] = 0
  
  # Portfolio state
  positions = {}  # {ticker: {'system': int, 'pyramid_units': list, 'stop_price': float}}
  balance = float(initial_balance)
  trades_log = []
  
  # Track System 1 profitable exits for filter rule
  system_1_exits = {}
  
  # Create a combined dataframe for efficient date-based access
  ticker_universe = {}
  for ticker, df in tickers_data.items():
    ticker_universe[ticker] = df.copy()
  
  print(f"Starting backtest for {len(ticker_universe)} tickers...")

  risk_pot = initial_balance * 0.01  # Total equity available for risk

  for i, date in enumerate(all_dates):
    if i % 100 == 0:  # Progress update
      print(f"Processing date {i}/{len(all_dates)} ({date.strftime('%Y-%m-%d')})")
    
    daily_positions_value = 0.0
    positions_to_remove = []
    
    # Batch process all tickers for this date
    for ticker, df in ticker_universe.items():
      if date not in df.index:
        continue
      
      row = df.loc[date]
      
      # Skip if no ATR or zero ATR
      if pd.isna(row['N']) or row['N'] == 0:
        continue
      
      price = row['close']
      high = row['high']
      low = row['low']
      N = row['N']
      
      # Check existing positions
      if ticker in positions:
        pos = positions[ticker]
        system = pos['system']
        pyramid_units = pos['pyramid_units']
        
        # Check if overall stop is hit
        if low < pos['stop_price']:
          # Stop loss triggered for entire position - exit each pyramid unit separately
          for pyramid_idx, pyramid in enumerate(pyramid_units):
            unit_exit_value = pyramid['units'] * pos['stop_price']
            unit_pnl = unit_exit_value - pyramid['entry_value']
            
            balance += unit_exit_value
            risk_pot += pyramid['units'] * pyramid['entry_n'] * 2
            risk_pot += unit_pnl
            
            # Log each pyramid unit's exit separately
            log_trade(trades_log, date, ticker, 'SELL', pyramid['units'], N, balance,
                  pos['stop_price'], unit_exit_value, 'Stop loss (overall)',
                  system=system, pnl=unit_pnl,
                  entry_value=pyramid['entry_value'],
                  risk_pot=risk_pot, pyramid_level=pyramid_idx + 1)
          
          positions_to_remove.append(ticker)
          
          # Track System 1 exits
          if system == 1:
            total_pnl = sum(p['units'] * pos['stop_price'] - p['entry_value'] for p in pyramid_units)
            if ticker not in system_1_exits:
              system_1_exits[ticker] = []
            system_1_exits[ticker].append({
              'date': date,
              'was_profitable': total_pnl > 0,
              'exit_reason': 'Stop loss'
            })
        else:
          # Check for regular exit signals
          should_exit = False
          exit_price = price
          exit_reason = ''
          
          # System-specific exit signals
          if system == 1 and row['signal_1_exit']:
            should_exit = True
            exit_reason = 'System 1 exit signal'
          elif system == 2 and row['signal_2_exit']:
            should_exit = True
            exit_reason = 'System 2 exit signal'
          
          if should_exit:
            # Exit all pyramid units - log each separately
            for pyramid_idx, pyramid in enumerate(pyramid_units):
              unit_exit_value = pyramid['units'] * exit_price
              unit_pnl = unit_exit_value - pyramid['entry_value']
              
              balance += unit_exit_value
              risk_pot += pyramid['units'] * pyramid['entry_n'] * 2
              risk_pot += unit_pnl
              
              # Log each pyramid unit's exit separately
              log_trade(trades_log, date, ticker, 'SELL', pyramid['units'], N, balance,
                    exit_price, unit_exit_value, exit_reason,
                    system=system, pnl=unit_pnl,
                    entry_value=pyramid['entry_value'],
                    risk_pot=risk_pot, pyramid_level=pyramid_idx + 1)
            
            positions_to_remove.append(ticker)
            
            # Track if this was a profitable System 1 exit
            if system == 1:
              total_pnl = sum(p['units'] * exit_price - p['entry_value'] for p in pyramid_units)
              was_profitable = total_pnl > 0
              if ticker not in system_1_exits:
                system_1_exits[ticker] = []
              system_1_exits[ticker].append({
                'date': date,
                'was_profitable': was_profitable,
                'exit_reason': exit_reason
              })
          else:
            # Pyramiding - check if we can add more units
            if len(pyramid_units) < 4 and risk_pot > 0:
              # Get the last pyramid's price
              last_pyramid = pyramid_units[-1]
              last_pyramid_price = last_pyramid['entry_price']
              
              if price > last_pyramid_price + 0.5 * N:
                unit_risk = risk_pot * 0.02  # 2% of risk pot
                add_units = unit_risk / (2 * N)
                pyramid_entry_price = last_pyramid_price + 0.5 * N
                cost = add_units * pyramid_entry_price
                
                if add_units > 0 and balance >= cost:
                  # Add new pyramid unit
                  new_pyramid = {
                    'units': add_units,
                    'entry_price': pyramid_entry_price,
                    'entry_n': N,
                    'entry_value': cost
                  }
                  pyramid_units.append(new_pyramid)
                  
                  # Update overall stop price
                  pos['stop_price'] = calculate_overall_stop(pyramid_units)
                  
                  risk_pot -= add_units * 2 * N
                  balance -= cost
                  
                  # Log the trade with pyramid level
                  log_trade(trades_log, date, ticker, 'BUY', add_units, N, balance,
                        pyramid_entry_price, cost, f'Pyramiding (unit {len(pyramid_units)})',
                        system=system, entry_value=cost, risk_pot=risk_pot,
                        overall_stop=pos['stop_price'], pyramid_level=len(pyramid_units))
      
      # Entry conditions - only check if no position
      elif risk_pot > 0:
        # Check System 1 filter rule
        can_enter_system_1 = True
        
        if row['signal_1_entry']:
          # Check if there was a profitable System 1 exit in the past 20 days
          if ticker in system_1_exits:
            cutoff_date = date - timedelta(days=20)
            recent_exits = [
              exit_info for exit_info in system_1_exits[ticker]
              if exit_info['date'] > cutoff_date
            ]
            
            # If there was a recent profitable exit (not stop loss), block entry
            for exit_info in recent_exits:
              if exit_info['was_profitable'] and exit_info['exit_reason'] != 'Stop loss':
                can_enter_system_1 = False
                break
        
        # System 1 entry (with filter)
        if row['signal_1_entry'] and can_enter_system_1:
          unit_risk = risk_pot * 0.02  # 2% of risk pot
          position_size = unit_risk / (2 * N)
          entry_price = row['high_20']  # Buy at breakout price
          cost = position_size * entry_price
          
          if position_size > 0 and balance >= cost:
            # Create initial pyramid unit
            pyramid_unit = {
              'units': position_size,
              'entry_price': entry_price,
              'entry_n': N,
              'entry_value': cost
            }
            
            # Create position with unified structure
            positions[ticker] = {
              'system': 1,
              'pyramid_units': [pyramid_unit],
              'stop_price': entry_price - 2 * N
            }
            
            risk_pot -= position_size * 2 * N
            balance -= cost
            
            # Log the trade with pyramid level 1 (initial entry)
            log_trade(trades_log, date, ticker, 'BUY', position_size, N, balance,
                  entry_price, cost, 'System 1 entry',
                  system=1, entry_value=cost, risk_pot=risk_pot,
                  overall_stop=entry_price - 2 * N, pyramid_level=1)
    
    # Remove exited positions
    for ticker in positions_to_remove:
      del positions[ticker]
    
    for ticker in positions:
      pos = positions[ticker]
      pyramid_units = pos['pyramid_units']
      price = ticker_universe[ticker].loc[date]['close']
      daily_positions_value += sum(p['units'] * price for p in pyramid_units)
    
    # Update results
    results.loc[date, 'balance'] = balance
    results.loc[date, 'positions_value'] = daily_positions_value
    results.loc[date, 'equity'] = balance + daily_positions_value
    results.loc[date, 'num_positions'] = len(positions)
    results.loc[date, 'risk_pot'] = risk_pot

  trades_df = pd.DataFrame(trades_log)
  return results.dropna(), trades_df

def analyze_pyramid_pnl(trades_df):
  """Analyze P&L by pyramid level"""
  if trades_df.empty:
    print("No trades to analyze")
    return
  
  sells = trades_df[trades_df['action'] == 'SELL'].copy()
  
  if sells.empty:
    print("No sell trades to analyze")
    return
  
  if 'pyramid_level' not in sells.columns:
    print("Pyramid level data not available")
    return
  
  print("\n" + "="*50)
  print("P&L BY PYRAMID LEVEL")
  print("="*50)
  
  # Aggregate statistics by pyramid level
  pyramid_stats = sells.groupby('pyramid_level').agg({
    'pnl': ['sum', 'mean', 'count'],
    'ticker': 'count'
  }).round(2)
  
  print(pyramid_stats)
  
  # Calculate percentage contribution
  total_pnl = sells['pnl'].sum()
  print(f"\nTotal P&L from all exits: ${total_pnl:,.2f}")
  print("\nP&L Contribution by Level:")
  
  for level in sorted(sells['pyramid_level'].unique()):
    level_pnl = sells[sells['pyramid_level'] == level]['pnl'].sum()
    level_count = len(sells[sells['pyramid_level'] == level])
    level_avg = sells[sells['pyramid_level'] == level]['pnl'].mean()
    pct = (level_pnl / total_pnl * 100) if total_pnl != 0 else 0
    
    level_name = "Initial Entry" if level == 1 else f"Pyramid Level {level}"
    print(f"  {level_name}: ${level_pnl:,.2f} ({pct:.1f}%) - {level_count} exits, avg ${level_avg:,.2f}")
  
  # Win rate by level
  print("\nWin Rate by Pyramid Level:")
  for level in sorted(sells['pyramid_level'].unique()):
    level_sells = sells[sells['pyramid_level'] == level]
    wins = (level_sells['pnl'] > 0).sum()
    total = len(level_sells)
    win_rate = (wins / total * 100) if total > 0 else 0
    
    level_name = "Initial Entry" if level == 1 else f"Pyramid Level {level}"
    print(f"  {level_name}: {win_rate:.1f}% ({wins}/{total} wins)")

def analyze_results(results, trades_df, initial_balance=100000, start_date=None, end_date=None):
  """Analyze and display backtest results with System breakdown"""
  
  # Filter results by date range if specified
  if start_date:
    start_date = pd.to_datetime(start_date)
    results = results[results.index >= start_date.tz_localize('UTC')]
    if not trades_df.empty:
      trades_df = trades_df[trades_df['date'] >= start_date.tz_localize('UTC')]
  
  if end_date:
    end_date = pd.to_datetime(end_date)
    results = results[results.index <= end_date.tz_localize('UTC')]
    if not trades_df.empty:
      trades_df = trades_df[trades_df['date'] <= end_date.tz_localize('UTC')]
  
  # Check if we have data after filtering
  if results.empty:
    print("No data available for the specified date range.")
    return results
  
  # Use the equity value at the start of the filtered period as initial balance
  initial_equity = results['equity'].iloc[0]
  
  # Calculate metrics
  results['returns'] = results['equity'].pct_change()
  
  total_return = (results['equity'].iloc[-1] / initial_equity - 1) * 100
  
  # Calculate annualized return based on actual days in the period
  num_days = (results.index[-1] - results.index[0]).days
  if num_days > 0:
    annualized_return = ((results['equity'].iloc[-1] / initial_equity) ** (365.25 / num_days) - 1) * 100
  else:
    annualized_return = 0
  
  sharpe_ratio = results['returns'].mean() / results['returns'].std() * np.sqrt(252) if results['returns'].std() > 0 else 0
  
  # Calculate drawdown
  equity_series = results['equity']
  running_max = equity_series.expanding().max()
  drawdown = (equity_series - running_max) / running_max
  max_drawdown = drawdown.min() * 100
  
  # Win/loss analysis
  if not trades_df.empty:
    # Overall analysis
    sells = trades_df[trades_df['action'] == 'SELL']
    if not sells.empty:
      winning_trades = (sells['pnl'] > 0).sum()
      total_closed_trades = len(sells)
      win_rate = winning_trades / total_closed_trades * 100
      
      # System-specific analysis
      system_1_sells = sells[sells['system'] == 1]
      system_2_sells = sells[sells['system'] == 2]
      
      sys1_wins = (system_1_sells['pnl'] > 0).sum() if len(system_1_sells) > 0 else 0
      sys1_total = len(system_1_sells)
      sys1_win_rate = sys1_wins / sys1_total * 100 if sys1_total > 0 else 0
      
      sys2_wins = (system_2_sells['pnl'] > 0).sum() if len(system_2_sells) > 0 else 0
      sys2_total = len(system_2_sells)
      sys2_win_rate = sys2_wins / sys2_total * 100 if sys2_total > 0 else 0
      
      # Analyze stop losses
      stop_loss_trades = sells[sells['reason'].str.contains('Stop loss', na=False)]
      stop_loss_count = len(stop_loss_trades)
    else:
      win_rate = 0
      total_closed_trades = 0
      sys1_win_rate = 0
      sys1_total = 0
      sys2_win_rate = 0
      sys2_total = 0
      stop_loss_count = 0
  else:
    win_rate = 0
    total_closed_trades = 0
    sys1_win_rate = 0
    sys1_total = 0
    sys2_win_rate = 0
    sys2_total = 0
    stop_loss_count = 0
  
  # Print summary
  print("\n" + "="*50)
  print("BACKTEST RESULTS SUMMARY")
  print("="*50)
  if start_date or end_date:
    print(f"Analysis Period:  {results.index[0].strftime('%Y-%m-%d')} to {results.index[-1].strftime('%Y-%m-%d')}")
    print(f"Days Analyzed:    {num_days}")
  print(f"Initial Equity:   ${initial_equity:,.2f}")
  print(f"Final Equity:     ${results['equity'].iloc[-1]:,.2f}")
  print(f"Total Return:     {total_return:.2f}%")
  print(f"Annualized Return:  {annualized_return:.2f}%")
  print(f"Sharpe Ratio:     {sharpe_ratio:.2f}")
  print(f"Max Drawdown:     {max_drawdown:.2f}%")
  print(f"\nTotal Trades:     {len(trades_df)}")
  print(f"Closed Positions:   {total_closed_trades}")
  print(f"Stop Loss Exits:  {stop_loss_count}")
  print(f"Overall Win Rate:   {win_rate:.2f}%")
  print(f"\nSystem 1 Trades:  {sys1_total} (Win Rate: {sys1_win_rate:.2f}%)")
  print(f"System 2 Trades:  {sys2_total} (Win Rate: {sys2_win_rate:.2f}%)")
  print(f"Max Positions:    {results['num_positions'].max()}")
  
  # Plot results
  fig, axes = plt.subplots(3, 1, figsize=(14, 10))
  
  # Add date range to the main title if specified
  title_suffix = ""
  if start_date or end_date:
    title_suffix = f" ({results.index[0].strftime('%Y-%m-%d')} to {results.index[-1].strftime('%Y-%m-%d')})"
  
  # Equity curve
  axes[0].plot(results.index, results['equity'], 'b-', linewidth=2)
  axes[0].fill_between(results.index, initial_equity, results['equity'], 
             where=results['equity'] >= initial_equity, alpha=0.3, color='green')
  axes[0].fill_between(results.index, initial_equity, results['equity'], 
             where=results['equity'] < initial_equity, alpha=0.3, color='red')
  axes[0].set_title(f'Portfolio Equity Over Time{title_suffix}', fontsize=14, fontweight='bold')
  axes[0].set_ylabel('Equity ($)', fontsize=12)
  axes[0].grid(True, alpha=0.3)
  axes[0].axhline(y=initial_equity, color='k', linestyle='--', alpha=0.5)
  
  # Drawdown
  axes[1].fill_between(results.index, 0, drawdown * 100, color='red', alpha=0.7)
  axes[1].set_title('Drawdown %', fontsize=14, fontweight='bold')
  axes[1].set_ylabel('Drawdown (%)', fontsize=12)
  axes[1].grid(True, alpha=0.3)
  
  # Number of positions
  axes[2].plot(results.index, results['num_positions'], 'g-', linewidth=2)
  axes[2].fill_between(results.index, 0, results['num_positions'], alpha=0.3, color='green')
  axes[2].set_title('Number of Open Positions', fontsize=14, fontweight='bold')
  axes[2].set_xlabel('Date', fontsize=12)
  axes[2].set_ylabel('Positions', fontsize=12)
  axes[2].grid(True, alpha=0.3)
  
  plt.tight_layout()
  plt.show()
  
  return results

# %%
# Main execution
if __name__ == "__main__":
  import time
  
  start_time = time.time()
  
  # Load all tickers with parallel processing
  print("Loading ticker data with parallel processing...")
  tickers_data = load_all_tickers_parallel('./data/alpaca_daily', max_workers=8)
  
  # Run optimized backtest with filter rules
  print("\nRunning optimized backtest with System 1 filter rules...")
  backtest_start = time.time()

# %%
  results, trades_df = vectorized_backtest_with_filter(tickers_data, initial_balance=100000)
  print(f"Backtest completed in {time.time() - backtest_start:.1f} seconds")

# %%
  # Analyze results
  backtest_start_date = '2016-01-01'
  backtest_end_date = '2025-11-12'
  
  analyzed_results = analyze_results(
    results, 
    trades_df,
    initial_balance=100000,
    start_date=backtest_start_date,
    end_date=backtest_end_date
  )
  
  # Analyze pyramid-level P&L
  if not trades_df.empty:
    analyze_pyramid_pnl(trades_df)
  
  print(f"\nTotal execution time: {time.time() - start_time:.1f} seconds")
  
  # Show top traded tickers
  if not trades_df.empty:
    print("\n" + "="*50)
    print("TOP 10 MOST TRADED TICKERS")
    print("="*50)
    print(trades_df['ticker'].value_counts().head(10))
    
    # Show System breakdown
    print("\n" + "="*50)
    print("TRADES BY SYSTEM")
    print("="*50)
    system_summary = trades_df.groupby('system').agg({
      'ticker': 'count',
      'value': 'sum'
    }).rename(columns={'ticker': 'trade_count', 'value': 'total_value'})
    print(system_summary)
# %%