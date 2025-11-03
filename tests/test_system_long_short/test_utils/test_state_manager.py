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


if __name__ == '__main__':
  unittest.main()
