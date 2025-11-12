"""
Scheduler for Turtle Trading System with Long/Short Positions

This script runs the appropriate workflows at the right times:
- 5:00 AM PT: EOD Analysis (prepare for next trading day)
- 6:25 AM PT: Market Open Setup
- 6:30 AM - 1:00 PM PT: Intraday Monitor (every 5 minutes)
- 1:15 PM PT: Post-Market Routine

Usage:
  python -m system_long_short.turtle_scheduler_ls [OPTIONS]

Examples:
  # Run with default settings (long+short, system1 only)
  python -m system_long_short.turtle_scheduler_ls

  # Run long-only, system 1 only
  python -m system_long_short.turtle_scheduler_ls --no-shorts

  # Run with both systems
  python -m system_long_short.turtle_scheduler_ls --enable-system2

  # Run with custom configuration
  python -m system_long_short.turtle_scheduler_ls --no-longs --enable-system2
"""

import schedule
import time
import argparse
from datetime import datetime
from .turtle_trading_ls import TurtleTradingLS
import os
import subprocess


# Global system instance (initialized in main)
system = None


def is_market_day():
  """Check if today is a market day (weekday)"""
  return datetime.now().weekday() < 5  # Monday = 0, Friday = 4


def run_eod_analysis():
  """Run end-of-day analysis"""
  if is_market_day():
    try:
      print(f"\n{'='*60}")
      print(f"Running EOD Analysis at {datetime.now()}")
      print(f"{'='*60}")
      system.daily_eod_analysis()
    except Exception as e:
      print(f"Error in EOD analysis: {e}")
      system.slack.send_message(f"❌ Error in EOD analysis: {str(e)}")


def run_market_open_setup():
  """Run market open setup"""
  if is_market_day():
    try:
      print(f"\n{'='*60}")
      print(f"Running Market Open Setup at {datetime.now()}")
      print(f"{'='*60}")

      system.market_open_setup()
    except Exception as e:
      print(f"Error in market open setup: {e}")
      system.slack.send_message(f"❌ Error in market open setup: {str(e)}")


def run_intraday_monitor():
  """Run intraday monitoring"""
  if is_market_day():
    # Only run during market hours (6:30 AM - 1:00 PM PT)
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # Market hours check (6:30 AM - 1:00 PM PT is 6:30 - 13:00)
    market_open = (hour == 6 and minute >= 30) or (7 <= hour < 13)

    if market_open:
      try:
        print(f"\n{'='*60}")
        print(f"Running Intraday Monitor at {datetime.now()}")
        print(f"{'='*60}")
        system.intraday_monitor()
      except Exception as e:
        print(f"Error in intraday monitor: {e}")
        system.slack.send_message(f"❌ Error in intraday monitor: {str(e)}")


def run_post_market():
  """Run post-market routine"""
  if is_market_day():
    try:
      print(f"\n{'='*60}")
      print(f"Running Post-Market Routine at {datetime.now()}")
      print(f"{'='*60}")
      system.post_market_routine()
    except Exception as e:
      print(f"Error in post-market routine: {e}")
      system.slack.send_message(f"❌ Error in post-market routine: {str(e)}")


def main():
  """Main scheduler loop"""
  global system

  # Parse command-line arguments
  parser = argparse.ArgumentParser(
    description='Turtle Trading System Scheduler (Long/Short)',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  # Run with default settings (long+short, system1 only)
  python -m system_long_short.turtle_scheduler_ls

  # Run long-only, system 1 only
  python -m system_long_short.turtle_scheduler_ls --no-shorts

  # Run with both systems
  python -m system_long_short.turtle_scheduler_ls --enable-system2

  # Run with custom configuration
  python -m system_long_short.turtle_scheduler_ls --no-longs --enable-system2 --check-shortability
    """
  )

  # Boolean flags
  parser.add_argument('--no-longs', action='store_true',
                      help='Disable long positions (default: enabled)')
  parser.add_argument('--no-shorts', action='store_true',
                      help='Disable short positions (default: enabled)')
  parser.add_argument('--enable-system2', action='store_true',
                      help='Enable System 2 (55-20) in addition to System 1 (default: System 1 only)')
  parser.add_argument('--no-system1', action='store_true',
                      help='Disable System 1 (20-10) - only use with --enable-system2')
  parser.add_argument('--check-shortability', action='store_true',
                      help='Check Alpaca shortable list (default: False)')
  parser.add_argument('--risk-per-unit', type=float, default=0.005,
                      help='Risk per unit as a fraction of account equity (default: 0.005)')

  args = parser.parse_args()

  # Note: Trading configuration now loaded from .env file
  # (Command-line args removed in favor of .env configuration)

  # Load configuration from .env file
  from utils.config import TradingConfig

  try:
    config = TradingConfig()
    print(f"Loaded configuration from .env file:")
    print(config)
  except ValueError as e:
    print(f"Error loading configuration: {e}")
    return
  except FileNotFoundError as e:
    print(f"Error: .env file not found. Please create one based on .env.example")
    return

  # Initialize trading system with configuration from .env
  # Command-line args can override .env values
  system = TurtleTradingLS(
    api_key=config.alpaca_key,
    api_secret=config.alpaca_secret,
    slack_token=config.slack_token,
    slack_channel=config.slack_channel,
    universe_file=config.universe_file,
    paper=config.paper,
    max_slippage=config.max_slippage,
    enable_longs=config.enable_longs,
    enable_shorts=config.enable_shorts,
    enable_system1=config.enable_system1,
    enable_system2=config.enable_system2,
    check_shortability=config.check_shortability,
    risk_per_unit=args.risk_per_unit if args.risk_per_unit else config.risk_per_unit
  )

  # Build configuration description
  config_desc = []
  if config.enable_longs and config.enable_shorts:
    config_desc.append("Long + Short")
  elif config.enable_longs:
    config_desc.append("Long Only")
  else:
    config_desc.append("Short Only")

  if config.enable_system1 and config.enable_system2:
    config_desc.append("Dual System (S1 + S2)")
  elif config.enable_system1:
    config_desc.append("System 1 (55-20)")
  else:
    config_desc.append("System 2 (20-10)")

  print("="*60)
  print("TURTLE TRADING SCHEDULER (LONG/SHORT) STARTED")
  print("="*60)
  print(f"Current time: {datetime.now()}")
  print(f"Configuration: {' / '.join(config_desc)}")
  print(f"Risk per unit: {args.risk_per_unit*100:.2f}% of equity")
  if CHECK_SHORTABILITY:
    print(f"Shortability check: enabled")
  print("\nScheduled tasks:")
  print("  - 05:00 AM PT: EOD Analysis")
  print("  - 06:25 AM PT: Market Open Setup")
  print("  - 06:30-13:00 PT: Intraday Monitor (every 5 minutes)")
  print("  - 13:15 PM PT: Post-Market Routine")
  print("\nPress Ctrl+C to stop\n")

  # Send startup notification
  system.slack.send_message(
    f"🚀 Turtle Trading System started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    f"Configuration: {' / '.join(config_desc)}\n"
    f"Risk per unit: {args.risk_per_unit*100:.2f}% of equity",
    title="System Startup"
  )

  # Schedule tasks (Pacific Time)

  # EOD Analysis - 5:00 AM PT (prepare for next day)
  schedule.every().day.at("05:00").do(run_eod_analysis)

  # Market Open Setup - 6:25 AM PT (5 minutes before open)
  schedule.every().day.at("06:25").do(run_market_open_setup)

  # Intraday Monitor - Every 5 minutes during market hours
  schedule.every(5).minutes.do(run_intraday_monitor)

  # Post-Market Routine - 1:15 PM PT (15 minutes after close)
  schedule.every().day.at("13:15").do(run_post_market)

  # Main loop
  try:
    while True:
      schedule.run_pending()
      time.sleep(60)  # Check every minute
  except KeyboardInterrupt:
    print("\n\nShutting down scheduler...")
    system.slack.send_message(
      f"🛑 Turtle Trading System stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
      title="System Shutdown"
    )


if __name__ == "__main__":
  main()
