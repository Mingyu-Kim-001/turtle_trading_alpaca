import json
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    StopLimitOrderRequest, 
    GetOrdersRequest,
    LimitOrderRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import requests
import warnings
warnings.filterwarnings('ignore')

_initial_risk_pot = 10000
class DailyLogger:
  """Log daily trading activities"""
  
  def __init__(self, log_dir='logs'):
    self.log_dir = log_dir
    os.makedirs(log_dir, exist_ok=True)
    self.today = datetime.now().strftime('%Y-%m-%d')
    self.log_file = os.path.join(log_dir, f'trading_{self.today}.log')
    self.order_log_file = os.path.join(log_dir, f'orders_{self.today}.json')
    self.state_log_file = os.path.join(log_dir, f'state_{self.today}.json')
    self.orders = []
    self.state_snapshots = []
    
  def log(self, message, level='INFO'):
    """Log a message with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] [{level}] {message}\n"
    
    print(log_line.strip())
    
    with open(self.log_file, 'a') as f:
      f.write(log_line)
  
  def log_order(self, order_type, ticker, status, details):
    """Log order details"""
    order_entry = {
      'timestamp': datetime.now().isoformat(),
      'type': order_type,
      'ticker': ticker,
      'status': status,
      'details': details
    }
    self.orders.append(order_entry)
    
    # Save to file
    with open(self.order_log_file, 'w') as f:
      json.dump(self.orders, f, indent=2)
  
  def log_state_snapshot(self, state, label='snapshot'):
    """Log a snapshot of trading state"""
    snapshot = {
      'timestamp': datetime.now().isoformat(),
      'label': label,
      'risk_pot': state.risk_pot,
      'positions': state.positions,
      'entry_queue': state.entry_queue,
      'position_count': len(state.positions),
      'queue_count': len(state.entry_queue)
    }
    self.state_snapshots.append(snapshot)
    
    # Save to file
    with open(self.state_log_file, 'w') as f:
      json.dump(self.state_snapshots, f, indent=2)
    
    self.log(f"State snapshot saved: {label}")
  
  def get_daily_orders(self):
    """Get all orders logged today"""
    return self.orders


class SlackNotifier:
  """Send notifications to Slack"""
  
  def __init__(self, token, channel):
    self.token = token
    self.channel = channel
    self.url = "https://slack.com/api/chat.postMessage"
  
  def send_message(self, message, title=None):
    """Send a message to Slack"""
    try:
      if title:
        formatted_message = f"*{title}*\n{message}"
      else:
        formatted_message = message
      
      payload = {
        "channel": self.channel,
        "text": formatted_message,
        "mrkdwn": True
      }
      
      headers = {
        "Authorization": f"Bearer {self.token}",
        "Content-Type": "application/json"
      }
      
      response = requests.post(self.url, json=payload, headers=headers)
      response.raise_for_status()
      return True
    except Exception as e:
      print(f"Failed to send Slack message: {e}")
      return False
  
  def send_summary(self, title, data):
    """Send a formatted summary to Slack"""
    message_lines = []
    for key, value in data.items():
      message_lines.append(f"• {key}: {value}")
    
    message = "\n".join(message_lines)
    self.send_message(message, title=title)

class StateManager:
  """Manage trading state persistence"""
  
  def __init__(self, state_file='trading_state.json'):
    self.state_file = state_file
    self.load_state()
  
  def load_state(self):
    """Load state from file"""
    try:
      with open(self.state_file, 'r') as f:
        data = json.load(f)
        self.risk_pot = data.get('risk_pot', _initial_risk_pot)
        self.positions = data.get('positions', {})
        self.entry_queue = data.get('entry_queue', [])
        self.pending_pyramid_orders = data.get('pending_pyramid_orders', {})
        self.last_updated = data.get('last_updated', None)
        print(f"State loaded: risk_pot=${self.risk_pot:,.2f}, positions={len(self.positions)}, pending_pyramids={len(self.pending_pyramid_orders)}")
    except FileNotFoundError:
      print("No existing state found, initializing new state")
      self.risk_pot = _initial_risk_pot
      self.positions = {}
      self.entry_queue = []
      self.pending_pyramid_orders = {}
      self.last_updated = None
      self.save_state()
  
  def save_state(self):
    """Save state to file"""
    data = {
      'risk_pot': self.risk_pot,
      'positions': self.positions,
      'entry_queue': self.entry_queue,
      'pending_pyramid_orders': self.pending_pyramid_orders,
      'last_updated': datetime.now().isoformat()
    }
    
    with open(self.state_file, 'w') as f:
      json.dump(data, f, indent=2)
    
    print(f"State saved at {datetime.now()}")
  
  def update_risk_pot(self, pnl):
    """Update risk pot after trade"""
    old_risk_pot = self.risk_pot
    self.risk_pot += pnl
    print(f"Risk pot updated: ${old_risk_pot:,.2f} -> ${self.risk_pot:,.2f} (PnL: ${pnl:,.2f})")
    self.save_state()
    

class TurtleTrading:
  """Main Turtle Trading System"""
  
  def __init__(self, api_key, api_secret, slack_token, slack_channel, 
               universe_file='ticker_universe.txt', paper=True,
               entry_margin=0.99, exit_margin=1.01):
    # Initialize Alpaca clients
    self.trading_client = TradingClient(api_key, api_secret, paper=paper)
    self.data_client = StockHistoricalDataClient(api_key, api_secret)
    
    # Initialize state manager
    self.state = StateManager()
    
    # Initialize Slack notifier
    self.slack = SlackNotifier(slack_token, slack_channel)
    
    # Initialize daily logger
    self.logger = DailyLogger()
    
    # Load ticker universe
    self.load_universe(universe_file)
    
    # Track daily PnL
    self.daily_pnl = 0
    
    # Entry/exit margins for stop-limit orders
    self.entry_margin = entry_margin
    self.exit_margin = exit_margin
    
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
  
  def get_historical_data(self, ticker, days=100):
    """Get historical data for a ticker"""
    try:
      end = datetime.now()
      start = end - timedelta(days=days)
      
      request_params = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start,
        end=end
      )
      
      bars = self.data_client.get_stock_bars(request_params)
      df = bars.df
      
      if df.empty:
        return None
      
      df = df.reset_index()
      df = df.rename(columns={'timestamp': 'date'})
      
      if isinstance(df.columns, pd.MultiIndex):
        df = df[ticker]
      
      df = df.set_index('date').sort_index()
      
      return df
    except Exception as e:
      self.logger.log(f"Error getting data for {ticker}: {e}", 'ERROR')
      return None
  
  def calculate_indicators(self, df):
    """Calculate ATR and signals"""
    df['prev_close'] = df['close'].shift(1)
    df['TR'] = np.maximum(
      df['high'] - df['low'],
      np.maximum(
        np.abs(df['high'] - df['prev_close']),
        np.abs(df['low'] - df['prev_close'])
      )
    )
    df['N'] = df['TR'].rolling(window=20).mean()
    df['high_20'] = df['high'].rolling(window=20).max()
    df['high_55'] = df['high'].rolling(window=55).max()
    df['low_10'] = df['low'].rolling(window=10).min()
    df['low_20'] = df['low'].rolling(window=20).min()
    
    return df
  
  def get_current_price(self, ticker):
    """Get current price for a ticker"""
    try:
      end = datetime.now()
      start = end - timedelta(minutes=15)
      
      request_params = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end
      )
      
      bars = self.data_client.get_stock_bars(request_params)
      df = bars.df
      
      if df.empty:
        return None
      
      if isinstance(df.index, pd.MultiIndex):
        latest_price = df.loc[ticker, 'close'].iloc[-1]
      else:
        latest_price = df['close'].iloc[-1]
      
      return float(latest_price)
    except Exception as e:
      self.logger.log(f"Error getting current price for {ticker}: {e}", 'ERROR')
      return None
  
  def get_buying_power(self):
    """Get available buying power"""
    try:
      account = self.trading_client.get_account()
      return float(account.buying_power)
    except Exception as e:
      self.logger.log(f"Error getting buying power: {e}", 'ERROR')
      return 0
  
  def calculate_overall_stop(self, pyramid_units):
    """Calculate the overall stop price for the entire position"""
    if not pyramid_units:
      return None
    
    highest_entry = max(unit['entry_price'] for unit in pyramid_units)
    highest_entry_n = next(unit['entry_n'] for unit in pyramid_units 
                           if unit['entry_price'] == highest_entry)
    
    return highest_entry - 2 * highest_entry_n
  
  def exit_all_positions_market(self):
    """
    Emergency exit: Close all positions using MARKET ORDERS
    
    WARNING: This uses market orders for immediate execution.
    Should only be used manually in emergency situations.
    """
    self.logger.log("="*60)
    self.logger.log("🚨 EMERGENCY EXIT: CLOSING ALL POSITIONS AT MARKET")
    self.logger.log("="*60)
    
    # Log state snapshot before exit
    self.logger.log_state_snapshot(self.state, 'before_exit_all')
    
    if not self.state.positions:
      self.logger.log("No positions to exit", 'WARNING')
      self.slack.send_message("⚠️ No positions to exit")
      return
    
    # Cancel all open orders first
    try:
      self.logger.log("Cancelling all open orders...")
      self.trading_client.cancel_orders()
      self.logger.log("All open orders cancelled")
      time.sleep(1)  # Brief wait for cancellations to process
    except Exception as e:
      self.logger.log(f"Error cancelling orders: {e}", 'ERROR')
    
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
        
        # Place MARKET order for immediate execution
        from alpaca.trading.requests import MarketOrderRequest
        
        order_data = MarketOrderRequest(
          symbol=ticker,
          qty=int(total_units),
          side=OrderSide.SELL,
          time_in_force=TimeInForce.DAY
        )
        
        self.logger.log(f"Placing MARKET sell order for {ticker}: {int(total_units)} units")
        
        order = self.trading_client.submit_order(order_data)
        order_id = str(order.id)
        
        self.logger.log(f"Market order placed: {order_id}")
        self.logger.log_order('EXIT_MARKET', ticker, 'PLACED', {
          'order_id': order_id,
          'units': int(total_units),
          'order_type': 'MARKET'
        })
        
        # Wait for order to fill (market orders usually fill quickly)
        time.sleep(2)
        
        # Get filled order details
        max_retries = 5
        filled_order = None
        
        for attempt in range(max_retries):
          try:
            filled_order = self.trading_client.get_order_by_id(order_id)
            if filled_order.status == 'filled':
              break
            elif filled_order.status in ['pending_new', 'accepted', 'new']:
              self.logger.log(f"Order still pending (attempt {attempt+1}/{max_retries}), waiting...")
              time.sleep(2)
            else:
              self.logger.log(f"Order status: {filled_order.status}", 'WARNING')
              break
          except Exception as e:
            self.logger.log(f"Error checking order status (attempt {attempt+1}/{max_retries}): {e}", 'WARNING')
            if attempt < max_retries - 1:
              time.sleep(2)
            else:
              raise
        
        if filled_order and filled_order.status == 'filled':
          filled_price = float(filled_order.filled_avg_price)
          exit_value = total_units * filled_price
          pnl = exit_value - entry_value
          pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0
          
          # Return allocated risk to pot
          for pyramid in position['pyramid_units']:
            risk_allocated = pyramid['units'] * 2 * pyramid['entry_n']
            self.state.risk_pot += risk_allocated
          
          # Add P&L to risk pot
          self.state.update_risk_pot(pnl)
          total_pnl += pnl
          
          self.logger.log(f"✅ {ticker} exited at ${filled_price:.2f}, P&L: ${pnl:,.2f} ({pnl_pct:.2f}%)")
          self.logger.log_order('EXIT_MARKET', ticker, 'FILLED', {
            'order_id': order_id,
            'units': int(total_units),
            'filled_price': filled_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct
          })
          
          exit_results.append({
            'ticker': ticker,
            'status': 'SUCCESS',
            'units': total_units,
            'exit_price': filled_price,
            'entry_value': entry_value,
            'exit_value': exit_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct
          })
          
          # Remove position from state
          del self.state.positions[ticker]
          
        else:
          self.logger.log(f"❌ Market order for {ticker} not filled, status: {filled_order.status if filled_order else 'unknown'}", 'ERROR')
          
          exit_results.append({
            'ticker': ticker,
            'status': 'FAILED',
            'reason': filled_order.status if filled_order else 'unknown'
          })
        
      except Exception as e:
        self.logger.log(f"❌ Error exiting {ticker}: {e}", 'ERROR')
        import traceback
        self.logger.log(traceback.format_exc(), 'ERROR')
        
        exit_results.append({
          'ticker': ticker,
          'status': 'ERROR',
          'reason': str(e)
        })
    
    # Save final state
    self.state.save_state()
    
    # Log state snapshot after exit
    self.logger.log_state_snapshot(self.state, 'after_exit_all')
    
    # Prepare summary
    successful = [r for r in exit_results if r['status'] == 'SUCCESS']
    failed = [r for r in exit_results if r['status'] != 'SUCCESS']
    
    self.logger.log("\n" + "="*60)
    self.logger.log("EXIT ALL COMPLETE")
    self.logger.log("="*60)
    self.logger.log(f"Successful: {len(successful)}/{len(exit_results)}")
    self.logger.log(f"Total P&L: ${total_pnl:,.2f}")
    self.logger.log(f"New Risk Pot: ${self.state.risk_pot:,.2f}")
    
    # Send detailed Slack notification
    summary_lines = [
      f"*🚨 EMERGENCY EXIT COMPLETE*",
      f"",
      f"*Results:*",
      f"• Successful: {len(successful)}/{len(exit_results)}",
      f"• Total P&L: ${total_pnl:,.2f}",
      f"• New Risk Pot: ${self.state.risk_pot:,.2f}",
      f"",
      f"*Position Details:*"
    ]
    
    for result in successful:
      emoji = "🟢" if result['pnl'] > 0 else "🔴"
      summary_lines.append(
        f"{emoji} {result['ticker']}: {result['units']:.0f} units @ ${result['exit_price']:.2f} "
        f"→ ${result['pnl']:,.2f} ({result['pnl_pct']:.2f}%)"
      )
    
    if failed:
      summary_lines.append(f"\n*⚠️ Failed Exits:*")
      for result in failed:
        summary_lines.append(f"• {result['ticker']}: {result.get('reason', 'Unknown error')}")
    
    self.slack.send_message("\n".join(summary_lines))
    
    return exit_results
  
  def enter_position(self, ticker, units, target_price, n):
    """Enter a new position or add to existing (pyramid) using stop-limit order"""
    try:
      units = int(units)
      
      if units <= 0:
        self.logger.log(f"Invalid units for {ticker}: {units}", 'ERROR')
        return False
      
      # Calculate prices
      stop_price = round(target_price * self.entry_margin, 2)
      limit_price = round(stop_price * 1.005, 2)
      stop_loss_price = round(target_price - 2 * n, 2)
      
      # Check if pyramiding or new position
      is_pyramid = ticker in self.state.positions
      pyramid_level = len(self.state.positions[ticker]['pyramid_units']) + 1 if is_pyramid else 1
      
      self.logger.log(f"Placing {'pyramid' if is_pyramid else 'entry'} order for {ticker}: "
                     f"units={units}, stop=${stop_price:.2f}, limit=${limit_price:.2f}")
      
      # Calculate risk allocation BEFORE order
      risk_allocated = units * 2 * n
      
      # Place stop-limit order
      order_data = StopLimitOrderRequest(
        symbol=ticker,
        qty=units,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        stop_price=stop_price,
        limit_price=limit_price
      )
      
      order = self.trading_client.submit_order(order_data)
      order_id = str(order.id)  # Convert UUID to string
      
      # Send Slack notification immediately when order is placed
      order_type = f"Pyramid Level {pyramid_level}" if is_pyramid else "Initial Entry"
      self.slack.send_summary("📤 ORDER PLACED", {
        "Ticker": ticker,
        "Type": order_type,
        "Order ID": order_id,
        "Units": units,
        "Stop Price": f"${stop_price:.2f}",
        "Limit Price": f"${limit_price:.2f}",
        "Status": "PENDING"
      })
      
      self.logger.log(f"Order placed: {order_id} for {ticker}")
      self.logger.log_order('ENTRY', ticker, 'PLACED', {
        'order_id': order_id,
        'units': units,
        'stop_price': stop_price,
        'limit_price': limit_price,
        'is_pyramid': is_pyramid,
        'pyramid_level': pyramid_level
      })
      
      # Wait for order to process
      time.sleep(3)
      
      # Check if order filled
      filled_order = self.trading_client.get_order_by_id(order_id)
      
      if filled_order.status == 'filled':
        filled_price = float(filled_order.filled_avg_price)
        cost = units * filled_price
        
        # Create pyramid unit
        pyramid_unit = {
          'units': units,
          'entry_price': filled_price,
          'entry_n': n,
          'entry_value': cost,
          'entry_date': datetime.now().isoformat(),
          'order_id': order_id
        }
        
        # Update or create position
        if is_pyramid:
          self.state.positions[ticker]['pyramid_units'].append(pyramid_unit)
          reason = f"Pyramid level {pyramid_level}"
        else:
          self.state.positions[ticker] = {
            'system': 1,
            'pyramid_units': [pyramid_unit],
            'entry_date': datetime.now().isoformat()
          }
          reason = "Initial entry"
        
        # Update stop price
        stop_price_final = self.calculate_overall_stop(self.state.positions[ticker]['pyramid_units'])
        self.state.positions[ticker]['stop_price'] = stop_price_final
        
        # CRITICAL: Update risk pot
        self.state.risk_pot -= risk_allocated
        
        # Save state
        self.state.save_state()
        
        self.logger.log(f"Order filled: {ticker} at ${filled_price:.2f}, "
                       f"risk pot decreased by ${risk_allocated:.2f}")
        self.logger.log_order('ENTRY', ticker, 'FILLED', {
          'order_id': order_id,
          'units': units,
          'filled_price': filled_price,
          'cost': cost,
          'risk_allocated': risk_allocated,
          'new_risk_pot': self.state.risk_pot
        })
        
        # Send Slack notification
        self.slack.send_summary("🟢 ENTRY EXECUTED", {
          "Ticker": ticker,
          "Type": reason,
          "Units": units,
          "Price": f"${filled_price:.2f}",
          "Cost": f"${cost:,.2f}",
          "Stop Price": f"${stop_price_final:.2f}",
          "Risk Allocated": f"${risk_allocated:,.2f}",
          "Risk Pot": f"${self.state.risk_pot:,.2f}"
        })
        
        return True
      elif filled_order.status in ['pending_new', 'accepted', 'new']:
        self.logger.log(f"Order pending for {ticker}, status: {filled_order.status}", 'WARNING')
        self.logger.log_order('ENTRY', ticker, 'PENDING', {
          'order_id': order_id,
          'status': filled_order.status
        })
        return False
      else:
        self.logger.log(f"Order not filled for {ticker}, status: {filled_order.status}", 'WARNING')
        self.logger.log_order('ENTRY', ticker, 'NOT_FILLED', {
          'order_id': order_id,
          'status': filled_order.status
        })
        return False
        
    except Exception as e:
      self.logger.log(f"Error entering position for {ticker}: {e}", 'ERROR')
      self.slack.send_message(f"❌ Error entering {ticker}: {str(e)}")
      return False
  def exit_position(self, ticker, target_price, reason):
      """Exit entire position using stop-limit order"""
      try:
        if ticker not in self.state.positions:
          self.logger.log(f"No position found for {ticker}", 'ERROR')
          return False
        
        # Check for existing open orders for this ticker
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
            self.logger.log(f"Sell order already exists for {ticker}: {existing_sell[0].id}", 'WARNING')
            return False
          
          # Cancel any buy orders to free up shares
          buy_orders = [o for o in open_orders if o.side == OrderSide.BUY]
          if buy_orders:
            self.logger.log(f"Cancelling {len(buy_orders)} buy orders for {ticker} to free shares")
            for order in buy_orders:
              try:
                self.trading_client.cancel_order_by_id(order.id)
                self.logger.log(f"Cancelled order {order.id}")
                time.sleep(0.5)  # Brief wait for order to cancel
              except Exception as e:
                self.logger.log(f"Error cancelling order {order.id}: {e}", 'ERROR')
        
        except Exception as e:
          self.logger.log(f"Error checking existing orders for {ticker}: {e}", 'WARNING')
          # Continue anyway, we'll catch the duplicate order error below
        
        position = self.state.positions[ticker]
        total_units = sum(p['units'] for p in position['pyramid_units'])
        
        stop_price = round(target_price * self.exit_margin, 2)
        limit_price = round(stop_price * 0.995, 2)
        
        self.logger.log(f"Placing exit order for {ticker}: units={total_units}, "
                      f"stop=${stop_price:.2f}, limit=${limit_price:.2f}")
        
        # Place stop-limit sell order with retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
          try:
            order_data = StopLimitOrderRequest(
              symbol=ticker,
              qty=int(total_units),
              side=OrderSide.SELL,
              time_in_force=TimeInForce.DAY,
              stop_price=stop_price,
              limit_price=limit_price
            )
            
            order = self.trading_client.submit_order(order_data)
            order_id = str(order.id)
            
            # Send Slack notification immediately
            self.slack.send_summary("📤 EXIT ORDER PLACED", {
              "Ticker": ticker,
              "Reason": reason,
              "Order ID": order_id,
              "Units": int(total_units),
              "Stop Price": f"${stop_price:.2f}",
              "Limit Price": f"${limit_price:.2f}",
              "Status": "PENDING",
              "Attempt": f"{attempt + 1}/{max_retries}"
            })
            
            self.logger.log(f"Exit order placed: {order_id} for {ticker}")
            self.logger.log_order('EXIT', ticker, 'PLACED', {
              'order_id': order_id,
              'units': int(total_units),
              'stop_price': stop_price,
              'limit_price': limit_price,
              'reason': reason
            })
            
            # Successfully placed order, break retry loop
            break
            
          except Exception as e:
            error_str = str(e)
            
            # Check if it's a duplicate order error
            if "40310000" in error_str or "insufficient qty" in error_str.lower():
              self.logger.log(f"Shares for {ticker} are held by another order", 'WARNING')
              self.logger.log(f"Error details: {error_str}", 'WARNING')
              return False  # Don't retry, order already exists
            
            # Connection errors - retry
            if attempt < max_retries - 1:
              self.logger.log(f"Connection error placing exit order for {ticker} (attempt {attempt + 1}/{max_retries}): {e}", 'WARNING')
              time.sleep(retry_delay)
              retry_delay *= 2  # Exponential backoff
              continue
            else:
              # Final attempt failed
              self.logger.log(f"Failed to place exit order for {ticker} after {max_retries} attempts: {e}", 'ERROR')
              self.slack.send_message(f"❌ Failed to exit {ticker} after {max_retries} attempts: {str(e)}")
              return False
        
        # Wait for order to process
        time.sleep(3)
        
        # Check if order filled (with retry for connection errors)
        for attempt in range(3):
          try:
            filled_order = self.trading_client.get_order_by_id(order_id)
            break
          except Exception as e:
            if attempt < 2:
              self.logger.log(f"Error checking order status (attempt {attempt + 1}/3): {e}", 'WARNING')
              time.sleep(2)
              continue
            else:
              self.logger.log(f"Cannot verify order status for {ticker}: {e}", 'ERROR')
              return False
        
        if filled_order.status == 'filled':
          filled_price = float(filled_order.filled_avg_price)
          exit_value = total_units * filled_price
          
          # Calculate P&L
          entry_value = sum(p['entry_value'] for p in position['pyramid_units'])
          pnl = exit_value - entry_value
          
          # Return allocated risk
          for pyramid in position['pyramid_units']:
            risk_allocated = pyramid['units'] * 2 * pyramid['entry_n']
            self.state.risk_pot += risk_allocated
          
          # Add P&L to risk pot
          self.state.update_risk_pot(pnl)
          
          # Track daily PnL
          self.daily_pnl += pnl
          
          # Remove position
          del self.state.positions[ticker]
          self.state.save_state()
          
          self.logger.log(f"Exit filled: {ticker} at ${filled_price:.2f}, P&L: ${pnl:.2f}")
          self.logger.log_order('EXIT', ticker, 'FILLED', {
            'order_id': order_id,
            'units': int(total_units),
            'filled_price': filled_price,
            'pnl': pnl,
            'new_risk_pot': self.state.risk_pot
          })
          
          # Send Slack notification
          emoji = "🟢" if pnl > 0 else "🔴"
          self.slack.send_summary(f"{emoji} EXIT EXECUTED", {
            "Ticker": ticker,
            "Reason": reason,
            "Units": int(total_units),
            "Exit Price": f"${filled_price:.2f}",
            "Entry Value": f"${entry_value:,.2f}",
            "Exit Value": f"${exit_value:,.2f}",
            "P&L": f"${pnl:,.2f}",
            "Risk Pot": f"${self.state.risk_pot:,.2f}"
          })
          
          return True
        elif filled_order.status in ['pending_new', 'accepted', 'new']:
          self.logger.log(f"Exit order pending for {ticker}, status: {filled_order.status}", 'WARNING')
          self.logger.log_order('EXIT', ticker, 'PENDING', {
            'order_id': order_id,
            'status': filled_order.status
          })
          return False
        else:
          self.logger.log(f"Exit order not filled for {ticker}, status: {filled_order.status}", 'WARNING')
          self.logger.log_order('EXIT', ticker, 'NOT_FILLED', {
            'order_id': order_id,
            'status': filled_order.status
          })
          return False
          
      except Exception as e:
        self.logger.log(f"Error exiting position for {ticker}: {e}", 'ERROR')
        self.slack.send_message(f"❌ Error exiting {ticker}: {str(e)}")
        return False
  
  def reconcile_orders(self):
    """Reconcile actual broker orders with internal state"""
    self.logger.log("Starting order reconciliation...")
    
    try:
      # Get today's orders from broker
      today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
      
      request = GetOrdersRequest(
        status=QueryOrderStatus.ALL,
        after=today_start,
        limit=500
      )
      
      broker_orders = self.trading_client.get_orders(request)
      
      # Group by ticker
      orders_by_ticker = {}
      for order in broker_orders:
        ticker = order.symbol
        if ticker not in orders_by_ticker:
          orders_by_ticker[ticker] = []
        orders_by_ticker[ticker].append({
          'id': str(order.id),  # Convert UUID to string
          'side': order.side,
          'qty': float(order.qty),
          'status': order.status,
          'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else None,
          'created_at': order.created_at
        })
      
      # Check for discrepancies
      discrepancies = []
      
      for ticker, orders in orders_by_ticker.items():
        filled_orders = [o for o in orders if o['status'] == 'filled']
        
        if not filled_orders:
          continue
        
        # Check if ticker is in our positions
        if ticker in self.state.positions:
          # Count pyramid units
          our_units = len(self.state.positions[ticker]['pyramid_units'])
          broker_buys = len([o for o in filled_orders if o['side'] == OrderSide.BUY])
          
          if our_units != broker_buys:
            discrepancies.append({
              'ticker': ticker,
              'issue': 'Unit count mismatch',
              'our_count': our_units,
              'broker_count': broker_buys,
              'orders': filled_orders
            })
      
      # Report discrepancies
      if discrepancies:
        self.logger.log(f"Found {len(discrepancies)} discrepancies", 'WARNING')
        
        for disc in discrepancies:
          self.logger.log(f"Discrepancy for {disc['ticker']}: "
                         f"Our count={disc['our_count']}, Broker={disc['broker_count']}", 
                         'WARNING')
          
          # Send Slack alert
          self.slack.send_summary("⚠️ ORDER DISCREPANCY DETECTED", {
            "Ticker": disc['ticker'],
            "Issue": disc['issue'],
            "Our Count": disc['our_count'],
            "Broker Count": disc['broker_count'],
            "Action Required": "Manual review needed"
          })
      else:
        self.logger.log("No discrepancies found")
      
      return orders_by_ticker, discrepancies
      
    except Exception as e:
      self.logger.log(f"Error reconciling orders: {e}", 'ERROR')
      return {}, []
  
  def align_state_with_broker(self, dry_run=True):
    """
    Align trading_state.json with actual broker positions
    
    This will:
    1. Get all current broker positions
    2. Get recent filled orders to reconstruct pyramid units
    3. Update internal state to match broker reality
    4. Recalculate risk pot based on actual positions
    
    Args:
      dry_run: If True, only show what would change without applying
    """
    self.logger.log("="*60)
    self.logger.log("STARTING STATE ALIGNMENT WITH BROKER")
    self.logger.log("="*60)
    
    if dry_run:
      self.logger.log("DRY RUN MODE - No changes will be applied", "WARNING")
    
    try:
      # Get current broker positions
      broker_positions = self.trading_client.get_all_positions()
      
      # Get recent orders (last 30 days) to reconstruct pyramid units
      lookback_start = datetime.now() - timedelta(days=30)
      
      request = GetOrdersRequest(
        status=QueryOrderStatus.CLOSED,
        after=lookback_start,
        limit=500
      )
      
      recent_orders = self.trading_client.get_orders(request)
      
      # Build broker state
      broker_state = {}
      orders_by_ticker = {}
      
      # Group orders by ticker
      for order in recent_orders:
        if order.status == 'filled' and order.side == OrderSide.BUY:
          ticker = order.symbol
          if ticker not in orders_by_ticker:
            orders_by_ticker[ticker] = []
          orders_by_ticker[ticker].append({
            'order_id': str(order.id),  # Convert UUID to string
            'qty': float(order.qty),
            'filled_price': float(order.filled_avg_price),
            'filled_at': order.filled_at
          })
      
      # Match with current positions
      for position in broker_positions:
        ticker = position.symbol
        qty = float(position.qty)
        current_price = float(position.current_price)
        avg_entry_price = float(position.avg_entry_price)
        market_value = float(position.market_value)
        cost_basis = float(position.cost_basis)
        
        self.logger.log(f"\nBroker position: {ticker}")
        self.logger.log(f"  Quantity: {qty}")
        self.logger.log(f"  Avg Entry: ${avg_entry_price:.2f}")
        self.logger.log(f"  Cost Basis: ${cost_basis:.2f}")
        
        # Get historical data to estimate N
        df = self.get_historical_data(ticker, days=30)
        if df is not None and len(df) >= 20:
          df = self.calculate_indicators(df)
          estimated_n = df.iloc[-1]['N']
        else:
          # Fallback: estimate N as 2% of avg entry price
          estimated_n = avg_entry_price * 0.02
          self.logger.log(f"  Using estimated N: ${estimated_n:.2f}", "WARNING")
        
        # Reconstruct pyramid units from orders
        # Group orders from same day with similar prices into single pyramid unit
        pyramid_units = []
        if ticker in orders_by_ticker:
          sorted_orders = sorted(orders_by_ticker[ticker], key=lambda x: x['filled_at'])
          
          i = 0
          while i < len(sorted_orders):
            current_order = sorted_orders[i]
            current_date = current_order['filled_at'].date()
            current_price = current_order['filled_price']
            
            # Accumulate orders from same day with similar price (within 2%)
            total_qty = current_order['qty']
            total_value = current_order['qty'] * current_order['filled_price']
            order_ids = [current_order['order_id']]
            grouped_count = 1
            
            j = i + 1
            while j < len(sorted_orders):
              next_order = sorted_orders[j]
              next_date = next_order['filled_at'].date()
              next_price = next_order['filled_price']
              
              # Check if same day and price within 2%
              if next_date == current_date:
                price_diff_pct = abs(next_price - current_price) / current_price
                if price_diff_pct <= 0.02:  # Within 2%
                  total_qty += next_order['qty']
                  total_value += next_order['qty'] * next_order['filled_price']
                  order_ids.append(next_order['order_id'])
                  grouped_count += 1
                  j += 1
                else:
                  break
              else:
                break
            
            # Calculate weighted average price
            avg_price = total_value / total_qty
            
            pyramid_units.append({
              'units': total_qty,
              'entry_price': avg_price,
              'entry_n': estimated_n,
              'entry_value': total_value,
              'entry_date': current_order['filled_at'].isoformat(),
              'order_id': ','.join(str(order_id) for order_id in order_ids),
              'grouped_orders': grouped_count
            })
            
            if grouped_count > 1:
              self.logger.log(f"  Grouped {grouped_count} orders from {current_date} into single pyramid unit "
                            f"(avg price: ${avg_price:.2f})")
            
            i = j if j > i + 1 else i + 1
          
          self.logger.log(f"  Reconstructed {len(pyramid_units)} pyramid units from {len(sorted_orders)} orders")
        else:
          # No order history found, create single unit
          pyramid_units.append({
            'units': qty,
            'entry_price': avg_entry_price,
            'entry_n': estimated_n,
            'entry_value': cost_basis,
            'entry_date': datetime.now().isoformat(),
            'order_id': 'unknown'
          })
          self.logger.log(f"  No order history, created single pyramid unit", "WARNING")
        
        # Calculate stop price
        stop_price = self.calculate_overall_stop(pyramid_units)
        
        broker_state[ticker] = {
          'system': 1,
          'pyramid_units': pyramid_units,
          'entry_date': pyramid_units[0]['entry_date'],
          'stop_price': stop_price
        }
        
        self.logger.log(f"  Stop Price: ${stop_price:.2f}")
      
      # Compare with current state
      self.logger.log("\n" + "="*60)
      self.logger.log("COMPARISON")
      self.logger.log("="*60)
      
      changes = []
      
      # Check for positions in broker but not in state
      for ticker in broker_state:
        if ticker not in self.state.positions:
          changes.append(('ADD', ticker, broker_state[ticker]))
          self.logger.log(f"❌ Missing in state: {ticker}", "WARNING")
      
      # Check for positions in state but not in broker
      for ticker in self.state.positions:
        if ticker not in broker_state:
          changes.append(('REMOVE', ticker, None))
          self.logger.log(f"❌ Extra in state (not in broker): {ticker}", "WARNING")
      
      # Check for mismatches
      for ticker in self.state.positions:
        if ticker in broker_state:
          state_units = len(self.state.positions[ticker]['pyramid_units'])
          broker_units = len(broker_state[ticker]['pyramid_units'])
          
          if state_units != broker_units:
            changes.append(('UPDATE', ticker, broker_state[ticker]))
            self.logger.log(f"❌ Unit mismatch for {ticker}: state={state_units}, broker={broker_units}", "WARNING")
      
      # Calculate new risk pot
      # Start with initial risk pot and subtract all allocated risk
      new_risk_pot = _initial_risk_pot  # Starting capital - you may want to make this configurable
      
      for ticker, position in broker_state.items():
        for pyramid in position['pyramid_units']:
          risk_allocated = pyramid['units'] * 2 * pyramid['entry_n']
          new_risk_pot -= risk_allocated
      
      self.logger.log(f"\nCurrent Risk Pot: ${self.state.risk_pot:.2f}")
      self.logger.log(f"Calculated Risk Pot: ${new_risk_pot:.2f}")
      
      if abs(self.state.risk_pot - new_risk_pot) > 1:
        changes.append(('RISK_POT', None, new_risk_pot))
        self.logger.log(f"❌ Risk pot mismatch: ${self.state.risk_pot:.2f} vs ${new_risk_pot:.2f}", "WARNING")
      
      # Summary
      self.logger.log("\n" + "="*60)
      self.logger.log("SUMMARY")
      self.logger.log("="*60)
      
      if not changes:
        self.logger.log("✅ State is aligned with broker - no changes needed")
        return True
      
      self.logger.log(f"Found {len(changes)} changes needed:")
      for change_type, ticker, data in changes:
        if change_type == 'ADD':
          units = sum(p['units'] for p in data['pyramid_units'])
          self.logger.log(f"  + ADD {ticker}: {units} units, {len(data['pyramid_units'])} pyramid levels")
        elif change_type == 'REMOVE':
          self.logger.log(f"  - REMOVE {ticker}")
        elif change_type == 'UPDATE':
          units = sum(p['units'] for p in data['pyramid_units'])
          self.logger.log(f"  ↻ UPDATE {ticker}: {units} units, {len(data['pyramid_units'])} pyramid levels")
        elif change_type == 'RISK_POT':
          self.logger.log(f"  ↻ UPDATE Risk Pot: ${data:.2f}")
      
      if dry_run:
        self.logger.log("\nDRY RUN - No changes applied. Run with dry_run=False to apply changes.", "WARNING")
        return False
      
      # Apply changes
      self.logger.log("\nApplying changes...", "WARNING")
      
      # Backup current state
      backup_file = f'trading_state_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
      with open(backup_file, 'w') as f:
        json.dump({
          'risk_pot': self.state.risk_pot,
          'positions': self.state.positions,
          'entry_queue': self.state.entry_queue
        }, f, indent=2)
      self.logger.log(f"Backup saved to: {backup_file}")
      
      # Apply changes
      for change_type, ticker, data in changes:
        if change_type == 'ADD':
          self.state.positions[ticker] = data
          self.logger.log(f"  ✅ Added {ticker}")
        elif change_type == 'REMOVE':
          del self.state.positions[ticker]
          self.logger.log(f"  ✅ Removed {ticker}")
        elif change_type == 'UPDATE':
          self.state.positions[ticker] = data
          self.logger.log(f"  ✅ Updated {ticker}")
        elif change_type == 'RISK_POT':
          self.state.risk_pot = data
          self.logger.log(f"  ✅ Updated risk pot to ${data:.2f}")
      
      # Save state
      self.state.save_state()
      
      # Log state snapshot after alignment
      self.logger.log_state_snapshot(self.state, 'after_alignment')
      
      # Send Slack notification
      self.slack.send_summary("🔄 STATE ALIGNED WITH BROKER", {
        "Changes Applied": len(changes),
        "Backup File": backup_file,
        "New Risk Pot": f"${self.state.risk_pot:.2f}",
        "Positions": len(self.state.positions)
      })
      
      self.logger.log("\n✅ State alignment complete!")
      return True
      
    except Exception as e:
      self.logger.log(f"Error aligning state: {e}", 'ERROR')
      import traceback
      self.logger.log(traceback.format_exc(), 'ERROR')
      return False
  
  def daily_eod_analysis(self):
    """Run end-of-day analysis to generate entry signals for next day"""
    self.logger.log("="*60)
    self.logger.log("RUNNING END-OF-DAY ANALYSIS")
    self.logger.log("="*60)
    
    # Log state snapshot at EOD
    self.logger.log_state_snapshot(self.state, 'EOD_start')
    
    self.slack.send_message("📊 Starting end-of-day analysis...", 
                            title="EOD Analysis")
    
    signals = []
    
    for ticker in self.universe:
      if ticker in self.state.positions:
        continue
      
      df = self.get_historical_data(ticker)
      if df is None or len(df) < 55:
        continue
      
      df = self.calculate_indicators(df)
      latest = df.iloc[-1]
      
      if pd.notna(latest['high_20']) and pd.notna(latest['N']):
        proximity = (latest['high_20'] - latest['close']) / latest['close']
        
        if -0.02 <= proximity <= 0.05:
          signals.append({
            'ticker': ticker,
            'entry_price': latest['high_20'],
            'current_price': latest['close'],
            'n': latest['N'],
            'proximity': proximity * 100
          })
    
    self.state.entry_queue = sorted(signals, key=lambda x: abs(x['proximity']))
    self.state.save_state()
    
    # Log state snapshot after EOD
    self.logger.log_state_snapshot(self.state, 'EOD_complete')
    
    self.logger.log(f"Found {len(signals)} potential entry signals")
    
    if signals:
      top_signals = self.state.entry_queue[:10]
      signal_text = "\n".join([
        f"• {s['ticker']}: ${s['current_price']:.2f} (target: ${s['entry_price']:.2f}, {s['proximity']:.1f}%)"
        for s in top_signals
      ])
      self.slack.send_message(f"Found {len(signals)} entry signals\n\nTop 10:\n{signal_text}",
                              title="📈 Entry Signals Generated")
    else:
      self.slack.send_message("No entry signals found", title="📈 Entry Signals")
  
  def market_open_setup(self):
    """Setup routine at market open"""
    self.logger.log("="*60)
    self.logger.log("MARKET OPEN SETUP")
    self.logger.log("="*60)
    
    # Log state snapshot at market open
    self.logger.log_state_snapshot(self.state, 'market_open')
    
    account = self.trading_client.get_account()
    
    summary = {
      "Risk Pot": f"${self.state.risk_pot:,.2f}",
      "Buying Power": f"${float(account.buying_power):,.2f}",
      "Equity": f"${float(account.equity):,.2f}",
      "Open Positions": len(self.state.positions),
      "Entry Queue": len(self.state.entry_queue)
    }
    
    self.slack.send_summary("🔔 Market Open", summary)
    self.logger.log(f"Market open - Risk Pot: ${self.state.risk_pot:,.2f}, "
                   f"Positions: {len(self.state.positions)}")
    
  def check_pending_orders(self):
    """Check status of pending orders and clean up"""
    try:
      request = GetOrdersRequest(
        status=QueryOrderStatus.OPEN,
        limit=100
      )
      open_orders = self.trading_client.get_orders(request)
      
      if open_orders:
        self.logger.log(f"Found {len(open_orders)} open orders")
        for order in open_orders:
          self.logger.log(f"  {order.symbol}: {order.side} {order.qty} @ {order.stop_price}, status: {order.status}")
      
      # Clean up stale pending pyramid orders
      for ticker in list(self.state.pending_pyramid_orders.keys()):
        order_id = self.state.pending_pyramid_orders[ticker]
        try:
          order = self.trading_client.get_order_by_id(order_id)
          if order.status not in ['pending_new', 'accepted', 'new']:
            del self.state.pending_pyramid_orders[ticker]
            self.logger.log(f"Removed stale pending pyramid order for {ticker}")
        except:
          del self.state.pending_pyramid_orders[ticker]
      
      if self.state.pending_pyramid_orders:
        self.state.save_state()
        
    except Exception as e:
      self.logger.log(f"Error checking pending orders: {e}", 'ERROR')

  def check_position_stops(self):
    """Check if any positions hit stop loss"""
    positions_to_exit = []
    
    for ticker, position in self.state.positions.items():
      current_price = self.get_current_price(ticker)
      
      if current_price is None:
        continue
      
      stop_price = position['stop_price']
      
      if current_price <= stop_price * 1.01:
        self.logger.log(f"Stop loss triggered for {ticker}: ${current_price:.2f} <= ${stop_price * 1.01:.2f}")
        positions_to_exit.append((ticker, current_price, 'Stop loss'))
    
    for ticker, price, reason in positions_to_exit:
      self.exit_position(ticker, price, reason)
  
  def check_exit_signals(self):
    """Check if any positions hit exit signals"""
    positions_to_exit = []
    
    for ticker, position in self.state.positions.items():
      df = self.get_historical_data(ticker, days=30)
      if df is None or len(df) < 10:
        continue
      
      df = self.calculate_indicators(df)
      latest = df.iloc[-1]
      
      current_price = self.get_current_price(ticker)
      if current_price is None:
        continue
      
      if pd.notna(latest['low_10']) and current_price < latest['low_10'] * 1.01:
        self.logger.log(f"System 1 exit signal for {ticker}: ${current_price:.2f} < ${latest['low_10'] * 1.01:.2f}")
        positions_to_exit.append((ticker, current_price, 'System 1 exit signal'))
    
    for ticker, price, reason in positions_to_exit:
      self.exit_position(ticker, price, reason)

  def check_pyramid_opportunities(self):
    """Check if any positions can pyramid"""
    for ticker, position in self.state.positions.items():
      # Check if already at max pyramid levels
      if len(position['pyramid_units']) >= 4:
        continue
      
      # Check if risk pot available
      if self.state.risk_pot <= 0:
        continue
      
      # Check if there's already a pending pyramid order for this ticker
      if ticker in self.state.pending_pyramid_orders:
        try:
          order_id = self.state.pending_pyramid_orders[ticker]
          order = self.trading_client.get_order_by_id(order_id)
          
          if order.status in ['pending_new', 'accepted', 'new']:
            self.logger.log(f"Pyramid order already pending for {ticker} (order {order_id})")
            continue
          elif order.status == 'filled':
            # Order was filled, should already be in pyramid_units
            # Clean up tracking
            del self.state.pending_pyramid_orders[ticker]
            self.state.save_state()
            self.logger.log(f"Pending pyramid order for {ticker} was filled, removed from tracking")
            continue
          else:
            # Order was cancelled, rejected, or expired - remove tracking
            self.logger.log(f"Pyramid order for {ticker} no longer pending (status: {order.status}), removing tracking")
            del self.state.pending_pyramid_orders[ticker]
            self.state.save_state()
            # Continue to check if we should place a new order
        except Exception as e:
          # Order not found or error - remove tracking and continue
          self.logger.log(f"Error checking pending pyramid order for {ticker}: {e}, removing tracking")
          del self.state.pending_pyramid_orders[ticker]
          self.state.save_state()
      
      # Get current price
      current_price = self.get_current_price(ticker)
      if current_price is None:
        continue
      
      # Get historical data for current N
      df = self.get_historical_data(ticker, days=30)
      if df is None:
        continue
      
      df = self.calculate_indicators(df)
      current_n = df.iloc[-1]['N']
      
      if pd.isna(current_n) or current_n == 0:
        continue
      
      # Get last pyramid entry price
      last_pyramid = position['pyramid_units'][-1]
      last_entry_price = last_pyramid['entry_price']
      
      # Calculate pyramid trigger: 0.5N above last entry
      pyramid_trigger = last_entry_price + 0.5 * current_n
      
      # Check if price has reached trigger (with 1% margin)
      if current_price > pyramid_trigger * 0.99:
        self.logger.log(f"Pyramid opportunity for {ticker}: ${current_price:.2f} > ${pyramid_trigger * 0.99:.2f}")
        
        # Calculate position size
        unit_risk = self.state.risk_pot * 0.02
        units = unit_risk / (2 * current_n)
        
        # Check buying power
        cost = units * pyramid_trigger
        buying_power = self.get_buying_power()
        
        if cost <= buying_power:
          # Attempt to enter pyramid position
          success = self.enter_position(ticker, units, pyramid_trigger, current_n)
          
          # If order was placed but not filled, track it
          if not success:
            # Check if order is pending
            try:
              # Get most recent order for this ticker
              request = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[ticker],
                limit=1
              )
              orders = self.trading_client.get_orders(request)
              
              if orders and len(orders) > 0:
                latest_order = orders[0]
                if latest_order.side == OrderSide.BUY and latest_order.status in ['pending_new', 'accepted', 'new']:
                  # Track this pending order
                  self.state.pending_pyramid_orders[ticker] = str(latest_order.id)  # Convert UUID to string
                  self.state.save_state()
                  self.logger.log(f"Tracking pending pyramid order {latest_order.id} for {ticker}")
            except Exception as e:
              self.logger.log(f"Error tracking pending pyramid order for {ticker}: {e}", 'ERROR')
        else:
          self.logger.log(f"Insufficient buying power for pyramid on {ticker}: need ${cost:,.2f}, have ${buying_power:,.2f}")

  def process_entry_queue(self):
    """Process pending entry signals"""
    if not self.state.entry_queue:
      return
    
    buying_power = self.get_buying_power()
    processed = []
    
    for signal in self.state.entry_queue[:]:
      if buying_power <= 0:
        break
      
      ticker = signal['ticker']
      
      if ticker in self.state.positions:
        processed.append(ticker)
        continue
      
      current_price = self.get_current_price(ticker)
      if current_price is None:
        continue
      
      entry_trigger = signal['entry_price'] * self.entry_margin
      if current_price >= entry_trigger:
        if self.state.risk_pot <= 0:
          self.logger.log("Risk pot exhausted, stopping entries")
          break
        
        unit_risk = self.state.risk_pot * 0.02
        units = unit_risk / (2 * signal['n'])
        cost = units * signal['entry_price']
        
        if cost <= buying_power:
          success = self.enter_position(ticker, units, signal['entry_price'], signal['n'])
          if success:
            processed.append(ticker)
            buying_power -= cost
        else:
          self.logger.log(f"Insufficient buying power for {ticker}: need ${cost:,.2f}, have ${buying_power:,.2f}")
          break
    
    self.state.entry_queue = [s for s in self.state.entry_queue if s['ticker'] not in processed]
    if processed:
      self.state.save_state()
  
  def intraday_monitor(self):
    """Main intraday monitoring loop (run every 5 minutes)"""
    self.logger.log("="*60)
    self.logger.log(f"INTRADAY MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    self.logger.log("="*60)
    
    # Check for any pending orders first
    self.logger.log("0. Checking pending orders...")
    self.check_pending_orders()
    
    # Log state snapshot before monitoring
    self.logger.log_state_snapshot(self.state, f'intraday_{datetime.now().strftime("%H%M")}')
    
    # ... rest of your code
    
    self.logger.log("1. Checking position stops...")
    self.check_position_stops()
    
    self.logger.log("2. Checking exit signals...")
    self.check_exit_signals()
    
    self.logger.log("3. Checking pyramid opportunities...")
    self.check_pyramid_opportunities()
    
    self.logger.log("4. Processing entry queue...")
    self.process_entry_queue()
    
    self.logger.log(f"Status: {len(self.state.positions)} positions, {len(self.state.entry_queue)} pending entries")
    self.logger.log(f"Risk Pot: ${self.state.risk_pot:,.2f}")
  
  def post_market_routine(self):
    """Post-market routine - generate daily report"""
    self.logger.log("="*60)
    self.logger.log("POST-MARKET ROUTINE")
    self.logger.log("="*60)
    
    # Log state snapshot at market close
    self.logger.log_state_snapshot(self.state, 'market_close')
    
    # Reconcile orders
    broker_orders, discrepancies = self.reconcile_orders()
    
    account = self.trading_client.get_account()
    
    # Get daily orders from logger
    daily_orders = self.logger.get_daily_orders()
    orders_placed = len([o for o in daily_orders if o['status'] == 'PLACED'])
    orders_filled = len([o for o in daily_orders if o['status'] == 'FILLED'])
    orders_not_filled = len([o for o in daily_orders if o['status'] == 'NOT_FILLED'])
    
    summary = {
      "Daily P&L": f"${self.daily_pnl:,.2f}",
      "Risk Pot": f"${self.state.risk_pot:,.2f}",
      "Equity": f"${float(account.equity):,.2f}",
      "Open Positions": len(self.state.positions),
      "Cash": f"${float(account.cash):,.2f}",
      "Orders Placed": orders_placed,
      "Orders Filled": orders_filled,
      "Orders Not Filled": orders_not_filled
    }
    
    if discrepancies:
      summary["⚠️ Discrepancies"] = len(discrepancies)
    
    # List open positions
    if self.state.positions:
      positions_text = "\n".join([
        f"• {ticker}: {len(pos['pyramid_units'])} pyramid levels, stop ${pos['stop_price']:.2f}"
        for ticker, pos in self.state.positions.items()
      ])
      summary["Positions"] = f"\n{positions_text}"
    
    # Order details
    if daily_orders:
      order_summary = []
      for order in daily_orders:
        order_summary.append(
          f"• {order['type']} {order['ticker']}: {order['status']}"
        )
      summary["Today's Orders"] = f"\n{'\n'.join(order_summary[:20])}"  # Limit to 20
    
    self.slack.send_summary("📊 Daily Summary", summary)
    
    self.logger.log(f"Daily summary sent - P&L: ${self.daily_pnl:,.2f}")
    
    # Reset daily PnL
    self.daily_pnl = 0


def load_config(config_path, key):
  """Load configuration from JSON file"""
  with open(config_path, 'r') as f:
    config = json.load(f)
    return config[key]


def main():
  # Load API keys
  alpaca_key = load_config('./.config/alpaca_api_keys.json', 'ALPACA_PAPER_KEY')
  alpaca_secret = load_config('./.config/alpaca_api_keys.json', 'ALPACA_PAPER_SECRET')
  slack_token = load_config('./.config/personal_slack_token.json', 'PERSONAL_SLACK_TOKEN')
  slack_channel = 'C09M9NNU8JH'
  
  # Initialize trading system
  system = TurtleTrading(
    api_key=alpaca_key,
    api_secret=alpaca_secret,
    slack_token=slack_token,
    slack_channel=slack_channel,
    paper=True,
    entry_margin=0.99,
    exit_margin=1.01
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