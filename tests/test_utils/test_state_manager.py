"""Tests for StateManager"""

import unittest
import os
import json
import tempfile
from system.utils.state_manager import StateManager


class TestStateManager(unittest.TestCase):
  """Test cases for StateManager class"""

  def setUp(self):
    """Set up test fixtures"""
    # Create a temp file that doesn't exist yet (so StateManager will initialize it)
    fd, self.state_file = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    os.remove(self.state_file)  # Remove it so StateManager creates it fresh

  def tearDown(self):
    """Clean up test fixtures"""
    if os.path.exists(self.state_file):
      os.remove(self.state_file)

  def test_initialization_with_no_file(self):
    """Test initialization when no state file exists"""
    state = StateManager(state_file=self.state_file)

    self.assertEqual(state.positions, {})
    self.assertEqual(state.entry_queue, [])
    self.assertEqual(state.pending_pyramid_orders, {})
    self.assertEqual(state.pending_entry_orders, {})

  def test_save_and_load_state(self):
    """Test saving and loading state"""
    state1 = StateManager(state_file=self.state_file)
    state1.positions = {'AAPL': {'units': 100}}
    state1.entry_queue = [{'ticker': 'MSFT'}]
    state1.save_state()

    # Load in new instance
    state2 = StateManager(state_file=self.state_file)

    self.assertEqual(state2.positions, {'AAPL': {'units': 100}})
    self.assertEqual(len(state2.entry_queue), 1)

  def test_state_persistence(self):
    """Test that state persists correctly"""
    # Create and modify state
    state1 = StateManager(state_file=self.state_file)
    state1.positions = {
      'AAPL': {'units': 50, 'entry': 150},
      'GOOGL': {'units': 10, 'entry': 2800}
    }
    state1.save_state()

    # Load in new instance and verify
    state2 = StateManager(state_file=self.state_file)
    self.assertEqual(len(state2.positions), 2)
    self.assertIn('AAPL', state2.positions)
    self.assertIn('GOOGL', state2.positions)


if __name__ == '__main__':
  unittest.main()
