"""Tests for IndicatorCalculator"""

import unittest
import pandas as pd
import numpy as np
from system_long.core.indicators import IndicatorCalculator


class TestIndicatorCalculator(unittest.TestCase):
  """Test cases for IndicatorCalculator class"""

  def setUp(self):
    """Set up test fixtures"""
    # Create sample OHLC data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    self.df = pd.DataFrame({
      'open': np.random.uniform(100, 110, 100),
      'high': np.random.uniform(110, 120, 100),
      'low': np.random.uniform(90, 100, 100),
      'close': np.random.uniform(100, 110, 100),
      'volume': np.random.randint(1000000, 5000000, 100)
    }, index=dates)

  def test_calculate_atr(self):
    """Test ATR calculation"""
    df_with_atr = IndicatorCalculator.calculate_atr(self.df, period=20)

    # Check that N column was added
    self.assertIn('N', df_with_atr.columns)
    self.assertIn('TR', df_with_atr.columns)

    # Check that N values are valid after period
    valid_n = df_with_atr['N'].iloc[20:]
    self.assertTrue(all(pd.notna(valid_n)))
    self.assertTrue(all(valid_n > 0))

  def test_calculate_donchian_channels(self):
    """Test Donchian Channel calculation"""
    df_with_channels = IndicatorCalculator.calculate_donchian_channels(
      self.df, entry_period=20, exit_period=10, long_entry_period=55
    )

    # Check that columns were added
    self.assertIn('high_20', df_with_channels.columns)
    self.assertIn('high_55', df_with_channels.columns)
    self.assertIn('low_10', df_with_channels.columns)
    self.assertIn('low_20', df_with_channels.columns)

    # Check that values are valid after periods
    self.assertTrue(all(pd.notna(df_with_channels['high_20'].iloc[20:])))
    self.assertTrue(all(pd.notna(df_with_channels['high_55'].iloc[55:])))

  def test_calculate_all_indicators(self):
    """Test calculating all indicators at once"""
    df_with_indicators = IndicatorCalculator.calculate_indicators(self.df)

    # Check all expected columns are present
    expected_columns = ['N', 'TR', 'high_20', 'high_55', 'low_10', 'low_20']
    for col in expected_columns:
      self.assertIn(col, df_with_indicators.columns)

  def test_atr_values_reasonable(self):
    """Test that ATR values are reasonable"""
    df_with_atr = IndicatorCalculator.calculate_atr(self.df, period=20)

    # ATR should be positive
    valid_atr = df_with_atr['N'].dropna()
    self.assertTrue(all(valid_atr > 0))

    # ATR should be less than the price range
    price_range = self.df['high'].max() - self.df['low'].min()
    self.assertTrue(all(valid_atr < price_range))

  def test_donchian_high_is_maximum(self):
    """Test that Donchian high is actually the maximum"""
    # Use deterministic data for this test
    test_df = pd.DataFrame({
      'high': list(range(100, 130)),  # Monotonically increasing
      'low': list(range(95, 125)),
      'close': list(range(98, 128))
    })

    df_with_channels = IndicatorCalculator.calculate_donchian_channels(test_df, entry_period=20)

    # The rolling max includes the current row, so at index i,
    # high_20 should be the max of high[i-19:i+1] (last 20 values including current)
    for i in range(20, min(25, len(df_with_channels))):
      # Since our data is monotonically increasing, high_20 should equal current high
      calculated_high = df_with_channels['high_20'].iloc[i]
      expected_high = test_df['high'].iloc[i]  # Current high (highest in window)
      self.assertAlmostEqual(calculated_high, expected_high, places=5)


if __name__ == '__main__':
  unittest.main()
