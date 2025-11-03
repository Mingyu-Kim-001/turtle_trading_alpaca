"""Tests for SignalGenerator for the long-short system"""

import unittest
import pandas as pd
import numpy as np
from system_long_short.core.signal_generator import SignalGenerator


class TestSignalGeneratorLongShort(unittest.TestCase):
  """Test cases for SignalGenerator class in the long-short system"""

  def setUp(self):
    """Set up test fixtures"""
    # Create sample data with indicators
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    self.df = pd.DataFrame({
      'open': np.linspace(100, 110, 100),
      'high': np.linspace(102, 112, 100),
      'low': np.linspace(98, 108, 100),
      'close': np.linspace(100, 110, 100),
      'N': np.full(100, 2.0),
      'high_20': np.linspace(101, 111, 100),
      'high_10': np.linspace(101.5, 111.5, 100),
      'low_10': np.linspace(99, 109, 100),
      'low_20': np.linspace(98, 108, 100)
    }, index=dates)

  # Long Entry Signal Tests
  def test_check_long_entry_signal_near_breakout(self):
    """Test long entry signal detection near breakout"""
    current_price = 110.5
    signal = SignalGenerator.check_long_entry_signal(self.df, current_price)

    self.assertIsNotNone(signal)
    self.assertIn('entry_price', signal)
    self.assertIn('n', signal)
    self.assertIn('proximity', signal)
    self.assertEqual(signal['side'], 'long')

  def test_check_long_entry_signal_far_from_breakout(self):
    """Test long entry signal when far from breakout"""
    current_price = 100.0
    signal = SignalGenerator.check_long_entry_signal(self.df, current_price)
    self.assertIsNone(signal)

  def test_check_long_entry_signal_above_breakout(self):
    """Test long entry signal when already above breakout"""
    current_price = 120.0
    signal = SignalGenerator.check_long_entry_signal(self.df, current_price)
    self.assertIsNone(signal)

  # Short Entry Signal Tests
  def test_check_short_entry_signal_near_breakdown(self):
    """Test short entry signal detection near breakdown"""
    # Price near 20-day low (last low_20 is 108)
    current_price = 107.5
    signal = SignalGenerator.check_short_entry_signal(self.df, current_price)

    self.assertIsNotNone(signal)
    self.assertIn('entry_price', signal)
    self.assertIn('n', signal)
    self.assertIn('proximity', signal)
    self.assertEqual(signal['side'], 'short')

  def test_check_short_entry_signal_far_from_breakdown(self):
    """Test short entry signal when far from breakdown"""
    current_price = 115.0
    signal = SignalGenerator.check_short_entry_signal(self.df, current_price)
    self.assertIsNone(signal)

  def test_check_short_entry_signal_below_breakdown(self):
    """Test short entry signal when already below breakdown"""
    current_price = 95.0
    signal = SignalGenerator.check_short_entry_signal(self.df, current_price)
    self.assertIsNone(signal)

  # Long Exit Signal Tests
  def test_check_long_exit_signal_triggered(self):
    """Test long exit signal when price breaks below 10-day low"""
    # Last low_10 is 109
    current_price = 108.0
    is_exit = SignalGenerator.check_long_exit_signal(self.df, current_price)
    self.assertTrue(is_exit)

  def test_check_long_exit_signal_not_triggered(self):
    """Test long exit signal not triggered"""
    current_price = 112.0
    is_exit = SignalGenerator.check_long_exit_signal(self.df, current_price)
    self.assertFalse(is_exit)

  # Short Exit Signal Tests
  def test_check_short_exit_signal_triggered(self):
    """Test short exit signal when price breaks above 10-day high"""
    # Last high_10 is 111.5
    current_price = 112.0
    is_exit = SignalGenerator.check_short_exit_signal(self.df, current_price)
    self.assertTrue(is_exit)

  def test_check_short_exit_signal_not_triggered(self):
    """Test short exit signal not triggered"""
    current_price = 109.0
    is_exit = SignalGenerator.check_short_exit_signal(self.df, current_price)
    self.assertFalse(is_exit)

  # Long Pyramid Tests
  def test_check_long_pyramid_opportunity(self):
    """Test long pyramid opportunity detection"""
    last_entry_price = 100.0
    current_price = 101.5
    initial_n = 2.0

    # 0.5N above entry = 100 + 0.5*2 = 101
    # Current price 101.5 > 101*0.99, so should trigger
    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertTrue(is_pyramid)

  def test_check_long_pyramid_opportunity_not_reached(self):
    """Test long pyramid opportunity not reached"""
    last_entry_price = 100.0
    current_price = 99.5
    initial_n = 2.0

    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid)

  def test_check_long_pyramid_opportunity_zero_n(self):
    """Test long pyramid opportunity with zero N"""
    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      100.0, 101.5, 0, threshold=0.5
    )
    self.assertFalse(is_pyramid)

  def test_check_long_pyramid_opportunity_none_n(self):
    """Test long pyramid opportunity with None N"""
    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      100.0, 101.5, None, threshold=0.5
    )
    self.assertFalse(is_pyramid)

  # Short Pyramid Tests
  def test_check_short_pyramid_opportunity(self):
    """Test short pyramid opportunity detection"""
    last_entry_price = 100.0
    current_price = 98.5
    initial_n = 2.0

    # 0.5N below entry = 100 - 0.5*2 = 99
    # Current price 98.5 < 99*1.01, so should trigger
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertTrue(is_pyramid)

  def test_check_short_pyramid_opportunity_not_reached(self):
    """Test short pyramid opportunity not reached"""
    last_entry_price = 100.0
    current_price = 100.5
    initial_n = 2.0

    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid)

  def test_check_short_pyramid_opportunity_zero_n(self):
    """Test short pyramid opportunity with zero N"""
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      100.0, 98.5, 0, threshold=0.5
    )
    self.assertFalse(is_pyramid)

  def test_check_short_pyramid_opportunity_none_n(self):
    """Test short pyramid opportunity with None N"""
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      100.0, 98.5, None, threshold=0.5
    )
    self.assertFalse(is_pyramid)


if __name__ == '__main__':
  unittest.main()
