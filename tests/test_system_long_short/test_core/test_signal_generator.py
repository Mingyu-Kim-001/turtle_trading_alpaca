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

  # REGRESSION TESTS FOR BUG FIXES

  def test_short_pyramid_regression_jnj_bug(self):
    """
    REGRESSION TEST: Prevent JNJ bug where price moved UP but pyramid triggered

    Bug scenario:
    - Entry: $185.91, N: $2.78
    - Pyramid trigger: $184.52 (entry - 0.5N)
    - Current: $186.30 (MOVED UP, not down!)
    - Old buggy logic: $186.30 < $184.52 * 1.01 = $186.37 ✓ (WRONG!)
    - New correct logic: Should NOT trigger
    """
    last_entry_price = 185.91
    current_price = 186.30  # Price INCREASED (wrong direction for short pyramid)
    initial_n = 2.78

    # Should NOT trigger pyramid when price moves against us
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid,
      "Pyramid should NOT trigger when price moves UP for short positions")

  def test_short_pyramid_prevents_false_trigger_with_small_n(self):
    """
    Test that small N values don't cause false triggers due to percentage-based margins

    When N is small relative to price, a percentage-based margin can be larger
    than the actual threshold distance, causing false triggers.
    """
    last_entry_price = 200.0
    initial_n = 2.0  # Small N

    # Price barely moved down (0.1N instead of 0.5N)
    current_price = 199.8  # 200 - 0.1*2 = 199.8

    # Pyramid trigger at 199.0 (200 - 0.5*2)
    # Old logic: 199.8 < 199.0 * 1.01 = 201.0 ✓ (FALSE TRIGGER!)
    # New logic: 199.8 > 199.0 + 0.02*2 = 199.04 (correctly prevents)

    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid,
      "Should not trigger pyramid when price moved only 0.1N instead of 0.5N")

  def test_short_pyramid_correctly_triggers_at_threshold(self):
    """Test that pyramid correctly triggers when price reaches threshold"""
    last_entry_price = 185.91
    current_price = 184.50  # Just at threshold (185.91 - 0.5*2.78 ≈ 184.52)
    initial_n = 2.78

    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertTrue(is_pyramid,
      "Pyramid should trigger when price reaches the 0.5N threshold")

  def test_short_pyramid_multiple_threshold_values(self):
    """Test pyramid triggering with different threshold values"""
    last_entry_price = 100.0
    initial_n = 2.0

    # Test 0.25N threshold (more aggressive pyramiding)
    # Trigger: 100 - 0.25*2 = 99.5, Tolerance: 0.02*2 = 0.04
    # Should trigger at or below 99.5 + 0.04 = 99.54
    current_price = 99.5  # At trigger
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.25
    )
    self.assertTrue(is_pyramid)

    # Test 1.0N threshold (more conservative pyramiding)
    # Trigger: 100 - 1.0*2 = 98, Tolerance: 0.02*2 = 0.04
    # Should trigger at or below 98 + 0.04 = 98.04
    current_price = 98.0  # At trigger
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=1.0
    )
    self.assertTrue(is_pyramid)

    # Not reached 1.0N threshold yet (above tolerance band)
    current_price = 98.5  # 98.5 > 98.04, should not trigger
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=1.0
    )
    self.assertFalse(is_pyramid)

  def test_long_pyramid_prevents_false_trigger_with_small_n(self):
    """
    Test that long pyramid also prevents false triggers with small N
    Ensures consistency between long and short pyramid logic
    """
    last_entry_price = 200.0
    initial_n = 2.0

    # Price barely moved up (0.1N instead of 0.5N)
    current_price = 200.2  # 200 + 0.1*2 = 200.2

    # Pyramid trigger at 201.0 (200 + 0.5*2)
    # Tolerance: 0.02*2 = 0.04
    # Should trigger at >= 201.0 - 0.04 = 200.96
    # 200.2 < 200.96, so should NOT trigger
    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid,
      "Should not trigger pyramid when price moved only 0.1N instead of 0.5N")

  def test_short_pyramid_direction_check(self):
    """
    Test that short pyramids only trigger when price moves DOWN
    Critical for preventing the JNJ-style bug
    """
    last_entry_price = 100.0
    initial_n = 2.0

    test_cases = [
      # (current_price, should_trigger, description)
      (101.0, False, "Price moved UP 1.0N - should NOT trigger"),
      (100.5, False, "Price moved UP 0.5N - should NOT trigger"),
      (100.2, False, "Price moved UP 0.2N - should NOT trigger"),
      (100.0, False, "Price unchanged - should NOT trigger"),
      (99.8, False, "Price moved DOWN 0.2N - not enough, should NOT trigger"),
      (99.0, True,  "Price moved DOWN 0.5N - should trigger"),
      (98.5, True,  "Price moved DOWN 0.75N - should trigger"),
      (98.0, True,  "Price moved DOWN 1.0N - should trigger"),
    ]

    for current_price, expected_trigger, description in test_cases:
      is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
        last_entry_price, current_price, initial_n, threshold=0.5
      )
      self.assertEqual(is_pyramid, expected_trigger,
        f"Failed: {description} (price={current_price})")

  def test_long_pyramid_direction_check(self):
    """
    Test that long pyramids only trigger when price moves UP
    Mirror test of short pyramid direction check
    """
    last_entry_price = 100.0
    initial_n = 2.0

    # Pyramid trigger: 100 + 0.5*2 = 101.0
    # Tolerance: 0.02*2 = 0.04
    # Should trigger at >= 101.0 - 0.04 = 100.96

    test_cases = [
      # (current_price, should_trigger, description)
      (99.0, False, "Price moved DOWN 1.0N - should NOT trigger"),
      (99.5, False, "Price moved DOWN 0.5N - should NOT trigger"),
      (99.8, False, "Price moved DOWN 0.2N - should NOT trigger"),
      (100.0, False, "Price unchanged - should NOT trigger"),
      (100.2, False, "Price moved UP 0.2N - not enough, should NOT trigger"),
      (100.96, True,  "Price at trigger threshold - should trigger"),
      (101.0, True,  "Price moved UP 0.5N - should trigger"),
      (101.5, True,  "Price moved UP 0.75N - should trigger"),
      (102.0, True,  "Price moved UP 1.0N - should trigger"),
    ]

    for current_price, expected_trigger, description in test_cases:
      is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
        last_entry_price, current_price, initial_n, threshold=0.5
      )
      self.assertEqual(is_pyramid, expected_trigger,
        f"Failed: {description} (price={current_price})")

  def test_pyramid_tolerance_is_based_on_n_not_price(self):
    """
    Verify that tolerance is based on N value, not price percentage
    This prevents the bug where percentage-based margins exceed threshold distances
    """
    # High price, low N scenario
    last_entry_price = 1000.0
    initial_n = 5.0

    # Pyramid trigger for short: 1000 - 0.5*5 = 997.5
    # Tolerance: 0.02 * 5 = 0.1
    # Should trigger at: 997.5 + 0.1 = 997.6

    # Just above trigger (should NOT trigger)
    current_price = 997.7
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertFalse(is_pyramid, "Should not trigger just above threshold")

    # At trigger (should trigger)
    current_price = 997.5
    is_pyramid = SignalGenerator.check_short_pyramid_opportunity(
      last_entry_price, current_price, initial_n, threshold=0.5
    )
    self.assertTrue(is_pyramid, "Should trigger at threshold")

  # DUAL SYSTEM TESTS WITH SYSTEM 2 PRIORITY

  def test_dual_system_both_systems_checked_independently(self):
    """Test that both System 1 and System 2 are checked independently for signals"""
    # Create mock data provider and indicator calculator
    class MockDataProvider:
      def get_historical_data(self, ticker):
        # Create data where both 20-day and 55-day breakouts trigger
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 102.0),
          'low': np.full(100, 98.0),
          'close': np.full(100, 100.0),
        }, index=dates)
        return df

    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        df['high_20'] = 99.0  # Current price will be near this
        df['high_55'] = 99.5  # And near this too
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df

    data_provider = MockDataProvider()
    indicator_calculator = MockIndicatorCalculator()
    universe = ['TEST']
    long_positions = {}
    short_positions = {}

    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, enable_system1=True, enable_system2=True,
      proximity_threshold=0.05
    )

    # Both System 1 and System 2 should generate signals
    system1_signals = [s for s in signals if s['system'] == 1]
    system2_signals = [s for s in signals if s['system'] == 2]

    self.assertGreater(len(system1_signals), 0, "System 1 should generate signals")
    self.assertGreater(len(system2_signals), 0, "System 2 should generate signals")

  def test_dual_system_signals_sorted_system2_first(self):
    """Test that signals are sorted with System 2 first, then by proximity"""
    # Create mock data provider and indicator calculator
    class MockDataProvider:
      def get_historical_data(self, ticker):
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 102.0),
          'low': np.full(100, 98.0),
          'close': np.full(100, 100.0),
        }, index=dates)
        return df

    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        df['high_20'] = 99.0
        df['high_55'] = 99.5
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df

    data_provider = MockDataProvider()
    indicator_calculator = MockIndicatorCalculator()
    universe = ['AAPL', 'GOOGL', 'MSFT']
    long_positions = {}
    short_positions = {}

    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, enable_system1=True, enable_system2=True,
      proximity_threshold=0.05
    )

    # Check that all System 2 signals come before System 1 signals
    found_system1 = False
    for signal in signals:
      if signal['system'] == 1:
        found_system1 = True
      elif signal['system'] == 2 and found_system1:
        self.fail("Found System 2 signal after System 1 signal - incorrect ordering")

  def test_dual_system_system1_win_filter_applied(self):
    """Test that System 1 win filter is applied correctly"""
    class MockDataProvider:
      def get_historical_data(self, ticker):
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 102.0),
          'low': np.full(100, 98.0),
          'close': np.full(100, 100.0),
        }, index=dates)
        return df

    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        df['high_20'] = 99.0
        df['high_55'] = 105.0  # Far away, won't trigger
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df

    data_provider = MockDataProvider()
    indicator_calculator = MockIndicatorCalculator()
    universe = ['TEST']
    long_positions = {}
    short_positions = {}

    # Test with last trade was a win - System 1 should be filtered
    last_trade_was_win = {('TEST', 'long'): True}

    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, proximity_threshold=0.05,
      last_trade_was_win=last_trade_was_win
    )

    system1_signals = [s for s in signals if s['system'] == 1 and s['ticker'] == 'TEST']
    self.assertEqual(len(system1_signals), 0, "System 1 should be filtered when last trade was a win")

    # Test without win filter - System 1 should generate signal
    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, proximity_threshold=0.05,
      last_trade_was_win={}
    )

    system1_signals = [s for s in signals if s['system'] == 1 and s['ticker'] == 'TEST']
    self.assertGreater(len(system1_signals), 0, "System 1 should generate signals when no win filter")

  def test_dual_system_system2_no_win_filter(self):
    """Test that System 2 always generates signals regardless of win filter"""
    class MockDataProvider:
      def get_historical_data(self, ticker):
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 102.0),
          'low': np.full(100, 98.0),
          'close': np.full(100, 100.0),
        }, index=dates)
        return df

    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        df['high_20'] = 105.0  # Far away, won't trigger
        df['high_55'] = 99.0
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df

    data_provider = MockDataProvider()
    indicator_calculator = MockIndicatorCalculator()
    universe = ['TEST']
    long_positions = {}
    short_positions = {}

    # System 2 should generate signals even when last trade was a win
    last_trade_was_win = {('TEST', 'long'): True}

    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, enable_system1=True, enable_system2=True,
      proximity_threshold=0.05,
      last_trade_was_win=last_trade_was_win
    )

    system2_signals = [s for s in signals if s['system'] == 2 and s['ticker'] == 'TEST']
    self.assertGreater(len(system2_signals), 0, "System 2 should always generate signals (no win filter)")

  def test_dual_system_both_signals_for_same_ticker(self):
    """Test that when both systems signal for the same ticker, both signals are included"""
    class MockDataProvider:
      def get_historical_data(self, ticker):
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        df = pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 102.0),
          'low': np.full(100, 98.0),
          'close': np.full(100, 100.0),
        }, index=dates)
        return df

    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        # Both channels at same level - both will trigger
        df['high_20'] = 99.0
        df['high_55'] = 99.0
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df

    data_provider = MockDataProvider()
    indicator_calculator = MockIndicatorCalculator()
    universe = ['TEST']
    long_positions = {}
    short_positions = {}

    signals = SignalGenerator.generate_entry_signals(
      universe, data_provider, indicator_calculator,
      long_positions, short_positions,
      enable_shorts=False, enable_system1=True, enable_system2=True,
      proximity_threshold=0.05
    )

    test_signals = [s for s in signals if s['ticker'] == 'TEST']
    system1_signals = [s for s in test_signals if s['system'] == 1]
    system2_signals = [s for s in test_signals if s['system'] == 2]

    # Both systems should generate signals (deduplication happens in process_entry_queue)
    self.assertEqual(len(system1_signals), 1, "System 1 should generate signal")
    self.assertEqual(len(system2_signals), 1, "System 2 should generate signal")

    # System 2 signal should come first due to sorting
    first_signal = test_signals[0]
    self.assertEqual(first_signal['system'], 2, "System 2 signal should be first in sorted list")


if __name__ == '__main__':
  unittest.main()
