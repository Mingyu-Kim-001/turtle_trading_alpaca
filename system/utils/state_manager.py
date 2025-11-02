"""State management for trading system"""

import json
from datetime import datetime


class StateManager:
  """Manage trading state persistence"""

  def __init__(self, state_file='trading_state.json'):
    self.state_file = state_file
    self.load_state()

  def load_state(self):
    """Load state from file"""
    try:
      with open(self.state_file, 'r') as f:
        data = json.load(f)
        self.positions = data.get('positions', {})
        self.entry_queue = data.get('entry_queue', [])
        self.pending_pyramid_orders = data.get('pending_pyramid_orders', {})
        self.pending_entry_orders = data.get('pending_entry_orders', {})
        self.last_updated = data.get('last_updated', None)
        print(f"State loaded: positions={len(self.positions)}, "
           f"pending_pyramids={len(self.pending_pyramid_orders)}, pending_entries={len(self.pending_entry_orders)}")
    except FileNotFoundError:
      print("No existing state found, initializing new state")
      self.positions = {}
      self.entry_queue = []
      self.pending_pyramid_orders = {}
      self.pending_entry_orders = {}
      self.last_updated = None
      self.save_state()

  def save_state(self):
    """Save state to file"""
    data = {
      'positions': self.positions,
      'entry_queue': self.entry_queue,
      'pending_pyramid_orders': self.pending_pyramid_orders,
      'pending_entry_orders': self.pending_entry_orders,
      'last_updated': datetime.now().isoformat()
    }

    with open(self.state_file, 'w') as f:
      json.dump(data, f, indent=2)

    print(f"State saved at {datetime.now()}")
