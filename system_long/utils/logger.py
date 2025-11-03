"""Logging utilities for Turtle Trading System"""

import os
import json
from datetime import datetime


class DailyLogger:
  """Log daily trading activities"""

  def __init__(self, log_dir='logs/system_long'):
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
    """Log a snapshot of trading state"""
    snapshot = {
      'timestamp': datetime.now().isoformat(),
      'label': label,
      'positions': state.positions,
      'entry_queue': state.entry_queue,
      'position_count': len(state.positions),
      'queue_count': len(state.entry_queue)
    }
    self.state_snapshots.append(snapshot)

    # Save to file
    with open(self.state_log_file, 'w') as f:
      json.dump(self.state_snapshots, f, indent=2)

    self.log(f"State snapshot saved: {label}")

  def get_daily_orders(self):
    """Get all orders logged today"""
    return self.orders
