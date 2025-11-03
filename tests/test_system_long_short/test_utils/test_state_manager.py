"""Tests for StateManager for the long-short system"""

import unittest
import os
import tempfile
from system_long_short.utils.state_manager import StateManager


class TestStateManagerLongShort(unittest.TestCase):
  """Test cases for StateManager class in the long-short system"""

  def setUp(self):
    """Set up test fixtures"""
    fd, self.state_file = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    os.remove(self.state_file)

  def tearDown(self):
    """Clean up test fixtures"""
    if os.path.exists(self.state_file):
      os.remove(self.state_file)

  def test_initialization_with_no_file(self):
    """Test initialization when no state file exists in the long-short system"""
    state = StateManager(state_file=self.state_file)
    self.assertEqual(state.long_positions, {})
    self.assertEqual(state.short_positions, {})
    self.assertEqual(state.entry_queue, [])
    self.assertEqual(state.pending_pyramid_orders, {})
    self.assertEqual(state.pending_entry_orders, {})

  def test_save_and_load_state(self):
    """Test saving and loading state with both long and short positions"""
    state1 = StateManager(state_file=self.state_file)
    state1.long_positions = {'AAPL': {'units': 100, 'side': 'long'}}
    state1.short_positions = {'TSLA': {'units': 50, 'side': 'short'}}
    state1.entry_queue = [{'ticker': 'MSFT', 'side': 'long'}]
    state1.save_state()

    # Load in new instance
    state2 = StateManager(state_file=self.state_file)

    self.assertEqual(state2.long_positions, {'AAPL': {'units': 100, 'side': 'long'}})
    self.assertEqual(state2.short_positions, {'TSLA': {'units': 50, 'side': 'short'}})
    self.assertEqual(len(state2.entry_queue), 1)
    self.assertEqual(state2.entry_queue[0]['ticker'], 'MSFT')

  def test_state_persistence(self):
    """Test that state persists correctly for both position types"""
    # Create and modify state
    state1 = StateManager(state_file=self.state_file)
    state1.long_positions = {
      'AAPL': {'units': 50, 'entry': 150, 'side': 'long'},
      'GOOGL': {'units': 10, 'entry': 2800, 'side': 'long'}
    }
    state1.short_positions = {
      'TSLA': {'units': 30, 'entry': 250, 'side': 'short'},
      'NVDA': {'units': 20, 'entry': 500, 'side': 'short'}
    }
    state1.save_state()

    # Load in new instance and verify
    state2 = StateManager(state_file=self.state_file)
    self.assertEqual(len(state2.long_positions), 2)
    self.assertEqual(len(state2.short_positions), 2)
    self.assertIn('AAPL', state2.long_positions)
    self.assertIn('GOOGL', state2.long_positions)
    self.assertIn('TSLA', state2.short_positions)
    self.assertIn('NVDA', state2.short_positions)


if __name__ == '__main__':
  unittest.main()
