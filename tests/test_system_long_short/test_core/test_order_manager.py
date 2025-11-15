"""Comprehensive tests for OrderManager"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from alpaca.trading.enums import OrderSide, OrderStatus
from system_long_short.core.order_manager import OrderManager


class TestOrderManagerLongEntry(unittest.TestCase):
  """Test long entry order placement"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier,
      max_slippage=0.005
    )

  def test_place_long_entry_order_immediate_fill(self):
    """Test long entry order that fills immediately"""
    # Setup mock order
    mock_order = Mock()
    mock_order.id = 'order-123'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 150.50
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    # Place order
    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      n=3.0,
      is_pyramid=False,
      pyramid_level=1
    )

    # Verify results
    self.assertTrue(success)
    self.assertEqual(order_id, 'order-123')
    self.assertEqual(filled_price, 150.50)

    # Verify order was submitted
    self.mock_client.submit_order.assert_called_once()
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.symbol, 'AAPL')
    self.assertEqual(call_args.qty, 100)
    self.assertEqual(call_args.side, OrderSide.BUY)
    self.assertEqual(call_args.stop_price, 150.0)
    self.assertAlmostEqual(call_args.limit_price, 150.75, places=2)  # 150 * 1.005

  def test_place_long_entry_order_stays_pending(self):
    """Test long entry order that stays pending"""
    mock_order_submitted = Mock()
    mock_order_submitted.id = 'order-456'
    
    mock_order_pending = Mock()
    mock_order_pending.id = 'order-456'
    mock_order_pending.status = 'pending_new'
    
    self.mock_client.submit_order.return_value = mock_order_submitted
    self.mock_client.get_order_by_id.return_value = mock_order_pending

    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='MSFT',
      units=50,
      target_price=300.0,
      n=5.0
    )

    self.assertFalse(success)
    self.assertEqual(order_id, 'order-456')
    self.assertIsNone(filled_price)

  def test_place_long_entry_order_invalid_units(self):
    """Test that invalid units are rejected"""
    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='GOOGL',
      units=0,
      target_price=2800.0,
      n=50.0
    )

    self.assertFalse(success)
    self.assertIsNone(order_id)
    self.assertIsNone(filled_price)
    self.mock_client.submit_order.assert_not_called()

  def test_place_long_entry_order_negative_units(self):
    """Test that negative units are rejected"""
    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='TSLA',
      units=-10,
      target_price=700.0,
      n=20.0
    )

    self.assertFalse(success)
    self.assertIsNone(order_id)
    self.mock_client.submit_order.assert_not_called()

  def test_place_long_entry_order_fractional_units(self):
    """Test that fractional units are properly rounded"""
    mock_order = Mock()
    mock_order.id = 'order-789'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 150.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='NVDA',
      units=100.123456789012345,  # More precision than Alpaca allows
      target_price=500.0,
      n=10.0
    )

    self.assertTrue(success)
    # Check that units were rounded to 9 decimal places
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.qty, 100.123456789)

  def test_place_long_entry_pyramid_order(self):
    """Test placing a pyramid order (not initial entry)"""
    mock_order = Mock()
    mock_order.id = 'pyramid-order'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 155.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='AAPL',
      units=100,
      target_price=155.0,
      n=3.0,
      is_pyramid=True,
      pyramid_level=2
    )

    self.assertTrue(success)
    # Verify logger was called with is_pyramid=True
    self.mock_logger.log_order.assert_called()
    log_call_args = self.mock_logger.log_order.call_args[0]
    self.assertEqual(log_call_args[0], 'LONG_ENTRY')
    self.assertTrue(log_call_args[3]['is_pyramid'])
    self.assertEqual(log_call_args[3]['pyramid_level'], 2)

  def test_place_long_entry_order_exception_handling(self):
    """Test exception handling during order placement"""
    self.mock_client.submit_order.side_effect = Exception("API Error")

    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker='ERROR',
      units=100,
      target_price=100.0,
      n=2.0
    )

    self.assertFalse(success)
    self.assertIsNone(order_id)
    self.assertIsNone(filled_price)
    self.mock_notifier.send_message.assert_called_once()


class TestOrderManagerShortEntry(unittest.TestCase):
  """Test short entry order placement"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier,
      max_slippage=0.005
    )

  def test_place_short_entry_order_immediate_fill(self):
    """Test short entry order that fills immediately"""
    mock_order = Mock()
    mock_order.id = 'short-123'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 149.50
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_short_entry_order(
      ticker='TSLA',
      units=100,
      target_price=150.0,
      n=3.0
    )

    self.assertTrue(success)
    self.assertEqual(order_id, 'short-123')
    self.assertEqual(filled_price, 149.50)

    # Verify order parameters
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.symbol, 'TSLA')
    self.assertEqual(call_args.qty, 100)
    self.assertEqual(call_args.side, OrderSide.SELL)
    self.assertEqual(call_args.stop_price, 150.0)
    self.assertAlmostEqual(call_args.limit_price, 149.25, places=2)  # 150 * 0.995

  def test_place_short_entry_order_rounds_to_whole_shares(self):
    """Test that short orders round down to whole shares (Alpaca requirement)"""
    mock_order = Mock()
    mock_order.id = 'short-456'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 200.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    # Try to place order with fractional shares
    success, order_id, filled_price = self.order_manager.place_short_entry_order(
      ticker='NVDA',
      units=100.9999,  # Should round DOWN to 100
      target_price=500.0,
      n=10.0
    )

    self.assertTrue(success)
    # Verify units were rounded down to whole number
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.qty, 100)

  def test_place_short_entry_order_rejects_fractional_less_than_one(self):
    """Test that fractional units less than 1 are rejected"""
    success, order_id, filled_price = self.order_manager.place_short_entry_order(
      ticker='AAPL',
      units=0.5,  # Rounds down to 0
      target_price=150.0,
      n=3.0
    )

    self.assertFalse(success)
    self.assertIsNone(order_id)
    self.mock_client.submit_order.assert_not_called()

  def test_place_short_entry_pyramid_order(self):
    """Test placing a short pyramid order"""
    mock_order = Mock()
    mock_order.id = 'short-pyramid'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 145.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_short_entry_order(
      ticker='TSLA',
      units=50,
      target_price=145.0,
      n=3.0,
      is_pyramid=True,
      pyramid_level=3
    )

    self.assertTrue(success)
    # Verify logger was called with pyramid info
    self.mock_logger.log_order.assert_called()
    log_call_args = self.mock_logger.log_order.call_args[0]
    self.assertEqual(log_call_args[0], 'SHORT_ENTRY')
    self.assertTrue(log_call_args[3]['is_pyramid'])
    self.assertEqual(log_call_args[3]['pyramid_level'], 3)


class TestOrderManagerLongExit(unittest.TestCase):
  """Test long exit order placement"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier,
      max_slippage=0.005
    )

  def test_place_long_exit_order_success(self):
    """Test successful long exit order"""
    mock_order = Mock()
    mock_order.id = 'exit-123'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 149.0
    
    self.mock_client.get_orders.return_value = []  # No existing orders
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      reason='10-day low exit signal'
    )

    self.assertTrue(success)
    self.assertEqual(order_id, 'exit-123')
    self.assertEqual(filled_price, 149.0)

  def test_place_long_exit_order_cancels_existing_buy_orders(self):
    """Test that exit order cancels conflicting buy orders"""
    # Mock existing buy order
    existing_buy_order = Mock()
    existing_buy_order.id = 'buy-order-123'
    existing_buy_order.side = OrderSide.BUY
    
    self.mock_client.get_orders.return_value = [existing_buy_order]
    
    # Mock exit order
    mock_exit_order = Mock()
    mock_exit_order.id = 'exit-456'
    mock_exit_order.status = OrderStatus.FILLED
    mock_exit_order.filled_avg_price = 149.0
    
    self.mock_client.submit_order.return_value = mock_exit_order
    self.mock_client.get_order_by_id.return_value = mock_exit_order

    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      reason='Stop loss'
    )

    # Verify buy order was cancelled
    self.mock_client.cancel_order_by_id.assert_called_once_with('buy-order-123')
    self.assertTrue(success)

  def test_place_long_exit_order_skips_if_sell_order_exists(self):
    """Test that exit order is skipped if sell order already exists"""
    existing_sell_order = Mock()
    existing_sell_order.id = 'sell-order-123'
    existing_sell_order.side = OrderSide.SELL
    
    self.mock_client.get_orders.return_value = [existing_sell_order]

    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      reason='Exit signal'
    )

    self.assertFalse(success)
    self.assertIsNone(order_id)
    self.mock_client.submit_order.assert_not_called()

  def test_place_long_exit_order_stop_loss_wider_slippage(self):
    """Test that stop-loss orders use wider 2% slippage margin"""
    mock_order = Mock()
    mock_order.id = 'exit-sl'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 145.0
    
    self.mock_client.get_orders.return_value = []
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      reason='2N stop loss',
      is_stop_loss=True
    )

    self.assertTrue(success)
    # Verify limit price uses 2% slippage for stop loss
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertAlmostEqual(call_args.limit_price, 147.0, places=2)  # 150 * 0.98

  def test_place_long_exit_order_rounds_units_down(self):
    """Test that units are rounded down to avoid requesting more than we have"""
    mock_order = Mock()
    mock_order.id = 'exit-round'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 149.0
    
    self.mock_client.get_orders.return_value = []
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    # Try to sell 100.000000001 shares
    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100.000000001,
      target_price=150.0,
      reason='Exit'
    )

    self.assertTrue(success)
    # Verify units were rounded down
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertLessEqual(call_args.qty, 100.0)

  def test_place_long_exit_order_retry_on_connection_error(self):
    """Test retry logic on connection errors"""
    self.mock_client.get_orders.return_value = []
    
    # Fail twice, then succeed
    mock_order = Mock()
    mock_order.id = 'exit-retry'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 149.0
    
    self.mock_client.submit_order.side_effect = [
      ConnectionError("Network error"),
      ConnectionError("Network error"),
      mock_order
    ]
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker='AAPL',
      units=100,
      target_price=150.0,
      reason='Exit'
    )

    self.assertTrue(success)
    # Verify it retried 3 times
    self.assertEqual(self.mock_client.submit_order.call_count, 3)


class TestOrderManagerShortExit(unittest.TestCase):
  """Test short exit order placement"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier,
      max_slippage=0.005
    )

  def test_place_short_exit_order_success(self):
    """Test successful short exit order (buy to cover)"""
    mock_order = Mock()
    mock_order.id = 'short-exit-123'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 151.0
    
    self.mock_client.get_orders.return_value = []
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_short_exit_order(
      ticker='TSLA',
      units=100,
      target_price=150.0,
      reason='10-day high exit signal'
    )

    self.assertTrue(success)
    self.assertEqual(order_id, 'short-exit-123')
    self.assertEqual(filled_price, 151.0)

    # Verify order is BUY (to cover short)
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.side, OrderSide.BUY)
    # For shorts, stop is ABOVE current price, limit is even higher
    self.assertEqual(call_args.stop_price, 150.0)
    self.assertAlmostEqual(call_args.limit_price, 150.75, places=2)  # 150 * 1.005

  def test_place_short_exit_order_cancels_existing_sell_orders(self):
    """Test that short exit cancels conflicting sell orders"""
    existing_sell_order = Mock()
    existing_sell_order.id = 'sell-order-456'
    existing_sell_order.side = OrderSide.SELL
    
    self.mock_client.get_orders.return_value = [existing_sell_order]
    
    mock_exit_order = Mock()
    mock_exit_order.id = 'short-exit-789'
    mock_exit_order.status = OrderStatus.FILLED
    mock_exit_order.filled_avg_price = 151.0
    
    self.mock_client.submit_order.return_value = mock_exit_order
    self.mock_client.get_order_by_id.return_value = mock_exit_order

    success, order_id, filled_price = self.order_manager.place_short_exit_order(
      ticker='TSLA',
      units=100,
      target_price=150.0,
      reason='Stop loss'
    )

    # Verify sell order was cancelled
    self.mock_client.cancel_order_by_id.assert_called_once_with('sell-order-456')
    self.assertTrue(success)

  def test_place_short_exit_order_rounds_to_whole_shares(self):
    """Test that short exit rounds to whole shares"""
    mock_order = Mock()
    mock_order.id = 'short-exit-round'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 151.0
    
    self.mock_client.get_orders.return_value = []
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    # Try to cover 99.9 shares
    success, order_id, filled_price = self.order_manager.place_short_exit_order(
      ticker='TSLA',
      units=99.9,  # Should round down to 99
      target_price=150.0,
      reason='Exit'
    )

    self.assertTrue(success)
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.qty, 99)


class TestOrderManagerUtilities(unittest.TestCase):
  """Test utility methods"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier
    )

  def test_get_open_orders(self):
    """Test getting open orders"""
    mock_orders = [Mock(), Mock()]
    self.mock_client.get_orders.return_value = mock_orders

    orders = self.order_manager.get_open_orders('AAPL')

    self.assertEqual(len(orders), 2)
    self.mock_client.get_orders.assert_called_once()

  def test_cancel_order(self):
    """Test cancelling an order"""
    success = self.order_manager.cancel_order('order-123')

    self.assertTrue(success)
    self.mock_client.cancel_order_by_id.assert_called_once_with('order-123')

  def test_cancel_all_orders(self):
    """Test cancelling all orders"""
    success = self.order_manager.cancel_all_orders()

    self.assertTrue(success)
    self.mock_client.cancel_orders.assert_called_once()

  def test_get_buying_power(self):
    """Test getting buying power"""
    mock_account = Mock()
    mock_account.buying_power = '50000.00'
    self.mock_client.get_account.return_value = mock_account

    buying_power = self.order_manager.get_buying_power()

    self.assertEqual(buying_power, 50000.0)


class TestOrderManagerMarketOrders(unittest.TestCase):
  """Test market order execution"""

  def setUp(self):
    """Set up test fixtures"""
    self.mock_client = Mock()
    self.mock_logger = Mock()
    self.mock_notifier = Mock()
    self.order_manager = OrderManager(
      self.mock_client,
      self.mock_logger,
      self.mock_notifier
    )

  def test_place_market_exit_order_long(self):
    """Test market order to exit long position"""
    mock_order = Mock()
    mock_order.id = 'market-123'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 150.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_market_exit_order(
      ticker='AAPL',
      units=100,
      side='long'
    )

    self.assertTrue(success)
    self.assertEqual(order_id, 'market-123')
    self.assertEqual(filled_price, 150.0)

    # Verify order was SELL (for long exit)
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.side, OrderSide.SELL)

  def test_place_market_exit_order_short(self):
    """Test market order to exit short position"""
    mock_order = Mock()
    mock_order.id = 'market-456'
    mock_order.status = OrderStatus.FILLED
    mock_order.filled_avg_price = 150.0
    
    self.mock_client.submit_order.return_value = mock_order
    self.mock_client.get_order_by_id.return_value = mock_order

    success, order_id, filled_price = self.order_manager.place_market_exit_order(
      ticker='TSLA',
      units=50,
      side='short'
    )

    self.assertTrue(success)
    # Verify order was BUY (for short exit)
    call_args = self.mock_client.submit_order.call_args[0][0]
    self.assertEqual(call_args.side, OrderSide.BUY)

  def test_place_market_exit_order_waits_for_fill(self):
    """Test that market order waits and retries for fill confirmation"""
    mock_order_pending = Mock()
    mock_order_pending.id = 'market-789'
    mock_order_pending.status = 'pending_new'
    
    mock_order_filled = Mock()
    mock_order_filled.id = 'market-789'
    mock_order_filled.status = OrderStatus.FILLED
    mock_order_filled.filled_avg_price = 150.0
    
    self.mock_client.submit_order.return_value = mock_order_pending
    # First check returns pending, second check returns filled
    self.mock_client.get_order_by_id.side_effect = [
      mock_order_pending,
      mock_order_filled
    ]

    success, order_id, filled_price = self.order_manager.place_market_exit_order(
      ticker='NVDA',
      units=25,
      side='long'
    )

    self.assertTrue(success)
    # Verify it checked status multiple times
    self.assertGreater(self.mock_client.get_order_by_id.call_count, 1)


if __name__ == '__main__':
  unittest.main()

