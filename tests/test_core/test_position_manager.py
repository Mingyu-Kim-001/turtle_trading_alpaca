"""Tests for PositionManager"""

import unittest
from system.core.position_manager import PositionManager


class TestPositionManager(unittest.TestCase):
  """Test cases for PositionManager class"""

  def test_calculate_position_size(self):
    """Test position size calculation with new formula (matching backtester)"""
    total_equity = 10000
    n = 2.5

    units = PositionManager.calculate_position_size(total_equity, n)

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

  def test_calculate_overall_stop(self):
    """Test overall stop calculation with new formula"""
    # 3 pyramid units with initial N = 2
    position = {
      'initial_n': 2,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2, 'units': 50},
        {'entry_price': 101, 'entry_n': 2, 'units': 50},
        {'entry_price': 102, 'entry_n': 2, 'units': 50}
      ]
    }

    stop_price = PositionManager.calculate_overall_stop(position)

    # With 3 pyramid units: stop = highest_entry - (2.5 - 0.5*3) * initial_n
    # 100 - (2.5 - 1.5) * 2 = 102 - 1.0 * 2 = 102 - 2 = 100.0
    self.assertAlmostEqual(stop_price, 98.0, places=2)

  def test_calculate_overall_stop_single_unit(self):
    """Test stop calculation with single unit"""
    # 1 pyramid unit with initial N = 2
    position = {
      'initial_n': 2,
      'pyramid_units': [
        {'entry_price': 100, 'entry_n': 2, 'units': 50}
      ]
    }

    stop_price = PositionManager.calculate_overall_stop(position)

    # With 1 pyramid unit: stop = highest_entry - (2.5 - 0.5*1) * initial_n
    # 100 - (2.5 - 0.5) * 2 = 100 - 2.0 * 2 = 100 - 4 = 96.0
    self.assertAlmostEqual(stop_price, 96.0, places=2)

  def test_calculate_overall_stop_empty_list(self):
    """Test stop calculation with empty pyramid list"""
    position = {'pyramid_units': []}
    stop_price = PositionManager.calculate_overall_stop(position)
    self.assertIsNone(stop_price)

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

  def test_create_new_position(self):
    """Test creating a new position"""
    position = PositionManager.create_new_position(
      units=100,
      entry_price=150.0,
      entry_n=3.0,
      order_id='order123',
      system=1
    )

    self.assertEqual(position['system'], 1)
    self.assertEqual(len(position['pyramid_units']), 1)
    self.assertEqual(position['pyramid_units'][0]['units'], 100)
    self.assertEqual(position['pyramid_units'][0]['entry_price'], 150.0)
    self.assertEqual(position['pyramid_units'][0]['entry_n'], 3.0)
    self.assertEqual(position['stop_price'], 150.0 - 2 * 3.0)
    # Check new fields
    self.assertEqual(position['initial_n'], 3.0)
    self.assertEqual(position['initial_units'], 100)

  def test_add_pyramid_unit(self):
    """Test adding a pyramid unit"""
    initial_n_val = 2.0
    initial_entry_price_val = 100.0
    initial_units_val = 100

    position = PositionManager.create_new_position(
      units=initial_units_val,
      entry_price=initial_entry_price_val,
      entry_n=initial_n_val,
      order_id='order123',
      system=1
    )

    updated_position = PositionManager.add_pyramid_unit(
      position,
      units=initial_units_val,
      entry_price=101,
      entry_n=2.1, # This value is ignored for initial_n in add_pyramid_unit
      order_id='order456'
    )

    self.assertEqual(len(updated_position['pyramid_units']), 2)
    self.assertEqual(updated_position['pyramid_units'][1]['units'], initial_units_val)
    # Expected stop: initial_entry_price - (2.5 - 0.5 * num_pyramids) * initial_n
    # 100 - (2.5 - 0.5 * 2) * 2.0 = 100 - (1.5) * 2.0 = 100 - 3.0 = 97.0
    self.assertAlmostEqual(updated_position['stop_price'], 97.0, places=2)

  def test_calculate_position_pnl(self):
    """Test P&L calculation"""
    position = {
      'pyramid_units': [
        {'units': 100, 'entry_price': 100, 'entry_n': 2, 'entry_value': 10000},
        {'units': 100, 'entry_price': 101, 'entry_n': 2.1, 'entry_value': 10100}
      ]
    }

    exit_price = 105
    total_units, entry_value, exit_value, pnl, pnl_pct = \
      PositionManager.calculate_position_pnl(position, exit_price)

    self.assertEqual(total_units, 200)
    self.assertEqual(entry_value, 20100)
    self.assertEqual(exit_value, 21000)
    self.assertEqual(pnl, 900)
    self.assertAlmostEqual(pnl_pct, (900 / 20100) * 100, places=2)

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
