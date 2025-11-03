"""Tests for SignalGenerator for the long-short system"""

import unittest
import pandas as pd
import numpy as np
from system_long_short.core.signal_generator import SignalGenerator


class TestSignalGeneratorLongShort(unittest.TestCase):
  """Test cases for SignalGenerator class in the long-short system"""

  def setUp(self):
    """Set up test fixtures"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    self.df = pd.DataFrame({
      'open': np.linspace(100, 110, 100),
      'high': np.linspace(102, 112, 100),
      'low': np.linspace(98, 108, 100),
      'close': np.linspace(100, 110, 100),
      'N': np.full(100, 2.0),
      'high_20': np.linspace(101, 111, 100),
      'low_20': np.linspace(98, 108, 100)
    }, index=dates)

  def test_check_long_entry_signal(self):
    """Test long entry signal detection"""
    # Price is near the 20-day high
    current_price = 110.5
    signal = SignalGenerator.check_long_entry_signal(self.df, current_price)
    self.assertIsNotNone(signal)
    self.assertEqual(signal['side'], 'long')


if __name__ == '__main__':
  unittest.main()
