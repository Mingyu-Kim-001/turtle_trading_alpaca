"""
Unified Turtle Trading Backtester for Long-Only and Long-Short Strategies

This script runs either a long-only or a long-short Turtle Trading backtest based on the
command-line arguments provided.
"""

import pandas as pd
import numpy as np
import sys
import os
import argparse
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from system_long.core.indicators import IndicatorCalculator

# --- Long-Only Backtester Class ---
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
    df = IndicatorCalculator.calculate_atr(df, period=20)
    df = IndicatorCalculator.calculate_donchian_channels(df, entry_period=20, exit_period=10)
    return df

  def _get_unit_size(self, total_equity, n_value):
    if n_value == 0 or total_equity <= 0:
      return 0
    unit_risk = total_equity * self.risk_per_unit_pct
    unit_size = unit_risk / n_value
    return unit_size

  def _calculate_total_equity(self, processed_data, date):
    market_value = 0
    for ticker, position in self.positions.items():
        if date in processed_data[ticker].index:
            prev_close = processed_data[ticker].loc[date]['close']
            market_value += position['units'] * prev_close
    return self.cash + market_value

  def run(self, all_data):
    processed_data = {ticker: self._calculate_indicators(df.copy()) for ticker, df in all_data.items()}
    all_dates = sorted(list(set(date for df in processed_data.values() for date in df.index)))

    for i in range(1, len(all_dates)):
      today_date = all_dates[i]
      yesterday_date = all_dates[i-1]
      total_equity = self._calculate_total_equity(processed_data, yesterday_date)

      for ticker, df in processed_data.items():
        if today_date not in df.index or yesterday_date not in df.index: continue
        if ticker in self.positions:
          today, yesterday = df.loc[today_date], df.loc[yesterday_date]
          position = self.positions[ticker]
          exit_signal, exit_reason = False, ''
          if today['low'] <= position['stop_price']:
            exit_price, exit_signal, exit_reason = position['stop_price'], True, 'Stop-loss'
          elif today['close'] < yesterday['low_10']:
            exit_price, exit_signal, exit_reason = today['close'], True, '10-day low'
          if exit_signal:
            self._close_position(ticker, exit_price, today_date, exit_reason)

      for ticker, df in processed_data.items():
        if today_date not in df.index: continue
        if ticker in self.positions:
            self._check_pyramiding(ticker, df.loc[today_date], total_equity)

      for ticker, df in processed_data.items():
        if today_date not in df.index or yesterday_date not in df.index: continue
        if ticker not in self.positions:
            today, yesterday = df.loc[today_date], df.loc[yesterday_date]
            if today['high'] > yesterday['high_20']:
                if not self.last_trade_was_win.get(ticker, False):
                    self._open_position(ticker, yesterday['high_20'], today['N'], total_equity, today_date)
                elif today['low'] < yesterday['low_20']:
                    self.last_trade_was_win[ticker] = False
      
      current_total_equity = self._calculate_total_equity(processed_data, today_date)
      self.cash_history.append((today_date, self.cash))
      self.equity_history.append((today_date, current_total_equity))
      self.unit_history.append((today_date, sum(p['pyramid_count'] for p in self.positions.values())))

    final_equity = self._calculate_total_equity(processed_data, all_dates[-1])
    return final_equity, self.trades, self.cash, self.cash_history, self.equity_history, self.unit_history

  def _open_position(self, ticker, entry_price, n_value, total_equity, today_date):
    if self.cash <= 0: return
    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0: return
    cost = unit_size * entry_price
    if self.cash < cost: return

    self.cash -= cost
    self.positions[ticker] = {
      'units': unit_size, 'entry_price': entry_price, 'entry_date': today_date,
      'stop_price': entry_price - 2 * n_value, 'n_value': n_value, 'pyramid_count': 1
    }

  def _close_position(self, ticker, exit_price, today_date, exit_reason):
    position = self.positions.pop(ticker)
    pnl = position['units'] * (exit_price - position['entry_price'])
    self.cash += position['units'] * exit_price
    self.trades.append({
      'ticker': ticker, 'entry_date': position['entry_date'], 'exit_date': today_date,
      'entry_price': position['entry_price'], 'exit_price': exit_price, 'pnl': pnl,
      'pyramid_count': position['pyramid_count'], 'exit_reason': exit_reason
    })
    self.last_trade_was_win[ticker] = pnl > 0

  def _check_pyramiding(self, ticker, today, total_equity):
    if self.cash <= 0: return
    position = self.positions[ticker]
    if position['pyramid_count'] < 4:
      pyramid_price = position['entry_price'] + 0.5 * position['n_value']
      if today['high'] >= pyramid_price:
        unit_size = self._get_unit_size(total_equity, position['n_value'])
        if unit_size > 0:
            cost = unit_size * pyramid_price
            if self.cash < cost: return
            self.cash -= cost
            position['units'] += unit_size
            position['entry_price'] = (position['entry_price'] * (position['units'] - unit_size) + pyramid_price * unit_size) / position['units']
            position['pyramid_count'] += 1
            position['stop_price'] = pyramid_price - 2 * position['n_value']

# --- Long-Short Backtester Class ---
class TurtleLongShortBacktester:
  def __init__(self, initial_equity=10_000, risk_per_unit_pct=0.01, max_positions=10,
               enable_shorts=True, check_shortability=False, shortable_tickers=None,
               enable_logging=True):
    self.initial_equity = initial_equity
    self.cash = initial_equity
    self.risk_per_unit_pct = risk_per_unit_pct
    self.max_positions = max_positions
    self.enable_shorts = enable_shorts
    self.check_shortability = check_shortability
    self.shortable_tickers = shortable_tickers or set()
    self.enable_logging = enable_logging
    self.long_positions, self.short_positions, self.trades, self.last_trade_was_win = {}, {}, [], {}
    self.cash_history, self.equity_history, self.long_unit_history, self.short_unit_history, self.net_unit_history = [], [], [], [], []

  def _calculate_indicators(self, df):
    df = IndicatorCalculator.calculate_atr(df, period=20)
    df = IndicatorCalculator.calculate_donchian_channels(df, entry_period=20, exit_period=10)
    return df

  def _get_unit_size(self, total_equity, n_value):
    if n_value == 0 or total_equity <= 0:
      return 0
    unit_risk = total_equity * self.risk_per_unit_pct
    unit_size = unit_risk / n_value
    return unit_size

  def _calculate_total_equity(self, processed_data, date):
    market_value = 0
    for ticker, position in self.long_positions.items():
      if date in processed_data[ticker].index:
        market_value += position['units'] * processed_data[ticker].loc[date]['close']
    for ticker, position in self.short_positions.items():
      if date in processed_data[ticker].index:
        market_value += position['units'] * (position['entry_price'] - processed_data[ticker].loc[date]['close'])
    return self.cash + market_value

  def _is_shortable(self, ticker):
    if not self.enable_shorts: return False
    if not self.check_shortability: return True
    return ticker in self.shortable_tickers

  def _total_position_count(self):
    return len(self.long_positions) + len(self.short_positions)

  def run(self, all_data):
    processed_data = {ticker: self._calculate_indicators(df.copy()) for ticker, df in all_data.items()}
    all_dates = sorted(list(set(date for df in processed_data.values() for date in df.index)))

    for i in range(1, len(all_dates)):
      today_date, yesterday_date = all_dates[i], all_dates[i-1]
      total_equity = self._calculate_total_equity(processed_data, yesterday_date)
      self._process_exits(processed_data, today_date, yesterday_date)
      self._process_pyramiding(processed_data, today_date, yesterday_date, total_equity)
      self._process_entries(processed_data, today_date, yesterday_date, total_equity)
      
      current_total_equity = self._calculate_total_equity(processed_data, today_date)

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
    return (final_equity, self.trades, self.cash, self.cash_history, self.equity_history,
            self.long_unit_history, self.short_unit_history, self.net_unit_history)

  def _process_exits(self, processed_data, today_date, yesterday_date):
    for ticker in list(self.long_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index or yesterday_date not in df.index: continue
      today, yesterday, position = df.loc[today_date], df.loc[yesterday_date], self.long_positions[ticker]
      exit_price, exit_reason = (position['stop_price'], 'Stop-loss') if today['low'] <= position['stop_price'] else (today['close'], '10-day low') if today['close'] < yesterday['low_10'] else (None, None)
      if exit_price: self._close_long_position(ticker, exit_price, today_date, exit_reason)

    for ticker in list(self.short_positions.keys()):
      df = processed_data[ticker]
      if today_date not in df.index or yesterday_date not in df.index: continue
      today, yesterday, position = df.loc[today_date], df.loc[yesterday_date], self.short_positions[ticker]
      exit_price, exit_reason = (position['stop_price'], 'Stop-loss') if today['high'] >= position['stop_price'] else (today['close'], '10-day high') if today['close'] > yesterday['high_10'] else (None, None)
      if exit_price: self._close_short_position(ticker, exit_price, today_date, exit_reason)

  def _process_pyramiding(self, processed_data, today_date, yesterday_date, total_equity):
    for ticker in list(self.long_positions.keys()):
      if today_date in processed_data[ticker].index: self._check_long_pyramiding(ticker, processed_data[ticker].loc[today_date], total_equity)
    for ticker in list(self.short_positions.keys()):
      if today_date in processed_data[ticker].index: self._check_short_pyramiding(ticker, processed_data[ticker].loc[today_date], total_equity)

  def _process_entries(self, processed_data, today_date, yesterday_date, total_equity):
    for ticker, df in processed_data.items():
      if today_date not in df.index or yesterday_date not in df.index: continue
      if ticker in self.long_positions or ticker in self.short_positions: continue
      if self._total_position_count() >= self.max_positions: continue
      today, yesterday = df.loc[today_date], df.loc[yesterday_date]
      if today['high'] > yesterday['high_20']:
        if not self.last_trade_was_win.get((ticker, 'long'), False):
          self._open_long_position(ticker, yesterday['high_20'], today['N'], total_equity, today_date)
        elif today['low'] < yesterday['low_20']:
          self.last_trade_was_win[(ticker, 'long')] = False
      if self._is_shortable(ticker) and today['low'] < yesterday['low_20']:
        if not self.last_trade_was_win.get((ticker, 'short'), False):
          self._open_short_position(ticker, yesterday['low_20'], today['N'], total_equity, today_date)
        elif today['high'] > yesterday['high_20']:
          self.last_trade_was_win[(ticker, 'short')] = False

  def _open_long_position(self, ticker, entry_price, n_value, total_equity, today_date):
    if self.cash <= 0: return
    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0: return
    cost = unit_size * entry_price
    if self.cash < cost: return
    self.cash -= cost
    self.long_positions[ticker] = {
      'units': unit_size, 'entry_price': entry_price, 'entry_date': today_date,
      'stop_price': entry_price - 2 * n_value, 'n_value': n_value, 'pyramid_count': 1, 'side': 'long'
    }

  def _close_long_position(self, ticker, exit_price, today_date, exit_reason):
    position = self.long_positions.pop(ticker)
    pnl = position['units'] * (exit_price - position['entry_price'])
    self.cash += position['units'] * exit_price
    self.trades.append({
        'ticker': ticker, 'side': 'long', 'entry_date': position['entry_date'], 'exit_date': today_date,
        'entry_price': position['entry_price'], 'exit_price': exit_price, 'pnl': pnl,
        'pyramid_count': position['pyramid_count'], 'exit_reason': exit_reason
    })
    self.last_trade_was_win[(ticker, 'long')] = pnl > 0

  def _check_long_pyramiding(self, ticker, today, total_equity):
    if self.cash <= 0: return
    position = self.long_positions[ticker]
    if position['pyramid_count'] >= 4: return
    pyramid_price = position['entry_price'] + 0.5 * position['n_value']
    if today['high'] >= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        cost = unit_size * pyramid_price
        if self.cash < cost: return
        self.cash -= cost
        old_units, position['units'] = position['units'], position['units'] + unit_size
        position['entry_price'] = (position['entry_price'] * old_units + pyramid_price * unit_size) / position['units']
        position['pyramid_count'] += 1
        position['stop_price'] = pyramid_price - 2 * position['n_value']

  def _open_short_position(self, ticker, entry_price, n_value, total_equity, today_date):
    if self.cash <= 0: return
    unit_size = self._get_unit_size(total_equity, n_value)
    if unit_size == 0: return
    margin_required = (unit_size * entry_price) * 0.5
    if self.cash < margin_required: return
    self.cash -= margin_required
    self.short_positions[ticker] = {
      'units': unit_size, 'entry_price': entry_price, 'entry_date': today_date,
      'stop_price': entry_price + 2 * n_value, 'n_value': n_value, 'pyramid_count': 1, 'side': 'short'
    }

  def _close_short_position(self, ticker, exit_price, today_date, exit_reason):
    position = self.short_positions.pop(ticker)
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
    self.trades.append({
        'ticker': ticker, 'side': 'short', 'entry_date': position['entry_date'], 'exit_date': today_date,
        'entry_price': position['entry_price'], 'exit_price': exit_price, 'pnl': pnl,
        'pyramid_count': position['pyramid_count'], 'exit_reason': exit_reason
    })
    self.last_trade_was_win[(ticker, 'short')] = pnl > 0

  def _check_short_pyramiding(self, ticker, today, total_equity):
    if self.cash <= 0: return
    position = self.short_positions[ticker]
    if position['pyramid_count'] >= 4: return
    pyramid_price = position['entry_price'] - 0.5 * position['n_value']
    if today['low'] <= pyramid_price:
      unit_size = self._get_unit_size(total_equity, position['n_value'])
      if unit_size > 0:
        margin_required = (unit_size * pyramid_price) * 0.5
        if self.cash < margin_required: return
        self.cash -= margin_required
        old_units, position['units'] = position['units'], position['units'] + unit_size
        position['entry_price'] = (position['entry_price'] * old_units + pyramid_price * unit_size) / position['units']
        position['pyramid_count'] += 1
        position['stop_price'] = pyramid_price + 2 * position['n_value']

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Unified Turtle Trading Backtester.")
  parser.add_argument('--mode', type=str, choices=['long', 'long_short'], default='long_short',
                      help='Strategy mode: "long" for long-only, "long_short" for long and short.')
  parser.add_argument('--log', action='store_true', help='Enable detailed trade logging.')
  args = parser.parse_args()

  # --- Data Loading ---
  data_dir = os.path.join(project_root, "data/alpaca_daily")
  all_files = sorted([f for f in os.listdir(data_dir) if f.endswith('_alpaca_daily.csv')])
  all_data = { f.split('_')[0]: pd.read_csv(os.path.join(data_dir, f), index_col='timestamp', parse_dates=True) for f in all_files }
  print(f"Loaded data for {len(all_data)} tickers")

  # --- Backtest Execution ---
  if args.mode == 'long':
      backtester = TurtleBacktester(enable_logging=args.log)
      final_equity, all_trades, final_cash, cash_history, equity_history, unit_history = backtester.run(all_data)
  else:
      backtester = TurtleLongShortBacktester(enable_logging=args.log)
      (final_equity, all_trades, final_cash, cash_history, equity_history,
       long_unit_history, short_unit_history, net_unit_history) = backtester.run(all_data)

  # --- Reporting ---
  print(f"\n{'='*60}\nBACKTEST SUMMARY (Mode: {args.mode})\n{'='*60}")
  initial_equity = backtester.initial_equity
  pnl = final_equity - initial_equity
  pnl_pct = (pnl / initial_equity) * 100 if initial_equity > 0 else 0
  print(f"Initial Equity: ${initial_equity:,.2f}")
  print(f"Final Equity:   ${final_equity:,.2f}")
  print(f"Total PnL:      ${pnl:,.2f} ({pnl_pct:.2f}%)")
  print(f"Final Cash:     ${final_cash:,.2f}")
  print("-" * 60)

  # --- Plotting ---
  plot_dir = os.path.join(project_root, 'backtesting', 'unified_backtester_plots')
  os.makedirs(plot_dir, exist_ok=True)
  mode_str = "long_short" if args.mode == 'long_short' else "long_only"

  if equity_history:
      dates, values = zip(*equity_history)
      plt.figure(figsize=(14, 7))
      plt.plot(dates, values)
      plt.title(f'Equity Over Time ({mode_str})')
      plt.ylabel('Equity ($)')
      plt.grid(True, alpha=0.3)
      plt.savefig(os.path.join(plot_dir, f'equity_{mode_str}.png'))
      plt.close()
      print(f"Equity plot saved to {plot_dir}/equity_{mode_str}.png")

  print("\nBacktest complete!")
