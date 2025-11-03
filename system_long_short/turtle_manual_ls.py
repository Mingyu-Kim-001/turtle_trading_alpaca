"""
Manual control script for Turtle Trading System with Long/Short Positions

This script allows manual execution of system functions for testing and management.

Usage:
  python turtle_manual_ls.py
"""

from turtle_trading_ls import TurtleTradingLS
import os


def main():
  """Interactive manual control"""

  # Initialize system
  alpaca_key = os.environ.get('ALPACA_PAPER_LS_KEY')
  alpaca_secret = os.environ.get('ALPACA_PAPER_LS_SECRET')
  slack_token = os.environ.get('PERSONAL_SLACK_TOKEN')
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

  print("\n" + "="*60)
  print("TURTLE TRADING SYSTEM (LONG/SHORT) - MANUAL CONTROL")
  print("="*60)
  print(f"Short selling: {'enabled' if system.enable_shorts else 'disabled'}")
  print(f"Long positions: {len(system.state.long_positions)}")
  print(f"Short positions: {len(system.state.short_positions)}")
  print(f"Entry queue: {len(system.state.entry_queue)}")

  while True:
    print("\n" + "="*60)
    print("Available commands:")
    print("="*60)
    print("1. Daily EOD Analysis")
    print("2. Market Open Setup")
    print("3. Intraday Monitor (single run)")
    print("4. Post-Market Routine")
    print("5. Check Long Position Stops")
    print("6. Check Short Position Stops")
    print("7. Check Exit Signals")
    print("8. Process Entry Queue")
    print("9. Emergency Exit All Positions")
    print("0. Exit")
    print("="*60)

    choice = input("\nEnter command number: ").strip()

    try:
      if choice == '1':
        print("\nRunning Daily EOD Analysis...")
        system.daily_eod_analysis()

      elif choice == '2':
        print("\nRunning Market Open Setup...")
        system.market_open_setup()

      elif choice == '3':
        print("\nRunning Intraday Monitor...")
        system.intraday_monitor()

      elif choice == '4':
        print("\nRunning Post-Market Routine...")
        system.post_market_routine()

      elif choice == '5':
        print("\nChecking Long Position Stops...")
        system.check_long_stops()
        print("Done!")

      elif choice == '6':
        print("\nChecking Short Position Stops...")
        system.check_short_stops()
        print("Done!")

      elif choice == '7':
        print("\nChecking Exit Signals...")
        system.check_long_exit_signals()
        system.check_short_exit_signals()
        print("Done!")

      elif choice == '8':
        print("\nProcessing Entry Queue...")
        system.process_entry_queue()
        print("Done!")

      elif choice == '9':
        confirm = input("\n⚠️  WARNING: This will exit ALL positions at market price. Type 'CONFIRM' to proceed: ")
        if confirm == 'CONFIRM':
          print("\nExecuting emergency exit...")
          results = system.exit_all_positions_market()
          print(f"\nExited {len([r for r in results if r['status'] == 'SUCCESS'])} positions")
        else:
          print("Cancelled.")

      elif choice == '0':
        print("\nExiting...")
        break

      else:
        print("\nInvalid command. Please try again.")

    except Exception as e:
      print(f"\n❌ Error: {e}")
      import traceback
      traceback.print_exc()


if __name__ == "__main__":
  main()
