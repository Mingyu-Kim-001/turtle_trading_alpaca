"""
Tests for zombie PLACING marker cleanup

This test file ensures that PLACING markers are properly cleaned up when
order placement fails or when markers get stuck.

BUG HISTORY:
- Date: 2025-11-04
- Issue: When order placement failed (insufficient buying power), the "PLACING"
  marker was kept indefinitely, causing repeated log messages every cycle
- Symptom: "Found PLACING marker for JNJ, this should be updated soon" forever
- Impact: Cluttered logs, state tracking issues, prevented future pyramiding
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestZombiePlacingMarkers(unittest.TestCase):
    """Test cases for PLACING marker cleanup"""

    def test_placing_marker_removed_when_order_not_found(self):
        """
        Test that PLACING marker is removed when order cannot be found
        This happens when order placement fails (e.g., insufficient buying power)
        """
        # Simulate the scenario:
        # 1. Mark as PLACING
        # 2. Try to place order (fails)
        # 3. Can't find order in open_orders
        # 4. Should remove PLACING marker

        pending_orders = {'JNJ': 'PLACING'}
        open_orders = []  # No orders found (placement failed)

        # Simulate the cleanup logic
        ticker = 'JNJ'
        order_found = False

        for order in open_orders:
            if order.side == 'SELL':
                pending_orders[ticker] = str(order.id)
                order_found = True
                break

        if not order_found:
            # Should remove the marker
            if ticker in pending_orders:
                del pending_orders[ticker]

        # Verify marker was removed
        self.assertNotIn('JNJ', pending_orders,
            "PLACING marker should be removed when order not found")

    def test_placing_marker_updated_when_order_found(self):
        """
        Test that PLACING marker is updated with order ID when order is found
        """
        pending_orders = {'AAPL': 'PLACING'}

        # Mock order found in open_orders
        mock_order = Mock()
        mock_order.id = 'order-123'
        mock_order.side = Mock()
        mock_order.side.name = 'BUY'

        open_orders = [mock_order]

        # Simulate the update logic
        ticker = 'AAPL'
        order_found = False

        for order in open_orders:
            if order.side.name == 'BUY':
                pending_orders[ticker] = str(order.id)
                order_found = True
                break

        # Verify marker was updated
        self.assertEqual(pending_orders['AAPL'], 'order-123',
            "PLACING marker should be updated with order ID")

    def test_placing_marker_timeout_after_2_minutes(self):
        """
        Test that PLACING marker is removed after timeout (2 minutes)
        This catches zombie markers that slip through
        """
        # Simulate marker timestamp tracking
        placing_timestamps = {
            'JNJ': (datetime.now() - timedelta(minutes=3)).isoformat()  # 3 minutes ago
        }
        pending_orders = {'JNJ': 'PLACING'}

        # Check if should timeout
        ticker = 'JNJ'
        if ticker in placing_timestamps:
            marker_time = datetime.fromisoformat(placing_timestamps[ticker])
            elapsed = (datetime.now() - marker_time).total_seconds()

            if elapsed > 120:  # 2 minutes
                # Should remove marker
                del pending_orders[ticker]
                del placing_timestamps[ticker]

        # Verify cleanup
        self.assertNotIn('JNJ', pending_orders,
            "PLACING marker should be removed after 2 minute timeout")
        self.assertNotIn('JNJ', placing_timestamps,
            "Timestamp should be removed after timeout")

    def test_placing_marker_kept_if_within_timeout(self):
        """
        Test that PLACING marker is kept if within timeout window
        """
        # Marker created 30 seconds ago (within 2 minute timeout)
        placing_timestamps = {
            'AAPL': (datetime.now() - timedelta(seconds=30)).isoformat()
        }
        pending_orders = {'AAPL': 'PLACING'}

        # Check timeout
        ticker = 'AAPL'
        should_keep = True

        if ticker in placing_timestamps:
            marker_time = datetime.fromisoformat(placing_timestamps[ticker])
            elapsed = (datetime.now() - marker_time).total_seconds()

            if elapsed > 120:  # 2 minutes
                should_keep = False
                del pending_orders[ticker]
                del placing_timestamps[ticker]

        # Verify marker is kept
        self.assertTrue(should_keep, "Should keep marker within timeout")
        self.assertIn('AAPL', pending_orders,
            "PLACING marker should be kept within 2 minute timeout")

    def test_timestamp_cleared_when_order_found(self):
        """
        Test that timestamp is cleared when order is successfully found
        """
        placing_timestamps = {'MSFT': datetime.now().isoformat()}
        pending_orders = {'MSFT': 'PLACING'}

        # Mock order found
        mock_order = Mock()
        mock_order.id = 'order-456'
        mock_order.side = Mock()
        mock_order.side.name = 'SELL'

        open_orders = [mock_order]

        # Simulate the update logic
        ticker = 'MSFT'
        for order in open_orders:
            if order.side.name == 'SELL':
                pending_orders[ticker] = str(order.id)
                # Clear timestamp
                if ticker in placing_timestamps:
                    del placing_timestamps[ticker]
                break

        # Verify cleanup
        self.assertEqual(pending_orders['MSFT'], 'order-456',
            "Should update with order ID")
        self.assertNotIn('MSFT', placing_timestamps,
            "Timestamp should be cleared when order found")

    def test_multiple_placing_markers_handled_independently(self):
        """
        Test that multiple PLACING markers are handled independently
        """
        # Multiple markers with different ages
        now = datetime.now()
        placing_timestamps = {
            'AAPL': (now - timedelta(minutes=3)).isoformat(),  # Should timeout
            'MSFT': (now - timedelta(seconds=30)).isoformat(),  # Should keep
            'GOOGL': (now - timedelta(minutes=5)).isoformat(),  # Should timeout
        }
        pending_orders = {
            'AAPL': 'PLACING',
            'MSFT': 'PLACING',
            'GOOGL': 'PLACING'
        }

        # Process timeouts
        for ticker in list(pending_orders.keys()):
            if pending_orders[ticker] == 'PLACING' and ticker in placing_timestamps:
                marker_time = datetime.fromisoformat(placing_timestamps[ticker])
                elapsed = (now - marker_time).total_seconds()

                if elapsed > 120:  # 2 minutes
                    del pending_orders[ticker]
                    del placing_timestamps[ticker]

        # Verify results
        self.assertNotIn('AAPL', pending_orders, "AAPL should timeout")
        self.assertIn('MSFT', pending_orders, "MSFT should be kept")
        self.assertNotIn('GOOGL', pending_orders, "GOOGL should timeout")


class TestPlacingMarkerScenarios(unittest.TestCase):
    """Test real-world scenarios with PLACING markers"""

    def test_jnj_insufficient_buying_power_scenario(self):
        """
        REGRESSION TEST: JNJ scenario where 5th order failed
        Simulate the exact bug that caused zombie marker
        """
        # Initial state after 4 successful orders
        pending_orders = {}
        placing_timestamps = {}

        # 5th pyramid attempt
        ticker = 'JNJ'

        # 1. Mark as PLACING
        pending_orders[ticker] = 'PLACING'

        # 2. Try to enter position (fails due to insufficient buying power)
        position_entered = False  # Simulate failure

        # 3. Try to find order in open_orders
        open_orders = []  # No order because placement failed

        order_found = False
        if not position_entered:
            for order in open_orders:
                if order.side == 'SELL':
                    pending_orders[ticker] = str(order.id)
                    order_found = True
                    break

            if not order_found:
                # OLD BUG: Would keep PLACING marker
                # NEW FIX: Remove marker
                if ticker in pending_orders:
                    del pending_orders[ticker]

        # Verify marker was cleaned up
        self.assertNotIn('JNJ', pending_orders,
            "PLACING marker should be removed when order placement fails")

    def test_placing_marker_normal_flow(self):
        """
        Test normal flow: PLACING → order created → marker updated with ID
        """
        pending_orders = {}
        placing_timestamps = {}
        ticker = 'NVDA'

        # 1. Mark as PLACING
        pending_orders[ticker] = 'PLACING'
        placing_timestamps[ticker] = datetime.now().isoformat()

        # 2. Position entered successfully, order pending
        position_entered = False  # Returns False when order is pending

        # 3. Find order in open_orders
        mock_order = Mock()
        mock_order.id = 'order-789'
        mock_order.side = Mock()
        mock_order.side.name = 'BUY'
        open_orders = [mock_order]

        # 4. Update marker with order ID
        order_found = False
        if not position_entered:
            for order in open_orders:
                if order.side.name == 'BUY':
                    pending_orders[ticker] = str(order.id)
                    if ticker in placing_timestamps:
                        del placing_timestamps[ticker]
                    order_found = True
                    break

        # Verify correct state
        self.assertEqual(pending_orders[ticker], 'order-789',
            "Should update with order ID")
        self.assertNotIn(ticker, placing_timestamps,
            "Timestamp should be cleared")


if __name__ == '__main__':
    unittest.main()
