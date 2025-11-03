"""Tests for SignalGenerator"""

import unittest
import pandas as pd
import numpy as np
from system_long.core.signal_generator import SignalGenerator


class TestSignalGenerator(unittest.TestCase):
  """Test cases for SignalGenerator class"""

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
      'high_55': np.linspace(100, 110, 100),
      'low_10': np.linspace(99, 109, 100),
      'low_20': np.linspace(98, 108, 100)
    }, index=dates)

  def test_check_entry_signal_near_breakout(self):
    """Test entry signal detection near breakout"""
    # Current price is close to high_20 breakout
    current_price = 110.5
    signal = SignalGenerator.check_entry_signal(self.df, current_price)

    self.assertIsNotNone(signal)
    self.assertIn('entry_price', signal)
    self.assertIn('n', signal)
    self.assertIn('proximity', signal)

  def test_check_entry_signal_far_from_breakout(self):
    """Test entry signal when far from breakout"""
    # Current price is far below high_20
    current_price = 100.0
    signal = SignalGenerator.check_entry_signal(self.df, current_price)

    # Should return None when too far from breakout
    self.assertIsNone(signal)

  def test_check_entry_signal_above_breakout(self):
    """Test entry signal when already above breakout"""
    # Current price well above high_20
    current_price = 120.0
    signal = SignalGenerator.check_entry_signal(self.df, current_price)

    # Should return None when too far above breakout
    self.assertIsNone(signal)

  def test_check_exit_signal_system_1(self):
    """Test System 1 exit signal"""
    # Price below 10-day low triggers exit
    current_price = 108.0
    is_exit = SignalGenerator.check_exit_signal(self.df, current_price, system=1)

    self.assertTrue(is_exit)

  def test_check_exit_signal_system_1_no_trigger(self):
    """Test System 1 exit signal not triggered"""
    # Price well above 10-day low (last low_10 is 109)
    current_price = 112.0
    is_exit = SignalGenerator.check_exit_signal(self.df, current_price, system=1)

    self.assertFalse(is_exit)

  def test_check_exit_signal_system_2(self):
    """Test System 2 exit signal"""
    # Price below 20-day low triggers exit
    current_price = 107.0
    is_exit = SignalGenerator.check_exit_signal(self.df, current_price, system=2)

    self.assertTrue(is_exit)

  def test_check_pyramid_opportunity(self):
    """Test pyramid opportunity detection"""
    last_entry_price = 100.0
    current_price = 101.5
    current_n = 2.0

    # 0.5N above entry = 100 + 0.5*2 = 101
    # Current price 101.5 > 101*0.99, so should trigger
    is_pyramid = SignalGenerator.check_pyramid_opportunity(
      last_entry_price, current_price, current_n, threshold=0.5
    )

    self.assertTrue(is_pyramid)

  def test_check_pyramid_opportunity_not_reached(self):
    """Test pyramid opportunity not reached"""
    last_entry_price = 100.0
    current_price = 99.5  # Price has not reached pyramid trigger
    current_n = 2.0

    # 0.5N above entry = 100 + 0.5*2 = 101, with 0.99 margin = 99.99
    # Current price 99.5 < 99.99, so should not trigger
    is_pyramid = SignalGenerator.check_pyramid_opportunity(
      last_entry_price, current_price, current_n, threshold=0.5
    )

    self.assertFalse(is_pyramid)

  def test_check_pyramid_opportunity_zero_n(self):
    """Test pyramid opportunity with zero N"""
    is_pyramid = SignalGenerator.check_pyramid_opportunity(
      100.0, 101.5, 0, threshold=0.5
    )

    self.assertFalse(is_pyramid)

  def test_check_pyramid_opportunity_none_n(self):
    """Test pyramid opportunity with None N"""
    is_pyramid = SignalGenerator.check_pyramid_opportunity(
      100.0, 101.5, None, threshold=0.5
    )

    self.assertFalse(is_pyramid)


if __name__ == '__main__':
  unittest.main()
