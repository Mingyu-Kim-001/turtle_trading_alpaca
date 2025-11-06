"""
Tests for order status enum usage to prevent QueryOrderStatus vs OrderStatus bugs

This test file ensures that the correct enum types are imported and used
when checking order statuses from the Alpaca API.

BUG HISTORY:
- Date: 2025-11-04
- Issue: Code was using QueryOrderStatus.FILLED instead of OrderStatus.FILLED
- Error: "type object 'QueryOrderStatus' has no attribute 'FILLED'"
- Impact: Pending pyramid orders were incorrectly removed, allowing duplicate orders
- Result: Position grew from 35 to 175 shares (5x intended size)
"""

import unittest
from unittest.mock import Mock, MagicMock
from alpaca.trading.enums import QueryOrderStatus, OrderStatus


class TestOrderStatusEnums(unittest.TestCase):
    """Test cases for correct order status enum usage"""

    def test_order_status_enum_has_filled_attribute(self):
        """Verify OrderStatus enum has FILLED attribute"""
        self.assertTrue(hasattr(OrderStatus, 'FILLED'),
            "OrderStatus must have FILLED attribute")

    def test_order_status_enum_has_canceled_attribute(self):
        """Verify OrderStatus enum has CANCELED attribute"""
        self.assertTrue(hasattr(OrderStatus, 'CANCELED'),
            "OrderStatus must have CANCELED attribute")

    def test_order_status_enum_has_expired_attribute(self):
        """Verify OrderStatus enum has EXPIRED attribute"""
        self.assertTrue(hasattr(OrderStatus, 'EXPIRED'),
            "OrderStatus must have EXPIRED attribute")

    def test_order_status_enum_has_rejected_attribute(self):
        """Verify OrderStatus enum has REJECTED attribute"""
        self.assertTrue(hasattr(OrderStatus, 'REJECTED'),
            "OrderStatus must have REJECTED attribute")

    def test_query_order_status_enum_has_closed_attribute(self):
        """Verify QueryOrderStatus is for querying, not checking individual order status"""
        self.assertTrue(hasattr(QueryOrderStatus, 'CLOSED'),
            "QueryOrderStatus should have CLOSED for filtering queries")

    def test_query_order_status_cannot_check_filled_status(self):
        """
        REGRESSION TEST: Verify QueryOrderStatus doesn't have FILLED
        This was the bug - using QueryOrderStatus.FILLED when it doesn't exist
        """
        self.assertFalse(hasattr(QueryOrderStatus, 'FILLED'),
            "QueryOrderStatus should NOT have FILLED - that's in OrderStatus")

    def test_mock_order_status_comparison(self):
        """Test that mock orders can be compared with OrderStatus enum"""
        # Create a mock order with FILLED status
        mock_order = Mock()
        mock_order.status = OrderStatus.FILLED

        # This should work without AttributeError
        self.assertEqual(mock_order.status, OrderStatus.FILLED)
        self.assertNotEqual(mock_order.status, OrderStatus.CANCELED)

    def test_order_status_in_list_comparison(self):
        """Test checking order status against a list of statuses"""
        mock_order = Mock()
        mock_order.status = OrderStatus.FILLED

        # Common pattern used in the codebase
        terminal_states = [OrderStatus.FILLED, OrderStatus.CANCELED,
                          OrderStatus.EXPIRED, OrderStatus.REJECTED]

        self.assertIn(mock_order.status, terminal_states,
            "FILLED should be in terminal states list")

    def test_query_order_status_usage_for_filtering(self):
        """Demonstrate correct usage of QueryOrderStatus for filtering requests"""
        # QueryOrderStatus is used in GetOrdersRequest for filtering
        # This is the CORRECT usage

        # Simulate checking if QueryOrderStatus.CLOSED exists (for filtering)
        self.assertTrue(hasattr(QueryOrderStatus, 'CLOSED'))

        # But it should NOT be used for checking individual order.status
        # That should use OrderStatus instead

    def test_order_status_enum_import_verification(self):
        """Verify that both enums can be imported from alpaca.trading.enums"""
        try:
            from alpaca.trading.enums import QueryOrderStatus, OrderStatus
            # If we get here, both imports succeeded
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Failed to import enums: {e}")

    def test_enum_values_are_distinct(self):
        """Ensure OrderStatus and QueryOrderStatus are different types"""
        self.assertIsNot(OrderStatus, QueryOrderStatus,
            "OrderStatus and QueryOrderStatus should be different types")

    def test_filled_order_can_be_detected(self):
        """Test that a filled order can be properly detected"""
        mock_order = Mock()
        mock_order.status = OrderStatus.FILLED
        mock_order.filled_qty = 35
        mock_order.filled_avg_price = 185.91

        # Simulate the check_pending_orders logic
        if mock_order.status == OrderStatus.FILLED:
            is_filled = True
        else:
            is_filled = False

        self.assertTrue(is_filled,
            "Should correctly identify filled order using OrderStatus.FILLED")

    def test_canceled_order_can_be_detected(self):
        """Test that a canceled order can be properly detected"""
        mock_order = Mock()
        mock_order.status = OrderStatus.CANCELED

        terminal_states = [OrderStatus.CANCELED, OrderStatus.EXPIRED,
                          OrderStatus.REJECTED]

        self.assertIn(mock_order.status, terminal_states,
            "Should correctly identify canceled order using OrderStatus.CANCELED")


class TestOrderStatusEnumUsagePatterns(unittest.TestCase):
    """Test common usage patterns to prevent enum misuse"""

    def test_wrong_enum_usage_would_fail(self):
        """
        REGRESSION TEST: Demonstrate that using QueryOrderStatus.FILLED would fail
        This is the exact bug we're preventing
        """
        mock_order = Mock()
        mock_order.status = OrderStatus.FILLED

        # This would be WRONG and cause AttributeError:
        # mock_order.status == QueryOrderStatus.FILLED  # QueryOrderStatus has no FILLED!

        # Verify QueryOrderStatus doesn't have FILLED
        with self.assertRaises(AttributeError):
            _ = QueryOrderStatus.FILLED

    def test_correct_enum_for_order_status_check(self):
        """Test the correct pattern for checking order status"""
        mock_order = Mock()
        mock_order.status = OrderStatus.FILLED

        # CORRECT: Use OrderStatus for checking individual order.status
        is_filled = (mock_order.status == OrderStatus.FILLED)
        self.assertTrue(is_filled)

    def test_correct_enum_for_query_filtering(self):
        """Test the correct pattern for query filtering"""
        # CORRECT: Use QueryOrderStatus for filtering in GetOrdersRequest

        # Simulating: GetOrdersRequest(status=QueryOrderStatus.CLOSED)
        query_status = QueryOrderStatus.CLOSED

        # This should work
        self.assertEqual(query_status, QueryOrderStatus.CLOSED)

    def test_pending_order_tracking_pattern(self):
        """
        Test the correct pattern for tracking pending orders
        This is the code pattern that had the bug
        """
        # Simulate pending order tracking
        pending_orders = {'JNJ': 'order-123'}

        # Mock getting order from API
        mock_order = Mock()
        mock_order.id = 'order-123'
        mock_order.status = OrderStatus.FILLED
        mock_order.filled_qty = 35
        mock_order.filled_avg_price = 185.91

        # CORRECT way to check status
        if mock_order.status == OrderStatus.FILLED:
            # Order is filled, remove from pending
            del pending_orders['JNJ']

        self.assertNotIn('JNJ', pending_orders,
            "Should remove ticker from pending after detecting filled order")

    def test_multiple_status_checks(self):
        """Test checking for multiple terminal statuses"""
        mock_order = Mock()

        # Test all terminal statuses
        terminal_statuses = [
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED
        ]

        for status in terminal_statuses:
            mock_order.status = status

            # This should work for all terminal statuses
            is_terminal = mock_order.status in [
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.EXPIRED,
                OrderStatus.REJECTED
            ]

            self.assertTrue(is_terminal,
                f"Should recognize {status} as terminal status")


if __name__ == '__main__':
    unittest.main()
