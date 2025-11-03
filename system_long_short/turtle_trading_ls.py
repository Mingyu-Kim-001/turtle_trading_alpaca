"""
Turtle Trading System with Long and Short Positions

This module orchestrates all components to implement the Turtle Trading strategy
with support for both long and short positions.
"""

import os
import time
import json
import pandas as pd
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus

from .utils import DailyLogger, SlackNotifier, StateManager
from .core import (
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
        entry_margin=0.99, exit_margin=1.01,
        enable_shorts=True, check_shortability=False):
    """
    Initialize Turtle Trading System with Long/Short support

    Args:
      api_key: Alpaca API key
      api_secret: Alpaca API secret
      slack_token: Slack bot token
      slack_channel: Slack channel ID
      universe_file: File containing ticker universe
      paper: Whether to use paper trading
      entry_margin: Margin for entry orders
      exit_margin: Margin for exit orders
      enable_shorts: Whether to enable short selling
      check_shortability: Whether to check if tickers are shortable
    """
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
      entry_margin,
      exit_margin
    )

    # Load ticker universe
    self.load_universe(universe_file)

    # Short selling configuration
    self.enable_shorts = enable_shorts
    self.check_shortability = check_shortability
    self.shortable_tickers = set()
    self.htb_exclusions = set()

    if self.enable_shorts:
      self._load_htb_exclusions()
      if self.check_shortability:
        self._load_shortable_tickers()

    # Track daily PnL
    self.daily_pnl = 0

    self.logger.log("Turtle Trading System (Long/Short) initialized")
    self.logger.log(f"Short selling: {'enabled' if enable_shorts else 'disabled'}")

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

  def enter_long_position(self, ticker, units, target_price, n):
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
          units, filled_price, n, order_id
        )
        reason = "Long initial entry"

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

  def enter_short_position(self, ticker, units, target_price, n):
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
          units, filled_price, n, order_id
        )
        reason = "Short initial entry"

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

  def exit_long_position(self, ticker, target_price, reason):
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
      ticker, total_units, target_price, reason
    )

    if success and filled_price:
      # Calculate P&L
      _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_long_position_pnl(
        position, filled_price
      )

      # Track daily PnL
      self.daily_pnl += pnl

      # Remove position
      del self.state.long_positions[ticker]
      self.state.save_state()

      total_equity = self.get_total_equity()

      # Send notification
      emoji = "🟢" if pnl > 0 else "🔴"
      self.slack.send_summary(f"{emoji} LONG EXIT EXECUTED", {
        "Ticker": ticker,
        "Reason": reason,
        "Units": int(total_units),
        "Exit Price": f"${filled_price:.2f}",
        "Entry Value": f"${entry_value:,.2f}",
        "Exit Value": f"${exit_value:,.2f}",
        "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True

    return False

  def exit_short_position(self, ticker, target_price, reason):
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
      ticker, total_units, target_price, reason
    )

    if success and filled_price:
      # Calculate P&L
      _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_short_position_pnl(
        position, filled_price
      )

      # Track daily PnL
      self.daily_pnl += pnl

      # Remove position
      del self.state.short_positions[ticker]
      self.state.save_state()

      total_equity = self.get_total_equity()

      # Send notification
      emoji = "🟢" if pnl > 0 else "🔴"
      self.slack.send_summary(f"{emoji} SHORT EXIT EXECUTED", {
        "Ticker": ticker,
        "Reason": reason,
        "Units": int(total_units),
        "Exit Price": f"${filled_price:.2f}",
        "Entry Value": f"${entry_value:,.2f}",
        "Exit Value": f"${exit_value:,.2f}",
        "P&L": f"${pnl:,.2f} ({pnl_pct:.2f}%)",
        "Total Equity": f"${total_equity:,.2f}"
      })

      return True

    return False

  def check_long_stops(self):
    """Check if any long positions hit stop loss"""
    if not self.state.long_positions:
      return

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.long_positions.items()):
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      stop_price = position['stop_price']

      if current_price <= stop_price * 1.01:
        self.logger.log(f"Long stop loss triggered for {ticker}: ${current_price:.2f} <= ${stop_price * 1.01:.2f}")
        self.exit_long_position(ticker, current_price, 'Stop loss')

  def check_short_stops(self):
    """Check if any short positions hit stop loss"""
    if not self.state.short_positions:
      return

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.short_positions.items()):
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      stop_price = position['stop_price']

      if current_price >= stop_price * 0.99:
        self.logger.log(f"Short stop loss triggered for {ticker}: ${current_price:.2f} >= ${stop_price * 0.99:.2f}")
        self.exit_short_position(ticker, current_price, 'Stop loss')

  def check_long_exit_signals(self):
    """Check if any long positions hit exit signals"""
    if not self.state.long_positions:
      return

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.long_positions.items()):
      df = self.data_provider.get_historical_data(ticker, days=30)
      if df is None:
        continue

      df = self.indicator_calculator.calculate_indicators(df)
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      if self.signal_generator.check_long_exit_signal(df, current_price):
        self.logger.log(f"Long exit signal for {ticker}")
        self.exit_long_position(ticker, current_price, 'Exit signal (10-day low)')

  def check_short_exit_signals(self):
    """Check if any short positions hit exit signals"""
    if not self.state.short_positions:
      return

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in list(self.state.short_positions.items()):
      df = self.data_provider.get_historical_data(ticker, days=30)
      if df is None:
        continue

      df = self.indicator_calculator.calculate_indicators(df)
      current_price = current_prices.get(ticker)

      if current_price is None:
        continue

      if self.signal_generator.check_short_exit_signal(df, current_price):
        self.logger.log(f"Short exit signal for {ticker}")
        self.exit_short_position(ticker, current_price, 'Exit signal (10-day high)')

  def check_long_pyramid_opportunities(self):
    """Check if any long positions can pyramid"""
    if not self.state.long_positions:
      return

    total_equity = self.get_total_equity()

    # Batch fetch prices for all long positions
    tickers = list(self.state.long_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in self.state.long_positions.items():
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
      last_pyramid = position['pyramid_units'][-1]
      last_entry_price = last_pyramid['entry_price']

      if self.signal_generator.check_long_pyramid_opportunity(
          last_entry_price, current_price, initial_n):
        pyramid_trigger = last_entry_price + 0.5 * initial_n
        self.logger.log(f"Long pyramid opportunity for {ticker}: ${current_price:.2f} > ${pyramid_trigger * 0.99:.2f}")

        # Use same units as initial entry
        units = initial_units

        cost = units * pyramid_trigger
        buying_power = self.order_manager.get_buying_power()

        if cost <= buying_power:
          success = self.enter_long_position(ticker, units, pyramid_trigger, initial_n)
          if not success:
            # Track pending order
            open_orders = self.order_manager.get_open_orders(ticker)
            for order in open_orders:
              if order.side.name == 'BUY':
                self.state.pending_pyramid_orders[ticker] = str(order.id)
                self.state.save_state()
                break

  def check_short_pyramid_opportunities(self):
    """Check if any short positions can pyramid"""
    if not self.state.short_positions:
      return

    total_equity = self.get_total_equity()

    # Batch fetch prices for all short positions
    tickers = list(self.state.short_positions.keys())
    current_prices = self.data_provider.get_current_prices_batch(tickers)

    for ticker, position in self.state.short_positions.items():
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
      last_pyramid = position['pyramid_units'][-1]
      last_entry_price = last_pyramid['entry_price']

      if self.signal_generator.check_short_pyramid_opportunity(
          last_entry_price, current_price, initial_n):
        pyramid_trigger = last_entry_price - 0.5 * initial_n
        self.logger.log(f"Short pyramid opportunity for {ticker}: ${current_price:.2f} < ${pyramid_trigger * 1.01:.2f}")

        # Use same units as initial entry
        units = initial_units

        margin_required = self.position_manager.calculate_margin_required(units, pyramid_trigger)
        buying_power = self.order_manager.get_buying_power()

        if margin_required <= buying_power:
          success = self.enter_short_position(ticker, units, pyramid_trigger, initial_n)
          if not success:
            # Track pending order
            open_orders = self.order_manager.get_open_orders(ticker)
            for order in open_orders:
              if order.side.name == 'SELL':
                self.state.pending_pyramid_orders[ticker] = str(order.id)
                self.state.save_state()
                break

  def process_entry_queue(self):
    """Process pending entry signals"""
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
        entry_trigger = signal['entry_price'] * 0.99
        if current_price >= entry_trigger:
          units = self.position_manager.calculate_position_size(
            total_equity, signal['n']
          )
          cost = units * signal['entry_price']

          if cost <= buying_power:
            success = self.enter_long_position(ticker, units, signal['entry_price'], signal['n'])
            if success:
              processed.append(ticker)
              buying_power -= cost
            else:
              # Track pending order
              open_orders = self.order_manager.get_open_orders(ticker)
              for order in open_orders:
                if order.side.name == 'BUY':
                  self.state.pending_entry_orders[ticker] = str(order.id)
                  self.state.save_state()
                  break

      else:  # short
        entry_trigger = signal['entry_price'] * 1.01
        if current_price <= entry_trigger:
          units = self.position_manager.calculate_position_size(
            total_equity, signal['n']
          )
          margin_required = self.position_manager.calculate_margin_required(
            units, signal['entry_price']
          )

          if margin_required <= buying_power:
            success = self.enter_short_position(ticker, units, signal['entry_price'], signal['n'])
            if success:
              processed.append(ticker)
              buying_power -= margin_required
            else:
              # Track pending order
              open_orders = self.order_manager.get_open_orders(ticker)
              for order in open_orders:
                if order.side.name == 'SELL':
                  self.state.pending_entry_orders[ticker] = str(order.id)
                  self.state.save_state()
                  break

    # Remove processed signals
    self.state.entry_queue = [s for s in self.state.entry_queue if s['ticker'] not in processed]
    if processed:
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
      self.enable_shorts,
      shortable_for_signals
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

    self.logger.log_state_snapshot(self.state, 'market_open')

    account = self.trading_client.get_account()

    summary = {
      "Buying Power": f"${float(account.buying_power):,.2f}",
      "Equity": f"${float(account.equity):,.2f}",
      "Cash": f"${float(account.cash):,.2f}",
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

    self.logger.log_state_snapshot(self.state, 'market_close')

    account = self.trading_client.get_account()

    daily_orders = self.logger.get_daily_orders()
    orders_placed = len([o for o in daily_orders if o['status'] == 'PLACED'])
    orders_filled = len([o for o in daily_orders if o['status'] == 'FILLED'])

    summary = {
      "Daily P&L": f"${self.daily_pnl:,.2f}",
      "Equity": f"${float(account.equity):,.2f}",
      "Cash": f"${float(account.cash):,.2f}",
      "Long Positions": len(self.state.long_positions),
      "Short Positions": len(self.state.short_positions),
      "Orders Placed": orders_placed,
      "Orders Filled": orders_filled
    }

    self.slack.send_summary("📊 Daily Summary", summary)

    # Reset daily PnL
    self.daily_pnl = 0

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
        exit_qty_for_ticker = sum(o.filled_qty for o in exit_orders if o.symbol == ticker)
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

        last_entry_price = pyramid_units[-1]['entry_price']
        last_n = pyramid_units[-1]['entry_n']
        stop_price = self.position_manager.calculate_stop_price(last_entry_price, last_n, side)

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

      stop_price = self.position_manager.calculate_stop_price(avg_price, n, position.side.name.lower())

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
  alpaca_key = os.environ.get('ALPACA_PAPER_LS_KEY')
  alpaca_secret = os.environ.get('ALPACA_PAPER_LS_SECRET')
  slack_token = os.environ.get('SLACK_BOT_TOKEN')
  slack_channel = 'C09Q7RR1PQD'

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
