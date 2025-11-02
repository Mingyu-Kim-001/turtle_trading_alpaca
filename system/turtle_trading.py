"""
Refactored Turtle Trading System

This module orchestrates all components to implement the Turtle Trading strategy.
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


class TurtleTrading:
  """Main Turtle Trading System - Orchestrates all components"""

  def __init__(self, api_key, api_secret, slack_token, slack_channel,
        universe_file='ticker_universe.txt', paper=True,
        entry_margin=0.99, exit_margin=1.01):
    """
    Initialize Turtle Trading System

    Args:
      api_key: Alpaca API key
      api_secret: Alpaca API secret
      slack_token: Slack bot token
      slack_channel: Slack channel ID
      universe_file: File containing ticker universe
      paper: Whether to use paper trading
      entry_margin: Margin for entry orders
      exit_margin: Margin for exit orders
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

    # Track daily PnL
    self.daily_pnl = 0

    self.logger.log("Turtle Trading System initialized")

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

  def get_total_equity(self):
    """
    Calculate total equity (cash + positions value)

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
        positions_value = 0

        for ticker in self.state.positions.keys():
          current_price = self.data_provider.get_current_price(ticker)
          if current_price:
            total_units = sum(p['units'] for p in self.state.positions[ticker]['pyramid_units'])
            positions_value += total_units * current_price

        return cash + positions_value
      except Exception as e2:
        self.logger.log(f"Error calculating total equity manually: {e2}", 'ERROR')
        return 10000  # Fallback value

  def enter_position(self, ticker, units, target_price, n):
    """
    Enter a new position or add pyramid level

    Args:
      ticker: Stock symbol
      units: Number of shares
      target_price: Target entry price
      n: Current ATR

    Returns:
      True if successful, False otherwise
    """
    # Check if pyramiding or new position
    is_pyramid = ticker in self.state.positions
    pyramid_level = len(self.state.positions[ticker]['pyramid_units']) + 1 if is_pyramid else 1

    # Place order
    success, order_id, filled_price = self.order_manager.place_entry_order(
      ticker, units, target_price, n, is_pyramid, pyramid_level
    )

    if success and filled_price:
      # Calculate cost
      cost = units * filled_price

      # Update or create position
      if is_pyramid:
        self.state.positions[ticker] = self.position_manager.add_pyramid_unit(
          self.state.positions[ticker],
          units, filled_price, n, order_id
        )
        reason = f"Pyramid level {pyramid_level}"
      else:
        self.state.positions[ticker] = self.position_manager.create_new_position(
          units, filled_price, n, order_id
        )
        reason = "Initial entry"

      self.state.save_state()

      stop_price = self.state.positions[ticker]['stop_price']
      total_equity = self.get_total_equity()

      # Send notification
      self.slack.send_summary("🟢 ENTRY EXECUTED", {
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

  def exit_position(self, ticker, target_price, reason):
    """
    Exit entire position

    Args:
      ticker: Stock symbol
      target_price: Target exit price
      reason: Reason for exit

    Returns:
      True if successful, False otherwise
    """
    if ticker not in self.state.positions:
      self.logger.log(f"No position found for {ticker}", 'ERROR')
      return False

    position = self.state.positions[ticker]
    total_units, entry_value, _, _, _ = self.position_manager.calculate_position_pnl(
      position, target_price
    )

    # Place exit order
    success, order_id, filled_price = self.order_manager.place_exit_order(
      ticker, total_units, target_price, reason
    )

    if success and filled_price:
      # Calculate P&L
      _, entry_value, exit_value, pnl, pnl_pct = self.position_manager.calculate_position_pnl(
        position, filled_price
      )

      # Track daily PnL
      self.daily_pnl += pnl

      # Remove position
      del self.state.positions[ticker]
      self.state.save_state()

      total_equity = self.get_total_equity()

      # Send notification
      emoji = "🟢" if pnl > 0 else "🔴"
      self.slack.send_summary(f"{emoji} EXIT EXECUTED", {
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

  def exit_all_positions_market(self):
    """Emergency exit all positions using market orders"""
    self.logger.log("="*60)
    self.logger.log("🚨 EMERGENCY EXIT: CLOSING ALL POSITIONS AT MARKET")
    self.logger.log("="*60)

    self.logger.log_state_snapshot(self.state, 'before_exit_all')

    if not self.state.positions:
      self.logger.log("No positions to exit", 'WARNING')
      self.slack.send_message("⚠️ No positions to exit")
      return

    # Cancel all open orders first
    self.order_manager.cancel_all_orders()
    time.sleep(1)

    positions_to_exit = list(self.state.positions.keys())
    self.logger.log(f"Exiting {len(positions_to_exit)} positions at market price")

    # Send initial notification
    self.slack.send_summary("🚨 EMERGENCY EXIT INITIATED", {
      "Positions to Close": len(positions_to_exit),
      "Tickers": ", ".join(positions_to_exit),
      "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

    exit_results = []
    total_pnl = 0

    for ticker in positions_to_exit:
      try:
        position = self.state.positions[ticker]
        total_units = sum(p['units'] for p in position['pyramid_units'])
        entry_value = sum(p['entry_value'] for p in position['pyramid_units'])

        self.logger.log(f"\nProcessing {ticker}: {total_units:.0f} units")

        # Place market order
        success, order_id, filled_price = self.order_manager.place_market_exit_order(
          ticker, total_units
        )

        if success and filled_price:
          exit_value = total_units * filled_price
          pnl = exit_value - entry_value
          pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

          total_pnl += pnl

          exit_results.append({
            'ticker': ticker,
            'status': 'SUCCESS',
            'units': total_units,
            'exit_price': filled_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
          })

          # Remove position
          del self.state.positions[ticker]
        else:
          exit_results.append({
            'ticker': ticker,
            'status': 'FAILED',
            'reason': 'Order not filled'
          })

      except Exception as e:
        self.logger.log(f"❌ Error exiting {ticker}: {e}", 'ERROR')
        exit_results.append({
          'ticker': ticker,
          'status': 'ERROR',
          'reason': str(e)
        })

    # Save final state
    self.state.save_state()
    self.logger.log_state_snapshot(self.state, 'after_exit_all')

    # Send summary
    successful = [r for r in exit_results if r['status'] == 'SUCCESS']
    self.logger.log(f"\nSuccessful: {len(successful)}/{len(exit_results)}")
    self.logger.log(f"Total P&L: ${total_pnl:,.2f}")

    return exit_results

  def check_position_stops(self):
    """Check if any positions hit stop loss"""
    for ticker, position in list(self.state.positions.items()):
      current_price = self.data_provider.get_current_price(ticker)

      if current_price is None:
        continue

      stop_price = position['stop_price']

      if current_price <= stop_price * 1.01:
        self.logger.log(f"Stop loss triggered for {ticker}: ${current_price:.2f} <= ${stop_price * 1.01:.2f}")
        self.exit_position(ticker, current_price, 'Stop loss')

  def check_exit_signals(self):
    """Check if any positions hit exit signals"""
    for ticker, position in list(self.state.positions.items()):
      df = self.data_provider.get_historical_data(ticker, days=30)
      if df is None:
        continue

      df = self.indicator_calculator.calculate_indicators(df)
      current_price = self.data_provider.get_current_price(ticker)

      if current_price is None:
        continue

      system = position.get('system', 1)
      if self.signal_generator.check_exit_signal(df, current_price, system):
        self.logger.log(f"System {system} exit signal for {ticker}")
        self.exit_position(ticker, current_price, f'System {system} exit signal')

  def check_pyramid_opportunities(self):
    """Check if any positions can pyramid"""
    total_equity = self.get_total_equity()

    for ticker, position in self.state.positions.items():
      # Check limits
      if not self.position_manager.can_pyramid(position):
        continue

      # Check for pending pyramid order
      if ticker in self.state.pending_pyramid_orders:
        continue

      # Get current price
      current_price = self.data_provider.get_current_price(ticker)
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

      if self.signal_generator.check_pyramid_opportunity(
          last_entry_price, current_price, initial_n):
        pyramid_trigger = last_entry_price + 0.5 * initial_n
        self.logger.log(f"Pyramid opportunity for {ticker}: ${current_price:.2f} > ${pyramid_trigger * 0.99:.2f}")

        # Use same units as initial entry
        units = initial_units

        cost = units * pyramid_trigger
        buying_power = self.order_manager.get_buying_power()

        if cost <= buying_power:
          success = self.enter_position(ticker, units, pyramid_trigger, initial_n)
          if not success:
            # Track pending order
            open_orders = self.order_manager.get_open_orders(ticker)
            for order in open_orders:
              if order.side.name == 'BUY':
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

    for signal in self.state.entry_queue[:]:
      if buying_power <= 0:
        break

      ticker = signal['ticker']

      # Skip if already in positions
      if ticker in self.state.positions:
        processed.append(ticker)
        continue

      # Check for pending entry order
      if ticker in self.state.pending_entry_orders:
        continue

      current_price = self.data_provider.get_current_price(ticker)
      if current_price is None:
        continue

      entry_trigger = signal['entry_price'] * 0.99
      if current_price >= entry_trigger:
        units = self.position_manager.calculate_position_size(
          total_equity, signal['n']
        )
        cost = units * signal['entry_price']

        if cost <= buying_power:
          success = self.enter_position(ticker, units, signal['entry_price'], signal['n'])
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
        else:
          self.logger.log(f"Insufficient buying power for {ticker}")
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

    signals = self.signal_generator.generate_entry_signals(
      self.universe,
      self.data_provider,
      self.indicator_calculator,
      self.state.positions
    )

    self.state.entry_queue = signals
    self.state.save_state()
    self.logger.log_state_snapshot(self.state, 'EOD_complete')

    self.logger.log(f"Found {len(signals)} potential entry signals")

    if signals:
      top_signals = signals[:10]
      signal_text = "\n".join([
        f"• {s['ticker']}: ${s['current_price']:.2f} (target: ${s['entry_price']:.2f}, {s['proximity']:.1f}%)"
        for s in top_signals
      ])
      self.slack.send_message(f"Found {len(signals)} entry signals\n\nTop 10:\n{signal_text}",
                  title="📈 Entry Signals Generated")

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
      "Open Positions": len(self.state.positions),
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

      self.logger.log("1. Checking position stops...")
      self.check_position_stops()
      time.sleep(0.5)

      self.logger.log("2. Checking exit signals...")
      self.check_exit_signals()
      time.sleep(0.5)

      self.logger.log("3. Checking pyramid opportunities...")
      self.check_pyramid_opportunities()
      time.sleep(0.5)

      self.logger.log("4. Processing entry queue...")
      self.process_entry_queue()

      total_equity = self.get_total_equity()
      self.logger.log(f"Status: {len(self.state.positions)} positions, {len(self.state.entry_queue)} pending entries")
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
      "Open Positions": len(self.state.positions),
      "Orders Placed": orders_placed,
      "Orders Filled": orders_filled
    }

    self.slack.send_summary("📊 Daily Summary", summary)

    # Reset daily PnL
    self.daily_pnl = 0


def main():
  """Main entry point"""
  alpaca_key = os.environ.get('ALPACA_PAPER_KEY')
  alpaca_secret = os.environ.get('ALPACA_PAPER_SECRET')
  slack_token = os.environ.get('SLACK_BOT_TOKEN')
  slack_channel = 'C09M9NNU8JH'

  system = TurtleTrading(
    api_key=alpaca_key,
    api_secret=alpaca_secret,
    slack_token=slack_token,
    slack_channel=slack_channel,
    paper=True
  )

  print("Turtle Trading System initialized successfully!")
  print("Available workflows:")
  print("  - system.daily_eod_analysis()     # After market close")
  print("  - system.market_open_setup()      # Before market open")
  print("  - system.intraday_monitor()       # Every 5 minutes during market")
  print("  - system.post_market_routine()    # After market close")
  print("\nLogs are stored in ./logs/")


if __name__ == "__main__":
  main()
