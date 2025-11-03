"""
Turtle Trading Backtester with Long and Short Positions

This backtester implements the Turtle Trading strategy with support for:
- Long positions: Entry on 20-day high, exit on 10-day low, stop at entry - 2N
- Short positions: Entry on 20-day low, exit on 10-day high, stop at entry + 2N
- Pyramiding up to 4 units for both longs and shorts
- Position sizing based on risk per unit (1% of equity per unit by default)
"""

import pandas as pd
import numpy as np
import sys
import os
from typing import Dict, List, Tuple, Optional

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from system.core.indicators import IndicatorCalculator


class TurtleLongShortBacktester:
  def __init__(self, initial_equity=10_000, risk_per_unit_pct=0.01, max_positions=10,
               enable_shorts=True, check_shortability=False, shortable_tickers=None,
               enable_logging=True):
    """
    Initialize the backtester

    Args:
      initial_equity: Starting capital
      risk_per_unit_pct: Risk per unit as % of equity (default 1%)
      max_positions: Maximum number of positions (long + short combined)
      enable_shorts: Whether to enable short selling
      check_shortability: If True, only short tickers in shortable_tickers set
      shortable_tickers: Set of tickers that are shortable (None = all shortable)
      enable_logging: Whether to print exit logs
    """
    self.initial_equity = initial_equity
    self.cash = initial_equity
    self.risk_per_unit_pct = risk_per_unit_pct
    self.max_positions = max_positions
    self.enable_shorts = enable_shorts
    self.check_shortability = check_shortability
    self.shortable_tickers = shortable_tickers or set()
    self.enable_logging = enable_logging

    self.long_positions = {}
    self.short_positions = {}
    self.trades = []
    self.last_trade_was_win = {}

    # History tracking
    self.cash_history = []
    self.equity_history = []
    self.long_unit_history = []
    self.short_unit_history = []
    self.net_unit_history = []

  def _calculate_indicators(self, df):
    """Calculate all necessary indicators."""
    df = IndicatorCalculator.calculate_atr(df, period=20)
    df = IndicatorCalculator.calculate_donchian_channels(df, entry_period=20, exit_period=10)
    return df

  def _get_unit_size(self, total_equity, n_value):
    """
    Calculate unit size based on risk per unit.

    For both longs and shorts:
      Risk per unit = equity * risk_per_unit_pct
      Unit size = Risk per unit / N

    Args:
      total_equity: Total portfolio equity
      n_value: ATR value
    """
    if n_value == 0 or total_equity <= 0:
      return 0
    unit_risk = total_equity * self.risk_per_unit_pct
    unit_size = unit_risk / n_value
    return unit_size

  def _calculate_total_equity(self, processed_data, date):
    """
    Calculate total equity (cash + value of all positions).

    Long positions: market_value = units * current_price
    Short positions: P&L is already reflected in cash, so just count unrealized P&L
    """
    market_value = 0

    # Value of long positions
    for ticker, position in self.long_positions.items():
      if date in processed_data[ticker].index:
        current_price = processed_data[ticker].loc[date]['close']
        market_value += position['units'] * current_price

    # Unrealized P&L from short positions
    for ticker, position in self.short_positions.items():
      if date in processed_data[ticker].index:
        current_price = processed_data[ticker].loc[date]['close']
        # Short unrealized P&L = units * (entry_price - current_price)
        unrealized_pnl = position['units'] * (position['entry_price'] - current_price)
        market_value += unrealized_pnl

    return self.cash + market_value

  def _is_shortable(self, ticker):
    """Check if ticker is shortable."""
    if not self.enable_shorts:
      return False
    if not self.check_shortability:
      return True
    return ticker in self.shortable_tickers

  def _total_position_count(self):
    """Get total number of positions (long + short)."""
    return len(self.long_positions) + len(self.short_positions)

  def run(self, all_data):
    """Run the backtest for all tickers simultaneously."""

    # Calculate indicators for all dataframes
    processed_data = {ticker: self._calculate_indicators(df.copy()) for ticker, df in all_data.items()}

    # Create a master date index
    all_dates = sorted(list(set(date for df in processed_data.values() for date in df.index)))

    for i in range(1, len(all_dates)):
      today_date = all_dates[i]
      yesterday_date = all_dates[i-1]

      total_equity = self._calculate_total_equity(processed_data, yesterday_date)

      # 1. Process exits first to free up cash
      self._process_exits(processed_data, today_date, yesterday_date)

      # 2. Process pyramiding opportunities
      self._process_pyramiding(processed_data, today_date, yesterday_date, total_equity)

      # 3. Process new entries (both long and short)
      self._process_entries(processed_data, today_date, yesterday_date, total_equity)

      # Track history
      current_total_equity = self._calculate_total_equity(processed_data, today_date)

      # Ensure cash never goes negative
      if self.cash < 0:
        raise ValueError(f"CRITICAL ERROR: Cash is negative: ${self.cash:.2f} on {today_date}")

      self.cash_history.append((today_date, self.cash))
      self.equity_history.append((today_date, current_total_equity))

      long_units = sum(p['pyramid_count'] for p in self.long_positions.values())
      short_units = sum(p['pyramid_count'] for p in self.short_positions.values())
      self.long_unit_history.append((today_date, long_units))
      self.short_unit_history.append((today_date, short_units))
      self.net_unit_history.append((today_date, long_units - short_units))

    final_equity = self._calculate_total_equity(processed_data, all_dates[-1])
    return (final_equity, self.trades, self.cash,
            self.cash_history, self.equity_history,
            self.long_unit_history, self.short_unit_history, self.net_unit_history)

  def _process_exits(self, processed_data, today_date, yesterday_date):
    """Process exits for both long and short positions."""

    # Exit long positions
    for ticker in list(self.long_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index or yesterday_date not in df.index:
        continue

      today = df.loc[today_date]
      yesterday = df.loc[yesterday_date]
      position = self.long_positions[ticker]

      exit_signal = False
      exit_reason = ''
      exit_price = None

      # Stop loss check (price falls to stop)
      if today['low'] <= position['stop_price']:
        exit_price = position['stop_price']
        exit_signal = True
        exit_reason = 'Stop-loss'
      # Exit signal (price falls below 10-day low)
      elif today['close'] < yesterday['low_10']:
        exit_price = today['close']
        exit_signal = True
        exit_reason = '10-day low'

      if exit_signal:
        self._close_long_position(ticker, exit_price, today_date, exit_reason)

    # Exit short positions
    for ticker in list(self.short_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index or yesterday_date not in df.index:
        continue

      today = df.loc[today_date]
      yesterday = df.loc[yesterday_date]
      position = self.short_positions[ticker]

      exit_signal = False
      exit_reason = ''
      exit_price = None

      # Stop loss check (price rises to stop)
      if today['high'] >= position['stop_price']:
        exit_price = position['stop_price']
        exit_signal = True
        exit_reason = 'Stop-loss'
      # Exit signal (price rises above 10-day high)
      elif today['close'] > yesterday['high_10']:
        exit_price = today['close']
        exit_signal = True
        exit_reason = '10-day high'

      if exit_signal:
        self._close_short_position(ticker, exit_price, today_date, exit_reason)

  def _process_pyramiding(self, processed_data, today_date, yesterday_date, total_equity):
    """Process pyramiding opportunities for both longs and shorts."""

    # Pyramid long positions (on upward moves)
    for ticker in list(self.long_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index:
        continue
      today = df.loc[today_date]
      self._check_long_pyramiding(ticker, today, total_equity)

    # Pyramid short positions (on downward moves)
    for ticker in list(self.short_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index:
        continue
      today = df.loc[today_date]
      self._check_short_pyramiding(ticker, today, total_equity)

  def _process_entries(self, processed_data, today_date, yesterday_date, total_equity):
    """Process new entry signals for both longs and shorts."""

    for ticker, df in processed_data.items():
      if today_date not in df.index or yesterday_date not in df.index:
        continue

      # Skip if already have a position in this ticker
      if ticker in self.long_positions or ticker in self.short_positions:
        continue

      # Skip if at max positions
      if self._total_position_count() >= self.max_positions:
        continue

      today = df.loc[today_date]
      yesterday = df.loc[yesterday_date]

      # Check for long entry signal (breakout above 20-day high)
      if today['high'] > yesterday['high_20']:
        if not self.last_trade_was_win.get((ticker, 'long'), False):
          entry_price = yesterday['high_20']
          self._open_long_position(ticker, entry_price, today['N'], total_equity, today_date)
        else:
          # Reset win flag if price breaks below 20-day low
          if today['low'] < yesterday['low_20']:
            self.last_trade_was_win[(ticker, 'long')] = False

      # Check for short entry signal (breakdown below 20-day low)
      if self._is_shortable(ticker) and today['low'] < yesterday['low_20']:
        if not self.last_trade_was_win.get((ticker, 'short'), False):
          entry_price = yesterday['low_20']
          self._open_short_position(ticker, entry_price, today['N'], total_equity, today_date)
        else:
          # Reset win flag if price breaks above 20-day high
          if today['high'] > yesterday['high_20']:
            self.last_trade_was_win[(ticker, 'short')] = False

  def _open_long_position(self, ticker, entry_price, n_value, total_equity, today_date):
    """Open a new long position."""
    if self.cash <= 0:
      return

    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0:
      return

    cost = unit_size * entry_price
    if self.cash < cost:
      return

    stop_price = entry_price - 2 * n_value

    self.long_positions[ticker] = {
      'units': unit_size,
      'entry_price': entry_price,
      'entry_date': today_date,
      'stop_price': stop_price,
      'n_value': n_value,
      'pyramid_count': 1,
      'side': 'long'
    }
    self.cash -= cost

    # Safety check
    if self.cash < 0:
      raise ValueError(f"Cash went negative after opening long {ticker}: ${self.cash:.2f}")

  def _close_long_position(self, ticker, exit_price, today_date, exit_reason):
    """Close a long position."""
    position = self.long_positions.pop(ticker)
    pnl = position['units'] * (exit_price - position['entry_price'])

    self.cash += position['units'] * exit_price

    # Log exit details
    if self.enable_logging:
      pnl_pct = (exit_price - position['entry_price']) / position['entry_price'] * 100
      duration = (today_date - position['entry_date']).days

      print(f"\n{'='*80}")
      print(f"EXIT LONG: {ticker} [{exit_reason}]")
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
      'side': 'long',
      'entry_date': position['entry_date'],
      'exit_date': today_date,
      'entry_price': position['entry_price'],
      'exit_price': exit_price,
      'pnl': pnl,
      'pyramid_count': position['pyramid_count'],
      'exit_reason': exit_reason
    })

    self.last_trade_was_win[(ticker, 'long')] = pnl > 0

  def _check_long_pyramiding(self, ticker, today, total_equity):
    """Check for long pyramiding opportunity (add on upward move)."""
    if self.cash <= 0:
      return

    position = self.long_positions[ticker]
    if position['pyramid_count'] >= 4:
      return

    # Pyramid trigger: last_entry + 0.5N
    pyramid_price = position['entry_price'] + 0.5 * position['n_value']

    if today['high'] >= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        cost = unit_size * pyramid_price
        if self.cash < cost:
          return

        self.cash -= cost

        # Safety check
        if self.cash < 0:
          raise ValueError(f"Cash went negative after pyramiding long {ticker}: ${self.cash:.2f}")

        # Update position
        old_units = position['units']
        new_units = old_units + unit_size
        position['units'] = new_units
        position['entry_price'] = (position['entry_price'] * old_units + pyramid_price * unit_size) / new_units
        position['pyramid_count'] += 1
        position['stop_price'] = pyramid_price - 2 * position['n_value']

  def _open_short_position(self, ticker, entry_price, n_value, total_equity, today_date):
    """Open a new short position."""
    if self.cash <= 0:
      return

    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0:
      return

    # For shorts, we need margin (use 50% of position value as simplified margin requirement)
    margin_required = (unit_size * entry_price) * 0.5
    if self.cash < margin_required:
      return

    # Short stop is ABOVE entry (price rises)
    stop_price = entry_price + 2 * n_value

    self.short_positions[ticker] = {
      'units': unit_size,
      'entry_price': entry_price,
      'entry_date': today_date,
      'stop_price': stop_price,
      'n_value': n_value,
      'pyramid_count': 1,
      'side': 'short'
    }

    # Deduct margin from cash
    self.cash -= margin_required

    # Safety check
    if self.cash < 0:
      raise ValueError(f"Cash went negative after opening short {ticker}: ${self.cash:.2f}")

  def _close_short_position(self, ticker, exit_price, today_date, exit_reason):
    """Close a short position."""
    position = self.short_positions.pop(ticker)

    # Short P&L = units * (entry_price - exit_price)
    pnl = position['units'] * (position['entry_price'] - exit_price)

    # Return margin + P&L
    margin_used = (position['units'] * position['entry_price']) * 0.5
    
    cash_change = margin_used + pnl
    if self.cash + cash_change < 0:
        # This trade bankrupts the account. Cap the loss.
        pnl = -self.cash - margin_used
        self.cash = 0
    else:
        self.cash += cash_change

    # Log exit details
    if self.enable_logging:
      pnl_pct = (position['entry_price'] - exit_price) / position['entry_price'] * 100
      duration = (today_date - position['entry_date']).days

      print(f"\n{'='*80}")
      print(f"EXIT SHORT: {ticker} [{exit_reason}]")
      print(f"{'='*80}")
      print(f"  Entry Date:       {position['entry_date'].strftime('%Y-%m-%d')}")
      print(f"  Exit Date:        {today_date.strftime('%Y-%m-%d')}")
      print(f"  Duration:         {duration} days")
      print(f"  Entry Price:      ${position['entry_price']:.2f} (short)")
      print(f"  Exit Price:       ${exit_price:.2f}")
      print(f"  Entry N:          ${position['n_value']:.2f}")
      print(f"  Stop Price:       ${position['stop_price']:.2f}")
      print(f"  Pyramid Count:    {position['pyramid_count']} unit(s)")
      print(f"  Total Units:      {position['units']:.2f}")
      print(f"  P&L:              ${pnl:,.2f} ({pnl_pct:+.2f}%)")
      print(f"{'='*80}")

    self.trades.append({
      'ticker': ticker,
      'side': 'short',
      'entry_date': position['entry_date'],
      'exit_date': today_date,
      'entry_price': position['entry_price'],
      'exit_price': exit_price,
      'pnl': pnl,
      'pyramid_count': position['pyramid_count'],
      'exit_reason': exit_reason
    })

    self.last_trade_was_win[(ticker, 'short')] = pnl > 0

  def _check_short_pyramiding(self, ticker, today, total_equity):
    """Check for short pyramiding opportunity (add on downward move)."""
    if self.cash <= 0:
      return

    position = self.short_positions[ticker]
    if position['pyramid_count'] >= 4:
      return

    # Pyramid trigger for shorts: last_entry - 0.5N (price moves DOWN)
    pyramid_price = position['entry_price'] - 0.5 * position['n_value']

    if today['low'] <= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        margin_required = (unit_size * pyramid_price) * 0.5
        if self.cash < margin_required:
          return

        self.cash -= margin_required

        # Safety check
        if self.cash < 0:
          raise ValueError(f"Cash went negative after pyramiding short {ticker}: ${self.cash:.2f}")

        # Update position
        old_units = position['units']
        new_units = old_units + unit_size
        position['units'] = new_units
        position['entry_price'] = (position['entry_price'] * old_units + pyramid_price * unit_size) / new_units
        position['pyramid_count'] += 1
        # Short stop moves UP with entry
        position['stop_price'] = pyramid_price + 2 * position['n_value']


def get_shortable_tickers_from_alpaca(api_key, api_secret):
  """
  Fetch list of shortable tickers from Alpaca API.

  Args:
    api_key: Alpaca API key
    api_secret: Alpaca API secret

  Returns:
    Set of shortable ticker symbols
  """
  from alpaca.trading.client import TradingClient

  trading_client = TradingClient(api_key, api_secret, paper=True)

  try:
    # Get all assets
    assets = trading_client.get_all_assets()

    # Filter for shortable stocks
    shortable = {asset.symbol for asset in assets
                 if asset.tradable and asset.shortable and asset.status == 'active'}

    print(f"Found {len(shortable)} shortable tickers from Alpaca")
    return shortable
  except Exception as e:
    print(f"Error fetching shortable tickers: {e}")
    return set()


if __name__ == "__main__":
  import matplotlib.pyplot as plt

  # Configuration
  ENABLE_SHORTS = True
  CHECK_SHORTABILITY = False  # Set to True to check Alpaca shortable list

  # Optionally fetch shortable tickers from Alpaca
  shortable_tickers = None
  if CHECK_SHORTABILITY:
    alpaca_key = os.environ.get('ALPACA_PAPER_KEY')
    alpaca_secret = os.environ.get('ALPACA_PAPER_SECRET')
    if alpaca_key and alpaca_secret:
      shortable_tickers = get_shortable_tickers_from_alpaca(alpaca_key, alpaca_secret)
    else:
      print("Warning: ALPACA_PAPER_KEY/SECRET not set, assuming all tickers shortable")
      CHECK_SHORTABILITY = False

  # Load data
  data_dir = os.path.join(project_root, "data/alpaca_daily")
  all_files = os.listdir(data_dir)
  csv_files = sorted([f for f in all_files if f.endswith('_alpaca_daily.csv')])

  all_data = {}
  for file_name in csv_files:
    ticker = file_name.split('_')[0]
    data_path = os.path.join(data_dir, file_name)
    if os.path.exists(data_path):
      all_data[ticker] = pd.read_csv(data_path, index_col='timestamp', parse_dates=True)

  print(f"Loaded data for {len(all_data)} tickers")

  # Run backtest
  # Set enable_logging=False for full backtest (too verbose)
  # Set enable_logging=True to see detailed exit information
  backtester = TurtleLongShortBacktester(
    initial_equity=10_000,
    risk_per_unit_pct=0.01,
    max_positions=10,
    enable_shorts=ENABLE_SHORTS,
    check_shortability=CHECK_SHORTABILITY,
    shortable_tickers=shortable_tickers,
    enable_logging=False
  )

  print(f"\nRunning backtest (shorts {'enabled' if ENABLE_SHORTS else 'disabled'})...")
  results = backtester.run(all_data)
  (final_equity, all_trades, final_cash, cash_history, equity_history,
   long_unit_history, short_unit_history, net_unit_history) = results

  # Generate Summary Report
  print("\n" + "="*60)
  print("OVERALL BACKTEST SUMMARY")
  print("="*60)

  total_initial_equity = backtester.initial_equity
  total_pnl = final_equity - total_initial_equity
  total_pnl_pct = (total_pnl / total_initial_equity) * 100 if total_initial_equity > 0 else 0

  print(f"Strategy: Turtle Trading {'Long + Short' if ENABLE_SHORTS else 'Long Only'}")
  print(f"Initial Equity: ${total_initial_equity:,.2f}")
  print(f"Final Equity:   ${final_equity:,.2f}")
  print(f"Final Cash:     ${final_cash:,.2f}")
  print(f"Total PnL:      ${total_pnl:,.2f} ({total_pnl_pct:.2f}%)")
  print("-" * 60)

  if all_trades:
    num_trades = len(all_trades)
    long_trades = [t for t in all_trades if t['side'] == 'long']
    short_trades = [t for t in all_trades if t['side'] == 'short']
    winning_trades = [t for t in all_trades if t['pnl'] > 0]
    losing_trades = [t for t in all_trades if t['pnl'] <= 0]

    win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0

    print(f"Total Trades: {num_trades}")
    print(f"  - Long Trades:  {len(long_trades)}")
    print(f"  - Short Trades: {len(short_trades)}")
    print(f"\nWin Rate: {win_rate:.2f}%")
    print(f"  - Winning Trades: {len(winning_trades)}")
    print(f"  - Losing Trades:  {len(losing_trades)}")
    print(f"\nAverage Win:  ${avg_win:,.2f}")
    print(f"Average Loss: ${avg_loss:,.2f}")
    if avg_loss != 0:
      print(f"Win/Loss Ratio: {abs(avg_win/avg_loss):.2f}")
    print("-" * 60)

    # Per-side breakdown
    if long_trades:
      long_wins = [t for t in long_trades if t['pnl'] > 0]
      long_pnl = sum(t['pnl'] for t in long_trades)
      long_win_rate = (len(long_wins) / len(long_trades)) * 100
      print(f"\nLong Trades Summary:")
      print(f"  Total: {len(long_trades)}")
      print(f"  Win Rate: {long_win_rate:.2f}%")
      print(f"  Total P&L: ${long_pnl:,.2f}")

    if short_trades:
      short_wins = [t for t in short_trades if t['pnl'] > 0]
      short_pnl = sum(t['pnl'] for t in short_trades)
      short_win_rate = (len(short_wins) / len(short_trades)) * 100
      print(f"\nShort Trades Summary:")
      print(f"  Total: {len(short_trades)}")
      print(f"  Win Rate: {short_win_rate:.2f}%")
      print(f"  Total P&L: ${short_pnl:,.2f}")

    print("-" * 60)

  # Generate and save plots
  plot_dir = os.path.join(project_root, 'backtesting', 'turtle_long_short_plots')
  os.makedirs(plot_dir, exist_ok=True)

  if cash_history:
    dates, cash_values = zip(*cash_history)
    min_cash = min(cash_values)
    max_cash = max(cash_values)

    # Validate no negative cash
    if min_cash < 0:
      print(f"\n⚠️ WARNING: Found negative cash values! Min: ${min_cash:,.2f}")
      negative_count = sum(1 for v in cash_values if v < 0)
      print(f"  Number of negative entries: {negative_count}")

    plt.figure(figsize=(14, 7))
    plt.plot(dates, cash_values, linewidth=2, color='green')
    plt.axhline(y=total_initial_equity, color='r', linestyle='--', label='Initial Equity')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=1.0, alpha=0.7)  # Zero line
    plt.title('Cash Over Time', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Cash ($)')

    # Force y-axis to never go below 0
    current_ylim = plt.ylim()
    plt.ylim(bottom=0, top=current_ylim[1])

    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(plot_dir, 'cash_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()  # Close the figure to free memory
    print(f"\nCash over time saved to: {plot_path}")
    print(f"  Min cash: ${min_cash:,.2f}, Max cash: ${max_cash:,.2f}")

  if equity_history:
    dates, equity_values = zip(*equity_history)
    plt.figure(figsize=(14, 7))
    plt.plot(dates, equity_values, linewidth=2)
    plt.axhline(y=total_initial_equity, color='r', linestyle='--', label='Initial Equity')
    plt.title('Total Equity Over Time (Long + Short)', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Total Equity ($)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(plot_dir, 'equity_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\nEquity curve saved to: {plot_path}")

  if net_unit_history:
    dates, net_units = zip(*net_unit_history)
    _, long_units = zip(*long_unit_history)
    _, short_units = zip(*short_unit_history)

    plt.figure(figsize=(14, 7))
    plt.plot(dates, long_units, label='Long Units', color='green', alpha=0.7)
    plt.plot(dates, short_units, label='Short Units', color='red', alpha=0.7)
    plt.plot(dates, net_units, label='Net Units (Long - Short)', color='blue', linewidth=2)
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.title('Position Units Over Time', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Units')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(plot_dir, 'units_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Units chart saved to: {plot_path}")

  print("\nBacktest complete!")
