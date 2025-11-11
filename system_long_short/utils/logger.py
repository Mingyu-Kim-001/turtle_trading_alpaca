"""Logging utilities for Turtle Trading System"""

import os
import json
from datetime import datetime


class DailyLogger:
  """Log daily trading activities"""

  def __init__(self, log_dir='logs/system_long_short'):
    self.log_dir = log_dir
    os.makedirs(log_dir, exist_ok=True)
    self.today = datetime.now().strftime('%Y-%m-%d')
    self.orders = []
    self.state_snapshots = []

  def _get_log_files(self):
    """Get current log file paths based on today's date"""
    today = datetime.now().strftime('%Y-%m-%d')
    return {
      'log_file': os.path.join(self.log_dir, f'trading_{today}.log'),
      'order_log_file': os.path.join(self.log_dir, f'orders_{today}.json'),
      'state_log_file': os.path.join(self.log_dir, f'state_{today}.json')
    }

  def _check_date_rollover(self):
    """Check if date has changed and reset daily data if so"""
    today = datetime.now().strftime('%Y-%m-%d')
    if today != self.today:
      self.today = today
      self.orders = []
      self.state_snapshots = []

  def log(self, message, level='INFO'):
    """Log a message with timestamp"""
    self._check_date_rollover()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}\n"

    print(log_line.strip())

    log_file = self._get_log_files()['log_file']
    with open(log_file, 'a') as f:
      f.write(log_line)

  def log_order(self, order_type, ticker, status, details):
    """Log order details"""
    self._check_date_rollover()
    order_entry = {
      'timestamp': datetime.now().isoformat(),
      'type': order_type,
      'ticker': ticker,
      'status': status,
      'details': details
    }
    self.orders.append(order_entry)

    # Save to file
    order_log_file = self._get_log_files()['order_log_file']
    with open(order_log_file, 'w') as f:
      json.dump(self.orders, f, indent=2)

  def log_state_snapshot(self, state, label='snapshot'):
    """Log a snapshot of trading state for long-short system"""
    self._check_date_rollover()
    snapshot = {
      'timestamp': datetime.now().isoformat(),
      'label': label,
      'long_positions': state.long_positions,
      'short_positions': state.short_positions,
      'entry_queue': state.entry_queue,
      'pending_pyramid_orders': state.pending_pyramid_orders,
      'pending_entry_orders': state.pending_entry_orders,
      'long_position_count': len(state.long_positions),
      'short_position_count': len(state.short_positions),
      'queue_count': len(state.entry_queue),
      'pending_pyramid_count': len(state.pending_pyramid_orders),
      'pending_entry_count': len(state.pending_entry_orders)
    }
    self.state_snapshots.append(snapshot)

    # Save to file
    state_log_file = self._get_log_files()['state_log_file']
    with open(state_log_file, 'w') as f:
      json.dump(self.state_snapshots, f, indent=2)

    self.log(f"State snapshot saved: {label} (pending_pyramids={len(state.pending_pyramid_orders)}, pending_entries={len(state.pending_entry_orders)}, pending_exits={len(getattr(state, 'pending_exit_orders', {}))})")

  def get_daily_orders(self):
    """Get all orders logged today"""
    return self.orders

  def log_pyramid_trigger(self, ticker, side, level, trigger_price, current_price, last_entry_price, n_value):
    """Log pyramid trigger event for debugging"""
    log_entry = {
      'timestamp': datetime.now().isoformat(),
      'ticker': ticker,
      'side': side,
      'level': level,
      'trigger_price': trigger_price,
      'current_price': current_price,
      'last_entry_price': last_entry_price,
      'n_value': n_value,
      'price_move_in_n': (current_price - last_entry_price) / n_value if n_value > 0 else 0
    }

    self.log(f"PYRAMID TRIGGER: {ticker} {side} L{level} | "
         f"Current: ${current_price:.2f} | Last Entry: ${last_entry_price:.2f} | "
         f"Trigger: ${trigger_price:.2f} | Move: {log_entry['price_move_in_n']:.2f}N")
