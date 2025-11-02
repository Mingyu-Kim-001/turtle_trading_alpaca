"""Tests for DailyLogger"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime
from system.utils.logger import DailyLogger


class TestDailyLogger(unittest.TestCase):
  """Test cases for DailyLogger class"""

  def setUp(self):
    """Set up test fixtures"""
    self.test_dir = tempfile.mkdtemp()
    self.logger = DailyLogger(log_dir=self.test_dir)

  def tearDown(self):
    """Clean up test fixtures"""
    shutil.rmtree(self.test_dir)

  def test_logger_initialization(self):
    """Test logger initializes correctly"""
    self.assertTrue(os.path.exists(self.test_dir))
    self.assertEqual(len(self.logger.orders), 0)
    self.assertEqual(len(self.logger.state_snapshots), 0)

  def test_log_message(self):
    """Test logging a message"""
    self.logger.log("Test message", "INFO")

    # Check log file was created
    self.assertTrue(os.path.exists(self.logger.log_file))

    # Check log file contains message
    with open(self.logger.log_file, 'r') as f:
      content = f.read()
      self.assertIn("Test message", content)
      self.assertIn("INFO", content)

  def test_log_order(self):
    """Test logging an order"""
    order_details = {
      'order_id': 'test123',
      'units': 100,
      'price': 150.50
    }

    self.logger.log_order('ENTRY', 'AAPL', 'FILLED', order_details)

    # Check order was added to list
    self.assertEqual(len(self.logger.orders), 1)

    # Check order file was created
    self.assertTrue(os.path.exists(self.logger.order_log_file))

    # Check order data
    with open(self.logger.order_log_file, 'r') as f:
      data = json.load(f)
      self.assertEqual(len(data), 1)
      self.assertEqual(data[0]['type'], 'ENTRY')
      self.assertEqual(data[0]['ticker'], 'AAPL')
      self.assertEqual(data[0]['status'], 'FILLED')

  def test_log_state_snapshot(self):
    """Test logging a state snapshot"""
    # Create mock state object
    class MockState:
      def __init__(self):
        self.risk_pot = 10000
        self.positions = {'AAPL': {}}
        self.entry_queue = []

    state = MockState()
    self.logger.log_state_snapshot(state, 'test_snapshot')

    # Check snapshot was added
    self.assertEqual(len(self.logger.state_snapshots), 1)

    # Check snapshot file was created
    self.assertTrue(os.path.exists(self.logger.state_log_file))

    # Check snapshot data
    with open(self.logger.state_log_file, 'r') as f:
      data = json.load(f)
      self.assertEqual(len(data), 1)
      self.assertEqual(data[0]['label'], 'test_snapshot')
      self.assertEqual(data[0]['risk_pot'], 10000)

  def test_get_daily_orders(self):
    """Test retrieving daily orders"""
    # Log some orders
    self.logger.log_order('ENTRY', 'AAPL', 'FILLED', {})
    self.logger.log_order('EXIT', 'MSFT', 'PENDING', {})

    orders = self.logger.get_daily_orders()
    self.assertEqual(len(orders), 2)


if __name__ == '__main__':
  unittest.main()
