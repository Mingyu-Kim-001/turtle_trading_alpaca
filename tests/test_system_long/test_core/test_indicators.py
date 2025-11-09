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

  def test_donchian_high_excludes_current_day(self):
    """Test that Donchian high excludes current day (correct Turtle Trading behavior)"""
    # Use deterministic data for this test
    test_df = pd.DataFrame({
      'high': list(range(100, 130)),  # Monotonically increasing
      'low': list(range(95, 125)),
      'close': list(range(98, 128))
    })

    df_with_channels = IndicatorCalculator.calculate_donchian_channels(test_df, entry_period=20)

    # IMPORTANT: high_20 should be the max of PREVIOUS 20 days (excluding current day)
    # This is achieved with shift(1).rolling(20).max()
    for i in range(20, min(25, len(df_with_channels))):
      calculated_high = df_with_channels['high_20'].iloc[i]
      # Expected: max of previous 20 days, which is the value at i-1 for monotonically increasing data
      expected_high = test_df['high'].iloc[i-1]
      self.assertAlmostEqual(calculated_high, expected_high, places=5,
                             msg=f"At index {i}, high_20 should be {expected_high} (previous day's high), "
                                 f"not {calculated_high}")

  def test_donchian_low_excludes_current_day(self):
    """Test that Donchian low excludes current day (correct Turtle Trading behavior)"""
    # Use deterministic data for this test
    test_df = pd.DataFrame({
      'high': list(range(100, 130)),
      'low': list(range(95, 125)),  # Monotonically increasing
      'close': list(range(98, 128))
    })

    df_with_channels = IndicatorCalculator.calculate_donchian_channels(test_df, entry_period=20)

    # IMPORTANT: low_20 should be the min of PREVIOUS 20 days (excluding current day)
    for i in range(20, min(25, len(df_with_channels))):
      calculated_low = df_with_channels['low_20'].iloc[i]
      # Expected: min of previous 20 days, which for monotonically increasing data
      # is the value 20 positions back (i-20)
      expected_low = test_df['low'].iloc[i-20]
      self.assertAlmostEqual(calculated_low, expected_low, places=5,
                             msg=f"At index {i}, low_20 should be {expected_low} "
                                 f"(min of previous 20 days), not {calculated_low}")

  def test_breakout_scenario(self):
    """Test realistic breakout scenario - today's high is highest but shouldn't trigger yet"""
    # Create data where today makes a new 20-day high
    highs = [100] * 20 + [105]  # Days 0-19: 100, Day 20: 105 (new high)
    test_df = pd.DataFrame({
      'high': highs,
      'low': [95] * 21,
      'close': [98] * 21
    })

    df_with_channels = IndicatorCalculator.calculate_donchian_channels(test_df, entry_period=20)

    # On day 20 (index 20), we have a new high of 105
    # But high_20 should still be 100 (the max of PREVIOUS 20 days)
    # This is correct: you enter when price breaks ABOVE the previous 20-day high
    day_20_high_20 = df_with_channels['high_20'].iloc[20]
    self.assertAlmostEqual(day_20_high_20, 100.0, places=5,
                           msg="high_20 should be 100 (previous 20-day max), not 105 (today's high)")

    # The current price of 105 is above high_20 of 100, so this would trigger an entry
    current_price = test_df['high'].iloc[20]
    self.assertGreater(current_price, day_20_high_20,
                       msg="Current price should be above high_20 to trigger entry")

  def test_all_channels_exclude_current_day(self):
    """Test that all 6 Donchian channels exclude current day"""
    test_df = pd.DataFrame({
      'high': list(range(100, 160)),  # 60 days
      'low': list(range(95, 155)),
      'close': list(range(98, 158))
    })

    df_with_channels = IndicatorCalculator.calculate_donchian_channels(test_df)

    # Check high_20 at index 30
    self.assertAlmostEqual(df_with_channels['high_20'].iloc[30], test_df['high'].iloc[29], places=5)

    # Check low_20 at index 30
    self.assertAlmostEqual(df_with_channels['low_20'].iloc[30], test_df['low'].iloc[10], places=5)

    # Check high_10 at index 30
    self.assertAlmostEqual(df_with_channels['high_10'].iloc[30], test_df['high'].iloc[29], places=5)

    # Check low_10 at index 30
    self.assertAlmostEqual(df_with_channels['low_10'].iloc[30], test_df['low'].iloc[20], places=5)

    # Check high_55 at index 55
    self.assertAlmostEqual(df_with_channels['high_55'].iloc[55], test_df['high'].iloc[54], places=5)

    # Check low_55 at index 55
    self.assertAlmostEqual(df_with_channels['low_55'].iloc[55], test_df['low'].iloc[0], places=5)


if __name__ == '__main__':
  unittest.main()
