"""
Manual Testing Script for Turtle Trading System

Run specific workflows manually for testing:
  python -m system.turtle_manual eod       # Run EOD analysis
  python -m system.turtle_manual open      # Run market open setup
  python -m system.turtle_manual monitor   # Run single intraday monitor cycle
  python -m system.turtle_manual close     # Run post-market routine
  python -m system.turtle_manual status    # Show current system status
  python -m system.turtle_manual align            # Rebuild state from broker (dry-run)
  python -m system.turtle_manual align --apply    # Rebuild state from broker (apply changes)
  python -m system.turtle_manual exit-all  # EXIT ALL POSITIONS AT MARKET PRICE (DANGEROUS!)

The 'align' command rebuilds trading_state.json from:
  - Current broker positions
  - Historical order fills from Alpaca
  - Recalculated N values from historical price data
"""

import sys
import os
from .turtle_trading import TurtleTrading


def show_status(system):
  """Display current system status"""
  print("\n" + "="*60)
  print("SYSTEM STATUS")
  print("="*60)
  
  try:
    account = system.trading_client.get_account()
    
    print(f"\nAccount Status:")
    print(f"  Equity: ${float(account.equity):,.2f}")
    print(f"  Cash: ${float(account.cash):,.2f}")
    print(f"  Buying Power: ${float(account.buying_power):,.2f}")

    print(f"\nTrading State:")
    print(f"  Open Positions: {len(system.state.positions)}")
    print(f"  Entry Queue: {len(system.state.entry_queue)}")
    
    if system.state.positions:
      print(f"\nOpen Positions:")
      for ticker, pos in system.state.positions.items():
        total_units = sum(p['units'] for p in pos['pyramid_units'])
        entry_value = sum(p['entry_value'] for p in pos['pyramid_units'])
        print(f"  {ticker}:")
        print(f"    - Units: {total_units:.0f}")
        print(f"    - Entry Value: ${entry_value:,.2f}")
        print(f"    - Pyramid Levels: {len(pos['pyramid_units'])}")
        print(f"    - Stop Price: ${pos['stop_price']:.2f}")
        
        # Show each pyramid unit
        for i, unit in enumerate(pos['pyramid_units'], 1):
          print(f"      Level {i}: {unit['units']:.0f} units @ ${unit['entry_price']:.2f}, "
                f"N=${unit['entry_n']:.2f}")
    
    if system.state.entry_queue:
      print(f"\nEntry Queue (Top 5):")
      for signal in system.state.entry_queue[:5]:
        print(f"  {signal['ticker']}: ${signal['current_price']:.2f} -> ${signal['entry_price']:.2f} ({signal['proximity']:.1f}%)")
    
    # Show broker positions for comparison
    print(f"\n" + "="*60)
    print("BROKER POSITIONS (for comparison)")
    print("="*60)
    
    broker_positions = system.trading_client.get_all_positions()
    
    if broker_positions:
      for position in broker_positions:
        ticker = position.symbol
        qty = float(position.qty)
        avg_entry = float(position.avg_entry_price)
        current = float(position.current_price)
        pnl = float(position.unrealized_pl)
        pnl_pct = float(position.unrealized_plpc) * 100
        
        print(f"\n  {ticker}:")
        print(f"    - Quantity: {qty:.0f}")
        print(f"    - Avg Entry: ${avg_entry:.2f}")
        print(f"    - Current: ${current:.2f}")
        print(f"    - Unrealized P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")
        
        # Check if in our state
        if ticker in system.state.positions:
          our_units = sum(p['units'] for p in system.state.positions[ticker]['pyramid_units'])
          if abs(our_units - qty) > 0.01:
            print(f"    ⚠️  MISMATCH: Our state shows {our_units:.0f} units")
        else:
          print(f"    ⚠️  MISSING: Not found in our state!")
    else:
      print("\n  No open positions at broker")
    
    # Check for positions in state but not at broker
    for ticker in system.state.positions:
      if not any(p.symbol == ticker for p in broker_positions):
        print(f"\n  ⚠️  {ticker}: In our state but NOT at broker!")
    
  except Exception as e:
    print(f"Error getting status: {e}")
    import traceback
    traceback.print_exc()


def main():
  if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)
  
  command = sys.argv[1].lower()
  
  # Load configuration
  alpaca_key = os.environ.get('ALPACA_PAPER_KEY')
  alpaca_secret = os.environ.get('ALPACA_PAPER_SECRET')
  slack_token = os.environ.get('PERSONAL_SLACK_TOKEN')
  slack_channel = 'C09M9NNU8JH'
  
  # Initialize system
  system = TurtleTrading(
    api_key=alpaca_key,
    api_secret=alpaca_secret,
    slack_token=slack_token,
    slack_channel=slack_channel,
    paper=True
  )
  
  if command == 'eod':
    print("Running EOD Analysis...")
    system.daily_eod_analysis()
    
  elif command == 'open':
    print("Running Market Open Setup...")
    system.market_open_setup()
    
  elif command == 'monitor':
    print("Running Intraday Monitor (single cycle)...")
    system.intraday_monitor()
    
  elif command == 'close':
    print("Running Post-Market Routine...")
    system.post_market_routine()
    
  elif command == 'status':
    show_status(system)
    
  elif command == 'align':
    # Check for --apply flag
    apply_changes = '--apply' in sys.argv

    print("\n" + "="*60)
    print("STATE REBUILD FROM BROKER")
    print("="*60)
    print("\nThis will:")
    print("  - Fetch your current positions from Alpaca")
    print("  - Reconstruct pyramid_units from order history")
    print("  - Recalculate N values from historical data")
    print("  - Rebuild trading_state.json without risk_pot")

    if apply_changes:
      print("\n⚠️  --apply flag detected: Changes WILL be saved!")
      print("Your old state will be backed up automatically.")
    else:
      print("\n🔍 DRY RUN MODE (no changes will be saved)")
      print("Use 'python -m system.turtle_manual align --apply' to save changes")

    print("\n" + "="*60)

    if apply_changes:
      response = input("\nType 'REBUILD' to confirm (anything else to cancel): ")
      if response != 'REBUILD':
        print("\nRebuild cancelled.")
        sys.exit(0)

    # Run the rebuild
    system.rebuild_state_from_broker(lookback_days=90, dry_run=not apply_changes)
  
  elif command == 'exit-all':
    print("\n" + "="*60)
    print("⚠️  DANGER: EXIT ALL POSITIONS AT MARKET PRICE")
    print("="*60)
    print("\nThis will:")
    print("  - Immediately sell ALL open positions")
    print("  - Use MARKET ORDERS (fills at current market price)")
    print("  - Update risk pot with realized P&L")
    print("  - Clear all positions from state")
    print("\n🚨 This action CANNOT be undone!")
    
    # Show current positions
    if system.state.positions:
      print("\nPositions to be closed:")
      for ticker, pos in system.state.positions.items():
        total_units = sum(p['units'] for p in pos['pyramid_units'])
        entry_value = sum(p['entry_value'] for p in pos['pyramid_units'])
        print(f"  - {ticker}: {total_units:.0f} units (entry: ${entry_value:,.2f})")
    else:
      print("\nNo open positions to close.")
      sys.exit(0)
    
    print("\n" + "="*60)
    response = input("\nType 'EXIT ALL NOW' to confirm (anything else to cancel): ")
    
    if response != 'EXIT ALL NOW':
      print("\nExit cancelled.")
      sys.exit(0)
    
    print("\n🔥 Executing market exit for all positions...")
    system.exit_all_positions_market()
    
  else:
    print(f"Unknown command: {command}")
    print(__doc__)
    sys.exit(1)
  
  print("\nDone!")


if __name__ == "__main__":
  main()