"""State management for trading system"""

import json
from datetime import datetime

# Default initial risk pot
_initial_risk_pot = 10000


class StateManager:
  """Manage trading state persistence"""

  def __init__(self, state_file='trading_state.json', initial_risk_pot=None):
    self.state_file = state_file
    self._initial_risk_pot = initial_risk_pot or _initial_risk_pot
    self.load_state()

  def load_state(self):
    """Load state from file"""
    try:
      with open(self.state_file, 'r') as f:
        data = json.load(f)
        self.risk_pot = data.get('risk_pot', self._initial_risk_pot)
        self.positions = data.get('positions', {})
        self.entry_queue = data.get('entry_queue', [])
        self.pending_pyramid_orders = data.get('pending_pyramid_orders', {})
        self.pending_entry_orders = data.get('pending_entry_orders', {})
        self.last_updated = data.get('last_updated', None)
        print(f"State loaded: risk_pot=${self.risk_pot:,.2f}, positions={len(self.positions)}, "
           f"pending_pyramids={len(self.pending_pyramid_orders)}, pending_entries={len(self.pending_entry_orders)}")
    except FileNotFoundError:
      print("No existing state found, initializing new state")
      self.risk_pot = self._initial_risk_pot
      self.positions = {}
      self.entry_queue = []
      self.pending_pyramid_orders = {}
      self.pending_entry_orders = {}
      self.last_updated = None
      self.save_state()

  def save_state(self):
    """Save state to file"""
    data = {
      'risk_pot': self.risk_pot,
      'positions': self.positions,
      'entry_queue': self.entry_queue,
      'pending_pyramid_orders': self.pending_pyramid_orders,
      'pending_entry_orders': self.pending_entry_orders,
      'last_updated': datetime.now().isoformat()
    }

    with open(self.state_file, 'w') as f:
      json.dump(data, f, indent=2)

    print(f"State saved at {datetime.now()}")

  def update_risk_pot(self, pnl):
    """Update risk pot after trade"""
    old_risk_pot = self.risk_pot
    self.risk_pot += pnl
    print(f"Risk pot updated: ${old_risk_pot:,.2f} -> ${self.risk_pot:,.2f} (PnL: ${pnl:,.2f})")
    self.save_state()
