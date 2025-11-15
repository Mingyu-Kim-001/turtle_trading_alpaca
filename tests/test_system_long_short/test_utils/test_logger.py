"""Tests for DailyLogger for the long-short system"""

import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime
from system_long_short.utils.logger import DailyLogger


class TestDailyLoggerLongShort(unittest.TestCase):
  """Test cases for DailyLogger class in the long-short system"""

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
    """Test logging a message in the long-short system"""
    self.logger.log("Test message for long-short", "INFO")

    # Check log file was created
    log_file = self.logger._get_log_files()['log_file']
    self.assertTrue(os.path.exists(log_file))

    # Check log file contains message
    with open(log_file, 'r') as f:
      content = f.read()
      self.assertIn("Test message for long-short", content)
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
    order_log_file = self.logger._get_log_files()['order_log_file']
    self.assertTrue(os.path.exists(order_log_file))

    # Check order data
    with open(order_log_file, 'r') as f:
      data = json.load(f)
      self.assertEqual(len(data), 1)
      self.assertEqual(data[0]['type'], 'ENTRY')
      self.assertEqual(data[0]['ticker'], 'AAPL')
      self.assertEqual(data[0]['status'], 'FILLED')

  def test_log_state_snapshot(self):
    """Test logging a state snapshot for long-short system"""
    # Create mock state object with long and short positions
    class MockState:
      def __init__(self):
        self.long_positions = {'AAPL': {}}
        self.short_positions = {'TSLA': {}}
        self.entry_queue = []
        self.pending_pyramid_orders = {}
        self.pending_entry_orders = {}
        self.pending_exit_orders = {}

    state = MockState()
    self.logger.log_state_snapshot(state, 'test_snapshot')

    # Check snapshot was added
    self.assertEqual(len(self.logger.state_snapshots), 1)

    # Check snapshot file was created
    state_log_file = self.logger._get_log_files()['state_log_file']
    self.assertTrue(os.path.exists(state_log_file))

    # Check snapshot data
    with open(state_log_file, 'r') as f:
      data = json.load(f)
      self.assertEqual(len(data), 1)
      self.assertEqual(data[0]['label'], 'test_snapshot')
      self.assertEqual(data[0]['long_position_count'], 1)
      self.assertEqual(data[0]['short_position_count'], 1)
      self.assertEqual(data[0]['queue_count'], 0)

  def test_get_daily_orders(self):
    """Test retrieving daily orders"""
    # Log some orders
    self.logger.log_order('ENTRY', 'AAPL', 'FILLED', {})
    self.logger.log_order('EXIT', 'MSFT', 'PENDING', {})

    orders = self.logger.get_daily_orders()
    self.assertEqual(len(orders), 2)


if __name__ == '__main__':
  unittest.main()
