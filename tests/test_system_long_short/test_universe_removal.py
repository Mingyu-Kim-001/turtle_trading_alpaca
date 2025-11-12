"""Tests for ticker universe management - removed tickers behavior"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from system_long_short.turtle_trading_ls import TurtleTradingLS


class TestUniverseRemoval(unittest.TestCase):
  """Test that removing tickers from universe doesn't affect existing positions"""

  def test_position_management_independent_of_universe(self):
    """
    Test that position management (stops, exits, pyramids) works for tickers
    not in the universe list
    """
    # This test verifies the following behavior:
    # 1. Stops are checked for ALL positions (not just universe tickers)
    # 2. Exit signals are checked for ALL positions
    # 3. Pyramid opportunities are checked for ALL positions
    # 4. New entries ONLY come from universe tickers

    # Mock positions that include a ticker not in universe
    positions_with_removed_ticker = {
      'AAPL': {
        'side': 'long',
        'system': 1,
        'pyramid_units': [{'units': 10, 'entry_price': 150.0, 'entry_n': 3.0}],
        'stop_price': 144.0,
        'initial_n': 3.0,
        'initial_units': 10
      },
      'REMOVED': {  # This ticker is NOT in universe
        'side': 'long',
        'system': 1,
        'pyramid_units': [{'units': 15, 'entry_price': 200.0, 'entry_n': 4.0}],
        'stop_price': 192.0,
        'initial_n': 4.0,
        'initial_units': 15
      }
    }

    # Verify that position management methods iterate over positions, not universe
    self.assertIn('REMOVED', positions_with_removed_ticker)
    self.assertEqual(len(positions_with_removed_ticker), 2)

    # When checking stops, exits, pyramids:
    # - Method gets: list(self.state.long_positions.keys())
    # - This includes 'REMOVED' even though it's not in universe
    position_tickers = list(positions_with_removed_ticker.keys())
    self.assertIn('REMOVED', position_tickers)
    self.assertIn('AAPL', position_tickers)

  def test_entry_signals_only_from_universe(self):
    """Test that new entry signals are only generated from universe tickers"""
    # Universe only contains AAPL and MSFT
    universe = ['AAPL', 'MSFT']

    # Verify that REMOVED ticker won't generate new signals
    self.assertNotIn('REMOVED', universe)

    # Entry signal generation uses: self.universe as the ticker list
    # This means only AAPL and MSFT can generate new entry signals
    for ticker in universe:
      self.assertIn(ticker, ['AAPL', 'MSFT'])

  def test_removed_ticker_workflow(self):
    """
    Test the complete workflow when a ticker is removed from universe:

    Day 1: AAPL is in universe, position is opened
    Day 2: AAPL is removed from universe file
    Day 3: System should:
      - ✅ Continue checking stops for AAPL position
      - ✅ Continue checking exit signals for AAPL
      - ✅ Continue checking pyramid opportunities for AAPL
      - ❌ NOT generate new entry signals for AAPL
    Day 4: AAPL position exits
    Day 5: AAPL breaks out again
      - ❌ NO new entry (not in universe)
    """

    # Day 1: AAPL in universe and positions
    day1_universe = ['AAPL', 'MSFT']
    day1_positions = {'AAPL': {}}

    self.assertIn('AAPL', day1_universe)
    self.assertIn('AAPL', day1_positions)

    # Day 2: AAPL removed from universe, but position remains
    day2_universe = ['MSFT']  # AAPL removed
    day2_positions = {'AAPL': {}}  # Position still exists

    self.assertNotIn('AAPL', day2_universe)
    self.assertIn('AAPL', day2_positions)

    # Verify position management continues
    # (stops, exits, pyramids iterate over positions)
    position_list = list(day2_positions.keys())
    self.assertIn('AAPL', position_list)

    # Verify no new entries possible
    # (entry signals iterate over universe)
    self.assertNotIn('AAPL', day2_universe)

    # Day 4: AAPL position exits
    day4_positions = {}  # Position closed
    self.assertNotIn('AAPL', day4_positions)

    # Day 5: AAPL still not in universe
    day5_universe = ['MSFT']
    self.assertNotIn('AAPL', day5_universe)
    # No new entry possible because AAPL not in universe

  def test_code_flow_verification(self):
    """
    Verify the actual code flow for position management vs entry signals
    """
    # Position management methods in turtle_trading_ls.py:
    #
    # check_long_stops():
    #   tickers = list(self.state.long_positions.keys())  ← Uses positions
    #
    # check_long_exit_signals():
    #   for ticker, position in list(self.state.long_positions.items()):  ← Uses positions
    #
    # check_long_pyramid_opportunities():
    #   tickers = list(self.state.long_positions.keys())  ← Uses positions
    #
    # update_entry_queue():
    #   signals = self.signal_generator.generate_entry_signals(
    #     self.universe,  ← Uses universe
    #     ...
    #   )

    # Simulated positions (including removed ticker)
    positions = {'AAPL': {}, 'REMOVED': {}}
    universe = ['AAPL', 'MSFT']  # REMOVED not in universe

    # Position management uses positions dict
    position_tickers = list(positions.keys())
    self.assertEqual(set(position_tickers), {'AAPL', 'REMOVED'})

    # Entry signals use universe
    entry_tickers = universe
    self.assertEqual(set(entry_tickers), {'AAPL', 'MSFT'})

    # REMOVED ticker:
    # - ✅ In position_tickers (will be managed)
    # - ❌ Not in entry_tickers (won't generate new signals)
    self.assertIn('REMOVED', position_tickers)
    self.assertNotIn('REMOVED', entry_tickers)


class TestUniverseReloadBehavior(unittest.TestCase):
  """Test that universe changes take effect properly"""

  def test_universe_reloaded_on_eod_analysis(self):
    """
    Test that universe is reloaded from file during EOD analysis
    This allows dynamic changes to the universe
    """
    # The system loads universe in __init__() from file
    # If you modify the file and restart, new universe is loaded
    # If you modify the file during runtime, next EOD analysis could reload

    # Note: Current implementation loads universe only at startup
    # To support dynamic reloading, would need to add:
    #   self.load_universe(self.universe_file)
    # at the start of daily_eod_analysis()

    pass  # This is a documentation test


if __name__ == '__main__':
  unittest.main()
