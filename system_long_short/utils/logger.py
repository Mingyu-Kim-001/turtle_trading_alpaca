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
    self.log_file = os.path.join(log_dir, f'trading_{self.today}.log')
    self.order_log_file = os.path.join(log_dir, f'orders_{self.today}.json')
    self.state_log_file = os.path.join(log_dir, f'state_{self.today}.json')
    self.orders = []
    self.state_snapshots = []

  def log(self, message, level='INFO'):
    """Log a message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}\n"

    print(log_line.strip())

    with open(self.log_file, 'a') as f:
      f.write(log_line)

  def log_order(self, order_type, ticker, status, details):
    """Log order details"""
    order_entry = {
      'timestamp': datetime.now().isoformat(),
      'type': order_type,
      'ticker': ticker,
      'status': status,
      'details': details
    }
    self.orders.append(order_entry)

    # Save to file
    with open(self.order_log_file, 'w') as f:
      json.dump(self.orders, f, indent=2)

  def log_state_snapshot(self, state, label='snapshot'):
    """Log a snapshot of trading state for long-short system"""
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
    with open(self.state_log_file, 'w') as f:
      json.dump(self.state_snapshots, f, indent=2)

    self.log(f"State snapshot saved: {label} (pending_pyramids={len(state.pending_pyramid_orders)}, pending_entries={len(state.pending_entry_orders)})")

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
