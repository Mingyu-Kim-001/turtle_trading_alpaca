"""State management for trading system with long and short positions"""

import json
from datetime import datetime


class StateManager:
  """Manage trading state persistence for long and short positions"""

  def __init__(self, state_file='system_long_short/trading_state_ls.json'):
    self.state_file = state_file
    self.load_state()

  def load_state(self):
    """Load state from file, handling empty or malformed JSON"""
    try:
        with open(self.state_file, 'r') as f:
            content = f.read()
            if not content:
                print("State file is empty, initializing new state")
                self._initialize_new_state()
                return

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                print("State file is malformed, initializing new state")
                self._initialize_new_state()
                return

            self.long_positions = data.get('long_positions', {})
            self.short_positions = data.get('short_positions', {})
            self.entry_queue = data.get('entry_queue', [])
            self.pending_pyramid_orders = data.get('pending_pyramid_orders', {})
            self.pending_entry_orders = data.get('pending_entry_orders', {})
            self.placing_marker_timestamps = data.get('placing_marker_timestamps', {})
            self.last_updated = data.get('last_updated', None)
            print(f"State loaded: long_positions={len(self.long_positions)}, "
                  f"short_positions={len(self.short_positions)}, "
                  f"pending_pyramids={len(self.pending_pyramid_orders)}, "
                  f"pending_entries={len(self.pending_entry_orders)}")

    except FileNotFoundError:
        print("No existing state found, initializing new state")
        self._initialize_new_state()

  def _initialize_new_state(self):
      """Initialize a new, empty state and save it"""
      self.long_positions = {}
      self.short_positions = {}
      self.entry_queue = []
      self.pending_pyramid_orders = {}
      self.pending_entry_orders = {}
      self.placing_marker_timestamps = {}  # Track PLACING marker timestamps for timeout
      self.last_updated = None
      self.save_state()

  def save_state(self):
    """Save state to file"""
    data = {
      'long_positions': self.long_positions,
      'short_positions': self.short_positions,
      'entry_queue': self.entry_queue,
      'pending_pyramid_orders': self.pending_pyramid_orders,
      'pending_entry_orders': self.pending_entry_orders,
      'placing_marker_timestamps': getattr(self, 'placing_marker_timestamps', {}),
      'last_updated': datetime.now().isoformat()
    }

    with open(self.state_file, 'w') as f:
      json.dump(data, f, indent=2)

    print(f"State saved at {datetime.now()}")
