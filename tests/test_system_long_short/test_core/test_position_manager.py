"""Tests for PositionManager for the long-short system"""

import unittest
from system_long_short.core.position_manager import PositionManager


class TestPositionManagerLongShort(unittest.TestCase):
  """Test cases for PositionManager class in the long-short system"""

  def test_calculate_position_size(self):
    """Test position size calculation for the long-short system"""
    total_equity = 10000
    n = 2.5
    # In long-short, default risk per unit is 1%
    units = PositionManager.calculate_position_size(total_equity, n, risk_per_unit_pct=0.01)
    # Expected: (10000 * 0.01) / 2.5 = 100 / 2.5 = 40
    self.assertEqual(units, 40)


if __name__ == '__main__':
  unittest.main()
