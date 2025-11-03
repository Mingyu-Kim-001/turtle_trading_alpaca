import pandas as pd
import numpy as np
import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from system_long.core.indicators import IndicatorCalculator

class TurtleBacktester:
  def __init__(self, initial_equity=10_000, risk_per_unit_pct=0.001, max_positions=10, enable_logging=True):
    self.initial_equity = initial_equity
    self.cash = initial_equity
    self.risk_per_unit_pct = risk_per_unit_pct
    self.max_positions = max_positions
    self.positions = {}
    self.trades = []
    self.last_trade_was_win = {}
    self.cash_history = []
    self.equity_history = []
    self.unit_history = []
    self.enable_logging = enable_logging

  def _calculate_indicators(self, df):
    """Calculate all necessary indicators."""
    df = IndicatorCalculator.calculate_atr(df, period=20)
    df = IndicatorCalculator.calculate_donchian_channels(df, entry_period=20, exit_period=10)
    return df

  def _get_unit_size(self, total_equity, n_value):
    """Calculates the unit size for a trade based on total equity."""
    if n_value == 0 or total_equity <= 0:
      return 0
    unit_risk = total_equity * self.risk_per_unit_pct
    # Risk per unit is 2N
    unit_size = unit_risk / n_value
    return unit_size

  def _calculate_total_equity(self, processed_data, date):
    """Calculates the total equity (cash + value of positions)."""
    market_value = 0
    for ticker, position in self.positions.items():
        if date in processed_data[ticker].index:
            prev_close = processed_data[ticker].loc[date]['close']
            market_value += position['units'] * prev_close
    return self.cash + market_value

  def run(self, all_data):
    """Runs the backtest for all tickers simultaneously."""
    
    # Calculate indicators for all dataframes
    processed_data = {ticker: self._calculate_indicators(df.copy()) for ticker, df in all_data.items()}

    # Create a master date index
    all_dates = sorted(list(set(date for df in processed_data.values() for date in df.index)))

    for i in range(1, len(all_dates)):
      today_date = all_dates[i]
      yesterday_date = all_dates[i-1]

      total_equity = self._calculate_total_equity(processed_data, yesterday_date)

      # 1. Process exits first to free up cash
      for ticker, df in processed_data.items():
        if today_date not in df.index or yesterday_date not in df.index:
          continue
        if ticker in self.positions:
          today = df.loc[today_date]
          yesterday = df.loc[yesterday_date]
          position = self.positions[ticker]
          exit_signal = False
          exit_reason = ''
          if today['low'] <= position['stop_price']:
            exit_price = position['stop_price']
            exit_signal = True
            exit_reason = 'Stop-loss'
          elif today['close'] < yesterday['low_10']:
            exit_price = today['close']
            exit_signal = True
            exit_reason = '10-day low'

          if exit_signal:
            self._close_position(ticker, exit_price, today_date, exit_reason)

      # 2. Process pyramiding opportunities
      for ticker, df in processed_data.items():
        if today_date not in df.index or yesterday_date not in df.index:
          continue
        if ticker in self.positions:
            today = df.loc[today_date]
            self._check_pyramiding(ticker, today, total_equity)

      # 3. Process new entries
      for ticker, df in processed_data.items():
        if today_date not in df.index or yesterday_date not in df.index:
          continue
        if ticker not in self.positions:
            today = df.loc[today_date]
            yesterday = df.loc[yesterday_date]
            if today['high'] > yesterday['high_20']:
                if not self.last_trade_was_win.get(ticker, False):
                    entry_price = yesterday['high_20']
                    self._open_position(ticker, entry_price, today['N'], total_equity, today_date)
                else:
                    if today['low'] < yesterday['low_20']:
                        self.last_trade_was_win[ticker] = False
      
      current_total_equity = self._calculate_total_equity(processed_data, today_date)
      self.cash_history.append((today_date, self.cash))
      self.equity_history.append((today_date, current_total_equity))
      total_units = sum(p['pyramid_count'] for p in self.positions.values())
      self.unit_history.append((today_date, total_units))
    final_equity = self._calculate_total_equity(processed_data, all_dates[-1])
    return final_equity, self.trades, self.cash, self.cash_history, self.equity_history, self.unit_history

  def _open_position(self, ticker, entry_price, n_value, total_equity, today_date):
    if self.cash <= 0:
        return
    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0:
      return

    cost = unit_size * entry_price
    if self.cash < cost:
        return

    stop_price = entry_price - 2 * n_value
    self.positions[ticker] = {
      'units': unit_size,
      'entry_price': entry_price,
      'entry_date': today_date,
      'stop_price': stop_price,
      'n_value': n_value,
      'pyramid_count': 1
    }
    self.cash -= cost

  def _close_position(self, ticker, exit_price, today_date, exit_reason):
    position = self.positions.pop(ticker)
    pnl = position['units'] * (exit_price - position['entry_price'])

    self.cash += position['units'] * exit_price

    # Log exit details
    if self.enable_logging:
      pnl_pct = (exit_price - position['entry_price']) / position['entry_price'] * 100
      duration = (today_date - position['entry_date']).days

      print(f"\n{'='*80}")
      print(f"EXIT: {ticker} [{exit_reason}]")
      print(f"{'='*80}")
      print(f"  Entry Date:       {position['entry_date'].strftime('%Y-%m-%d')}")
      print(f"  Exit Date:        {today_date.strftime('%Y-%m-%d')}")
      print(f"  Duration:         {duration} days")
      print(f"  Entry Price:      ${position['entry_price']:.2f}")
      print(f"  Exit Price:       ${exit_price:.2f}")
      print(f"  Entry N:          ${position['n_value']:.2f}")
      print(f"  Stop Price:       ${position['stop_price']:.2f}")
      print(f"  Pyramid Count:    {position['pyramid_count']} unit(s)")
      print(f"  Total Units:      {position['units']:.2f}")
      print(f"  P&L:              ${pnl:,.2f} ({pnl_pct:+.2f}%)")
      print(f"{'='*80}")

    self.trades.append({
      'ticker': ticker,
      'entry_date': position['entry_date'],
      'exit_date': today_date,
      'entry_price': position['entry_price'],
      'exit_price': exit_price,
      'pnl': pnl,
      'pyramid_count': position['pyramid_count'],
      'exit_reason': exit_reason
    })
    self.last_trade_was_win[ticker] = pnl > 0

  def _check_pyramiding(self, ticker, today, total_equity):
    if self.cash <= 0:
        return
    position = self.positions[ticker]
    if position['pyramid_count'] < 4:
      pyramid_price = position['entry_price'] + 0.5 * position['n_value']
      if today['high'] >= pyramid_price:
        unit_size = self._get_unit_size(total_equity, position['n_value'])
        if unit_size > 0:
            cost = unit_size * pyramid_price
            if self.cash < cost:
                return
            self.cash -= cost
            position['units'] += unit_size
            position['entry_price'] = (position['entry_price'] * (position['units'] - unit_size) + pyramid_price * unit_size) / position['units']
            position['pyramid_count'] += 1
            position['stop_price'] = pyramid_price - 2 * position['n_value']

if __name__ == "__main__":
  import matplotlib.pyplot as plt

  data_dir = os.path.join(project_root, "data/alpaca_daily")
  all_files = os.listdir(data_dir)
  csv_files = sorted([f for f in all_files if f.endswith('_alpaca_daily.csv')])

  all_data = {}
  for file_name in csv_files:
    ticker = file_name.split('_')[0]
    data_path = os.path.join(data_dir, file_name)
    if os.path.exists(data_path):
      all_data[ticker] = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)

  # Set enable_logging=False for full backtest (too verbose)
  # Set enable_logging=True to see detailed exit information
  backtester = TurtleBacktester(enable_logging=False)
  final_equity, all_trades, final_cash, cash_history, equity_history, unit_history = backtester.run(all_data)

  # Generate Summary Report
  print("Overall Backtest Summary")
  print("=" * 30)
  total_initial_equity = backtester.initial_equity
  total_pnl = final_equity - total_initial_equity
  total_pnl_pct = (total_pnl / total_initial_equity) * 100 if total_initial_equity > 0 else 0
  print(f"Initial Equity: ${total_initial_equity:,.2f}")
  print(f"Final Equity:   ${final_equity:,.2f}")
  print(f"Final Cash:     ${final_cash:,.2f}")
  print(f"Total PnL:      ${total_pnl:,.2f} ({total_pnl_pct:.2f}%)")
  print("-" * 30)
  
  if all_trades:
    num_trades = len(all_trades)
    winning_trades = [t for t in all_trades if t['pnl'] > 0]
    win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
    avg_pnl = total_pnl / num_trades if num_trades > 0 else 0
    
    print(f"Total Trades: {num_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Average P/L per Trade: ${avg_pnl:,.2f}")
    print("-" * 30)

    # Detailed per-ticker summary
    ticker_summary = {}
    for trade in all_trades:
      ticker = trade['ticker']
      if ticker not in ticker_summary:
          ticker_summary[ticker] = {
              'trades': 0,
              'wins': 0,
              'losses': 0,
              'total_pnl': 0,
              'pyramid_trades': 0,
              'exit_reasons': {}
          }
      
      summary = ticker_summary[ticker]
      summary['trades'] += 1
      summary['total_pnl'] += trade['pnl']
      if trade['pnl'] > 0:
          summary['wins'] += 1
      else:
          summary['losses'] += 1
      
      if trade['pyramid_count'] > 1:
          summary['pyramid_trades'] += 1
          
      reason = trade['exit_reason']
      summary['exit_reasons'][reason] = summary['exit_reasons'].get(reason, 0) + 1

    if ticker_summary:
      print("\n--- Per-Ticker Trade Summary ---")
      # Sort tickers by the number of trades
      sorted_tickers = sorted(ticker_summary.items(), key=lambda item: item[1]['trades'], reverse=True)
      
      for i, (ticker, summary) in enumerate(sorted_tickers):
        print(f"\nTicker: {ticker}")
        print(f"  - Total Trades: {summary['trades']}")
        print(f"  - Wins/Losses: {summary['wins']}/{summary['losses']}")
        print(f"  - Total PnL: ${summary['total_pnl']:,.2f}")
        print(f"  - Pyramid Trades (trades with >1 unit): {summary['pyramid_trades']}")
        print("  - Exit Reasons:")
        for reason, count in summary['exit_reasons'].items():
          print(f"    - {reason}: {count}")
        if i >= 9:  # Limit to top 10 tickers
          break
        

  # Generate and save plots
  if cash_history:
    dates, cash_values = zip(*cash_history)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, cash_values)
    plt.title('Cash Over Time')
    plt.xlabel('Date')
    plt.ylabel('Cash Amount')
    plt.grid(True)
    plot_path = os.path.join(project_root, 'backtesting', 'turtle_backtester_plots', 'cash_over_time.png')
    plt.savefig(plot_path)
    print(f"\nPlot of cash over time saved to: {plot_path}")

  if equity_history:
    dates, equity_values = zip(*equity_history)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, equity_values)
    plt.title('Total Equity Over Time')
    plt.xlabel('Date')
    plt.ylabel('Total Equity Amount')
    plt.grid(True)
    plot_path = os.path.join(project_root, 'backtesting', 'turtle_backtester_plots', 'equity_over_time.png')
    plt.savefig(plot_path)
    print(f"Plot of total equity over time saved to: {plot_path}")

  if unit_history:
    dates, unit_values = zip(*unit_history)
    plt.figure(figsize=(12, 6))
    plt.plot(dates, unit_values)
    plt.title('Total Units Over Time')
    plt.xlabel('Date')
    plt.ylabel('Total Units')
    plt.grid(True)
    plot_path = os.path.join(project_root, 'backtesting', 'turtle_backtester_plots', 'units_over_time.png')
    plt.savefig(plot_path)
    print(f"Plot of total units over time saved to: {plot_path}")
