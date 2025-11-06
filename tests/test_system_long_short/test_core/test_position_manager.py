"""Tests for PositionManager for the long-short system"""

import unittest
from system_long_short.core.position_manager import PositionManager


class TestPositionManagerLongShort(unittest.TestCase):
  """Test cases for PositionManager class in the long-short system"""

  def test_calculate_position_size(self):
    """Test position size calculation"""
    total_equity = 10000
    n = 2.5
    units = PositionManager.calculate_position_size(total_equity, n, risk_per_unit_pct=0.001)
    # Expected: (10000 * 0.001) / 2.5 = 10 / 2.5 = 4
    self.assertEqual(units, 4)

  def test_calculate_position_size_zero_equity(self):
    """Test position size with zero total equity"""
    units = PositionManager.calculate_position_size(0, 2.5)
    self.assertEqual(units, 0)

  def test_calculate_position_size_zero_n(self):
    """Test position size with zero N"""
    units = PositionManager.calculate_position_size(10000, 0)
    self.assertEqual(units, 0)

  def test_calculate_margin_required(self):
    """Test margin calculation for short positions"""
    units = 100
    entry_price = 150.0
    margin = PositionManager.calculate_margin_required(units, entry_price, margin_pct=0.5)
    # Expected: 100 * 150 * 0.5 = 7500
    self.assertEqual(margin, 7500.0)

  def test_calculate_long_stop_single_unit(self):
    """Test long stop calculation with single unit"""
    position = {
      'side': 'long',
      'initial_n': 2.0,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2.0, 'units': 50}
      ]
    }
    stop_price = PositionManager.calculate_long_stop(position)
    # Stop is last_entry - 2N = 100 - 2*2.0 = 96.0
    self.assertAlmostEqual(stop_price, 96.0, places=2)

  def test_calculate_long_stop_multiple_units(self):
    """Test long stop calculation with multiple pyramid units"""
    position = {
      'side': 'long',
      'initial_n': 2.0,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2.0, 'units': 50},
        {'entry_price': 101, 'entry_n': 2.0, 'units': 50},
        {'entry_price': 102, 'entry_n': 2.0, 'units': 50}
      ]
    }
    stop_price = PositionManager.calculate_long_stop(position)
    # Stop is last_entry - 2N = 102 - 2*2.0 = 98.0
    self.assertAlmostEqual(stop_price, 98.0, places=2)

  def test_calculate_short_stop_single_unit(self):
    """Test short stop calculation with single unit"""
    position = {
      'side': 'short',
      'initial_n': 2.0,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2.0, 'units': 50}
      ]
    }
    stop_price = PositionManager.calculate_short_stop(position)
    # Stop is last_entry + 2N = 100 + 2*2.0 = 104.0
    self.assertAlmostEqual(stop_price, 104.0, places=2)

  def test_calculate_short_stop_multiple_units(self):
    """Test short stop calculation with multiple pyramid units"""
    position = {
      'side': 'short',
      'initial_n': 2.0,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2.0, 'units': 50},
        {'entry_price': 99, 'entry_n': 2.0, 'units': 50},
        {'entry_price': 98, 'entry_n': 2.0, 'units': 50}
      ]
    }
    stop_price = PositionManager.calculate_short_stop(position)
    # Stop is last_entry + 2N = 98 + 2*2.0 = 102.0
    self.assertAlmostEqual(stop_price, 102.0, places=2)

  def test_can_pyramid(self):
    """Test checking if position can pyramid"""
    position_3_levels = {
      'pyramid_units': [{'units': 50}, {'units': 50}, {'units': 50}]
    }
    position_4_levels = {
      'pyramid_units': [{'units': 50}, {'units': 50}, {'units': 50}, {'units': 50}]
    }
    self.assertTrue(PositionManager.can_pyramid(position_3_levels, max_pyramids=4))
    self.assertFalse(PositionManager.can_pyramid(position_4_levels, max_pyramids=4))

  def test_create_new_long_position(self):
    """Test creating a new long position"""
    position = PositionManager.create_new_long_position(
      units=100,
      entry_price=150.0,
      entry_n=3.0,
      order_id='order123',
      system=1
    )
    self.assertEqual(position['side'], 'long')
    self.assertEqual(position['system'], 1)
    self.assertEqual(len(position['pyramid_units']), 1)
    self.assertEqual(position['pyramid_units'][0]['units'], 100)
    self.assertEqual(position['pyramid_units'][0]['entry_price'], 150.0)
    self.assertEqual(position['stop_price'], 150.0 - 2 * 3.0)
    self.assertEqual(position['initial_n'], 3.0)
    self.assertEqual(position['initial_units'], 100)

  def test_create_new_short_position(self):
    """Test creating a new short position"""
    position = PositionManager.create_new_short_position(
      units=100,
      entry_price=150.0,
      entry_n=3.0,
      order_id='order123',
      system=1
    )
    self.assertEqual(position['side'], 'short')
    self.assertEqual(position['system'], 1)
    self.assertEqual(len(position['pyramid_units']), 1)
    self.assertEqual(position['pyramid_units'][0]['units'], 100)
    self.assertEqual(position['pyramid_units'][0]['entry_price'], 150.0)
    self.assertEqual(position['stop_price'], 150.0 + 2 * 3.0)  # Stop ABOVE for shorts
    self.assertEqual(position['initial_n'], 3.0)
    self.assertEqual(position['initial_units'], 100)

  def test_add_pyramid_unit_long(self):
    """Test adding a pyramid unit to long position"""
    position = PositionManager.create_new_long_position(
      units=100,
      entry_price=100.0,
      entry_n=2.0,
      order_id='order123',
      system=1
    )
    updated_position = PositionManager.add_pyramid_unit(
      position,
      units=100,
      entry_price=101.0,
      entry_n=2.1,  # This gets ignored, uses initial_n
      order_id='order456'
    )
    self.assertEqual(len(updated_position['pyramid_units']), 2)
    self.assertEqual(updated_position['pyramid_units'][1]['units'], 100)
    # Stop is last_entry - 2N = 101 - 2*2.0 = 97.0
    self.assertAlmostEqual(updated_position['stop_price'], 97.0, places=2)

  def test_add_pyramid_unit_short(self):
    """Test adding a pyramid unit to short position"""
    position = PositionManager.create_new_short_position(
      units=100,
      entry_price=100.0,
      entry_n=2.0,
      order_id='order123',
      system=1
    )
    updated_position = PositionManager.add_pyramid_unit(
      position,
      units=100,
      entry_price=99.0,
      entry_n=2.1,  # This gets ignored, uses initial_n
      order_id='order456'
    )
    self.assertEqual(len(updated_position['pyramid_units']), 2)
    self.assertEqual(updated_position['pyramid_units'][1]['units'], 100)
    # Stop is last_entry + 2N = 99 + 2*2.0 = 103.0
    self.assertAlmostEqual(updated_position['stop_price'], 103.0, places=2)

  def test_calculate_long_position_pnl(self):
    """Test P&L calculation for long position"""
    position = {
      'side': 'long',
      'pyramid_units': [
        {'units': 100, 'entry_price': 100, 'entry_n': 2, 'entry_value': 10000},
        {'units': 100, 'entry_price': 101, 'entry_n': 2.1, 'entry_value': 10100}
      ]
    }
    exit_price = 105
    total_units, entry_value, exit_value, pnl, pnl_pct = \
      PositionManager.calculate_long_position_pnl(position, exit_price)

    self.assertEqual(total_units, 200)
    self.assertEqual(entry_value, 20100)
    self.assertEqual(exit_value, 21000)
    self.assertEqual(pnl, 900)
    self.assertAlmostEqual(pnl_pct, (900 / 20100) * 100, places=2)

  def test_calculate_short_position_pnl(self):
    """Test P&L calculation for short position"""
    position = {
      'side': 'short',
      'pyramid_units': [
        {'units': 100, 'entry_price': 100, 'entry_n': 2, 'entry_value': 10000},
        {'units': 100, 'entry_price': 99, 'entry_n': 2.1, 'entry_value': 9900}
      ]
    }
    exit_price = 95  # Covering at lower price = profit
    total_units, entry_value, exit_value, pnl, pnl_pct = \
      PositionManager.calculate_short_position_pnl(position, exit_price)

    self.assertEqual(total_units, 200)
    self.assertEqual(entry_value, 19900)
    self.assertEqual(exit_value, 19000)  # What we pay to close
    # P&L = units * (avg_entry - exit) = 200 * (99.5 - 95) = 200 * 4.5 = 900
    self.assertEqual(pnl, 900)
    self.assertAlmostEqual(pnl_pct, (900 / 19900) * 100, places=2)

  def test_calculate_allocated_risk(self):
    """Test allocated risk calculation"""
    position = {
      'pyramid_units': [
        {'units': 100, 'entry_price': 100, 'entry_n': 2},
        {'units': 100, 'entry_price': 101, 'entry_n': 2.1}
      ]
    }
    allocated_risk = PositionManager.calculate_allocated_risk(position)
    # Expected: 100*2*2 + 100*2*2.1 = 400 + 420 = 820
    self.assertAlmostEqual(allocated_risk, 820, places=2)


if __name__ == '__main__':
  unittest.main()
