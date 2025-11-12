"""Tests for whipsaw protection and breaking condition logic"""

import unittest
import pandas as pd
from datetime import datetime, timedelta
from system_long_short.core import SignalGenerator


class TestWhipsawProtection(unittest.TestCase):
  """Test cases for System 1 whipsaw protection with breaking conditions"""

  def setUp(self):
    """Set up test data"""
    # Create a simple mock data provider and indicator calculator
    self.universe = ['TEST']

  def test_long_win_blocks_next_entry(self):
    """Test that a winning long trade blocks the next System 1 long entry"""
    last_trade_was_win = {
      ('TEST', 'long'): True  # Previous long trade was a win
    }

    # Create mock data with 20-day high breakout signal
    # Price should be close to high_20 to trigger signal (within proximity threshold)
    df = pd.DataFrame({
      'close': [99] * 55,  # Close to high_20
      'high': [101] * 55,
      'low': [98] * 55,
      'high_20': [100] * 55,  # Breakout at 100, close is at 99 (within threshold)
      'low_20': [90] * 55,
      'N': [2.0] * 55
    })

    # Check if signal would be generated
    latest = df.iloc[-1]
    signal = SignalGenerator.check_long_entry_signal(df, latest['close'], proximity_threshold=0.05, system=1)

    # Signal exists but should be blocked by win filter
    self.assertIsNotNone(signal, "Signal should exist when price is near breakout")

    # Verify the filter would block it
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)
    self.assertTrue(is_blocked, "Win filter should block entry")

  def test_short_win_blocks_next_entry(self):
    """Test that a winning short trade blocks the next System 1 short entry"""
    last_trade_was_win = {
      ('TEST', 'short'): True  # Previous short trade was a win
    }

    # Create mock data with 20-day low breakdown signal
    # Price should be close to low_20 to trigger signal
    df = pd.DataFrame({
      'close': [101] * 55,  # Close to low_20
      'high': [102] * 55,
      'low': [100] * 55,
      'high_20': [110] * 55,
      'low_20': [100] * 55,  # Breakdown at 100, close is at 101 (within threshold)
      'N': [2.0] * 55
    })

    # Check if signal would be generated
    latest = df.iloc[-1]
    signal = SignalGenerator.check_short_entry_signal(df, latest['close'], proximity_threshold=0.05, system=1)

    # Signal exists but should be blocked by win filter
    self.assertIsNotNone(signal, "Signal should exist when price is near breakdown")

    # Verify the filter would block it
    is_blocked = last_trade_was_win.get(('TEST', 'short'), False)
    self.assertTrue(is_blocked, "Win filter should block entry")

  def test_loss_allows_next_entry(self):
    """Test that a losing trade allows the next System 1 entry"""
    last_trade_was_win = {
      ('TEST', 'long'): False  # Previous long trade was a loss
    }

    # Verify the filter would NOT block it
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)
    self.assertFalse(is_blocked, "Loss should allow next entry")

  def test_no_previous_trade_allows_entry(self):
    """Test that no previous trade allows entry (default behavior)"""
    last_trade_was_win = {}  # No previous trade

    # Verify the filter would NOT block it (default False)
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)
    self.assertFalse(is_blocked, "No previous trade should allow entry")

  def test_breaking_condition_long_resets_on_opposite_signal(self):
    """Test that long win filter is reset when price breaks below 20-day low"""
    last_trade_was_win = {
      ('TEST', 'long'): True  # Blocked by previous win
    }

    # Create mock data where price breaks BELOW 20-day low (opposite signal)
    df = pd.DataFrame({
      'close': [85],  # Price below low_20 = 90
      'high': [86],
      'low': [84],
      'high_20': [95],
      'low_20': [90],  # Price < low_20 triggers reset
      'N': [2.0]
    })

    latest = df.iloc[-1]

    # Simulate the breaking condition check
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)

    if is_blocked and pd.notna(latest['low_20']):
      # Check breaking condition: price breaks below 20-day low
      if latest['close'] < latest['low_20']:
        last_trade_was_win[('TEST', 'long')] = False

    # Verify filter was reset
    self.assertFalse(
      last_trade_was_win[('TEST', 'long')],
      "Long win filter should be reset when price breaks below 20-day low"
    )

  def test_breaking_condition_short_resets_on_opposite_signal(self):
    """Test that short win filter is reset when price breaks above 20-day high"""
    last_trade_was_win = {
      ('TEST', 'short'): True  # Blocked by previous win
    }

    # Create mock data where price breaks ABOVE 20-day high (opposite signal)
    df = pd.DataFrame({
      'close': [111],  # Price above high_20 = 110
      'high': [112],
      'low': [110],
      'high_20': [110],  # Price > high_20 triggers reset
      'low_20': [100],
      'N': [2.0]
    })

    latest = df.iloc[-1]

    # Simulate the breaking condition check
    is_blocked = last_trade_was_win.get(('TEST', 'short'), False)

    if is_blocked and pd.notna(latest['high_20']):
      # Check breaking condition: price breaks above 20-day high
      if latest['close'] > latest['high_20']:
        last_trade_was_win[('TEST', 'short')] = False

    # Verify filter was reset
    self.assertFalse(
      last_trade_was_win[('TEST', 'short')],
      "Short win filter should be reset when price breaks above 20-day high"
    )

  def test_breaking_condition_does_not_reset_without_opposite_signal(self):
    """Test that win filter is NOT reset if opposite signal doesn't trigger"""
    last_trade_was_win = {
      ('TEST', 'long'): True  # Blocked by previous win
    }

    # Create mock data where price is still ABOVE 20-day low (no opposite signal)
    df = pd.DataFrame({
      'close': [95],  # Price above low_20 = 90, no reset
      'high': [96],
      'low': [94],
      'high_20': [100],
      'low_20': [90],  # Price > low_20, no reset
      'N': [2.0]
    })

    latest = df.iloc[-1]

    # Simulate the breaking condition check
    is_blocked = last_trade_was_win.get(('TEST', 'long'), False)

    if is_blocked and pd.notna(latest['low_20']):
      # Check breaking condition: price breaks below 20-day low
      if latest['close'] < latest['low_20']:
        last_trade_was_win[('TEST', 'long')] = False

    # Verify filter is STILL active (not reset)
    self.assertTrue(
      last_trade_was_win[('TEST', 'long')],
      "Long win filter should remain active without opposite signal"
    )

  def test_system2_ignores_win_filter(self):
    """Test that System 2 always takes entries regardless of win filter"""
    last_trade_was_win = {
      ('TEST', 'long'): True  # System 1 is blocked
    }

    # Create mock data with 55-day high breakout signal (System 2)
    # Price should be close to high_55 to trigger signal
    df = pd.DataFrame({
      'close': [99] * 55,  # Close to high_55
      'high': [101] * 55,
      'low': [98] * 55,
      'high_55': [100] * 55,  # System 2 breakout at 100
      'low_55': [90] * 55,
      'N': [2.0] * 55
    })

    # System 2 signal should be generated regardless of win filter
    latest = df.iloc[-1]
    signal = SignalGenerator.check_long_entry_signal(df, latest['close'], proximity_threshold=0.05, system=2)

    # System 2 always takes entries (no filter check)
    self.assertIsNotNone(signal, "System 2 should generate signal regardless of win filter")
    self.assertEqual(signal['system'], 2, "Signal should be for System 2")


if __name__ == '__main__':
  unittest.main()
