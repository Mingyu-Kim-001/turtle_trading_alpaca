"""
Unified Turtle Trading Backtester

This backtester supports all combinations of:
- Long only / Short only / Long and Short
- System 1 only (20-10) / System 1 and System 2 (20-10 + 55-20)

System 1 (20-10): Entry on 20-day high/low, exit on 10-day low/high, stop at entry ± 2N
System 2 (55-20): Entry on 55-day high/low, exit on 20-day low/high, stop at entry ± 2N
- Pyramiding up to 4 units for both longs and shorts
- Position sizing based on risk per unit
- Each position tracks which system it belongs to for proper exit signals (when both systems enabled)

Entry Priority (when both systems enabled):
1. Pyramiding existing positions (highest priority)
2. System 2 (55-20) new entries
3. System 1 (20-10) new entries with random selection for variety across runs
"""

import pandas as pd
import numpy as np
import sys
import os
import json
import random
from typing import Dict, List, Tuple, Optional

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from system_long.core.indicators import IndicatorCalculator


class TurtleUnifiedBacktester:
  def __init__(self, initial_equity=10_000, risk_per_unit_pct=0.005, max_positions=100,
               enable_longs=True, enable_shorts=True,
               enable_system1=True, enable_system2=False,
               check_shortability=False, shortable_tickers=None,
               enable_logging=True):
    """
    Initialize the unified backtester

    Args:
      initial_equity: Starting capital
      risk_per_unit_pct: Risk per unit as % of equity (default 0.5%)
      max_positions: Maximum number of positions (long + short combined)
      enable_longs: Whether to enable long positions
      enable_shorts: Whether to enable short positions
      enable_system1: Whether to enable System 1 (20-10)
      enable_system2: Whether to enable System 2 (55-20)
      check_shortability: If True, only short tickers in shortable_tickers set
      shortable_tickers: Set of tickers that are shortable (None = all shortable)
      enable_logging: Whether to print exit logs
    """
    if not enable_longs and not enable_shorts:
      raise ValueError("At least one of enable_longs or enable_shorts must be True")
    if not enable_system1 and not enable_system2:
      raise ValueError("At least one of enable_system1 or enable_system2 must be True")
    
    self.initial_equity = initial_equity
    self.cash = initial_equity
    self.risk_per_unit_pct = risk_per_unit_pct
    self.max_positions = max_positions
    self.enable_longs = enable_longs
    self.enable_shorts = enable_shorts
    self.enable_system1 = enable_system1
    self.enable_system2 = enable_system2
    self.check_shortability = check_shortability
    self.shortable_tickers = shortable_tickers or set()
    self.enable_logging = enable_logging
    
    # Determine if we need to track systems (only when both systems are enabled)
    self.track_systems = enable_system1 and enable_system2

    # Create result directory and set up log file
    config_name = self._get_config_name()
    self.result_dir = os.path.join(os.path.dirname(__file__), f'turtle_unified_{config_name}_results')
    os.makedirs(self.result_dir, exist_ok=True)
    self.daily_log_file = os.path.join(self.result_dir, f'daily_backtest_log_{config_name}.jsonl')
    if os.path.exists(self.daily_log_file):
        os.remove(self.daily_log_file)

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

  def _get_config_name(self):
    """Generate a configuration name based on settings."""
    parts = []
    if self.enable_longs and self.enable_shorts:
      parts.append("long_short")
    elif self.enable_longs:
      parts.append("long_only")
    else:
      parts.append("short_only")
    
    if self.enable_system1 and self.enable_system2:
      parts.append("dual_system")
    elif self.enable_system1:
      parts.append("system1")
    else:
      parts.append("system2")
    
    return "_".join(parts)

  def _log_daily_report(self, date, equity, pnl, trades_this_day, processed_data, yesterday_date):
      """Logs a daily summary of state, P&L, and trades to a JSONL file."""
      # Build open positions with daily PnL and close price for each ticker
      long_positions_dict = {}
      for ticker, pos in self.long_positions.items():
          position_info = {
              "entry_date": pos['entry_date'].strftime('%Y-%m-%d'),
              "entry_price": round(pos['entry_price'], 2),
              "entry_n": round(pos['n_value'], 2),
              "pyramiding": pos['pyramid_count'],
              "units": round(pos['units'], 4)
          }
          # Add system info if tracking systems
          if self.track_systems:
              position_info["system"] = pos['system']
          
          # Get close price and calculate daily PnL
          if ticker in processed_data and date in processed_data[ticker].index:
              current_close = processed_data[ticker].loc[date]['close']
              position_info["close_price"] = round(current_close, 2)
              
              # Calculate daily PnL
              # If position was opened today, calculate from entry price to current close
              if pos['entry_date'] == date:
                  daily_pnl = (current_close - pos['entry_price']) * pos['units']
                  position_info["daily_pnl"] = round(daily_pnl, 2)
              elif yesterday_date in processed_data[ticker].index:
                  # Position opened before today, calculate from previous close to current close
                  previous_close = processed_data[ticker].loc[yesterday_date]['close']
                  daily_pnl = (current_close - previous_close) * pos['units']
                  position_info["daily_pnl"] = round(daily_pnl, 2)
              else:
                  # No previous data available
                  position_info["daily_pnl"] = 0.0
          else:
              position_info["close_price"] = None
              position_info["daily_pnl"] = 0.0
          
          long_positions_dict[ticker] = position_info
      
      short_positions_dict = {}
      for ticker, pos in self.short_positions.items():
          position_info = {
              "entry_date": pos['entry_date'].strftime('%Y-%m-%d'),
              "entry_price": round(pos['entry_price'], 2),
              "entry_n": round(pos['n_value'], 2),
              "pyramiding": pos['pyramid_count'],
              "units": round(pos['units'], 4)
          }
          # Add system info if tracking systems
          if self.track_systems:
              position_info["system"] = pos['system']
          
          # Get close price and calculate daily PnL
          if ticker in processed_data and date in processed_data[ticker].index:
              current_close = processed_data[ticker].loc[date]['close']
              position_info["close_price"] = round(current_close, 2)
              
              # Calculate daily PnL for shorts
              # If position was opened today, calculate from entry price to current close
              if pos['entry_date'] == date:
                  daily_pnl = (pos['entry_price'] - current_close) * pos['units']
                  position_info["daily_pnl"] = round(daily_pnl, 2)
              elif yesterday_date in processed_data[ticker].index:
                  # Position opened before today, calculate from previous close to current close
                  previous_close = processed_data[ticker].loc[yesterday_date]['close']
                  daily_pnl = (previous_close - current_close) * pos['units']
                  position_info["daily_pnl"] = round(daily_pnl, 2)
              else:
                  # No previous data available
                  position_info["daily_pnl"] = 0.0
          else:
              position_info["close_price"] = None
              position_info["daily_pnl"] = 0.0
          
          short_positions_dict[ticker] = position_info
      
      log_entry = {
          "date": date.strftime('%Y-%m-%d'),
          "equity": round(equity, 2),
          "cash": round(self.cash, 2),
          "daily_pnl": round(pnl, 2),
          "trades_today": trades_this_day,
          "open_positions": {
              "long": long_positions_dict,
              "short": short_positions_dict
          }
      }

      class CustomEncoder(json.JSONEncoder):
          def default(self, obj):
              if isinstance(obj, (np.integer, np.floating, np.bool_)):
                  return obj.item()
              if isinstance(obj, pd.Timestamp):
                  return obj.strftime('%Y-%m-%d')
              return super().default(obj)

      with open(self.daily_log_file, 'a') as f:
          f.write(json.dumps(log_entry, cls=CustomEncoder) + '\n')

  def _calculate_indicators(self, df):
    """Calculate all necessary indicators."""
    df = IndicatorCalculator.calculate_atr(df, period=20)
    # calculate_donchian_channels already calculates both 20-day and 55-day channels
    # It calculates high_20, low_20, high_10, low_10, high_55, low_55
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
    Short positions: margin_held + unrealized P&L

    Note: For shorts, margin was deducted from cash when opening the position.
    We need to add it back when calculating equity since it's still our money,
    just held as collateral.
    """
    market_value = 0

    # Value of long positions
    for ticker, position in self.long_positions.items():
      if date in processed_data[ticker].index:
        current_price = processed_data[ticker].loc[date]['close']
        market_value += position['units'] * current_price

    # Short positions: margin held + unrealized P&L
    for ticker, position in self.short_positions.items():
      if date in processed_data[ticker].index:
        current_price = processed_data[ticker].loc[date]['close']
        # Short unrealized P&L = units * (entry_price - current_price)
        unrealized_pnl = position['units'] * (position['entry_price'] - current_price)
        # Margin held as collateral (50% of position value at entry)
        margin_held = (position['units'] * position['entry_price']) * 0.5
        market_value += unrealized_pnl + margin_held

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

      total_equity_yesterday = self._calculate_total_equity(processed_data, yesterday_date)
      trades_today = []

      # 1. Process exits first to free up cash
      exit_trades = self._process_exits(processed_data, today_date, yesterday_date)
      trades_today.extend(exit_trades)

      # 2. Process pyramiding opportunities
      pyramid_trades = self._process_pyramiding(processed_data, today_date, yesterday_date, total_equity_yesterday)
      trades_today.extend(pyramid_trades)

      # 3. Process new entries
      entry_trades = self._process_entries(processed_data, today_date, yesterday_date, total_equity_yesterday)
      trades_today.extend(entry_trades)

      # Track history
      current_total_equity = self._calculate_total_equity(processed_data, today_date)
      daily_pnl = current_total_equity - total_equity_yesterday

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

      self._log_daily_report(today_date, current_total_equity, daily_pnl, trades_today, processed_data, yesterday_date)

    final_equity = self._calculate_total_equity(processed_data, all_dates[-1])
    return (final_equity, self.trades, self.cash,
            self.cash_history, self.equity_history,
            self.long_unit_history, self.short_unit_history, self.net_unit_history)

  def _process_exits(self, processed_data, today_date, yesterday_date):
    """Process exits for both long and short positions, respecting their system."""
    exit_trades = []

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
      else:
        # Use appropriate exit signal based on entry system
        if self.track_systems:
          if position['system'] == 1:
            # System 1: exit on 10-day low
            if today['close'] < yesterday['low_10']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '10-day low (S1)'
          elif position['system'] == 2:
            # System 2: exit on 20-day low
            if today['close'] < yesterday['low_20']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '20-day low (S2)'
        else:
          # Only one system enabled, use System 1 exit rules
          if self.enable_system1:
            if today['close'] < yesterday['low_10']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '10-day low'
          elif self.enable_system2:
            if today['close'] < yesterday['low_20']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '20-day low'

      if exit_signal:
        trade = self._close_long_position(ticker, exit_price, today_date, exit_reason)
        if trade:
            exit_trades.append(trade)

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
      else:
        # Use appropriate exit signal based on entry system
        if self.track_systems:
          if position['system'] == 1:
            # System 1: exit on 10-day high
            if today['close'] > yesterday['high_10']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '10-day high (S1)'
          elif position['system'] == 2:
            # System 2: exit on 20-day high
            if today['close'] > yesterday['high_20']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '20-day high (S2)'
        else:
          # Only one system enabled, use System 1 exit rules
          if self.enable_system1:
            if today['close'] > yesterday['high_10']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '10-day high'
          elif self.enable_system2:
            if today['close'] > yesterday['high_20']:
              exit_price = today['close']
              exit_signal = True
              exit_reason = '20-day high'

      if exit_signal:
        trade = self._close_short_position(ticker, exit_price, today_date, exit_reason)
        if trade:
            exit_trades.append(trade)
    
    return exit_trades

  def _process_pyramiding(self, processed_data, today_date, yesterday_date, total_equity):
    """Process pyramiding opportunities for both longs and shorts."""
    pyramid_trades = []

    # Pyramid long positions (on upward moves)
    if self.enable_longs:
      for ticker in list(self.long_positions.keys()):
        df = processed_data[ticker]
        if today_date not in df.index:
          continue
        today = df.loc[today_date]
        trade = self._check_long_pyramiding(ticker, today, total_equity)
        if trade:
            pyramid_trades.append(trade)

    # Pyramid short positions (on downward moves)
    if self.enable_shorts:
      for ticker in list(self.short_positions.keys()):
        df = processed_data[ticker]
        if today_date not in df.index:
          continue
        today = df.loc[today_date]
        trade = self._check_short_pyramiding(ticker, today, total_equity)
        if trade:
            pyramid_trades.append(trade)
    
    return pyramid_trades

  def _process_entries(self, processed_data, today_date, yesterday_date, total_equity):
    """
    Process new entry signals with priority:
    1. System 2 (55-20) entries first (if enabled)
    2. System 1 (20-10) entries with random selection (if enabled)
    """
    entry_trades = []

    # Collect all System 2 and System 1 candidates
    system2_candidates = []
    system1_candidates = []

    for ticker, df in processed_data.items():
      if today_date not in df.index or yesterday_date not in df.index:
        continue

      # Skip if already have a position in this ticker
      if ticker in self.long_positions or ticker in self.short_positions:
        continue

      today = df.loc[today_date]
      yesterday = df.loc[yesterday_date]

      # Check System 2 (55-day) entry signals
      if self.enable_system2:
        # Match original logic exactly: check long first, then short with elif
        # Original doesn't check enable_longs - always allows longs
        if today['high'] > yesterday['high_55']:
          # System 2 long entry (only add if longs enabled)
          if self.enable_longs:
            system2_candidates.append({
              'ticker': ticker,
              'side': 'long',
              'entry_price': yesterday['high_55'],
              'n_value': today['N'],
              'system': 2
            })
        elif self._is_shortable(ticker) and today['low'] < yesterday['low_55']:
          # System 2 short entry (only add if shorts enabled)
          if self.enable_shorts:
            system2_candidates.append({
              'ticker': ticker,
              'side': 'short',
              'entry_price': yesterday['low_55'],
              'n_value': today['N'],
              'system': 2
            })

      # Check System 1 (20-day) entry signals independently
      if self.enable_system1:
        # Match original logic exactly: check long first, then short with elif
        # Original doesn't check enable_longs - always allows longs
        if today['high'] > yesterday['high_20']:
          # System 1 long entry (only add if longs enabled)
          if self.enable_longs:
            if not self.last_trade_was_win.get((ticker, 'long', 1), False):
              # System 1 long entry candidate
              system1_candidates.append({
                'ticker': ticker,
                'side': 'long',
                'entry_price': yesterday['high_20'],
                'n_value': today['N'],
                'system': 1
              })
            else:
              # Reset win flag if price breaks below 20-day low
              if today['low'] < yesterday['low_20']:
                self.last_trade_was_win[(ticker, 'long', 1)] = False

        elif self._is_shortable(ticker) and today['low'] < yesterday['low_20']:
          # System 1 short entry (only add if shorts enabled)
          if self.enable_shorts:
            if not self.last_trade_was_win.get((ticker, 'short', 1), False):
              # System 1 short entry candidate
              system1_candidates.append({
                'ticker': ticker,
                'side': 'short',
                'entry_price': yesterday['low_20'],
                'n_value': today['N'],
                'system': 1
              })
            else:
              # Reset win flag if price breaks above 20-day high
              if today['high'] > yesterday['high_20']:
                self.last_trade_was_win[(ticker, 'short', 1)] = False

    # Process System 2 entries first
    for candidate in system2_candidates:
      if self._total_position_count() >= self.max_positions:
        break

      if candidate['side'] == 'long':
        trade = self._open_long_position(
          candidate['ticker'],
          candidate['entry_price'],
          candidate['n_value'],
          total_equity,
          today_date,
          system=candidate['system'] if self.track_systems else None
        )
      else:  # short
        trade = self._open_short_position(
          candidate['ticker'],
          candidate['entry_price'],
          candidate['n_value'],
          total_equity,
          today_date,
          system=candidate['system'] if self.track_systems else None
        )

      if trade:
        entry_trades.append(trade)

    # Randomize System 1 candidates for variety across runs
    random.shuffle(system1_candidates)

    # Process System 1 entries after System 2
    for candidate in system1_candidates:
      if self._total_position_count() >= self.max_positions:
        break

      if candidate['side'] == 'long':
        trade = self._open_long_position(
          candidate['ticker'],
          candidate['entry_price'],
          candidate['n_value'],
          total_equity,
          today_date,
          system=candidate['system'] if self.track_systems else None
        )
      else:  # short
        trade = self._open_short_position(
          candidate['ticker'],
          candidate['entry_price'],
          candidate['n_value'],
          total_equity,
          today_date,
          system=candidate['system'] if self.track_systems else None
        )

      if trade:
        entry_trades.append(trade)

    return entry_trades

  def _open_long_position(self, ticker, entry_price, n_value, total_equity, today_date, system=None):
    """Open a new long position."""
    # Check if ticker already has a position
    if ticker in self.long_positions or ticker in self.short_positions:
      return None

    if self.cash <= 0:
      return None

    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0:
      return None

    cost = unit_size * entry_price
    if self.cash < cost:
      return None

    stop_price = entry_price - 2 * n_value

    position_data = {
      'units': unit_size,
      'entry_price': entry_price,
      'entry_date': today_date,
      'stop_price': stop_price,
      'n_value': n_value,
      'pyramid_count': 1,
      'side': 'long'
    }
    
    # Track system if both systems are enabled (match original behavior)
    if self.track_systems:
      if system is not None:
        position_data['system'] = system
      else:
        # If track_systems is True but system is None, default to 1 (shouldn't happen)
        position_data['system'] = 1
    
    self.long_positions[ticker] = position_data
    self.cash -= cost

    # Safety check
    if self.cash < 0:
      raise ValueError(f"Cash went negative after opening long {ticker}: ${self.cash:.2f}")

    trade_data = {
        'ticker': ticker,
        'side': 'long',
        'action': 'entry',
        'price': entry_price,
        'units': unit_size,
        'stop_price': stop_price
    }
    
    if self.track_systems and system is not None:
      trade_data['system'] = system

    return trade_data

  def _close_long_position(self, ticker, exit_price, today_date, exit_reason):
    """Close a long position."""
    position = self.long_positions.pop(ticker)
    pnl = position['units'] * (exit_price - position['entry_price'])

    self.cash += position['units'] * exit_price

    # Log exit details
    if self.enable_logging:
      pnl_pct = (exit_price - position['entry_price']) / position['entry_price'] * 100
      duration = (today_date - position['entry_date']).days

      system_str = f" System {position.get('system', '')}" if self.track_systems else ""
      print(f"\n{'='*80}")
      print(f"EXIT LONG: {ticker} [{exit_reason}]{system_str}")
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

    trade = {
      'ticker': ticker,
      'side': 'long',
      'action': 'exit',
      'entry_date': position['entry_date'],
      'exit_date': today_date,
      'entry_price': position['entry_price'],
      'exit_price': exit_price,
      'pnl': pnl,
      'pyramid_count': position['pyramid_count'],
      'exit_reason': exit_reason
    }
    
    if self.track_systems and 'system' in position:
      trade['system'] = position['system']
    
    self.trades.append(trade)

    # Update win tracking for System 1 only
    if self.enable_system1:
      if self.track_systems:
        if position.get('system') == 1:
          self.last_trade_was_win[(ticker, 'long', 1)] = pnl > 0
      else:
        # Only System 1 enabled
        self.last_trade_was_win[(ticker, 'long', 1)] = pnl > 0
    
    return trade

  def _check_long_pyramiding(self, ticker, today, total_equity):
    """Check for long pyramiding opportunity (add on upward move)."""
    if self.cash <= 0:
      return None

    position = self.long_positions[ticker]
    if position['pyramid_count'] >= 4:
      return None

    # Pyramid trigger: last_entry + 0.5N
    pyramid_price = position['entry_price'] + 0.5 * position['n_value']

    if today['high'] >= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        cost = unit_size * pyramid_price
        if self.cash < cost:
          return None

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
        
        return {
            'ticker': ticker,
            'side': 'long',
            'action': 'pyramid',
            'price': pyramid_price,
            'units_added': unit_size,
            'new_total_units': position['units'],
            'new_pyramid_count': position['pyramid_count']
        }
    return None

  def _open_short_position(self, ticker, entry_price, n_value, total_equity, today_date, system=None):
    """Open a new short position."""
    # Check if ticker already has a position
    if ticker in self.long_positions or ticker in self.short_positions:
      return None

    if self.cash <= 0:
      return None

    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0:
      return None

    # For shorts, we need margin (use 50% of position value as simplified margin requirement)
    margin_required = (unit_size * entry_price) * 0.5
    if self.cash < margin_required:
      return None

    # Short stop is ABOVE entry (price rises)
    stop_price = entry_price + 2 * n_value

    position_data = {
      'units': unit_size,
      'entry_price': entry_price,
      'entry_date': today_date,
      'stop_price': stop_price,
      'n_value': n_value,
      'pyramid_count': 1,
      'side': 'short'
    }
    
    # Track system if both systems are enabled (match original behavior)
    if self.track_systems:
      if system is not None:
        position_data['system'] = system
      else:
        # If track_systems is True but system is None, default to 1 (shouldn't happen)
        position_data['system'] = 1

    self.short_positions[ticker] = position_data

    # Deduct margin from cash
    self.cash -= margin_required

    # Safety check
    if self.cash < 0:
      raise ValueError(f"Cash went negative after opening short {ticker}: ${self.cash:.2f}")

    trade_data = {
        'ticker': ticker,
        'side': 'short',
        'action': 'entry',
        'price': entry_price,
        'units': unit_size,
        'stop_price': stop_price
    }
    
    if self.track_systems and system is not None:
      trade_data['system'] = system

    return trade_data

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

      system_str = f" System {position.get('system', '')}" if self.track_systems else ""
      print(f"\n{'='*80}")
      print(f"EXIT SHORT: {ticker} [{exit_reason}]{system_str}")
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

    trade = {
      'ticker': ticker,
      'side': 'short',
      'action': 'exit',
      'entry_date': position['entry_date'],
      'exit_date': today_date,
      'entry_price': position['entry_price'],
      'exit_price': exit_price,
      'pnl': pnl,
      'pyramid_count': position['pyramid_count'],
      'exit_reason': exit_reason
    }
    
    if self.track_systems and 'system' in position:
      trade['system'] = position['system']
    
    self.trades.append(trade)

    # Update win tracking for System 1 only
    if self.enable_system1:
      if self.track_systems:
        if position.get('system') == 1:
          self.last_trade_was_win[(ticker, 'short', 1)] = pnl > 0
      else:
        # Only System 1 enabled
        self.last_trade_was_win[(ticker, 'short', 1)] = pnl > 0
    
    return trade

  def _check_short_pyramiding(self, ticker, today, total_equity):
    """Check for short pyramiding opportunity (add on downward move)."""
    if self.cash <= 0:
      return None

    position = self.short_positions[ticker]
    if position['pyramid_count'] >= 4:
      return None

    # Pyramid trigger for shorts: last_entry - 0.5N (price moves DOWN)
    pyramid_price = position['entry_price'] - 0.5 * position['n_value']

    if today['low'] <= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        margin_required = (unit_size * pyramid_price) * 0.5
        if self.cash < margin_required:
          return None

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

        return {
            'ticker': ticker,
            'side': 'short',
            'action': 'pyramid',
            'price': pyramid_price,
            'units_added': unit_size,
            'new_total_units': position['units'],
            'new_pyramid_count': position['pyramid_count']
        }
    return None


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
  import time
  import argparse

  # Parse command-line arguments
  parser = argparse.ArgumentParser(
    description='Turtle Trading Unified Backtester',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  # Run with default settings (long+short, dual system)
  python turtle_unified_backtester.py

  # Run long-only, system 1 only
  python turtle_unified_backtester.py --no-shorts --no-system2

  # Run with custom parameters
  python turtle_unified_backtester.py --initial-equity 20000 --risk-per-unit 0.01 --max-positions 50

  # Run with fixed seed for reproducibility
  python turtle_unified_backtester.py --seed 12345
    """
  )
  
  parser.add_argument('--initial-equity', type=float, default=10000,
                      help='Initial equity (default: 10000)')
  parser.add_argument('--risk-per-unit', type=float, default=0.005,
                      help='Risk per unit as percentage of equity (default: 0.005 = 0.5%%)')
  parser.add_argument('--max-positions', type=int, default=100,
                      help='Maximum number of positions (default: 100)')
  parser.add_argument('--seed', type=int, default=None,
                      help='Random seed for reproducibility (default: current timestamp)')
  
  # Boolean flags
  parser.add_argument('--no-longs', action='store_true',
                      help='Disable long positions (default: enabled)')
  parser.add_argument('--no-shorts', action='store_true',
                      help='Disable short positions (default: enabled)')
  parser.add_argument('--no-system1', action='store_true',
                      help='Disable System 1 (20-10) (default: enabled)')
  parser.add_argument('--no-system2', action='store_true',
                      help='Disable System 2 (55-20) (default: enabled)')
  parser.add_argument('--check-shortability', action='store_true',
                      help='Check Alpaca shortable list (default: False)')
  parser.add_argument('--enable-logging', action='store_true',
                      help='Enable detailed exit logging (default: False)')
  
  args = parser.parse_args()
  
  # Set random seed
  if args.seed is not None:
    random_seed = args.seed
  else:
    random_seed = int(time.time())
  random.seed(random_seed)
  print(f"Random seed for this run: {random_seed}")
  print(f"(Use this seed to reproduce exact results if needed)\n")

  # Configuration from arguments
  ENABLE_LONGS = not args.no_longs
  ENABLE_SHORTS = not args.no_shorts
  ENABLE_SYSTEM1 = not args.no_system1
  ENABLE_SYSTEM2 = not args.no_system2
  CHECK_SHORTABILITY = args.check_shortability

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
  backtester = TurtleUnifiedBacktester(
    initial_equity=args.initial_equity,
    risk_per_unit_pct=args.risk_per_unit,
    max_positions=args.max_positions,
    enable_longs=ENABLE_LONGS,
    enable_shorts=ENABLE_SHORTS,
    enable_system1=ENABLE_SYSTEM1,
    enable_system2=ENABLE_SYSTEM2,
    check_shortability=CHECK_SHORTABILITY,
    shortable_tickers=shortable_tickers,
    enable_logging=args.enable_logging
  )

  config_desc = []
  if ENABLE_LONGS and ENABLE_SHORTS:
    config_desc.append("Long + Short")
  elif ENABLE_LONGS:
    config_desc.append("Long Only")
  else:
    config_desc.append("Short Only")
  
  if ENABLE_SYSTEM1 and ENABLE_SYSTEM2:
    config_desc.append("Dual System (20-10 + 55-20)")
  elif ENABLE_SYSTEM1:
    config_desc.append("System 1 (20-10)")
  else:
    config_desc.append("System 2 (55-20)")

  print(f"\nRunning backtest: {' / '.join(config_desc)}...")
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

  print(f"Strategy: {' / '.join(config_desc)}")
  if ENABLE_SYSTEM1 and ENABLE_SYSTEM2:
    print(f"System 1: 20-day entry, 10-day exit")
    print(f"System 2: 55-day entry, 20-day exit")
    print(f"Entry Priority: Pyramiding > System 2 > System 1 (randomized)")
  elif ENABLE_SYSTEM1:
    print(f"System 1: 20-day entry, 10-day exit")
  else:
    print(f"System 2: 55-day entry, 20-day exit")
  print(f"Random Seed: {random_seed}")
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
    if ENABLE_SYSTEM1 and ENABLE_SYSTEM2:
      system1_trades = [t for t in all_trades if t.get('system') == 1]
      system2_trades = [t for t in all_trades if t.get('system') == 2]
      print(f"  - System 1 (20-10): {len(system1_trades)}")
      print(f"  - System 2 (55-20): {len(system2_trades)}")
    if ENABLE_LONGS:
      print(f"  - Long Trades:  {len(long_trades)}")
    if ENABLE_SHORTS:
      print(f"  - Short Trades: {len(short_trades)}")
    print(f"\nWin Rate: {win_rate:.2f}%")
    print(f"  - Winning Trades: {len(winning_trades)}")
    print(f"  - Losing Trades:  {len(losing_trades)}")
    print(f"\nAverage Win:  ${avg_win:,.2f}")
    print(f"Average Loss: ${avg_loss:,.2f}")
    if avg_loss != 0:
      print(f"Win/Loss Ratio: {abs(avg_win/avg_loss):.2f}")
    print("-" * 60)

  # Generate and save plots
  result_dir = backtester.result_dir
  os.makedirs(result_dir, exist_ok=True)

  if cash_history:
    dates, cash_values = zip(*cash_history)
    min_cash = min(cash_values)
    max_cash = max(cash_values)

    if min_cash < 0:
      print(f"\n⚠️ WARNING: Found negative cash values! Min: ${min_cash:,.2f}")
      negative_count = sum(1 for v in cash_values if v < 0)
      print(f"  Number of negative entries: {negative_count}")

    plt.figure(figsize=(14, 7))
    plt.plot(dates, cash_values, linewidth=2, color='green')
    plt.axhline(y=total_initial_equity, color='r', linestyle='--', label='Initial Equity')
    plt.axhline(y=0, color='black', linestyle='-', linewidth=1.0, alpha=0.7)
    plt.title(f'Cash Over Time ({"/ ".join(config_desc)})', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Cash ($)')
    plt.ylim(bottom=0)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(result_dir, 'cash_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nCash over time saved to: {plot_path}")
    print(f"  Min cash: ${min_cash:,.2f}, Max cash: ${max_cash:,.2f}")

  if equity_history:
    dates, equity_values = zip(*equity_history)
    plt.figure(figsize=(14, 7))
    plt.plot(dates, equity_values, linewidth=2)
    plt.axhline(y=total_initial_equity, color='r', linestyle='--', label='Initial Equity')
    plt.title(f'Total Equity Over Time ({"/ ".join(config_desc)})', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Total Equity ($)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(result_dir, 'equity_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nEquity curve saved to: {plot_path}")

  if net_unit_history:
    dates, net_units = zip(*net_unit_history)
    _, long_units = zip(*long_unit_history)
    _, short_units = zip(*short_unit_history)

    plt.figure(figsize=(14, 7))
    if ENABLE_LONGS:
      plt.plot(dates, long_units, label='Long Units', color='green', alpha=0.7)
    if ENABLE_SHORTS:
      plt.plot(dates, short_units, label='Short Units', color='red', alpha=0.7)
    if ENABLE_LONGS and ENABLE_SHORTS:
      plt.plot(dates, net_units, label='Net Units (Long - Short)', color='blue', linewidth=2)
    plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    plt.title(f'Position Units Over Time ({"/ ".join(config_desc)})', fontsize=14)
    plt.xlabel('Date')
    plt.ylabel('Units')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plot_path = os.path.join(result_dir, 'units_over_time.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Units chart saved to: {plot_path}")

  print("\nBacktest complete!")

