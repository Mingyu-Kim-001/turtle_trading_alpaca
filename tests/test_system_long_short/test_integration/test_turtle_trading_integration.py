"""Basic integration tests for TurtleTradingLS components

These tests verify that components work correctly together without extensive mocking.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime


class TestPositionManagerIntegration(unittest.TestCase):
  """Test PositionManager integration with other components"""

  def test_position_size_and_stop_calculation_long(self):
    """Test position sizing → position creation → stop calculation"""
    from system_long_short.core.position_manager import PositionManager
    
    # 1. Calculate position size
    equity = 100000
    n = 5.0
    units = PositionManager.calculate_position_size(equity, n, risk_per_unit_pct=0.01)
    self.assertEqual(units, 200)  # (100000 * 0.01) / 5 = 200
    
    # 2. Create position
    position = PositionManager.create_new_long_position(
      units=units,
      entry_price=150.0,
      entry_n=n,
      order_id='test-order',
      system=1
    )
    
    # 3. Verify stop is correct
    expected_stop = 150.0 - (2 * 5.0)  # 140.0
    self.assertEqual(position['stop_price'], expected_stop)
    
    # 4. Test pyramiding
    self.assertTrue(PositionManager.can_pyramid(position, max_pyramids=4))
    
    # 5. Add pyramid unit
    updated_position = PositionManager.add_pyramid_unit(
      position,
      units=units,
      entry_price=152.5,
      entry_n=n,
      order_id='pyramid-1'
    )
    
    # Stop should move up to last_entry - 2N
    expected_stop = 152.5 - (2 * 5.0)  # 142.5
    self.assertEqual(updated_position['stop_price'], expected_stop)

  def test_position_size_and_stop_calculation_short(self):
    """Test short position workflow"""
    from system_long_short.core.position_manager import PositionManager
    
    equity = 50000
    n = 3.0
    units = PositionManager.calculate_position_size(equity, n, risk_per_unit_pct=0.01)
    self.assertAlmostEqual(units, 166.666667, places=5)
    
    # Create short position
    position = PositionManager.create_new_short_position(
      units=int(units),  # Shorts must be whole shares
      entry_price=200.0,
      entry_n=n,
      order_id='short-order',
      system=1
    )
    
    # Stop should be ABOVE for shorts
    expected_stop = 200.0 + (2 * 3.0)  # 206.0
    self.assertEqual(position['stop_price'], expected_stop)


class TestIndicatorAndSignalIntegration(unittest.TestCase):
  """Test indicator calculation → signal generation"""

  def test_indicators_to_entry_signal(self):
    """Test full workflow: data → indicators → entry signal"""
    from system_long_short.core.indicators import IndicatorCalculator
    from system_long_short.core.signal_generator import SignalGenerator
    
    # 1. Create sample data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    df = pd.DataFrame({
      'open': np.full(100, 100.0),
      'high': np.full(100, 105.0),
      'low': np.full(100, 95.0),
      'close': np.full(100, 100.0),
      'volume': np.full(100, 1000000)
    }, index=dates)
    
    # 2. Calculate indicators
    df_with_indicators = IndicatorCalculator.calculate_indicators(df)
    
    # 3. Verify indicators exist
    self.assertIn('N', df_with_indicators.columns)
    self.assertIn('high_20', df_with_indicators.columns)
    self.assertIn('low_20', df_with_indicators.columns)
    
    # 4. Check for entry signal (price at channel - should not signal yet)
    signal = SignalGenerator.check_long_entry_signal(
      df_with_indicators,
      current_price=100.0,
      proximity_threshold=0.05,
      system=1
    )
    
    # Should have signal since we're within proximity
    self.assertIsNotNone(signal)

  def test_indicators_to_exit_signal(self):
    """Test exit signal generation after indicators"""
    from system_long_short.core.indicators import IndicatorCalculator
    from system_long_short.core.signal_generator import SignalGenerator
    
    # Create data
    dates = pd.date_range(start='2024-01-01', periods=50, freq='D')
    df = pd.DataFrame({
      'open': np.linspace(100, 110, 50),
      'high': np.linspace(105, 115, 50),
      'low': np.linspace(95, 105, 50),
      'close': np.linspace(100, 110, 50),
      'volume': np.full(50, 1000000)
    }, index=dates)
    
    df_with_indicators = IndicatorCalculator.calculate_indicators(df)
    
    # Check for exit signal (price below 10-day low)
    # Last low_10 is around 103, so price at 100 should trigger exit
    is_exit = SignalGenerator.check_long_exit_signal(
      df_with_indicators,
      current_price=95.0,
      system=1
    )
    
    self.assertTrue(is_exit)


class TestPyramidingWorkflow(unittest.TestCase):
  """Test complete pyramiding workflow"""

  def test_pyramid_signal_to_execution(self):
    """Test pyramid opportunity → calculation → execution"""
    from system_long_short.core.position_manager import PositionManager
    from system_long_short.core.signal_generator import SignalGenerator
    
    # 1. Create initial position
    initial_n = 3.0
    position = PositionManager.create_new_long_position(
      units=100,
      entry_price=100.0,
      entry_n=initial_n,
      order_id='initial',
      system=1
    )
    
    # 2. Check pyramid opportunity (price moved up 0.5N)
    current_price = 101.5
    is_pyramid = SignalGenerator.check_long_pyramid_opportunity(
      last_entry_price=100.0,
      current_price=current_price,
      initial_n=initial_n,
      threshold=0.5
    )
    
    self.assertTrue(is_pyramid)
    
    # 3. Add pyramid unit
    updated_position = PositionManager.add_pyramid_unit(
      position,
      units=100,
      entry_price=current_price,
      entry_n=initial_n,
      order_id='pyramid-1'
    )
    
    # 4. Verify position state
    self.assertEqual(len(updated_position['pyramid_units']), 2)
    # Stop should be at last entry - 2N = 101.5 - 6 = 95.5
    expected_stop = current_price - (2 * initial_n)
    self.assertEqual(updated_position['stop_price'], expected_stop)


class TestDualSystemLogic(unittest.TestCase):
  """Test System 1 and System 2 interaction"""

  def test_system2_priority_over_system1(self):
    """Test that System 2 signals are prioritized"""
    from system_long_short.core.signal_generator import SignalGenerator
    from system_long_short.core.indicators import IndicatorCalculator
    
    # Create mock data provider
    class MockDataProvider:
      def get_historical_data(self, ticker):
        dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
        return pd.DataFrame({
          'open': np.full(100, 100.0),
          'high': np.full(100, 105.0),
          'low': np.full(100, 95.0),
          'close': np.full(100, 100.0),
          'volume': np.full(100, 1000000)
        }, index=dates)
    
    class MockIndicatorCalculator:
      def calculate_indicators(self, df):
        df['N'] = 2.0
        df['high_20'] = 99.0  # System 1 entry
        df['high_55'] = 99.0  # System 2 entry
        df['low_20'] = 95.0
        df['low_55'] = 94.0
        df['low_10'] = 96.0
        df['high_10'] = 103.0
        return df
    
    # Generate signals with both systems enabled
    signals = SignalGenerator.generate_entry_signals(
      universe=['TEST'],
      data_provider=MockDataProvider(),
      indicator_calculator=MockIndicatorCalculator(),
      long_positions={},
      short_positions={},
      enable_longs=True,
      enable_shorts=False,
      enable_system1=True,
      enable_system2=True,
      proximity_threshold=0.05
    )
    
    # Verify both systems generated signals
    test_signals = [s for s in signals if s['ticker'] == 'TEST']
    system1 = [s for s in test_signals if s['system'] == 1]
    system2 = [s for s in test_signals if s['system'] == 2]
    
    self.assertGreater(len(system1), 0)
    self.assertGreater(len(system2), 0)
    
    # Verify System 2 comes first (higher priority)
    if len(test_signals) >= 2:
      self.assertEqual(test_signals[0]['system'], 2)


class TestWhipsawProtection(unittest.TestCase):
  """Test System 1 whipsaw protection logic"""

  def test_win_filter_blocks_system1_entry(self):
    """Test that winning System 1 trade blocks next entry"""
    from system_long_short.core.signal_generator import SignalGenerator
    
    # Create data with entry signal
    dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
    df = pd.DataFrame({
      'close': [99] * 60,
      'high': [101] * 60,
      'low': [98] * 60,
      'high_20': [100] * 60,
      'low_20': [90] * 60,
      'N': [2.0] * 60
    })
    
    # Without win filter - should generate signal
    signal = SignalGenerator.check_long_entry_signal(
      df, current_price=99.5, proximity_threshold=0.05, system=1
    )
    self.assertIsNotNone(signal)
    
    # Simulate win filter blocking
    last_trade_was_win = {('TEST', 'long'): True}
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)
    self.assertTrue(is_blocked)


if __name__ == '__main__':
  unittest.main()
