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

    # Load existing orders from today's log file if it exists
    self._load_existing_orders()
    self._load_existing_snapshots()

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
      # Load existing data for the new day if available
      self._load_existing_orders()
      self._load_existing_snapshots()

  def _load_existing_orders(self):
    """Load existing orders from today's JSON file if it exists"""
    order_log_file = self._get_log_files()['order_log_file']
    if os.path.exists(order_log_file):
      try:
        with open(order_log_file, 'r') as f:
          self.orders = json.load(f)
      except (json.JSONDecodeError, IOError):
        # If file is corrupted or empty, start fresh
        self.orders = []

  def _load_existing_snapshots(self):
    """Load existing state snapshots from today's JSON file if it exists"""
    state_log_file = self._get_log_files()['state_log_file']
    if os.path.exists(state_log_file):
      try:
        with open(state_log_file, 'r') as f:
          self.state_snapshots = json.load(f)
      except (json.JSONDecodeError, IOError):
        # If file is corrupted or empty, start fresh
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

  def log_state_snapshot(self, state, label='snapshot', equity=None):
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

    # Store equity if provided (useful for market_open to track starting equity)
    if equity is not None:
      snapshot['equity'] = equity

    self.state_snapshots.append(snapshot)

    # Save to file
    state_log_file = self._get_log_files()['state_log_file']
    with open(state_log_file, 'w') as f:
      json.dump(self.state_snapshots, f, indent=2)

    self.log(f"State snapshot saved: {label} (pending_pyramids={len(state.pending_pyramid_orders)}, pending_entries={len(state.pending_entry_orders)}, pending_exits={len(getattr(state, 'pending_exit_orders', {}))})")

  def get_daily_orders(self):
    """Get all orders logged today"""
    return self.orders

  def log_pyramid_trigger(self, ticker, side, level, trigger_price, current_price, last_entry_price, n_value,
                          initial_n=None, latest_n=None, use_latest_n=False):
    """
    Log pyramid trigger event for debugging

    Args:
      ticker: Ticker symbol
      side: 'LONG' or 'SHORT'
      level: Pyramid level (1-4)
      trigger_price: Price that triggered the pyramid
      current_price: Current market price
      last_entry_price: Last entry price
      n_value: N value used for calculation (could be initial_n or latest_n)
      initial_n: Initial N from first entry (optional)
      latest_n: Latest N from current data (optional)
      use_latest_n: Whether latest_n mode is active
    """
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

    # Build log message with N tracking info
    n_info = ""
    if initial_n is not None and latest_n is not None:
      n_mode = "latest_N" if use_latest_n else "initial_N"
      n_diff_pct = ((latest_n - initial_n) / initial_n * 100) if initial_n > 0 else 0
      n_info = f" | N: {n_value:.3f} ({n_mode}) [init={initial_n:.3f}, latest={latest_n:.3f}, Δ={n_diff_pct:+.1f}%]"
      log_entry['initial_n'] = initial_n
      log_entry['latest_n'] = latest_n
      log_entry['use_latest_n'] = use_latest_n
      log_entry['n_diff_pct'] = n_diff_pct

    self.log(f"PYRAMID TRIGGER: {ticker} {side} L{level} | "
         f"Current: ${current_price:.2f} | Last Entry: ${last_entry_price:.2f} | "
         f"Trigger: ${trigger_price:.2f} | Move: {log_entry['price_move_in_n']:.2f}N{n_info}")
