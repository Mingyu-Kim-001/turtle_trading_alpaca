"""Order execution and management for long and short positions"""

import time
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
  StopLimitOrderRequest,
  MarketOrderRequest,
  GetOrdersRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

from ..utils.decorators import retry_on_connection_error


class OrderManager:
  """Handle order execution, tracking, and reconciliation for long and short positions"""

  def __init__(self, trading_client, logger=None, notifier=None,
        max_slippage=0.005):
    """
    Initialize order manager

    Args:
      trading_client: Alpaca TradingClient instance
      logger: DailyLogger instance (optional)
      notifier: SlackNotifier instance (optional)
      max_slippage: Maximum slippage for limit prices (default 0.005 = 0.5%)
    """
    self.trading_client = trading_client
    self.logger = logger
    self.notifier = notifier
    self.max_slippage = max_slippage

  def _log(self, message, level='INFO'):
    """Helper to log message"""
    if self.logger:
      self.logger.log(message, level)
    else:
      print(f"[{level}] {message}")

  def _notify(self, title, data):
    """Helper to send notification"""
    if self.notifier:
      self.notifier.send_summary(title, data)

  def place_long_entry_order(self, ticker, units, target_price, n, is_pyramid=False, pyramid_level=1):
    """
    Place a long entry order (buy)

    Args:
      ticker: Stock symbol
      units: Number of shares (can be fractional)
      target_price: Target entry price
      n: Current ATR
      is_pyramid: Whether this is a pyramid order
      pyramid_level: Pyramid level number

    Returns:
      Tuple of (success, order_id, filled_price)
    """
    try:
      # Round to 9 decimal places for Alpaca's precision
      units = round(float(units), 9)
      if units <= 0:
        self._log(f"Invalid units for {ticker}: {units}", 'ERROR')
        return False, None, None

      # Calculate prices - for longs, enter at target price
      # Stop price is the target entry price
      # Limit is above target to allow for slippage
      stop_price = round(target_price, 2)  # Target entry price
      limit_price = round(target_price * (1 + self.max_slippage), 2)  # Maximum acceptable buy price

      order_type = f"Long Pyramid Level {pyramid_level}" if is_pyramid else "Long Initial Entry"
      self._log(f"Placing {order_type.lower()} order for {ticker}: "
           f"units={units:.4f}, stop=${stop_price:.2f}, limit=${limit_price:.2f}")

      # Place stop-limit buy order
      order_data = StopLimitOrderRequest(
        symbol=ticker,
        qty=units,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        stop_price=stop_price,
        limit_price=limit_price
      )

      order = self.trading_client.submit_order(order_data)
      order_id = str(order.id)

      # Notify immediately when order placed
      self._notify("📤 LONG ENTRY ORDER PLACED", {
        "Ticker": ticker,
        "Type": order_type,
        "Order ID": order_id,
        "Units": f"{units:.4f}",
        "Stop Price": f"${stop_price:.2f}",
        "Limit Price": f"${limit_price:.2f}",
        "Status": "PENDING"
      })

      if self.logger:
        self.logger.log_order('LONG_ENTRY', ticker, 'PLACED', {
          'order_id': order_id,
          'units': units,
          'stop_price': stop_price,
          'limit_price': limit_price,
          'is_pyramid': is_pyramid,
          'pyramid_level': pyramid_level
        })

      # Wait and check if filled
      time.sleep(3)
      filled_order = self.trading_client.get_order_by_id(order_id)

      if filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        self._log(f"Long entry filled: {ticker} at ${filled_price:.2f}")

        if self.logger:
          self.logger.log_order('LONG_ENTRY', ticker, 'FILLED', {
            'order_id': order_id,
            'units': units,
            'filled_price': filled_price,
            'is_pyramid': is_pyramid,
            'pyramid_level': pyramid_level if is_pyramid else None
          })

        return True, order_id, filled_price

      else:
        self._log(f"Long entry pending for {ticker}, status: {filled_order.status}", 'WARNING')
        if self.logger:
          self.logger.log_order('LONG_ENTRY', ticker, 'PENDING', {
            'order_id': order_id,
            'status': filled_order.status,
            'is_pyramid': is_pyramid,
            'pyramid_level': pyramid_level if is_pyramid else None
          })
        return False, order_id, None

    except Exception as e:
      self._log(f"Error placing long entry order for {ticker}: {e}", 'ERROR')
      if self.notifier:
        self.notifier.send_message(f"❌ Error entering long {ticker}: {str(e)}")
      return False, None, None

  def place_short_entry_order(self, ticker, units, target_price, n, is_pyramid=False, pyramid_level=1):
    """
    Place a short entry order (sell short)

    Args:
      ticker: Stock symbol
      units: Number of shares (can be fractional)
      target_price: Target entry price
      n: Current ATR
      is_pyramid: Whether this is a pyramid order
      pyramid_level: Pyramid level number

    Returns:
      Tuple of (success, order_id, filled_price)
    """
    try:
      # Round to 9 decimal places for Alpaca's precision
      units = round(float(units), 9)
      if units <= 0:
        self._log(f"Invalid units for {ticker}: {units}", 'ERROR')
        return False, None, None

      # Calculate prices - for shorts, enter at target price
      # Stop price is the target entry price
      # Limit is below target to allow for slippage
      stop_price = round(target_price, 2)  # Target entry price
      limit_price = round(target_price * (1 - self.max_slippage), 2)  # Minimum acceptable sell price

      order_type = f"Short Pyramid Level {pyramid_level}" if is_pyramid else "Short Initial Entry"
      self._log(f"Placing {order_type.lower()} order for {ticker}: "
           f"units={units:.4f}, stop=${stop_price:.2f}, limit=${limit_price:.2f}")

      # Place stop-limit sell short order
      order_data = StopLimitOrderRequest(
        symbol=ticker,
        qty=units,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        stop_price=stop_price,
        limit_price=limit_price
      )

      order = self.trading_client.submit_order(order_data)
      order_id = str(order.id)

      # Notify immediately when order placed
      self._notify("📤 SHORT ENTRY ORDER PLACED", {
        "Ticker": ticker,
        "Type": order_type,
        "Order ID": order_id,
        "Units": f"{units:.4f}",
        "Stop Price": f"${stop_price:.2f}",
        "Limit Price": f"${limit_price:.2f}",
        "Status": "PENDING"
      })

      if self.logger:
        self.logger.log_order('SHORT_ENTRY', ticker, 'PLACED', {
          'order_id': order_id,
          'units': units,
          'stop_price': stop_price,
          'limit_price': limit_price,
          'is_pyramid': is_pyramid,
          'pyramid_level': pyramid_level
        })

      # Wait and check if filled
      time.sleep(3)
      filled_order = self.trading_client.get_order_by_id(order_id)

      if filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        self._log(f"Short entry filled: {ticker} at ${filled_price:.2f}")

        if self.logger:
          self.logger.log_order('SHORT_ENTRY', ticker, 'FILLED', {
            'order_id': order_id,
            'units': units,
            'filled_price': filled_price,
            'is_pyramid': is_pyramid,
            'pyramid_level': pyramid_level if is_pyramid else None
          })

        return True, order_id, filled_price

      else:
        self._log(f"Short entry pending for {ticker}, status: {filled_order.status}", 'WARNING')
        if self.logger:
          self.logger.log_order('SHORT_ENTRY', ticker, 'PENDING', {
            'order_id': order_id,
            'status': filled_order.status,
            'is_pyramid': is_pyramid,
            'pyramid_level': pyramid_level if is_pyramid else None
          })
        return False, order_id, None

    except Exception as e:
      self._log(f"Error placing short entry order for {ticker}: {e}", 'ERROR')
      if self.notifier:
        self.notifier.send_message(f"❌ Error entering short {ticker}: {str(e)}")
      return False, None, None

  def place_long_exit_order(self, ticker, units, target_price, reason, is_stop_loss=False):
    """
    Place a long exit order (sell)

    Args:
      ticker: Stock symbol
      units: Number of shares
      target_price: Target exit price
      reason: Reason for exit

    Returns:
      Tuple of (success, order_id, filled_price)
    """
    try:
      # Check for existing open orders
      try:
        request = GetOrdersRequest(
          status=QueryOrderStatus.OPEN,
          symbols=[ticker],
          limit=10
        )
        open_orders = self.trading_client.get_orders(request)

        # Check if there's already a sell order
        existing_sell = [o for o in open_orders if o.side == OrderSide.SELL]
        if existing_sell:
          self._log(f"Sell order already exists for {ticker}: {existing_sell[0].id}", 'WARNING')
          return False, None, None

        # Cancel any buy orders to free up shares
        buy_orders = [o for o in open_orders if o.side == OrderSide.BUY]
        if buy_orders:
          self._log(f"Cancelling {len(buy_orders)} buy orders for {ticker} to free shares")
          for order in buy_orders:
            try:
              self.trading_client.cancel_order_by_id(order.id)
              self._log(f"Cancelled order {order.id}")
              time.sleep(0.5)
            except Exception as e:
              self._log(f"Error cancelling order {order.id}: {e}", 'ERROR')

      except Exception as e:
        self._log(f"Error checking existing orders for {ticker}: {e}", 'WARNING')

      # Calculate prices
      stop_price = round(target_price, 2)
      # Use wider 2% margin for stop-loss orders to ensure fills, 0.5% for exit signals
      slippage = 0.02 if is_stop_loss else 0.005
      limit_price = round(stop_price * (1 - slippage), 2)

      # Round units to 8 decimal places for Alpaca's precision
      units = round(float(units), 8)

      self._log(f"Placing long exit order for {ticker}: units={units:.4f}, "
           f"stop=${stop_price:.2f}, limit=${limit_price:.2f}")

      # Place stop-limit sell order with retry logic
      max_retries = 3
      retry_delay = 2
      order_id = None

      for attempt in range(max_retries):
        try:
          order_data = StopLimitOrderRequest(
            symbol=ticker,
            qty=units,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            stop_price=stop_price,
            limit_price=limit_price
          )

          order = self.trading_client.submit_order(order_data)
          order_id = str(order.id)

          # Notify immediately
          self._notify("📤 LONG EXIT ORDER PLACED", {
            "Ticker": ticker,
            "Reason": reason,
            "Order ID": order_id,
            "Units": f"{units:.4f}",
            "Stop Price": f"${stop_price:.2f}",
            "Limit Price": f"${limit_price:.2f}",
            "Status": "PENDING"
          })

          if self.logger:
            self.logger.log_order('LONG_EXIT', ticker, 'PLACED', {
              'order_id': order_id,
              'units': units,
              'stop_price': stop_price,
              'limit_price': limit_price,
              'reason': reason
            })

          break

        except Exception as e:
          error_str = str(e)

          # Check if it's a duplicate order error
          if "40310000" in error_str or "insufficient qty" in error_str.lower():
            self._log(f"Shares for {ticker} are held by another order", 'WARNING')
            return False, None, None

          # Retry on connection errors
          if attempt < max_retries - 1:
            self._log(f"Error placing exit order for {ticker} (attempt {attempt + 1}/{max_retries}): {e}", 'WARNING')
            time.sleep(retry_delay)
            retry_delay *= 2
            continue
          else:
            self._log(f"Failed to place exit order for {ticker} after {max_retries} attempts: {e}", 'ERROR')
            if self.notifier:
              self.notifier.send_message(f"❌ Failed to exit long {ticker}: {str(e)}")
            return False, None, None

      if order_id is None:
        return False, None, None

      # Wait and check if filled
      time.sleep(3)

      # Check order status with retry
      for attempt in range(3):
        try:
          filled_order = self.trading_client.get_order_by_id(order_id)
          break
        except Exception as e:
          if attempt < 2:
            self._log(f"Error checking order status (attempt {attempt + 1}/3): {e}", 'WARNING')
            time.sleep(2)
            continue
          else:
            self._log(f"Cannot verify order status for {ticker}: {e}", 'ERROR')
            return False, order_id, None

      if filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        self._log(f"Long exit filled: {ticker} at ${filled_price:.2f}")

        if self.logger:
          self.logger.log_order('LONG_EXIT', ticker, 'FILLED', {
            'order_id': order_id,
            'units': units,
            'filled_price': filled_price
          })

        return True, order_id, filled_price

      else:
        self._log(f"Long exit order pending for {ticker}, status: {filled_order.status}", 'WARNING')
        if self.logger:
          self.logger.log_order('LONG_EXIT', ticker, 'PENDING', {
            'order_id': order_id,
            'status': filled_order.status
          })
        return False, order_id, None

    except Exception as e:
      self._log(f"Error placing long exit order for {ticker}: {e}", 'ERROR')
      if self.notifier:
        self.notifier.send_message(f"❌ Error exiting long {ticker}: {str(e)}")
      return False, None, None

  def place_short_exit_order(self, ticker, units, target_price, reason, is_stop_loss=False):
    """
    Place a short exit order (buy to cover)

    Args:
      ticker: Stock symbol
      units: Number of shares
      target_price: Target exit price
      reason: Reason for exit

    Returns:
      Tuple of (success, order_id, filled_price)
    """
    try:
      # Check for existing open orders
      try:
        request = GetOrdersRequest(
          status=QueryOrderStatus.OPEN,
          symbols=[ticker],
          limit=10
        )
        open_orders = self.trading_client.get_orders(request)

        # Check if there's already a buy order (exit order for shorts)
        existing_buy = [o for o in open_orders if o.side == OrderSide.BUY]
        if existing_buy:
          self._log(f"Buy order already exists for {ticker}: {existing_buy[0].id}", 'WARNING')
          return False, None, None

        # Cancel any sell orders to free up margin
        sell_orders = [o for o in open_orders if o.side == OrderSide.SELL]
        if sell_orders:
          self._log(f"Cancelling {len(sell_orders)} sell orders for {ticker} to free margin")
          for order in sell_orders:
            try:
              self.trading_client.cancel_order_by_id(order.id)
              self._log(f"Cancelled order {order.id}")
              time.sleep(0.5)
            except Exception as e:
              self._log(f"Error cancelling order {order.id}: {e}", 'ERROR')

      except Exception as e:
        self._log(f"Error checking existing orders for {ticker}: {e}", 'WARNING')

      # Calculate prices - for short exits (buy to cover), stop is ABOVE current price
      stop_price = round(target_price, 2)
      # Use wider 2% margin for stop-loss orders to ensure fills, 0.5% for exit signals
      slippage = 0.02 if is_stop_loss else 0.005
      limit_price = round(stop_price * (1 + slippage), 2)

      # Round units to 8 decimal places for Alpaca's precision
      units = round(float(units), 8)

      self._log(f"Placing short exit order for {ticker}: units={units:.4f}, "
           f"stop=${stop_price:.2f}, limit=${limit_price:.2f}")

      # Place stop-limit buy order to cover
      order_data = StopLimitOrderRequest(
        symbol=ticker,
        qty=units,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        stop_price=stop_price,
        limit_price=limit_price
      )

      order = self.trading_client.submit_order(order_data)
      order_id = str(order.id)

      # Notify immediately
      self._notify("📤 SHORT EXIT ORDER PLACED", {
        "Ticker": ticker,
        "Reason": reason,
        "Order ID": order_id,
        "Units": f"{units:.4f}",
        "Stop Price": f"${stop_price:.2f}",
        "Limit Price": f"${limit_price:.2f}",
        "Status": "PENDING"
      })

      if self.logger:
        self.logger.log_order('SHORT_EXIT', ticker, 'PLACED', {
          'order_id': order_id,
          'units': units,
          'stop_price': stop_price,
          'limit_price': limit_price,
          'reason': reason
        })

      # Wait and check if filled
      time.sleep(3)

      # Check order status with retry
      for attempt in range(3):
        try:
          filled_order = self.trading_client.get_order_by_id(order_id)
          break
        except Exception as e:
          if attempt < 2:
            self._log(f"Error checking order status (attempt {attempt + 1}/3): {e}", 'WARNING')
            time.sleep(2)
            continue
          else:
            self._log(f"Cannot verify order status for {ticker}: {e}", 'ERROR')
            return False, order_id, None

      if filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        self._log(f"Short exit filled: {ticker} at ${filled_price:.2f}")

        if self.logger:
          self.logger.log_order('SHORT_EXIT', ticker, 'FILLED', {
            'order_id': order_id,
            'units': units,
            'filled_price': filled_price
          })

        return True, order_id, filled_price

      else:
        self._log(f"Short exit order pending for {ticker}, status: {filled_order.status}", 'WARNING')
        if self.logger:
          self.logger.log_order('SHORT_EXIT', ticker, 'PENDING', {
            'order_id': order_id,
            'status': filled_order.status
          })
        return False, order_id, None

    except Exception as e:
      self._log(f"Error placing short exit order for {ticker}: {e}", 'ERROR')
      if self.notifier:
        self.notifier.send_message(f"❌ Error exiting short {ticker}: {str(e)}")
      return False, None, None

  def place_market_exit_order(self, ticker, units, side='long'):
    """
    Place a market order to exit position immediately

    Args:
      ticker: Stock symbol
      units: Number of shares
      side: 'long' or 'short'

    Returns:
      Tuple of (success, order_id, filled_price)
    """
    try:
      # Round units to 8 decimal places for Alpaca's precision
      units = round(float(units), 8)

      order_side = OrderSide.SELL if side == 'long' else OrderSide.BUY
      self._log(f"Placing MARKET {order_side.name.lower()} order for {ticker}: {units:.4f} units")

      order_data = MarketOrderRequest(
        symbol=ticker,
        qty=units,
        side=order_side,
        time_in_force=TimeInForce.DAY
      )

      order = self.trading_client.submit_order(order_data)
      order_id = str(order.id)

      self._log(f"Market order placed: {order_id}")
      if self.logger:
        self.logger.log_order(f'{side.upper()}_EXIT_MARKET', ticker, 'PLACED', {
          'order_id': order_id,
          'units': units,
          'order_type': 'MARKET'
        })

      # Wait for order to fill
      time.sleep(2)

      # Get filled order details
      max_retries = 10
      filled_order = None

      for attempt in range(max_retries):
        try:
          filled_order = self.trading_client.get_order_by_id(order_id)
          if filled_order.status == 'filled':
            break
          elif filled_order.status in ['pending_new', 'accepted', 'new']:
            self._log(f"Order still pending (attempt {attempt+1}/{max_retries}), waiting...")
            time.sleep(2)
          else:
            self._log(f"Order status: {filled_order.status}", 'WARNING')
            break
        except Exception as e:
          self._log(f"Error checking order status (attempt {attempt+1}/{max_retries}): {e}", 'WARNING')
          if attempt < max_retries - 1:
            time.sleep(2)
          else:
            raise

      if filled_order and filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        self._log(f"✅ {ticker} {side} exited at ${filled_price:.2f}")

        if self.logger:
          self.logger.log_order(f'{side.upper()}_EXIT_MARKET', ticker, 'FILLED', {
            'order_id': order_id,
            'units': units,
            'filled_price': filled_price
          })

        return True, order_id, filled_price
      else:
        self._log(f"❌ Market order for {ticker} not filled", 'ERROR')
        return False, order_id, None

    except Exception as e:
      self._log(f"❌ Error placing market exit order for {ticker}: {e}", 'ERROR')
      return False, None, None

  @retry_on_connection_error(max_retries=3, initial_delay=2, backoff=2)
  def get_open_orders(self, ticker=None):
    """
    Get open orders

    Args:
      ticker: Optional ticker to filter by

    Returns:
      List of open orders
    """
    try:
      request = GetOrdersRequest(
        status=QueryOrderStatus.OPEN,
        symbols=[ticker] if ticker else None,
        limit=500
      )
      return self.trading_client.get_orders(request)
    except Exception as e:
      self._log(f"Error getting open orders: {e}", 'ERROR')
      return []

  def cancel_order(self, order_id):
    """
    Cancel an order

    Args:
      order_id: Order ID to cancel

    Returns:
      True if successful, False otherwise
    """
    try:
      self.trading_client.cancel_order_by_id(order_id)
      self._log(f"Cancelled order {order_id}")
      return True
    except Exception as e:
      self._log(f"Error cancelling order {order_id}: {e}", 'ERROR')
      return False

  def cancel_all_orders(self):
    """Cancel all open orders"""
    try:
      self._log("Cancelling all open orders...")
      self.trading_client.cancel_orders()
      self._log("All open orders cancelled")
      return True
    except Exception as e:
      self._log(f"Error cancelling orders: {e}", 'ERROR')
      return False

  def get_buying_power(self):
    """Get available buying power"""
    try:
      account = self.trading_client.get_account()
      return float(account.buying_power)
    except Exception as e:
      self._log(f"Error getting buying power: {e}", 'ERROR')
      return 0
