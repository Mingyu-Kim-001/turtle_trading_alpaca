"""
Turtle Trading System with Long and Short Positions

This module orchestrates all components to implement the Turtle Trading strategy
with support for both long and short positions.

Dual System Logic with System 2 Priority:
- System 1 (20-10): Entry on 20-day high/low, exit on 10-day low/high
- System 2 (55-20): Entry on 55-day high/low, exit on 20-day low/high
- Priority: System 2 > System 1 (when both signal for same ticker)
- Only one position per ticker at a time
"""

import sys
import os
import inspect

# Add the project root to the Python path
# This allows the script to be run from anywhere and still find the correct modules
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

import os
import time
import json
import pandas as pd
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus, OrderStatus

from system_long_short.utils import DailyLogger, SlackNotifier, StateManager
from system_long_short.core import (
  DataProvider,
  IndicatorCalculator,
  SignalGenerator,
  PositionManager,
  OrderManager
)


class TurtleTradingLS:
  """Main Turtle Trading System with Long and Short Positions"""

  def __init__(self, api_key, api_secret, slack_token, slack_channel,
        universe_file='system_long_short/ticker_universe.txt', paper=True,
        max_slippage=0.005,
        enable_longs=True, enable_shorts=True,
        enable_system1=True, enable_system2=False,
        check_shortability=False, risk_per_unit=0.005):
    """
    Initialize Turtle Trading System with Long/Short support

    Args:
      api_key: Alpaca API key
      api_secret: Alpaca API secret
      slack_token: Slack bot token
      slack_channel: Slack channel ID
      universe_file: File containing ticker universe
      paper: Whether to use paper trading
      max_slippage: Maximum slippage for limit prices (default 0.005 = 0.5%)
      enable_longs: Whether to enable long positions
      enable_shorts: Whether to enable short selling
      enable_system1: Whether to enable System 1 (20-10)
      enable_system2: Whether to enable System 2 (55-20)
      check_shortability: Whether to check if tickers are shortable
      risk_per_unit: Risk per unit as fraction of account equity (default 0.005 = 0.5%)
    """
    # Validate configuration
    if not enable_longs and not enable_shorts:
      raise ValueError("At least one of enable_longs or enable_shorts must be True")
    if not enable_system1 and not enable_system2:
      raise ValueError("At least one of enable_system1 or enable_system2 must be True")

    # Initialize Alpaca trading client
    self.trading_client = TradingClient(api_key, api_secret, paper=paper)

    # Initialize components
    self.data_provider = DataProvider(api_key, api_secret)
    self.indicator_calculator = IndicatorCalculator()
    self.signal_generator = SignalGenerator()
    self.position_manager = PositionManager()
    self.state = StateManager()
    self.logger = DailyLogger()
    self.slack = SlackNotifier(slack_token, slack_channel)
    self.order_manager = OrderManager(
      self.trading_client,
      self.logger,
      self.slack,
      max_slippage
    )

    # Load ticker universe
    self.load_universe(universe_file)

    # Trading configuration
    self.enable_longs = enable_longs
    self.enable_shorts = enable_shorts
    self.enable_system1 = enable_system1
    self.enable_system2 = enable_system2
    self.check_shortability = check_shortability
    self.risk_per_unit = risk_per_unit
    self.shortable_tickers = set()
    self.htb_exclusions = set()

    # Determine if we need to track systems (only when both systems are enabled)
    self.track_systems = enable_system1 and enable_system2

    if self.enable_shorts:
      self._load_htb_exclusions()
      if self.check_shortability:
        self._load_shortable_tickers()

    # Load fractionable tickers
    self.fractionable_tickers = set()
    self._load_fractionable_tickers()

    # Track daily PnL
    self.daily_pnl = 0  # Realized P&L from closed positions
    self.starting_equity = None  # Starting equity at market open

    # Log configuration
    config_parts = []
    if enable_longs and enable_shorts:
      config_parts.append("Long+Short")
    elif enable_longs:
      config_parts.append("Long only")
    else:
      config_parts.append("Short only")

    if enable_system1 and enable_system2:
      config_parts.append("Dual System (S1+S2)")
    elif enable_system1:
      config_parts.append("System 1 only")
    else:
      config_parts.append("System 2 only")

    self.logger.log("Turtle Trading System (Long/Short) initialized")
    self.logger.log(f"Configuration: {' / '.join(config_parts)}")

    # Check for zombie orders on startup
    self.reconcile_zombie_orders()

  def load_universe(self, universe_file):
    """Load ticker universe from file"""
    if os.path.exists(universe_file):
      with open(universe_file, 'r') as f:
        self.universe = [line.strip() for line in f if line.strip()]
      print(f"Loaded {len(self.universe)} tickers from {universe_file}")
    else:
      self.universe = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
              'BRK.B', 'V', 'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM']
      print(f"Using default universe of {len(self.universe)} tickers")

      with open(universe_file, 'w') as f:
        f.write('\n'.join(self.universe))

  def _load_htb_exclusions(self):
    """
    Load hard-to-borrow exclusion list from file

    Tickers in htb_exclusions.txt will not be shorted, regardless of
    other shortability checks. Update this file based on your experience
    with stocks that have:
    - High borrow rates
    - Limited share availability
    - Short squeeze risk
    """
    htb_file = 'system_long_short/htb_exclusions.txt'
    if os.path.exists(htb_file):
      try:
        with open(htb_file, 'r') as f:
          self.htb_exclusions = {
            line.strip().upper() for line in f
            if line.strip() and not line.strip().startswith('#')
          }
        if self.htb_exclusions:
          self.logger.log(f"Loaded {len(self.htb_exclusions)} HTB exclusions: {', '.join(sorted(self.htb_exclusions))}")
      except Exception as e:
        self.logger.log(f"Error loading HTB exclusions: {e}", 'WARNING')
        self.htb_exclusions = set()
    else:
      self.logger.log("No system_long_short/htb_exclusions.txt found, all stocks eligible for shorting")

  def _load_shortable_tickers(self):
    """
    Load shortable tickers from Alpaca

    Note: This checks asset.shortable and asset.easy_to_borrow flags.
    However, these are general flags and don't guarantee:
    - Shares are currently available to borrow
    - Low borrow rates
    - No locate requirements

    Real-time availability is checked when orders are placed.
    """
    try:
      assets = self.trading_client.get_all_assets()
      self.shortable_tickers = {
        asset.symbol for asset in assets
        if (asset.tradable and
            asset.shortable and
            asset.status == 'active' and
            asset.easy_to_borrow)  # Filter out known HTB stocks
      }
      self.logger.log(f"Loaded {len(self.shortable_tickers)} shortable tickers from Alpaca")
      self.logger.log("Note: easy_to_borrow flag used, but HTB status can change intraday")
    except Exception as e:
      self.logger.log(f"Error loading shortable tickers: {e}", 'ERROR')
      self.shortable_tickers = set()

  def _load_fractionable_tickers(self):
    """
    Load fractionable tickers from Alpaca

    Checks asset.fractionable flag to determine which tickers support fractional trading.
    If a ticker is not fractionable, position sizes will be rounded to whole shares.
    """
    try:
      assets = self.trading_client.get_all_assets()
      self.fractionable_tickers = {
        asset.symbol for asset in assets
        if (asset.tradable and
            asset.fractionable and
            asset.status == 'active')
      }
      self.logger.log(f"Loaded {len(self.fractionable_tickers)} fractionable tickers from Alpaca")
    except Exception as e:
      self.logger.log(f"Error loading fractionable tickers: {e}", 'ERROR')
      self.fractionable_tickers = set()

  def _is_ticker_shortable(self, ticker):
    """
    Comprehensive check if ticker can be shorted

    Checks (in order):
    1. Is short selling enabled globally?
    2. Is ticker in HTB exclusion list?
    3. If check_shortability=True, is ticker in Alpaca's shortable list?

    Returns:
      bool: True if ticker can be shorted, False otherwise
    """
    if not self.enable_shorts:
      return False

    # Check HTB exclusion list
    if ticker.upper() in self.htb_exclusions:
      return False

    # Check Alpaca shortable list (if enabled)
    if self.check_shortability and ticker not in self.shortable_tickers:
      return False

    return True

  def reconcile_zombie_orders(self):
    """
    Check for zombie orders on startup - orders that exist in Alpaca but aren't tracked in state.
    This can happen if the system crashes or has connection errors after placing an order.
    """
    self.logger.log("Checking for zombie orders...")

    try:
      # Get all open orders from Alpaca
      from alpaca.trading.requests import GetOrdersRequest
      from alpaca.trading.enums import QueryOrderStatus
      request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
      open_orders = self.trading_client.get_orders(filter=request)

      # Build set of tracked order IDs
      tracked_order_ids = set(self.state.pending_entry_orders.values())
      tracked_order_ids.update(
        oid for oid in self.state.pending_pyramid_orders.values() if oid != 'PLACING'
      )
      tracked_order_ids.update(
        getattr(self.state, 'pending_exit_orders', {}).values()
      )

      # Find zombie orders
      zombies = []
      for order in open_orders:
        order_id = str(order.id)
        if order_id not in tracked_order_ids:
          zombies.append(order)

      if zombies:
        self.logger.log(f"Found {len(zombies)} zombie order(s):", 'WARNING')
        for order in zombies:
          self.logger.log(f"  - {order.symbol} {order.side.name} {order.qty} @ stop=${order.stop_price} (Order ID: {order.id})", 'WARNING')

        # Cancel all zombie orders
        for order in zombies:
          try:
            self.logger.log(f"Canceling zombie order for {order.symbol} (ID: {order.id})", 'WARNING')
            self.order_manager.cancel_order(str(order.id))
            self.logger.log(f"✓ Canceled zombie order for {order.symbol}", 'WARNING')
          except Exception as cancel_error:
            self.logger.log(f"Failed to cancel zombie order {order.id} for {order.symbol}: {cancel_error}", 'ERROR')

      else:
        self.logger.log("No zombie orders found.")

    except Exception as e:
      self.logger.log(f"Error checking for zombie orders: {e}", 'ERROR')

  def get_total_equity(self):
    """
    Calculate total equity (cash + long positions value + short unrealized P&L)

    Returns:
      Total equity as float
    """
    try:
      account = self.trading_client.get_account()
      return float(account.equity)
    except Exception as e:
      self.logger.log(f"Error getting total equity: {e}", 'ERROR')
      # Fallback: calculate manually
      try:
        account = self.trading_client.get_account()
        cash = float(account.cash)
        equity = cash

        # Add long position values
        for ticker in self.state.long_positions.keys():
          current_price = self.data_provider.get_current_price(ticker)
          if current_price:
            total_units = sum(p['units'] for p in self.state.long_positions[ticker]['pyramid_units'])
            equity += total_units * current_price

        # Add short position unrealized P&L
        for ticker in self.state.short_positions.keys():
          current_price = self.data_provider.get_current_price(ticker)
          if current_price:
            position = self.state.short_positions[ticker]
            _, _, _, pnl, _ = self.position_manager.calculate_short_position_pnl(
              position, current_price
            )
            equity += pnl

        return equity
      except Exception as e2:
        self.logger.log(f"Error calculating total equity manually: {e2}", 'ERROR')
        return 10000  # Fallback value

  def enter_long_position(self, ticker, units, target_price, n, system=1):
    """Enter or pyramid a long position"""
    is_pyramid = ticker in self.state.long_positions
    pyramid_level = len(self.state.long_positions[ticker]['pyramid_units']) + 1 if is_pyramid else 1

    # Place order
    success, order_id, filled_price = self.order_manager.place_long_entry_order(
      ticker, units, target_price, n, is_pyramid, pyramid_level
    )

    if success and filled_price:
      cost = units * filled_price

      # Update or create position
      if is_pyramid:
        self.state.long_positions[ticker] = self.position_manager.add_pyramid_unit(
          self.state.long_positions[ticker],
          units, filled_price, n, order_id
        )
        reason = f"Long pyramid level {pyramid_level}"
      else:
        self.state.long_positions[ticker] = self.position_manager.create_new_long_position(
          units, filled_price, n, order_id, system
        )
        reason = f"Long initial entry (S{system})"

      self.state.save_state()

      stop_price = self.state.long_positions[ticker]['stop_price']
      total_equity = self.get_total_equity()

      # Send notification
      self.slack.send_summary("🟢 LONG ENTRY EXECUTED", {
        "Ticker": ticker,
        "Type": reason,
        "Units": units,
        "Price": f"${filled_price:.2f}",
        "Cost": f"${cost:,.2f}",
        "Stop Price": f"${stop_price:.2f}",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True

    return False

  def enter_short_position(self, ticker, units, target_price, n, system=1):
    """Enter or pyramid a short position"""
    # Double-check shortability (in case signal was stale)
    if not self._is_ticker_shortable(ticker):
      self.logger.log(f"Cannot short {ticker}: not shortable (HTB or not in shortable list)", 'WARNING')
      return False

    is_pyramid = ticker in self.state.short_positions
    pyramid_level = len(self.state.short_positions[ticker]['pyramid_units']) + 1 if is_pyramid else 1

    # Check margin requirements
    margin_required = self.position_manager.calculate_margin_required(units, target_price)
    buying_power = self.order_manager.get_buying_power()

    if margin_required > buying_power:
      self.logger.log(f"Insufficient margin for short {ticker}: need ${margin_required:,.2f}, have ${buying_power:,.2f}", 'WARNING')
      return False

    # Place order
    success, order_id, filled_price = self.order_manager.place_short_entry_order(
      ticker, units, target_price, n, is_pyramid, pyramid_level
    )

    if success and filled_price:
      # Update or create position
      if is_pyramid:
        self.state.short_positions[ticker] = self.position_manager.add_pyramid_unit(
          self.state.short_positions[ticker],
          units, filled_price, n, order_id
        )
        reason = f"Short pyramid level {pyramid_level}"
      else:
        self.state.short_positions[ticker] = self.position_manager.create_new_short_position(
          units, filled_price, n, order_id, system
        )
        reason = f"Short initial entry (S{system})"

      self.state.save_state()

      stop_price = self.state.short_positions[ticker]['stop_price']
      total_equity = self.get_total_equity()

      # Send notification
      self.slack.send_summary("🔴 SHORT ENTRY EXECUTED", {
        "Ticker": ticker,
        "Type": reason,
        "Units": units,
        "Price": f"${filled_price:.2f}",
        "Margin": f"${margin_required:,.2f}",
        "Stop Price": f"${stop_price:.2f}",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True

    return False

  def exit_long_position(self, ticker, target_price, reason, is_stop_loss=False):
    """Exit entire long position"""
    if ticker not in self.state.long_positions:
      self.logger.log(f"No long position found for {ticker}", 'ERROR')
      return False

    position = self.state.long_positions[ticker]
    total_units, entry_value, _, _, _ = self.position_manager.calculate_long_position_pnl(
      position, target_price
    )

    # Place exit order
    success, order_id, filled_price = self.order_manager.place_long_exit_order(
      ticker, total_units, target_price, reason, is_stop_loss=is_stop_loss
    )

    if success and filled_price:
      # Calculate P&L
      _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_long_position_pnl(
        position, filled_price
      )

      # Track daily PnL
      self.daily_pnl += pnl

      # Update win tracking for System 1 only
      if position.get('system') == 1:
        self.state.last_trade_was_win[(ticker, 'long')] = pnl > 0
        self.logger.log(f"System 1 long trade for {ticker}: {'WIN' if pnl > 0 else 'LOSS'} (P&L: ${pnl:,.2f})")

      # Remove position
      del self.state.long_positions[ticker]
      self.state.save_state()

      total_equity = self.get_total_equity()

      # Send notification
      emoji = "🟢" if pnl > 0 else "🔴"
      self.slack.send_summary(f"{emoji} LONG EXIT EXECUTED", {
        "Ticker": ticker,
        "Reason": reason,
        "Units": f"{total_units:.4f}",
        "Exit Price": f"${filled_price:.2f}",
        "Entry Value": f"${entry_value:,.2f}",
        "Exit Value": f"${exit_value:,.2f}",
        "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True
    elif success and order_id:
      # Order placed but not filled immediately - mark as pending
      if not hasattr(self.state, 'pending_exit_orders'):
        self.state.pending_exit_orders = {}
      self.state.pending_exit_orders[ticker] = order_id
      self.state.save_state()
      self.logger.log(f"Long exit order for {ticker} is pending (order ID: {order_id})")
      return True

    return False

  def exit_short_position(self, ticker, target_price, reason, is_stop_loss=False):
    """Exit entire short position"""
    if ticker not in self.state.short_positions:
      self.logger.log(f"No short position found for {ticker}", 'ERROR')
      return False

    position = self.state.short_positions[ticker]
    total_units, entry_value, _, _, _ = self.position_manager.calculate_short_position_pnl(
      position, target_price
    )

    # Place exit order (buy to cover)
    success, order_id, filled_price = self.order_manager.place_short_exit_order(
      ticker, total_units, target_price, reason, is_stop_loss=is_stop_loss
    )

    if success and filled_price:
      # Calculate P&L
      _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_short_position_pnl(
        position, filled_price
      )

      # Track daily PnL
      self.daily_pnl += pnl

      # Update win tracking for System 1 only
      if position.get('system') == 1:
        self.state.last_trade_was_win[(ticker, 'short')] = pnl > 0
        self.logger.log(f"System 1 short trade for {ticker}: {'WIN' if pnl > 0 else 'LOSS'} (P&L: ${pnl:,.2f})")

      # Remove position
      del self.state.short_positions[ticker]
      self.state.save_state()

      total_equity = self.get_total_equity()

      # Send notification
      emoji = "🟢" if pnl > 0 else "🔴"
      self.slack.send_summary(f"{emoji} SHORT EXIT EXECUTED", {
        "Ticker": ticker,
        "Reason": reason,
        "Units": f"{total_units:.4f}",
        "Exit Price": f"${filled_price:.2f}",
        "Entry Value": f"${entry_value:,.2f}",
        "Exit Value": f"${exit_value:,.2f}",
        "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True
    elif success and order_id:
      # Order placed but not filled immediately - mark as pending
      if not hasattr(self.state, 'pending_exit_orders'):
        self.state.pending_exit_orders = {}
      self.state.pending_exit_orders[ticker] = order_id
      self.state.save_state()
      self.logger.log(f"Short exit order for {ticker} is pending (order ID: {order_id})")
      return True

    return False

  def cleanup_entry_queue_for_removed_tickers(self):
    """Remove entry signals for tickers no longer in universe"""
    if not self.state.entry_queue:
      return

    initial_count = len(self.state.entry_queue)
    removed_tickers = []

    # Filter out signals for tickers not in current universe
    filtered_queue = []
    for signal in self.state.entry_queue:
      if signal['ticker'] in self.universe:
        filtered_queue.append(signal)
      else:
        removed_tickers.append(f"{signal['ticker']} ({signal.get('side', 'long')})")

    if removed_tickers:
      self.state.entry_queue = filtered_queue
      self.state.save_state()
      self.logger.log(
        f"Cleaned entry queue: removed {len(removed_tickers)} signal(s) for tickers no longer in universe: {', '.join(removed_tickers)}",
        'INFO'
      )
      self.logger.log(f"Entry queue: {initial_count} -> {len(filtered_queue)} signals")

  def detect_and_adjust_for_deposits_withdrawals(self):
    """
    Detect mid-session deposits/withdrawals and adjust starting_equity baseline

    This ensures daily PnL reports are accurate even if cash is added/removed during trading.
    Compares actual equity with expected equity (starting + realized + unrealized P&L).
    """
    if self.starting_equity is None:
      return

    try:
      account = self.trading_client.get_account()
      current_equity = float(account.equity)

      # Calculate unrealized P&L from all positions
      unrealized_pnl = 0

      # Batch fetch prices for all positions
      all_tickers = list(self.state.long_positions.keys()) + list(self.state.short_positions.keys())
      if all_tickers:
        current_prices = self.data_provider.get_current_prices_batch(all_tickers)

        for ticker, position in self.state.long_positions.items():
          current_price = current_prices.get(ticker)
          if current_price:
            _, _, _, pnl, _ = self.position_manager.calculate_long_position_pnl(position, current_price)
            unrealized_pnl += pnl

        for ticker, position in self.state.short_positions.items():
          current_price = current_prices.get(ticker)
          if current_price:
            _, _, _, pnl, _ = self.position_manager.calculate_short_position_pnl(position, current_price)
            unrealized_pnl += pnl

      # Expected equity = starting equity + realized P&L + unrealized P&L
      expected_equity = self.starting_equity + self.daily_pnl + unrealized_pnl
      equity_diff = current_equity - expected_equity

      # Use threshold of $100 to avoid false positives from rounding/slippage
      if abs(equity_diff) > 100:
        change_type = "Deposit" if equity_diff > 0 else "Withdrawal"
        self.logger.log(
          f"Account balance change detected: ${equity_diff:+,.2f}",
          'WARNING'
        )
        self.logger.log(f"  → {change_type} detected: ${abs(equity_diff):,.2f}", 'WARNING')

        # Adjust starting equity to maintain accurate daily P&L
        self.starting_equity += equity_diff
        self.logger.log(
          f"  → Adjusted starting equity baseline: ${self.starting_equity:,.2f}",
          'WARNING'
        )

        # Send Slack notification
        emoji = "💰" if equity_diff > 0 else "💸"
        self.slack.send_summary(f"{emoji} Account Balance Change Detected", {
          "Type": change_type,
          "Amount": f"${abs(equity_diff):,.2f}",
          "New Starting Equity": f"${self.starting_equity:,.2f}",
          "Current Equity": f"${current_equity:,.2f}",
          "Note": "Daily P&L baseline adjusted"
        })

    except Exception as e:
      self.logger.log(f"Error detecting deposits/withdrawals: {e}", 'ERROR')

  def check_long_stops(self):
    """Check if any long positions hit stop loss"""
    if not self.state.long_positions:
      return

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.long_positions.items()):
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Managing long position for {ticker} (removed from universe)", 'INFO')

      # Check for pending exit order to prevent duplicates
      if ticker in getattr(self.state, 'pending_exit_orders', {}):
        continue

      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      stop_price = position['stop_price']

      if current_price <= stop_price * 1.005:
        self.logger.log(f"Long stop loss triggered for {ticker}: ${current_price:.2f} <= ${stop_price * 1.005:.2f}")
        self.exit_long_position(ticker, stop_price, 'Stop loss', is_stop_loss=True)

  def check_short_stops(self):
    """Check if any short positions hit stop loss"""
    if not self.state.short_positions:
      return

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.short_positions.items()):
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Managing short position for {ticker} (removed from universe)", 'INFO')

      # Check for pending exit order to prevent duplicates
      if ticker in getattr(self.state, 'pending_exit_orders', {}):
        continue

      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      stop_price = position['stop_price']

      if current_price >= stop_price * 0.995:
        self.logger.log(f"Short stop loss triggered for {ticker}: ${current_price:.2f} >= ${stop_price * 0.995:.2f}")
        self.exit_short_position(ticker, stop_price, 'Stop loss', is_stop_loss=True)

  def check_long_exit_signals(self):
    """Check if any long positions hit exit signals"""
    if not self.state.long_positions:
      return

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.long_positions.items()):
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Checking exit signals for long {ticker} (removed from universe)", 'INFO')

      # Check for pending exit order to prevent duplicates
      if ticker in getattr(self.state, 'pending_exit_orders', {}):
        continue

      df = self.data_provider.get_historical_data(ticker, days=30)
      if df is None:
        continue

      df = self.indicator_calculator.calculate_indicators(df)
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      # Get system from position (default to 1 for backwards compatibility)
      system = position.get('system', 1)
      exit_level = '10-day' if system == 1 else '20-day'

      if self.signal_generator.check_long_exit_signal(df, current_price, system):
        self.logger.log(f"Long exit signal for {ticker} (System {system})")
        self.exit_long_position(ticker, current_price, f'Exit signal ({exit_level} low, S{system})')

  def check_short_exit_signals(self):
    """Check if any short positions hit exit signals"""
    if not self.state.short_positions:
      return

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.short_positions.items()):
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Checking exit signals for short {ticker} (removed from universe)", 'INFO')

      # Check for pending exit order to prevent duplicates
      if ticker in getattr(self.state, 'pending_exit_orders', {}):
        continue

      df = self.data_provider.get_historical_data(ticker, days=30)
      if df is None:
        continue

      df = self.indicator_calculator.calculate_indicators(df)
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      # Get system from position (default to 1 for backwards compatibility)
      system = position.get('system', 1)
      exit_level = '10-day' if system == 1 else '20-day'

      if self.signal_generator.check_short_exit_signal(df, current_price, system):
        self.logger.log(f"Short exit signal for {ticker} (System {system})")
        self.exit_short_position(ticker, current_price, f'Exit signal ({exit_level} high, S{system})')

  def check_long_pyramid_opportunities(self):
    """Check if any long positions can pyramid"""
    if not self.state.long_positions:
      return

    total_equity = self.get_total_equity()

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in self.state.long_positions.items():
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Checking pyramid opportunities for long {ticker} (removed from universe)", 'INFO')

      # Check limits
      if not self.position_manager.can_pyramid(position):
        continue

      # Check for pending pyramid order
      if ticker in self.state.pending_pyramid_orders:
        continue

      # Get current price
      current_price = current_prices.get(ticker)
      if current_price is None:
        continue

      # Use initial N and initial units from position
      initial_n = position.get('initial_n')
      initial_units = position.get('initial_units')

      if initial_n is None or initial_units is None or initial_n == 0:
        self.logger.log(f"Missing initial_n or initial_units for {ticker}, skipping pyramid", 'WARNING')
        continue

      # Check pyramid opportunity
      # Use FIRST pyramid (initial entry) for calculating trigger, not last
      initial_entry_price = position['pyramid_units'][0]['entry_price']
      pyramid_count = len(position['pyramid_units'])

      # Calculate pyramid trigger based on initial entry and pyramid count
      # This ensures pyramids at 0.5N, 1.0N, 1.5N from initial entry
      pyramid_entry_price = initial_entry_price + (pyramid_count * 0.5 * initial_n)

      if self.signal_generator.check_long_pyramid_opportunity(
          initial_entry_price, current_price, initial_n, threshold=pyramid_count * 0.5):
        pyramid_level = pyramid_count + 1

        # Log detailed pyramid trigger information
        self.logger.log_pyramid_trigger(
          ticker, 'LONG', pyramid_level, pyramid_entry_price,
          current_price, initial_entry_price, initial_n
        )

        # Check if current price is within trigger threshold (like entry queue logic)
        trigger_threshold = pyramid_entry_price * 0.995
        if current_price < trigger_threshold:
          self.logger.log(f"LONG {ticker}: Price not at trigger yet ({current_price:.2f} < {trigger_threshold:.2f})")
          continue

        # Use same units as initial entry
        units = initial_units

        cost = units * pyramid_entry_price
        buying_power = self.order_manager.get_buying_power()

        if cost <= buying_power:
          # Mark as pending BEFORE placing order to prevent duplicate triggers
          self.state.pending_pyramid_orders[ticker] = 'PLACING'
          self.state.save_state()
          self.logger.log(f"Marked {ticker} as pending pyramid to prevent duplicates")

          success = self.enter_long_position(ticker, units, pyramid_entry_price, initial_n)

          if success:
            # Order filled immediately, position updated, remove pending marker
            if ticker in self.state.pending_pyramid_orders:
              del self.state.pending_pyramid_orders[ticker]
              self.state.save_state()
              self.logger.log(f"Removed pending marker for {ticker} (filled immediately)")
          else:
            # Track actual pending order
            open_orders = self.order_manager.get_open_orders(ticker)
            order_found = False
            for order in open_orders:
              if order.side.name == 'BUY':
                self.state.pending_pyramid_orders[ticker] = str(order.id)
                # Clear timestamp since we found the order
                if ticker in self.state.placing_marker_timestamps:
                  del self.state.placing_marker_timestamps[ticker]
                self.state.save_state()
                self.logger.log(f"Updated pending marker for {ticker} with order ID: {order.id}")
                order_found = True
                break

            if not order_found:
              # Order placement likely failed - remove PLACING marker
              self.logger.log(f"Could not find open order for {ticker}, order placement may have failed. Removing PLACING marker.", 'WARNING')
              if ticker in self.state.pending_pyramid_orders:
                del self.state.pending_pyramid_orders[ticker]
                self.state.save_state()

  def check_short_pyramid_opportunities(self):
    """Check if any short positions can pyramid"""
    if not self.state.short_positions:
      return

    total_equity = self.get_total_equity()

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in self.state.short_positions.items():
      # Enhanced logging for removed tickers
      if ticker not in self.universe:
        self.logger.log(f"Checking pyramid opportunities for short {ticker} (removed from universe)", 'INFO')

      # Check limits
      if not self.position_manager.can_pyramid(position):
        continue

      # Check for pending pyramid order
      if ticker in self.state.pending_pyramid_orders:
        continue

      # Get current price
      current_price = current_prices.get(ticker)
      if current_price is None:
        continue

      # Use initial N and initial units from position
      initial_n = position.get('initial_n')
      initial_units = position.get('initial_units')

      if initial_n is None or initial_units is None or initial_n == 0:
        self.logger.log(f"Missing initial_n or initial_units for {ticker}, skipping pyramid", 'WARNING')
        continue

      # Check pyramid opportunity
      # Use FIRST pyramid (initial entry) for calculating trigger, not last
      initial_entry_price = position['pyramid_units'][0]['entry_price']
      pyramid_count = len(position['pyramid_units'])

      # Calculate pyramid trigger based on initial entry and pyramid count
      # This ensures pyramids at 0.5N, 1.0N, 1.5N from initial entry
      pyramid_entry_price = initial_entry_price - (pyramid_count * 0.5 * initial_n)

      if self.signal_generator.check_short_pyramid_opportunity(
          initial_entry_price, current_price, initial_n, threshold=pyramid_count * 0.5):
        pyramid_level = pyramid_count + 1

        # Log detailed pyramid trigger information
        self.logger.log_pyramid_trigger(
          ticker, 'SHORT', pyramid_level, pyramid_entry_price,
          current_price, initial_entry_price, initial_n
        )

        # Check if current price is within trigger threshold (like entry queue logic)
        trigger_threshold = pyramid_entry_price * 1.005
        if current_price > trigger_threshold:
          self.logger.log(f"SHORT {ticker}: Price not at trigger yet ({current_price:.2f} > {trigger_threshold:.2f})")
          continue

        # Use same units as initial entry
        units = initial_units

        margin_required = self.position_manager.calculate_margin_required(units, pyramid_entry_price)
        buying_power = self.order_manager.get_buying_power()

        if margin_required <= buying_power:
          # Mark as pending BEFORE placing order to prevent duplicate triggers
          self.state.pending_pyramid_orders[ticker] = 'PLACING'
          self.state.save_state()
          self.logger.log(f"Marked {ticker} as pending pyramid to prevent duplicates")

          success = self.enter_short_position(ticker, units, pyramid_entry_price, initial_n)

          if success:
            # Order filled immediately, position updated, remove pending marker
            if ticker in self.state.pending_pyramid_orders:
              del self.state.pending_pyramid_orders[ticker]
              self.state.save_state()
              self.logger.log(f"Removed pending marker for {ticker} (filled immediately)")
          else:
            # Track actual pending order
            open_orders = self.order_manager.get_open_orders(ticker)
            order_found = False
            for order in open_orders:
              if order.side.name == 'SELL':
                self.state.pending_pyramid_orders[ticker] = str(order.id)
                # Clear timestamp since we found the order
                if ticker in self.state.placing_marker_timestamps:
                  del self.state.placing_marker_timestamps[ticker]
                self.state.save_state()
                self.logger.log(f"Updated pending marker for {ticker} with order ID: {order.id}")
                order_found = True
                break

            if not order_found:
              # Order placement likely failed - remove PLACING marker
              self.logger.log(f"Could not find open order for {ticker}, order placement may have failed. Removing PLACING marker.", 'WARNING')
              if ticker in self.state.pending_pyramid_orders:
                del self.state.pending_pyramid_orders[ticker]
                self.state.save_state()

  def process_entry_queue(self):
    """Process pending entry signals with System 2 priority"""
    if not self.state.entry_queue:
      return

    total_equity = self.get_total_equity()
    buying_power = self.order_manager.get_buying_power()
    processed = []

    # Filter signals that need checking
    signals_to_check = []
    for signal in self.state.entry_queue[:]:
      ticker = signal['ticker']
      side = signal.get('side', 'long')

      # Skip if already have a position
      if ticker in self.state.long_positions or ticker in self.state.short_positions:
        processed.append(ticker)
        continue

      # Check for pending entry order
      if ticker in self.state.pending_entry_orders:
        continue

      signals_to_check.append(signal)

    # Apply System 2 priority: if both systems signal for same ticker+side, keep only System 2
    # Signals are already sorted by (system, proximity) from signal_generator
    filtered_signals = []
    seen_ticker_side = set()

    for signal in signals_to_check:
      ticker_side_key = (signal['ticker'], signal.get('side', 'long'))

      if ticker_side_key not in seen_ticker_side:
        filtered_signals.append(signal)
        seen_ticker_side.add(ticker_side_key)
      # If we've seen this ticker+side before, it means System 2 already added it
      # (since signals are sorted with System 2 first), so skip this System 1 signal

    signals_to_check = filtered_signals

    # Batch fetch current prices for all tickers at once
    if signals_to_check:
      tickers_to_fetch = [s['ticker'] for s in signals_to_check]
      self.logger.log(f"Batch fetching prices for {len(tickers_to_fetch)} tickers...")
      current_prices = self.data_provider.get_current_prices_batch(tickers_to_fetch)
    else:
      current_prices = {}

    # Now process signals with pre-fetched prices
    for signal in signals_to_check:
      if buying_power <= 0:
        break

      ticker = signal['ticker']
      side = signal.get('side', 'long')
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      # Check entry trigger
      if side == 'long':
        entry_trigger = signal['entry_price'] * 0.995
        system = signal.get('system', 1)  # Get system from signal
        current_str = f"${current_price:.2f}" if current_price is not None else "None"
        self.logger.log(f"[DEBUG] LONG {ticker} (S{system}): entry_price=${signal['entry_price']:.2f}, trigger=${entry_trigger:.2f}, current={current_str}")
        if current_price >= entry_trigger:
          # Check if ticker supports fractional shares
          is_fractionable = ticker in self.fractionable_tickers
          units = self.position_manager.calculate_position_size(
            total_equity, signal['n'], self.risk_per_unit, fractional=is_fractionable
          )
          cost = units * signal['entry_price']
          self.logger.log(f"[DEBUG] {ticker}: units={units}, cost=${cost:,.2f}, buying_power=${buying_power:,.2f}")

          if cost <= buying_power:
            self.logger.log(f"[DEBUG] {ticker}: Attempting long entry (S{system})")
            success = self.enter_long_position(ticker, units, signal['entry_price'], signal['n'], system)
            if success:
              processed.append(ticker)
              buying_power -= cost
            else:
              self.logger.log(f"[DEBUG] {ticker}: Long entry FAILED", 'WARNING')
              # Track pending order
              open_orders = self.order_manager.get_open_orders(ticker)
              for order in open_orders:
                if order.side.name == 'BUY':
                  self.state.pending_entry_orders[ticker] = str(order.id)
                  self.state.save_state()
                  break
          else:
            self.logger.log(f"[DEBUG] {ticker}: BLOCKED - insufficient buying power (need ${cost:,.2f}, have ${buying_power:,.2f})", 'WARNING')
        else:
          self.logger.log(f"[DEBUG] {ticker}: Price not at trigger yet ({current_price:.2f} < {entry_trigger:.2f})")

      else:  # short
        entry_trigger = signal['entry_price'] * 1.005
        system = signal.get('system', 1)  # Get system from signal
        current_str = f"${current_price:.2f}" if current_price is not None else "None"
        self.logger.log(f"[DEBUG] SHORT {ticker} (S{system}): entry_price=${signal['entry_price']:.2f}, trigger=${entry_trigger:.2f}, current={current_str}")
        if current_price <= entry_trigger:
          # Check if ticker supports fractional shares
          is_fractionable = ticker in self.fractionable_tickers
          units = self.position_manager.calculate_position_size(
            total_equity, signal['n'], self.risk_per_unit, fractional=is_fractionable
          )
          margin_required = self.position_manager.calculate_margin_required(
            units, signal['entry_price']
          )
          self.logger.log(f"[DEBUG] {ticker}: units={units}, margin=${margin_required:,.2f}, buying_power=${buying_power:,.2f}")

          if margin_required <= buying_power:
            self.logger.log(f"[DEBUG] {ticker}: Attempting short entry (S{system})")
            success = self.enter_short_position(ticker, units, signal['entry_price'], signal['n'], system)
            if success:
              processed.append(ticker)
              buying_power -= margin_required
            else:
              self.logger.log(f"[DEBUG] {ticker}: Short entry FAILED", 'WARNING')
              # Track pending order
              open_orders = self.order_manager.get_open_orders(ticker)
              for order in open_orders:
                if order.side.name == 'SELL':
                  self.state.pending_entry_orders[ticker] = str(order.id)
                  self.state.save_state()
                  break
          else:
            self.logger.log(f"[DEBUG] {ticker}: BLOCKED - insufficient buying power (need ${margin_required:,.2f}, have ${buying_power:,.2f})", 'WARNING')
        else:
          self.logger.log(f"[DEBUG] {ticker}: Price not at trigger yet ({current_price:.2f} > {entry_trigger:.2f})")

    # Remove processed signals
    self.state.entry_queue = [s for s in self.state.entry_queue if s['ticker'] not in processed]
    if processed:
      self.state.save_state()

  def update_entry_queue(self):
    """Update the entry queue with fresh signals during intraday monitoring."""
    self.logger.log("Updating entry queue...")

    if self.enable_shorts:
      if self.check_shortability:
        shortable_for_signals = self.shortable_tickers - self.htb_exclusions
      else:
        shortable_for_signals = set(self.universe) - self.htb_exclusions
    else:
      shortable_for_signals = None

    signals = self.signal_generator.generate_entry_signals(
      self.universe,
      self.data_provider,
      self.indicator_calculator,
      self.state.long_positions,
      self.state.short_positions,
      enable_longs=self.enable_longs,
      enable_shorts=self.enable_shorts,
      enable_system1=self.enable_system1,
      enable_system2=self.enable_system2,
      shortable_tickers=shortable_for_signals,
      last_trade_was_win=self.state.last_trade_was_win
    )

    self.state.entry_queue = signals
    self.state.save_state()
    self.logger.log(f"Entry queue updated with {len(signals)} signals.")

  def check_pending_orders(self):
    """Check status of pending orders and update state if they are filled or canceled."""
    self.logger.log("Checking status of pending orders...")

    # Track timestamps for PLACING markers (to timeout zombie markers)
    if not hasattr(self.state, 'placing_marker_timestamps'):
      self.state.placing_marker_timestamps = {}

    # Check pending entry orders
    for ticker, order_id in list(self.state.pending_entry_orders.items()):
      try:
        order = self.trading_client.get_order_by_id(order_id)

        if order.status == OrderStatus.FILLED:
          self.logger.log(f"Pending entry order for {ticker} ({order_id}) has FILLED. Updating position state.")

          # Get filled details
          filled_qty = float(order.filled_qty)
          filled_price = float(order.filled_avg_price)
          side = order.side.name.lower()

          # Get current data to calculate N
          df = self.data_provider.get_historical_data(ticker, days=30)
          if df is not None:
            df = self.indicator_calculator.calculate_indicators(df)
            n = df['N'].iloc[-1]

            # Create position based on side
            if side == 'buy':  # Long position
              if ticker not in self.state.long_positions:
                self.state.long_positions[ticker] = self.position_manager.create_new_long_position(
                  filled_qty, filled_price, n, order_id
                )
                self.logger.log(f"Created long position for {ticker}: {filled_qty:.0f} units @ ${filled_price:.2f}")

                # Send notification
                stop_price = self.state.long_positions[ticker]['stop_price']
                total_equity = self.get_total_equity()
                self.slack.send_summary("🟢 LONG ENTRY EXECUTED (Pending Order Filled)", {
                  "Ticker": ticker,
                  "Type": "Long initial entry",
                  "Units": int(filled_qty),
                  "Price": f"${filled_price:.2f}",
                  "Cost": f"${filled_qty * filled_price:,.2f}",
                  "Stop Price": f"${stop_price:.2f}",
                  "Total Equity": f"${total_equity:,.2f}"
                })
            else:  # Short position
              if ticker not in self.state.short_positions:
                self.state.short_positions[ticker] = self.position_manager.create_new_short_position(
                  filled_qty, filled_price, n, order_id
                )
                self.logger.log(f"Created short position for {ticker}: {filled_qty:.0f} units @ ${filled_price:.2f}")

                # Send notification
                stop_price = self.state.short_positions[ticker]['stop_price']
                total_equity = self.get_total_equity()
                margin_required = self.position_manager.calculate_margin_required(filled_qty, filled_price)
                self.slack.send_summary("🔴 SHORT ENTRY EXECUTED (Pending Order Filled)", {
                  "Ticker": ticker,
                  "Type": "Short initial entry",
                  "Units": int(filled_qty),
                  "Price": f"${filled_price:.2f}",
                  "Margin": f"${margin_required:,.2f}",
                  "Stop Price": f"${stop_price:.2f}",
                  "Total Equity": f"${total_equity:,.2f}"
                })

          del self.state.pending_entry_orders[ticker]
          self.state.save_state()

        elif order.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
          # Check for partial fills before removing
          filled_qty = float(order.filled_qty) if order.filled_qty else 0

          if filled_qty > 0:
            self.logger.log(
              f"Pending entry order for {ticker} ({order_id}) is {order.status} with PARTIAL FILL: "
              f"{filled_qty}/{order.qty} filled",
              'WARNING'
            )

            # Process the partial fill
            filled_price = float(order.filled_avg_price)
            side = order.side.name.lower()

            # Get current data to calculate N
            df = self.data_provider.get_historical_data(ticker, days=30)
            if df is not None:
              df = self.indicator_calculator.calculate_indicators(df)
              n = df['N'].iloc[-1]

              # Create position based on side
              if side == 'buy':  # Long position
                if ticker not in self.state.long_positions:
                  self.state.long_positions[ticker] = self.position_manager.create_new_long_position(
                    filled_qty, filled_price, n, order_id
                  )
                  self.logger.log(f"Created long position for {ticker}: {filled_qty:.4f} units @ ${filled_price:.2f} (partial fill)")

                  # Send notification
                  stop_price = self.state.long_positions[ticker]['stop_price']
                  total_equity = self.get_total_equity()
                  self.slack.send_summary("🟢 LONG ENTRY EXECUTED (Partial Fill)", {
                    "Ticker": ticker,
                    "Type": "Long initial entry",
                    "Units": f"{filled_qty:.4f}",
                    "Requested": f"{order.qty}",
                    "Price": f"${filled_price:.2f}",
                    "Cost": f"${filled_qty * filled_price:,.2f}",
                    "Stop Price": f"${stop_price:.2f}",
                    "Total Equity": f"${total_equity:,.2f}",
                    "Note": f"Partial fill - order {order.status}"
                  })
              else:  # Short position
                if ticker not in self.state.short_positions:
                  self.state.short_positions[ticker] = self.position_manager.create_new_short_position(
                    filled_qty, filled_price, n, order_id
                  )
                  self.logger.log(f"Created short position for {ticker}: {filled_qty:.4f} units @ ${filled_price:.2f} (partial fill)")

                  # Send notification
                  stop_price = self.state.short_positions[ticker]['stop_price']
                  total_equity = self.get_total_equity()
                  margin_required = self.position_manager.calculate_margin_required(filled_qty, filled_price)
                  self.slack.send_summary("🔴 SHORT ENTRY EXECUTED (Partial Fill)", {
                    "Ticker": ticker,
                    "Type": "Short initial entry",
                    "Units": f"{filled_qty:.4f}",
                    "Requested": f"{order.qty}",
                    "Price": f"${filled_price:.2f}",
                    "Margin": f"${margin_required:,.2f}",
                    "Stop Price": f"${stop_price:.2f}",
                    "Total Equity": f"${total_equity:,.2f}",
                    "Note": f"Partial fill - order {order.status}"
                  })
          else:
            self.logger.log(f"Pending entry order for {ticker} ({order_id}) is {order.status}. Removing from pending list.")

          del self.state.pending_entry_orders[ticker]
          self.state.save_state()

      except Exception as e:
        self.logger.log(f"Could not get status for pending entry order {order_id} ({ticker}): {e}. Attempting to cancel order.", 'WARNING')
        try:
          # Try to cancel the order before removing from tracking to avoid zombie orders
          self.order_manager.cancel_order(order_id)
          self.logger.log(f"Successfully canceled pending entry order {order_id} ({ticker})", 'WARNING')
        except Exception as cancel_error:
          self.logger.log(f"Failed to cancel order {order_id} ({ticker}): {cancel_error}. Manual intervention may be required.", 'ERROR')

        # Remove from tracking after attempting cancellation
        del self.state.pending_entry_orders[ticker]
        self.state.save_state()

    # Check pending pyramid orders
    for ticker, order_id in list(self.state.pending_pyramid_orders.items()):
      # Handle 'PLACING' marker - these are temporary and will be updated or removed
      if order_id == 'PLACING':
        # Track how long this marker has been stuck
        if ticker not in self.state.placing_marker_timestamps:
          self.state.placing_marker_timestamps[ticker] = datetime.now().isoformat()
          self.logger.log(f"Found PLACING marker for {ticker}, tracking timeout", 'INFO')
        else:
          # Check if marker has been stuck for more than 2 minutes (2 monitoring cycles)
          marker_time = datetime.fromisoformat(self.state.placing_marker_timestamps[ticker])
          elapsed = (datetime.now() - marker_time).total_seconds()
          if elapsed > 120:  # 2 minutes
            self.logger.log(f"PLACING marker for {ticker} stuck for {elapsed:.0f}s, order likely failed. Removing marker.", 'WARNING')
            del self.state.pending_pyramid_orders[ticker]
            del self.state.placing_marker_timestamps[ticker]
            self.state.save_state()
          else:
            self.logger.log(f"Found PLACING marker for {ticker} ({elapsed:.0f}s elapsed), waiting for update", 'INFO')
        continue

      try:
        order = self.trading_client.get_order_by_id(order_id)

        if order.status == OrderStatus.FILLED:
          self.logger.log(f"Pending pyramid order for {ticker} ({order_id}) has FILLED. Updating position state.")

          # Get filled details
          filled_qty = float(order.filled_qty)
          filled_price = float(order.filled_avg_price)
          side = order.side.name.lower()

          # Update the position with the new pyramid unit
          if side == 'buy' and ticker in self.state.long_positions:
            position = self.state.long_positions[ticker]
            initial_n = position.get('initial_n')
            pyramid_level = len(position['pyramid_units']) + 1

            self.state.long_positions[ticker] = self.position_manager.add_pyramid_unit(
              position, filled_qty, filled_price, initial_n, order_id
            )
            self.logger.log(f"Added pyramid unit to long position {ticker}: level {pyramid_level}, {filled_qty:.0f} units @ ${filled_price:.2f}")

            # Send notification
            stop_price = self.state.long_positions[ticker]['stop_price']
            total_equity = self.get_total_equity()
            self.slack.send_summary("🟢 LONG PYRAMID EXECUTED (Pending Order Filled)", {
              "Ticker": ticker,
              "Type": f"Long pyramid level {pyramid_level}",
              "Units": int(filled_qty),
              "Price": f"${filled_price:.2f}",
              "Cost": f"${filled_qty * filled_price:,.2f}",
              "Stop Price": f"${stop_price:.2f}",
              "Total Equity": f"${total_equity:,.2f}"
            })

          elif side == 'sell' and ticker in self.state.short_positions:
            position = self.state.short_positions[ticker]
            initial_n = position.get('initial_n')
            pyramid_level = len(position['pyramid_units']) + 1

            self.state.short_positions[ticker] = self.position_manager.add_pyramid_unit(
              position, filled_qty, filled_price, initial_n, order_id
            )
            self.logger.log(f"Added pyramid unit to short position {ticker}: level {pyramid_level}, {filled_qty:.0f} units @ ${filled_price:.2f}")

            # Send notification
            stop_price = self.state.short_positions[ticker]['stop_price']
            total_equity = self.get_total_equity()
            margin_required = self.position_manager.calculate_margin_required(filled_qty, filled_price)
            self.slack.send_summary("🔴 SHORT PYRAMID EXECUTED (Pending Order Filled)", {
              "Ticker": ticker,
              "Type": f"Short pyramid level {pyramid_level}",
              "Units": int(filled_qty),
              "Price": f"${filled_price:.2f}",
              "Margin": f"${margin_required:,.2f}",
              "Stop Price": f"${stop_price:.2f}",
              "Total Equity": f"${total_equity:,.2f}"
            })
          else:
            self.logger.log(f"Warning: Filled pyramid order for {ticker} but position not found or side mismatch", 'WARNING')

          del self.state.pending_pyramid_orders[ticker]
          self.state.save_state()

        elif order.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
          # Check for partial fills before removing
          filled_qty = float(order.filled_qty) if order.filled_qty else 0

          if filled_qty > 0:
            self.logger.log(
              f"Pending pyramid order for {ticker} ({order_id}) is {order.status} with PARTIAL FILL: "
              f"{filled_qty}/{order.qty} filled",
              'WARNING'
            )

            # Process the partial fill
            filled_price = float(order.filled_avg_price)
            side = order.side.name.lower()

            # Update the position with the partially filled pyramid unit
            if side == 'buy' and ticker in self.state.long_positions:
              position = self.state.long_positions[ticker]
              initial_n = position.get('initial_n')
              pyramid_level = len(position['pyramid_units']) + 1

              self.state.long_positions[ticker] = self.position_manager.add_pyramid_unit(
                position, filled_qty, filled_price, initial_n, order_id
              )
              self.logger.log(f"Added pyramid unit to long position {ticker}: level {pyramid_level}, {filled_qty:.4f} units @ ${filled_price:.2f} (partial fill)")

              # Send notification
              stop_price = self.state.long_positions[ticker]['stop_price']
              total_equity = self.get_total_equity()
              self.slack.send_summary("🟢 LONG PYRAMID EXECUTED (Partial Fill)", {
                "Ticker": ticker,
                "Type": f"Long pyramid level {pyramid_level}",
                "Units": f"{filled_qty:.4f}",
                "Requested": f"{order.qty}",
                "Price": f"${filled_price:.2f}",
                "Cost": f"${filled_qty * filled_price:,.2f}",
                "Stop Price": f"${stop_price:.2f}",
                "Total Equity": f"${total_equity:,.2f}",
                "Note": f"Partial fill - order {order.status}"
              })

            elif side == 'sell' and ticker in self.state.short_positions:
              position = self.state.short_positions[ticker]
              initial_n = position.get('initial_n')
              pyramid_level = len(position['pyramid_units']) + 1

              self.state.short_positions[ticker] = self.position_manager.add_pyramid_unit(
                position, filled_qty, filled_price, initial_n, order_id
              )
              self.logger.log(f"Added pyramid unit to short position {ticker}: level {pyramid_level}, {filled_qty:.4f} units @ ${filled_price:.2f} (partial fill)")

              # Send notification
              stop_price = self.state.short_positions[ticker]['stop_price']
              total_equity = self.get_total_equity()
              margin_required = self.position_manager.calculate_margin_required(filled_qty, filled_price)
              self.slack.send_summary("🔴 SHORT PYRAMID EXECUTED (Partial Fill)", {
                "Ticker": ticker,
                "Type": f"Short pyramid level {pyramid_level}",
                "Units": f"{filled_qty:.4f}",
                "Requested": f"{order.qty}",
                "Price": f"${filled_price:.2f}",
                "Margin": f"${margin_required:,.2f}",
                "Stop Price": f"${stop_price:.2f}",
                "Total Equity": f"${total_equity:,.2f}",
                "Note": f"Partial fill - order {order.status}"
              })
            else:
              self.logger.log(f"Warning: Partial fill for pyramid order {ticker} but position not found or side mismatch", 'WARNING')
          else:
            self.logger.log(f"Pending pyramid order for {ticker} ({order_id}) is {order.status}. Removing from pending list.")

          del self.state.pending_pyramid_orders[ticker]
          self.state.save_state()

      except Exception as e:
        self.logger.log(f"Could not get status for pending pyramid order {order_id} ({ticker}): {e}. Attempting to cancel order.", 'WARNING')
        try:
          # Try to cancel the order before removing from tracking to avoid zombie orders
          self.order_manager.cancel_order(order_id)
          self.logger.log(f"Successfully canceled pending pyramid order {order_id} ({ticker})", 'WARNING')
        except Exception as cancel_error:
          self.logger.log(f"Failed to cancel order {order_id} ({ticker}): {cancel_error}. Manual intervention may be required.", 'ERROR')

        # Remove from tracking after attempting cancellation
        del self.state.pending_pyramid_orders[ticker]
        self.state.save_state()

    # Check pending exit orders
    if hasattr(self.state, 'pending_exit_orders'):
      for ticker, order_id in list(self.state.pending_exit_orders.items()):
        try:
          order = self.trading_client.get_order_by_id(order_id)

          if order.status == OrderStatus.FILLED:
            self.logger.log(f"Pending exit order for {ticker} ({order_id}) has FILLED. Closing position.")

            # Get filled details
            filled_qty = float(order.filled_qty)
            filled_price = float(order.filled_avg_price)
            side = order.side.name.lower()

            # Determine if this was a long or short exit
            if side == 'sell' and ticker in self.state.long_positions:
              # Long exit (sell)
              position = self.state.long_positions[ticker]
              _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_long_position_pnl(
                position, filled_price
              )

              # Track daily PnL
              self.daily_pnl += pnl

              # Update win tracking for System 1 only
              if position.get('system') == 1:
                self.state.last_trade_was_win[(ticker, 'long')] = pnl > 0
                self.logger.log(f"System 1 long trade for {ticker}: {'WIN' if pnl > 0 else 'LOSS'} (P&L: ${pnl:,.2f})")

              # Remove position
              del self.state.long_positions[ticker]

              total_equity = self.get_total_equity()

              # Send notification
              emoji = "🟢" if pnl > 0 else "🔴"
              self.slack.send_summary(f"{emoji} LONG EXIT EXECUTED (Pending Order Filled)", {
                "Ticker": ticker,
                "Units": f"{filled_qty:.4f}",
                "Exit Price": f"${filled_price:.2f}",
                "Entry Value": f"${entry_value:,.2f}",
                "Exit Value": f"${exit_value:,.2f}",
                "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
                "Total Equity": f"${total_equity:,.2f}"
              })

            elif side == 'buy' and ticker in self.state.short_positions:
              # Short exit (buy to cover)
              position = self.state.short_positions[ticker]
              _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_short_position_pnl(
                position, filled_price
              )

              # Track daily PnL
              self.daily_pnl += pnl

              # Update win tracking for System 1 only
              if position.get('system') == 1:
                self.state.last_trade_was_win[(ticker, 'short')] = pnl > 0
                self.logger.log(f"System 1 short trade for {ticker}: {'WIN' if pnl > 0 else 'LOSS'} (P&L: ${pnl:,.2f})")

              # Remove position
              del self.state.short_positions[ticker]

              total_equity = self.get_total_equity()

              # Send notification
              emoji = "🟢" if pnl > 0 else "🔴"
              self.slack.send_summary(f"{emoji} SHORT EXIT EXECUTED (Pending Order Filled)", {
                "Ticker": ticker,
                "Units": f"{filled_qty:.4f}",
                "Exit Price": f"${filled_price:.2f}",
                "Entry Value": f"${entry_value:,.2f}",
                "Exit Value": f"${exit_value:,.2f}",
                "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
                "Total Equity": f"${total_equity:,.2f}"
              })
            else:
              self.logger.log(f"Warning: Filled exit order for {ticker} but position not found or side mismatch", 'WARNING')

            del self.state.pending_exit_orders[ticker]
            self.state.save_state()

          elif order.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
            # Check for partial fills before removing
            filled_qty = float(order.filled_qty) if order.filled_qty else 0

            if filled_qty > 0:
              self.logger.log(
                f"Pending exit order for {ticker} ({order_id}) is {order.status} with PARTIAL FILL: "
                f"{filled_qty}/{order.qty} filled",
                'WARNING'
              )

              # Process the partial fill
              filled_price = float(order.filled_avg_price)
              side = order.side.name.lower()

              # Determine if this was a long or short exit
              if side == 'sell' and ticker in self.state.long_positions:
                # Long exit (sell) - partially closed
                position = self.state.long_positions[ticker]
                total_units = sum(p['units'] for p in position['pyramid_units'])

                # Calculate P&L for the partial exit
                avg_entry_price = sum(p['units'] * p['entry_price'] for p in position['pyramid_units']) / total_units
                pnl = (filled_price - avg_entry_price) * filled_qty
                pnl_pct = (pnl / (avg_entry_price * filled_qty)) * 100

                # Track daily PnL
                self.daily_pnl += pnl

                # Update position by removing units proportionally from pyramid levels
                remaining_to_remove = filled_qty
                updated_pyramid_units = []
                for unit in position['pyramid_units']:
                  if remaining_to_remove >= unit['units']:
                    # Remove entire unit
                    remaining_to_remove -= unit['units']
                  elif remaining_to_remove > 0:
                    # Partial removal from this unit
                    unit['units'] -= remaining_to_remove
                    unit['entry_value'] = unit['units'] * unit['entry_price']
                    updated_pyramid_units.append(unit)
                    remaining_to_remove = 0
                  else:
                    # No more to remove, keep unit
                    updated_pyramid_units.append(unit)

                if updated_pyramid_units:
                  # Position still exists with remaining units
                  position['pyramid_units'] = updated_pyramid_units
                  self.state.long_positions[ticker] = position
                  remaining_units = sum(p['units'] for p in updated_pyramid_units)
                  self.logger.log(f"Partially closed long position {ticker}: {filled_qty:.4f} units closed, {remaining_units:.4f} units remaining")
                else:
                  # Position fully closed
                  del self.state.long_positions[ticker]
                  self.logger.log(f"Fully closed long position {ticker} (partial fill matched total position)")

                  # Update win tracking for System 1 only
                  if position.get('system') == 1:
                    self.state.last_trade_was_win[(ticker, 'long')] = pnl > 0

                total_equity = self.get_total_equity()

                # Send notification
                emoji = "🟢" if pnl > 0 else "🔴"
                position_status = "CLOSED" if ticker not in self.state.long_positions else "PARTIALLY CLOSED"
                self.slack.send_summary(f"{emoji} LONG EXIT {position_status} (Partial Fill)", {
                  "Ticker": ticker,
                  "Units Closed": f"{filled_qty:.4f}",
                  "Units Requested": f"{order.qty}",
                  "Exit Price": f"${filled_price:.2f}",
                  "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
                  "Total Equity": f"${total_equity:,.2f}",
                  "Note": f"Partial fill - order {order.status}"
                })

              elif side == 'buy' and ticker in self.state.short_positions:
                # Short exit (buy to cover) - partially closed
                position = self.state.short_positions[ticker]
                total_units = sum(p['units'] for p in position['pyramid_units'])

                # Calculate P&L for the partial exit
                avg_entry_price = sum(p['units'] * p['entry_price'] for p in position['pyramid_units']) / total_units
                pnl = (avg_entry_price - filled_price) * filled_qty
                pnl_pct = (pnl / (avg_entry_price * filled_qty)) * 100

                # Track daily PnL
                self.daily_pnl += pnl

                # Update position by removing units proportionally from pyramid levels
                remaining_to_remove = filled_qty
                updated_pyramid_units = []
                for unit in position['pyramid_units']:
                  if remaining_to_remove >= unit['units']:
                    # Remove entire unit
                    remaining_to_remove -= unit['units']
                  elif remaining_to_remove > 0:
                    # Partial removal from this unit
                    unit['units'] -= remaining_to_remove
                    unit['entry_value'] = unit['units'] * unit['entry_price']
                    updated_pyramid_units.append(unit)
                    remaining_to_remove = 0
                  else:
                    # No more to remove, keep unit
                    updated_pyramid_units.append(unit)

                if updated_pyramid_units:
                  # Position still exists with remaining units
                  position['pyramid_units'] = updated_pyramid_units
                  self.state.short_positions[ticker] = position
                  remaining_units = sum(p['units'] for p in updated_pyramid_units)
                  self.logger.log(f"Partially closed short position {ticker}: {filled_qty:.4f} units closed, {remaining_units:.4f} units remaining")
                else:
                  # Position fully closed
                  del self.state.short_positions[ticker]
                  self.logger.log(f"Fully closed short position {ticker} (partial fill matched total position)")

                  # Update win tracking for System 1 only
                  if position.get('system') == 1:
                    self.state.last_trade_was_win[(ticker, 'short')] = pnl > 0

                total_equity = self.get_total_equity()

                # Send notification
                emoji = "🟢" if pnl > 0 else "🔴"
                position_status = "CLOSED" if ticker not in self.state.short_positions else "PARTIALLY CLOSED"
                self.slack.send_summary(f"{emoji} SHORT EXIT {position_status} (Partial Fill)", {
                  "Ticker": ticker,
                  "Units Closed": f"{filled_qty:.4f}",
                  "Units Requested": f"{order.qty}",
                  "Exit Price": f"${filled_price:.2f}",
                  "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
                  "Total Equity": f"${total_equity:,.2f}",
                  "Note": f"Partial fill - order {order.status}"
                })
              else:
                self.logger.log(f"Warning: Partial fill for exit order {ticker} but position not found or side mismatch", 'WARNING')
            else:
              self.logger.log(f"Pending exit order for {ticker} ({order_id}) is {order.status}. Removing from pending list.")

            del self.state.pending_exit_orders[ticker]
            self.state.save_state()

        except Exception as e:
          self.logger.log(f"Could not get status for pending exit order {order_id} ({ticker}): {e}. Attempting to cancel order.", 'WARNING')
          try:
            # Try to cancel the order before removing from tracking to avoid zombie orders
            self.order_manager.cancel_order(order_id)
            self.logger.log(f"Successfully canceled pending exit order {order_id} ({ticker})", 'WARNING')
          except Exception as cancel_error:
            self.logger.log(f"Failed to cancel order {order_id} ({ticker}): {cancel_error}. Manual intervention may be required.", 'ERROR')

          # CRITICAL: Verify if position actually exists in Alpaca before just removing from pending
          # If position doesn't exist in Alpaca but exists in our state, we have a sync issue
          try:
            alpaca_positions = self.trading_client.get_all_positions()
            alpaca_tickers = {p.symbol for p in alpaca_positions}

            if ticker not in alpaca_tickers:
              # Position doesn't exist in Alpaca - remove from our state too
              self.logger.log(f"Position {ticker} not found in Alpaca - removing from state to fix sync issue", 'WARNING')

              if ticker in self.state.long_positions:
                del self.state.long_positions[ticker]
                self.logger.log(f"Removed orphaned long position {ticker} from state", 'WARNING')
              elif ticker in self.state.short_positions:
                del self.state.short_positions[ticker]
                self.logger.log(f"Removed orphaned short position {ticker} from state", 'WARNING')
            else:
              self.logger.log(f"Position {ticker} still exists in Alpaca - will retry exit on next cycle", 'INFO')

          except Exception as verify_error:
            self.logger.log(f"Could not verify position existence for {ticker}: {verify_error}", 'ERROR')

          # Remove from tracking after attempting cancellation
          del self.state.pending_exit_orders[ticker]
          self.state.save_state()

  def daily_eod_analysis(self):
    """Run end-of-day analysis to generate entry signals"""
    self.logger.log("="*60)
    self.logger.log("RUNNING END-OF-DAY ANALYSIS")
    self.logger.log("="*60)

    self.logger.log_state_snapshot(self.state, 'EOD_start')
    self.slack.send_message("📊 Starting end-of-day analysis...", title="EOD Analysis")

    # Build list of tickers eligible for shorting
    # Start with all tickers if not checking shortability, otherwise use Alpaca's list
    if self.enable_shorts:
      if self.check_shortability:
        # Use Alpaca's shortable list, excluding HTB stocks
        shortable_for_signals = self.shortable_tickers - self.htb_exclusions
      else:
        # All universe tickers are eligible except HTB exclusions
        shortable_for_signals = set(self.universe) - self.htb_exclusions
    else:
      shortable_for_signals = None

    signals = self.signal_generator.generate_entry_signals(
      self.universe,
      self.data_provider,
      self.indicator_calculator,
      self.state.long_positions,
      self.state.short_positions,
      enable_longs=self.enable_longs,
      enable_shorts=self.enable_shorts,
      enable_system1=self.enable_system1,
      enable_system2=self.enable_system2,
      shortable_tickers=shortable_for_signals,
      last_trade_was_win=self.state.last_trade_was_win
    )

    self.state.entry_queue = signals
    self.state.save_state()
    self.logger.log_state_snapshot(self.state, 'EOD_complete')

    self.logger.log(f"Found {len(signals)} potential entry signals")

    if signals:
      long_signals = [s for s in signals if s.get('side') == 'long']
      short_signals = [s for s in signals if s.get('side') == 'short']

      top_signals = signals[:10]
      signal_text = "\n".join([
        f"• {s['ticker']} ({s.get('side', 'long').upper()}): ${s['current_price']:.2f} "
        f"(target: ${s['entry_price']:.2f}, {s['proximity']:.1f}%)"
        for s in top_signals
      ])

      self.slack.send_message(
        f"Found {len(signals)} entry signals\n"
        f"  Long: {len(long_signals)}, Short: {len(short_signals)}\n\n"
        f"Top 10:\n{signal_text}",
        title="📈 Entry Signals Generated"
      )

  def market_open_setup(self):
    """Setup routine at market open"""
    self.logger.log("="*60)
    self.logger.log("MARKET OPEN SETUP")
    self.logger.log("="*60)

    # SAFETY CHECK: Cancel any stale orders from previous day
    # This handles cases where post-market routine failed or didn't run
    self.logger.log("Checking for stale orders from previous day...")
    try:
      open_orders = self.order_manager.get_open_orders()
      if open_orders:
        self.logger.log(f"Found {len(open_orders)} stale orders - cancelling them", 'WARNING')
        for order in open_orders:
          try:
            self.order_manager.cancel_order(str(order.id))
            self.logger.log(f"  ✓ Cancelled stale {order.symbol} {order.side.name} order from previous day")
          except Exception as cancel_error:
            self.logger.log(f"  ✗ Failed to cancel stale order {order.id}: {cancel_error}", 'WARNING')

        # Clear pending order tracking
        self.state.pending_entry_orders = {}
        self.state.pending_pyramid_orders = {}
        if hasattr(self.state, 'pending_exit_orders'):
          self.state.pending_exit_orders = {}
        self.state.save_state()
      else:
        self.logger.log("No stale orders found - clean start ✓")
    except Exception as e:
      self.logger.log(f"Error checking for stale orders: {e}", 'WARNING')

    self.logger.log_state_snapshot(self.state, 'market_open')

    account = self.trading_client.get_account()

    # Capture starting equity for daily P&L calculation
    self.starting_equity = float(account.equity)

    summary = {
      "Equity": f"${float(account.equity):,.2f}",
      "Buying Power": f"${float(account.buying_power):,.2f}",
      "Long Positions": len(self.state.long_positions),
      "Short Positions": len(self.state.short_positions),
      "Entry Queue": len(self.state.entry_queue)
    }

    self.slack.send_summary("🔔 Market Open", summary)

  def intraday_monitor(self):
    """Main intraday monitoring loop"""
    self.logger.log("="*60)
    self.logger.log(f"INTRADAY MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    self.logger.log("="*60)

    try:
      # Check status of pending orders first
      self.check_pending_orders()
      time.sleep(0.5)

      # Update the entry queue at the beginning of each cycle
      self.update_entry_queue()
      time.sleep(0.5)

      # Clean up entry queue for any tickers removed from universe
      self.cleanup_entry_queue_for_removed_tickers()
      time.sleep(0.5)

      # Detect and adjust for mid-session deposits/withdrawals
      self.detect_and_adjust_for_deposits_withdrawals()
      time.sleep(0.5)

      self.logger.log_state_snapshot(self.state, f'intraday_{datetime.now().strftime("%H%M")}')

      self.logger.log("1. Checking long position stops...")
      self.check_long_stops()
      time.sleep(0.5)

      self.logger.log("2. Checking short position stops...")
      self.check_short_stops()
      time.sleep(0.5)

      self.logger.log("3. Checking long exit signals...")
      self.check_long_exit_signals()
      time.sleep(0.5)

      self.logger.log("4. Checking short exit signals...")
      self.check_short_exit_signals()
      time.sleep(0.5)

      self.logger.log("5. Checking long pyramid opportunities...")
      self.check_long_pyramid_opportunities()
      time.sleep(0.5)

      self.logger.log("6. Checking short pyramid opportunities...")
      self.check_short_pyramid_opportunities()
      time.sleep(0.5)

      self.logger.log("7. Processing entry queue...")
      self.process_entry_queue()

      total_equity = self.get_total_equity()
      self.logger.log(
        f"Status: {len(self.state.long_positions)} long, "
        f"{len(self.state.short_positions)} short, "
        f"{len(self.state.entry_queue)} pending entries"
      )
      self.logger.log(f"Total Equity: ${total_equity:,.2f}")

    except Exception as e:
      self.logger.log(f"Critical error in intraday monitor: {e}", 'ERROR')
      import traceback
      self.logger.log(traceback.format_exc(), 'ERROR')

  def post_market_routine(self):
    """Post-market routine - generate daily report"""
    self.logger.log("="*60)
    self.logger.log("POST-MARKET ROUTINE")
    self.logger.log("="*60)

    # CRITICAL: Check pending orders first to catch any fills from end of day
    # This is essential because the last intraday monitor runs before 1:00 PM,
    # but orders placed near market close may fill after the last check
    self.logger.log("Checking pending orders before generating end-of-day report...")
    try:
      self.check_pending_orders()
    except Exception as e:
      self.logger.log(f"Error checking pending orders in post-market routine: {e}", 'ERROR')

    self.logger.log_state_snapshot(self.state, 'market_close')

    # Get account info with retry logic
    account = None
    max_retries = 3
    for attempt in range(max_retries):
      try:
        account = self.trading_client.get_account()
        break
      except (ConnectionResetError, ConnectionError, Exception) as e:
        self.logger.log(f"Connection error getting account info (attempt {attempt + 1}/{max_retries}): {e}", 'WARNING')
        if attempt < max_retries - 1:
          time.sleep(2 * (attempt + 1))  # Exponential backoff
        else:
          self.logger.log(f"Failed to get account info after {max_retries} attempts", 'ERROR')
          # Use cached equity value as fallback
          account = None

    # Analyze daily orders with detailed breakdown
    daily_orders = self.logger.get_daily_orders()

    # Categorize orders
    long_entry_placed = len([o for o in daily_orders if o['type'] == 'LONG_ENTRY' and o['status'] == 'PLACED' and not o['details'].get('is_pyramid', False)])
    long_entry_filled = len([o for o in daily_orders if o['type'] == 'LONG_ENTRY' and o['status'] == 'FILLED' and not o['details'].get('is_pyramid', False)])
    long_pyramid_placed = len([o for o in daily_orders if o['type'] == 'LONG_ENTRY' and o['status'] == 'PLACED' and o['details'].get('is_pyramid', False)])
    long_pyramid_filled = len([o for o in daily_orders if o['type'] == 'LONG_ENTRY' and o['status'] == 'FILLED' and o['details'].get('is_pyramid', False)])

    short_entry_placed = len([o for o in daily_orders if o['type'] == 'SHORT_ENTRY' and o['status'] == 'PLACED' and not o['details'].get('is_pyramid', False)])
    short_entry_filled = len([o for o in daily_orders if o['type'] == 'SHORT_ENTRY' and o['status'] == 'FILLED' and not o['details'].get('is_pyramid', False)])
    short_pyramid_placed = len([o for o in daily_orders if o['type'] == 'SHORT_ENTRY' and o['status'] == 'PLACED' and o['details'].get('is_pyramid', False)])
    short_pyramid_filled = len([o for o in daily_orders if o['type'] == 'SHORT_ENTRY' and o['status'] == 'FILLED' and o['details'].get('is_pyramid', False)])

    long_exit_stoploss = len([o for o in daily_orders if o['type'] == 'LONG_EXIT' and o['status'] == 'FILLED' and 'stop loss' in o['details'].get('reason', '').lower()])
    long_exit_signal = len([o for o in daily_orders if o['type'] == 'LONG_EXIT' and o['status'] == 'FILLED' and 'exit signal' in o['details'].get('reason', '').lower()])
    short_exit_stoploss = len([o for o in daily_orders if o['type'] == 'SHORT_EXIT' and o['status'] == 'FILLED' and 'stop loss' in o['details'].get('reason', '').lower()])
    short_exit_signal = len([o for o in daily_orders if o['type'] == 'SHORT_EXIT' and o['status'] == 'FILLED' and 'exit signal' in o['details'].get('reason', '').lower()])

    # Calculate total daily P&L (including unrealized)
    current_equity = float(account.equity) if account else None
    if current_equity and self.starting_equity:
      total_pnl = current_equity - self.starting_equity
      unrealized_pnl = total_pnl - self.daily_pnl
    else:
      total_pnl = None
      unrealized_pnl = None

    summary = {
      "Total Daily P&L": f"${total_pnl:,.2f}" if total_pnl is not None else "N/A",
      "Realized P&L": f"${self.daily_pnl:,.2f}",
      "Unrealized P&L": f"${unrealized_pnl:,.2f}" if unrealized_pnl is not None else "N/A",
      "Equity": f"${current_equity:,.2f}" if current_equity else "N/A",
      "Buying Power": f"${float(account.buying_power):,.2f}" if account else "N/A",
      "─────": "─────",
      "Long Positions": len(self.state.long_positions),
      "Short Positions": len(self.state.short_positions),
      "──────": "──────",
      "Long Entries": f"{long_entry_filled}/{long_entry_placed} filled",
      "Long Pyramids": f"{long_pyramid_filled}/{long_pyramid_placed} filled",
      "Short Entries": f"{short_entry_filled}/{short_entry_placed} filled",
      "Short Pyramids": f"{short_pyramid_filled}/{short_pyramid_placed} filled",
      "───────": "───────",
      "Long Exits (Stop)": long_exit_stoploss,
      "Long Exits (Signal)": long_exit_signal,
      "Short Exits (Stop)": short_exit_stoploss,
      "Short Exits (Signal)": short_exit_signal
    }

    self.slack.send_summary("📊 Daily Summary", summary)

    # CRITICAL: Cancel all unfilled orders at end of day
    # Stop-limit orders that didn't fill during the day should be cancelled
    # This prevents stale orders from executing the next day
    self.logger.log("\nCancelling all unfilled orders at market close...")
    try:
      open_orders = self.order_manager.get_open_orders()
      if open_orders:
        self.logger.log(f"Found {len(open_orders)} open orders to cancel")
        cancelled_count = 0
        for order in open_orders:
          try:
            self.order_manager.cancel_order(str(order.id))
            self.logger.log(f"  ✓ Cancelled {order.symbol} {order.side.name} order (ID: {order.id})")
            cancelled_count += 1
          except Exception as cancel_error:
            self.logger.log(f"  ✗ Failed to cancel {order.symbol} order {order.id}: {cancel_error}", 'WARNING')

        self.logger.log(f"Cancelled {cancelled_count}/{len(open_orders)} orders")

        if cancelled_count > 0:
          self.slack.send_message(f"🧹 Cancelled {cancelled_count} unfilled order(s) at market close")
      else:
        self.logger.log("No open orders to cancel")

      # Clear pending order tracking since we cancelled everything
      self.state.pending_entry_orders = {}
      self.state.pending_pyramid_orders = {}
      if hasattr(self.state, 'pending_exit_orders'):
        self.state.pending_exit_orders = {}
      self.state.save_state()

    except Exception as e:
      self.logger.log(f"Error cancelling orders at market close: {e}", 'ERROR')

    # Reset daily PnL and starting equity
    self.daily_pnl = 0
    self.starting_equity = None

  def exit_all_positions_market(self):
    """Emergency exit all positions using market orders"""
    self.logger.log("="*60)
    self.logger.log("🚨 EMERGENCY EXIT: CLOSING ALL POSITIONS AT MARKET")
    self.logger.log("="*60)

    positions_to_exit = (
      list(self.state.long_positions.keys()) +
      list(self.state.short_positions.keys())
    )

    if not positions_to_exit:
      self.logger.log("No positions to exit", 'WARNING')
      self.slack.send_message("⚠️ No positions to exit")
      return

    # Cancel all open orders first
    self.order_manager.cancel_all_orders()
    time.sleep(1)

    self.logger.log(f"Exiting {len(positions_to_exit)} positions at market price")

    # Send initial notification
    self.slack.send_summary("🚨 EMERGENCY EXIT INITIATED", {
      "Positions to Close": len(positions_to_exit),
      "Long": len(self.state.long_positions),
      "Short": len(self.state.short_positions),
      "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    exit_results = []
    total_pnl = 0

    # Exit all long positions
    for ticker in list(self.state.long_positions.keys()):
      try:
        position = self.state.long_positions[ticker]
        total_units = sum(p['units'] for p in position['pyramid_units'])

        self.logger.log(f"\nExiting long {ticker}: {total_units:.0f} units")

        success, order_id, filled_price = self.order_manager.place_market_exit_order(
          ticker, total_units, 'long'
        )

        if success and filled_price:
          _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_long_position_pnl(
            position, filled_price
          )

          total_pnl += pnl

          exit_results.append({
            'ticker': ticker,
            'side': 'long',
            'status': 'SUCCESS',
            'units': total_units,
            'exit_price': filled_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
          })

          del self.state.long_positions[ticker]
        else:
          exit_results.append({
            'ticker': ticker,
            'side': 'long',
            'status': 'FAILED',
            'reason': 'Order not filled'
          })

      except Exception as e:
        self.logger.log(f"❌ Error exiting long {ticker}: {e}", 'ERROR')
        exit_results.append({
          'ticker': ticker,
          'side': 'long',
          'status': 'ERROR',
          'reason': str(e)
        })

    # Exit all short positions
    for ticker in list(self.state.short_positions.keys()):
      try:
        position = self.state.short_positions[ticker]
        total_units = sum(p['units'] for p in position['pyramid_units'])

        self.logger.log(f"\nExiting short {ticker}: {total_units:.0f} units")

        success, order_id, filled_price = self.order_manager.place_market_exit_order(
          ticker, total_units, 'short'
        )

        if success and filled_price:
          _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_short_position_pnl(
            position, filled_price
          )

          total_pnl += pnl

          exit_results.append({
            'ticker': ticker,
            'side': 'short',
            'status': 'SUCCESS',
            'units': total_units,
            'exit_price': filled_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
          })

          del self.state.short_positions[ticker]
        else:
          exit_results.append({
            'ticker': ticker,
            'side': 'short',
            'status': 'FAILED',
            'reason': 'Order not filled'
          })

      except Exception as e:
        self.logger.log(f"❌ Error exiting short {ticker}: {e}", 'ERROR')
        exit_results.append({
          'ticker': ticker,
          'side': 'short',
          'status': 'ERROR',
          'reason': str(e)
        })

    # Save final state
    self.state.save_state()

    # Send summary
    successful = [r for r in exit_results if r['status'] == 'SUCCESS']
    self.logger.log(f"\nSuccessful: {len(successful)}/{len(exit_results)}")
    self.logger.log(f"Total P&L: ${total_pnl:,.2f}")

    return exit_results

  def rebuild_state_from_broker(self, lookback_days=90, dry_run=True):
    """
    Rebuild trading_state_ls.json from Alpaca for long and short positions
    """
    from datetime import datetime, timedelta
    from collections import defaultdict

    self.logger.log("="*60)
    self.logger.log("REBUILDING STATE FROM BROKER (LONG/SHORT)")
    self.logger.log("="*60)

    # Step 1: Get current broker positions
    self.logger.log("\n📊 Step 1: Fetching current broker positions...")
    broker_positions = self.trading_client.get_all_positions()
    long_broker_pos = {p.symbol: p for p in broker_positions if p.side.name == 'LONG'}
    short_broker_pos = {p.symbol: p for p in broker_positions if p.side.name == 'SHORT'}

    if not broker_positions:
        self.logger.log("⚠️  No open positions at broker. Nothing to rebuild.")
        return None

    self.logger.log(f"Found {len(long_broker_pos)} long and {len(short_broker_pos)} short positions.")

    # Step 2: Fetch order history
    self.logger.log(f"\n📜 Step 2: Fetching order history (last {lookback_days} days)...")
    after_date = datetime.now() - timedelta(days=lookback_days)
    request = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500, after=after_date)
    all_orders = self.trading_client.get_orders(filter=request)

    filled_buys = [o for o in all_orders if o.side.name == 'BUY' and o.status.name == 'FILLED']
    filled_sells = [o for o in all_orders if o.side.name == 'SELL' and o.status.name == 'FILLED']
    self.logger.log(f"Found {len(filled_buys)} filled BUY and {len(filled_sells)} filled SELL orders.")

    # Step 3 & 4: Reconstruct positions for each side
    rebuilt_long_pos = self._reconstruct_positions('long', long_broker_pos, filled_buys, filled_sells, lookback_days)
    rebuilt_short_pos = self._reconstruct_positions('short', short_broker_pos, filled_sells, filled_buys, lookback_days)

    # Step 5: Build complete state
    self.logger.log("\n✅ Step 5: Building complete state...")
    rebuilt_state = {
        'long_positions': rebuilt_long_pos,
        'short_positions': rebuilt_short_pos,
        'entry_queue': [],
        'pending_pyramid_orders': {},
        'pending_entry_orders': {},
        'last_updated': datetime.now().isoformat()
    }
    self.logger.log(f"Rebuilt state: {len(rebuilt_long_pos)} long, {len(rebuilt_short_pos)} short positions")

    # Step 6: Save state
    if dry_run:
        self.logger.log("\n🔍 DRY RUN - State NOT saved. Run with --apply to save.")
    else:
        self.logger.log("\n💾 Saving rebuilt state...")
        # Backup and save
        import shutil
        backup_file = f"system_long_short/trading_state_ls_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            shutil.copy(self.state.state_file, backup_file)
            self.logger.log(f"  Old state backed up to: {backup_file}")
        except FileNotFoundError:
            pass # No old state to back up

        self.state.long_positions = rebuilt_long_pos
        self.state.short_positions = rebuilt_short_pos
        self.state.entry_queue = []
        self.state.pending_pyramid_orders = {}
        self.state.pending_entry_orders = {}
        self.state.save_state()
        self.logger.log("  ✅ State successfully rebuilt and saved!")

    self.logger.log("\n" + "="*60)
    return rebuilt_state

  def _reconstruct_positions(self, side, broker_positions, entry_orders, exit_orders, lookback_days):
    from collections import defaultdict

    self.logger.log(f"\n--- Reconstructing {side.upper()} positions ---")
    orders_by_ticker = defaultdict(list)
    for order in entry_orders:
        if order.symbol in broker_positions:
            orders_by_ticker[order.symbol].append({
                'id': str(order.id),
                'filled_qty': float(order.filled_qty),
                'filled_avg_price': float(order.filled_avg_price),
                'filled_at': order.filled_at
            })

    rebuilt_positions = {}
    for ticker, pos in broker_positions.items():
        broker_qty = abs(float(pos.qty))
        self.logger.log(f"\nProcessing {ticker} ({side.upper()}): {broker_qty:.0f} units")

        if ticker not in orders_by_ticker:
            self.logger.log(f"  ⚠️  No {side.upper()} orders found in history. Using broker avg price.")
            n = self._get_n_for_rebuild(ticker, datetime.now())
            rebuilt_positions[ticker] = self._create_single_pyramid_unit(pos, n)
            continue

        # Sort orders chronologically
        ticker_orders = sorted(orders_by_ticker[ticker], key=lambda x: x['filled_at'])

        # Filter out orders that have been closed out
        exit_qty_for_ticker = sum(float(o.filled_qty) for o in exit_orders if o.symbol == ticker)
        # This part is tricky. A simple FIFO for exits is assumed.
        # A more robust solution would trace every buy/sell pair.

        # For now, we use the most recent orders that sum up to the current position size
        cumulative_qty = 0
        relevant_orders = []
        for order in reversed(ticker_orders):
            if cumulative_qty < broker_qty:
                relevant_orders.append(order)
                cumulative_qty += order['filled_qty']
        relevant_orders.reverse() # Back to chronological

        if not relevant_orders:
            self.logger.log(f"  ⚠️  Could not determine relevant entry orders for {ticker}. Using broker avg price.")
            n = self._get_n_for_rebuild(ticker, datetime.now())
            rebuilt_positions[ticker] = self._create_single_pyramid_unit(pos, n)
            continue

        self.logger.log(f"  Found {len(relevant_orders)} relevant entry orders.")

        # Group orders into pyramid levels (orders within 1 day)
        pyramid_levels = self._group_orders_into_pyramids(relevant_orders)
        self.logger.log(f"  Reconstructed {len(pyramid_levels)} pyramid level(s).")

        # Reconstruct pyramid_units list
        pyramid_units = []
        for i, level_orders in enumerate(pyramid_levels, 1):
            total_qty = sum(o['filled_qty'] for o in level_orders)
            total_value = sum(o['filled_qty'] * o['filled_avg_price'] for o in level_orders)
            avg_price = total_value / total_qty
            entry_date = level_orders[0]['filled_at']
            n = self._get_n_for_rebuild(ticker, entry_date)
            order_ids = ",".join(o['id'] for o in level_orders)

            pyramid_units.append({
                'units': total_qty,
                'entry_price': avg_price,
                'entry_n': n,
                'entry_value': total_value,
                'entry_date': entry_date.isoformat(),
                'order_id': order_ids,
                'grouped_orders': len(level_orders)
            })
            self.logger.log(f"    Level {i}: {total_qty:.0f} units @ ${avg_price:.2f}, N=${n:.2f}")

        # Final verification and stop price calculation
        reconstructed_qty = sum(p['units'] for p in pyramid_units)
        if abs(reconstructed_qty - broker_qty) > 0.01:
            self.logger.log(f"  ⚠️  Mismatch: Reconstructed {reconstructed_qty:.0f} units, broker has {broker_qty:.0f}", 'WARNING')

        temp_position = {
            'pyramid_units': pyramid_units,
            'initial_n': pyramid_units[0]['entry_n']
        }
        if side == 'long':
            stop_price = self.position_manager.calculate_long_stop(temp_position)
        else:
            stop_price = self.position_manager.calculate_short_stop(temp_position)

        rebuilt_positions[ticker] = {
            'pyramid_units': pyramid_units,
            'entry_date': pyramid_units[0]['entry_date'],
            'stop_price': stop_price,
            'initial_n': pyramid_units[0]['entry_n'],
            'initial_units': pyramid_units[0]['units']
        }
        self.logger.log(f"  Stop Price: ${stop_price:.2f}")

    return rebuilt_positions

  def _get_n_for_rebuild(self, ticker, end_date):
      hist = self.data_provider.get_historical_data(ticker, 60, end_date=end_date.date())
      if hist is not None and len(hist) >= 20:
          hist_with_n = self.indicator_calculator.calculate_atr(hist)
          n_value = hist_with_n['N'].iloc[-1]
          if pd.notna(n_value) and n_value > 0:
              return float(n_value)
      return None # Sentinel for fallback

  def _create_single_pyramid_unit(self, position, n_value):
      avg_price = float(position.avg_entry_price)
      qty = abs(float(position.qty))
      n = n_value if n_value else avg_price * 0.02 # Fallback N
      side = position.side.name.lower()

      temp_pos = {
          'pyramid_units': [{'entry_price': avg_price, 'entry_n': n}],
          'initial_n': n
      }

      if side == 'long':
          stop_price = self.position_manager.calculate_long_stop(temp_pos)
      else:
          stop_price = self.position_manager.calculate_short_stop(temp_pos)

      return {
          'pyramid_units': [{
              'units': qty,
              'entry_price': avg_price,
              'entry_n': n,
              'entry_value': qty * avg_price,
              'entry_date': datetime.now().isoformat(),
              'order_id': 'UNKNOWN_REBUILT'
          }],
          'entry_date': datetime.now().isoformat(),
          'stop_price': stop_price,
          'initial_n': n,
          'initial_units': qty
      }

  def _group_orders_into_pyramids(self, orders):
      if not orders:
          return []
      pyramid_levels = []
      current_level = [orders[0]]
      for i in range(1, len(orders)):
          time_diff = (orders[i]['filled_at'] - orders[i-1]['filled_at']).total_seconds()
          if time_diff < 86400: # Within 1 day
              current_level.append(orders[i])
          else:
              pyramid_levels.append(current_level)
              current_level = [orders[i]]
      pyramid_levels.append(current_level)
      return pyramid_levels


def main():
  """Main entry point"""
  alpaca_key = os.environ.get('ALPACA_API_KEY')
  alpaca_secret = os.environ.get('ALPACA_SECRET')
  slack_token = os.environ.get('SLACK_BOT_TOKEN')
  slack_channel = os.environ.get('PERSONAL_SLACK_CHANNEL_ID')
  
  if not slack_channel:
    print("Warning: PERSONAL_SLACK_CHANNEL_ID not set, notifications will be disabled")
    slack_channel = None

  system = TurtleTradingLS(
    api_key=alpaca_key,
    api_secret=alpaca_secret,
    slack_token=slack_token,
    slack_channel=slack_channel,
    paper=True,
    enable_shorts=True,
    check_shortability=False
  )

  print("Turtle Trading System (Long/Short) initialized successfully!")
  print("Available workflows:")
  print("  - system.daily_eod_analysis()     # After market close")
  print("  - system.market_open_setup()      # Before market open")
  print("  - system.intraday_monitor()       # Every 5 minutes during market")
  print("  - system.post_market_routine()    # After market close")
  print("\nLogs are stored in ./logs/")

if __name__ == "__main__":
  main()
