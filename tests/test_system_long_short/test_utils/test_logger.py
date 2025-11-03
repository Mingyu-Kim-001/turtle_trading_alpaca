"""Tests for DailyLogger for the long-short system"""

import unittest
import os
import tempfile
import shutil
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

  def test_log_message(self):
    """Test logging a message in the long-short system"""
    self.logger.log("Test message for long-short", "INFO")
    self.assertTrue(os.path.exists(self.logger.log_file))
    with open(self.logger.log_file, 'r') as f:
      content = f.read()
      self.assertIn("Test message for long-short", content)


if __name__ == '__main__':
  unittest.main()
