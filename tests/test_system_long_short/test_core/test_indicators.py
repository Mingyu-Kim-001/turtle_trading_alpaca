"""Tests for IndicatorCalculator for the long-short system"""

import unittest
import pandas as pd
import numpy as np
from system_long_short.core.indicators import IndicatorCalculator


class TestIndicatorCalculatorLongShort(unittest.TestCase):
  """Test cases for IndicatorCalculator class in the long-short system"""

  def setUp(self):
    """Set up test fixtures"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    self.df = pd.DataFrame({
      'open': np.random.uniform(100, 110, 100),
      'high': np.random.uniform(110, 120, 100),
      'low': np.random.uniform(90, 100, 100),
      'close': np.random.uniform(100, 110, 100),
      'volume': np.random.randint(1000000, 5000000, 100)
    }, index=dates)

  def test_calculate_atr(self):
    """Test ATR calculation for the long-short system"""
    df_with_atr = IndicatorCalculator.calculate_atr(self.df, period=20)
    self.assertIn('N', df_with_atr.columns)
    self.assertTrue(all(pd.notna(df_with_atr['N'].iloc[20:])))


if __name__ == '__main__':
  unittest.main()
