"""
Manual Testing Script for Turtle Trading System (Long/Short)

Run specific workflows manually for testing:
  python -m system_long_short.turtle_manual_ls eod       # Run EOD analysis
  python -m system_long_short.turtle_manual_ls open      # Run market open setup
  python -m system_long_short.turtle_manual_ls monitor   # Run single intraday monitor cycle
  python -m system_long_short.turtle_manual_ls close     # Run post-market routine
  python -m system_long_short.turtle_manual_ls status    # Show current system status
  python -m system_long_short.turtle_manual_ls align            # Rebuild state from broker (dry-run)
  python -m system_long_short.turtle_manual_ls align --apply    # Rebuild state from broker (apply changes)
  python -m system_long_short.turtle_manual_ls exit-all  # EXIT ALL POSITIONS AT MARKET PRICE (DANGEROUS!)

Configuration flags:
  --enable-system2          Enable dual system (System 1 + System 2)
  --no-system1              Disable System 1 (only use with --enable-system2)
  --no-longs                Disable long positions
  --no-shorts               Disable short positions
  --check-shortability      Check Alpaca shortable list

Examples:
  # Default: System 1 only, long+short
  python -m system_long_short.turtle_manual_ls status

  # Dual system (System 1 + System 2)
  python -m system_long_short.turtle_manual_ls monitor --enable-system2

  # System 2 only
  python -m system_long_short.turtle_manual_ls eod --no-system1 --enable-system2

  # Long-only with dual system
  python -m system_long_short.turtle_manual_ls status --no-shorts --enable-system2

The 'align' command rebuilds trading_state_ls.json from:
  - Current broker positions (both long and short)
  - Historical order fills from Alpaca
  - Recalculated N values from historical price data
"""

import sys
import os
import argparse
from .turtle_trading_ls import TurtleTradingLS


def show_status(system):
  """Display current system status"""
  print("\n" + "="*60)
  print("SYSTEM STATUS (LONG/SHORT)")
  print("="*60)

  try:
    account = system.trading_client.get_account()

    print(f"\nAccount Status:")
    print(f"  Equity: ${float(account.equity):,.2f}")
    print(f"  Cash: ${float(account.cash):,.2f}")
    print(f"  Buying Power: ${float(account.buying_power):,.2f}")

    print(f"\nTrading State:")
    print(f"  Long Positions: {len(system.state.long_positions)}")
    print(f"  Short Positions: {len(system.state.short_positions)}")
    print(f"  Entry Queue: {len(system.state.entry_queue)}")

    if system.state.long_positions:
      print(f"\nLong Positions:")
      for ticker, pos in system.state.long_positions.items():
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

    if system.state.short_positions:
      print(f"\nShort Positions:")
      for ticker, pos in system.state.short_positions.items():
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
        side_label = "LONG" if signal['side'] == 'long' else "SHORT"
        print(f"  {signal['ticker']} ({side_label}): ${signal['current_price']:.2f} -> ${signal['entry_price']:.2f} ({signal['proximity']:.1f}%)")

    # Show broker positions for comparison
    print(f"\n" + "="*60)
    print("BROKER POSITIONS (for comparison)")
    print("="*60)

    broker_positions = system.trading_client.get_all_positions()

    if broker_positions:
      for position in broker_positions:
        ticker = position.symbol
        qty = float(position.qty)
        side = position.side
        avg_entry = float(position.avg_entry_price)
        current = float(position.current_price)
        pnl = float(position.unrealized_pl)
        pnl_pct = float(position.unrealized_plpc) * 100

        side_label = "LONG" if side.value == "long" else "SHORT"

        print(f"\n  {ticker} ({side_label}):")
        print(f"    - Quantity: {qty:.0f}")
        print(f"    - Avg Entry: ${avg_entry:.2f}")
        print(f"    - Current: ${current:.2f}")
        print(f"    - Unrealized P&L: ${pnl:.2f} ({pnl_pct:.2f}%)")

        # Check if in our state
        state_dict = system.state.long_positions if side.value == "long" else system.state.short_positions
        if ticker in state_dict:
          our_units = sum(p['units'] for p in state_dict[ticker]['pyramid_units'])
          if abs(our_units - abs(qty)) > 0.01:
            print(f"    ⚠️  MISMATCH: Our state shows {our_units:.0f} units")
        else:
          print(f"    ⚠️  MISSING: Not found in our state!")
    else:
      print("\n  No open positions at broker")

    # Check for positions in state but not at broker
    for ticker in system.state.long_positions:
      if not any(p.symbol == ticker and p.side.value == "long" for p in broker_positions):
        print(f"\n  ⚠️  {ticker} (LONG): In our state but NOT at broker!")

    for ticker in system.state.short_positions:
      if not any(p.symbol == ticker and p.side.value == "short" for p in broker_positions):
        print(f"\n  ⚠️  {ticker} (SHORT): In our state but NOT at broker!")

  except Exception as e:
    print(f"Error getting status: {e}")
    import traceback
    traceback.print_exc()


def main():
  # Parse command-line arguments
  parser = argparse.ArgumentParser(
    description='Turtle Trading Manual Control (Long/Short)',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Commands:
  eod        Run end-of-day analysis
  open       Run market open setup
  monitor    Run single intraday monitor cycle
  close      Run post-market routine
  status     Show current system status
  align      Rebuild state from broker (add --apply to save)
  exit-all   Exit all positions at market price (add --force to skip confirmation)

Examples:
  # Default: System 1 only, long+short
  python -m system_long_short.turtle_manual_ls status

  # Dual system (System 1 + System 2)
  python -m system_long_short.turtle_manual_ls monitor --enable-system2

  # System 2 only
  python -m system_long_short.turtle_manual_ls eod --no-system1 --enable-system2

  # Long-only with dual system
  python -m system_long_short.turtle_manual_ls status --no-shorts --enable-system2
    """
  )
  
  parser.add_argument('command', 
                      choices=['eod', 'open', 'monitor', 'close', 'status', 'align', 'exit-all'],
                      help='Command to execute')
  
  # Configuration flags
  parser.add_argument('--no-longs', action='store_true',
                      help='Disable long positions (default: enabled)')
  parser.add_argument('--no-shorts', action='store_true',
                      help='Disable short positions (default: enabled)')
  parser.add_argument('--enable-system2', action='store_true',
                      help='Enable System 2 (55-20) for dual system (default: System 1 only)')
  parser.add_argument('--no-system1', action='store_true',
                      help='Disable System 1 (20-10) - only use with --enable-system2')
  parser.add_argument('--check-shortability', action='store_true',
                      help='Check Alpaca shortable list (default: False)')
  
  # Special flags for specific commands
  parser.add_argument('--apply', action='store_true',
                      help='Apply changes (for align command)')
  parser.add_argument('--force', action='store_true',
                      help='Skip confirmation (for exit-all command)')
  
  args = parser.parse_args()
  
  # Configuration from arguments
  ENABLE_LONGS = not args.no_longs
  ENABLE_SHORTS = not args.no_shorts
  ENABLE_SYSTEM1 = not args.no_system1
  ENABLE_SYSTEM2 = args.enable_system2
  CHECK_SHORTABILITY = args.check_shortability
  
  # Validate configuration
  if not ENABLE_LONGS and not ENABLE_SHORTS:
    parser.error("At least one of long or short positions must be enabled")
  if not ENABLE_SYSTEM1 and not ENABLE_SYSTEM2:
    parser.error("At least one system must be enabled (use --enable-system2 if disabling System 1)")

  # Load configuration
  alpaca_key = os.environ.get('ALPACA_API_KEY')
  alpaca_secret = os.environ.get('ALPACA_SECRET')
  slack_token = os.environ.get('SLACK_BOT_TOKEN')
  slack_channel = os.environ.get('PERSONAL_SLACK_CHANNEL_ID')
  
  if not slack_channel:
    print("Warning: PERSONAL_SLACK_CHANNEL_ID not set, notifications will be disabled")
    slack_channel = None

  # Build configuration description
  config_desc = []
  if ENABLE_LONGS and ENABLE_SHORTS:
    config_desc.append("Long+Short")
  elif ENABLE_LONGS:
    config_desc.append("Long Only")
  else:
    config_desc.append("Short Only")
  
  if ENABLE_SYSTEM1 and ENABLE_SYSTEM2:
    config_desc.append("Dual System (S1+S2)")
  elif ENABLE_SYSTEM1:
    config_desc.append("System 1 Only")
  else:
    config_desc.append("System 2 Only")

  print(f"\nConfiguration: {' / '.join(config_desc)}\n")

  # Initialize system
  system = TurtleTradingLS(
    api_key=alpaca_key,
    api_secret=alpaca_secret,
    slack_token=slack_token,
    slack_channel=slack_channel,
    paper=True,
    enable_longs=ENABLE_LONGS,
    enable_shorts=ENABLE_SHORTS,
    enable_system1=ENABLE_SYSTEM1,
    enable_system2=ENABLE_SYSTEM2,
    check_shortability=CHECK_SHORTABILITY
  )
  
  command = args.command

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
    apply_changes = args.apply

    print("\n" + "="*60)
    print("STATE REBUILD FROM BROKER (LONG/SHORT)")
    print("="*60)
    print("\nThis will:")
    print("  - Fetch your current positions from Alpaca (long and short)")
    print("  - Reconstruct pyramid_units from order history")
    print("  - Recalculate N values from historical data")
    print("  - Rebuild trading_state_ls.json")

    if apply_changes:
      print("\n⚠️  --apply flag detected: Changes WILL be saved!")
      print("Your old state will be backed up automatically.")
    else:
      print("\n🔍 DRY RUN MODE (no changes will be saved)")
      print("Use 'python -m system_long_short.turtle_manual_ls align --apply' to save changes")

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
    print("  - Immediately exit ALL open positions (long and short)")
    print("  - Use MARKET ORDERS (fills at current market price)")
    print("  - Clear all positions from state")
    print("\n🚨 This action CANNOT be undone!")

    # Fetch positions directly from broker
    print("\nFetching positions from broker...")
    try:
      broker_positions = system.trading_client.get_all_positions()

      if not broker_positions:
        print("\nNo open positions at broker to close.")
        sys.exit(0)

      print("\nPositions to be closed (from broker):")
      for position in broker_positions:
        ticker = position.symbol
        qty = float(position.qty)
        side = "LONG" if position.side.value == "long" else "SHORT"
        avg_entry = float(position.avg_entry_price)
        current = float(position.current_price)
        value = abs(qty * current)
        print(f"  - {ticker} ({side}): {abs(qty):.0f} units @ ${avg_entry:.2f} (current: ${current:.2f}, value: ${value:,.2f})")

      print("\n" + "="*60)

      # Check for --force flag
      if not args.force:
        response = input("\nType 'EXIT ALL NOW' to confirm (anything else to cancel): ")
        if response != 'EXIT ALL NOW':
          print("\nExit cancelled.")
          sys.exit(0)
      else:
        print("\n⚠️  --force flag detected: Skipping confirmation...")

      print("\n🔥 Closing all positions at market price...")
      from alpaca.trading.requests import ClosePositionRequest

      for position in broker_positions:
        ticker = position.symbol
        side = "LONG" if position.side.value == "long" else "SHORT"
        print(f"  Closing {ticker} ({side})...")
        try:
          system.trading_client.close_position(ticker)
          print(f"    ✓ {ticker} closed")
        except Exception as e:
          print(f"    ✗ Error closing {ticker}: {e}")

      # Clear state
      print("\n🧹 Clearing state file...")
      system.state.long_positions = {}
      system.state.short_positions = {}
      system.state.entry_queue = []
      system.state.pending_pyramid_orders = {}
      system.state.pending_entry_orders = {}
      system.state.save_state()
      print("  ✓ State cleared and saved")

    except Exception as e:
      print(f"\nError fetching broker positions: {e}")
      import traceback
      traceback.print_exc()
      sys.exit(1)

  else:
    print(f"Unknown command: {command}")
    print(__doc__)
    sys.exit(1)

  print("\nDone!")


if __name__ == "__main__":
  main()
