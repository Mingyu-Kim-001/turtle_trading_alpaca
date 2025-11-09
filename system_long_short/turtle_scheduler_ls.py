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


def git_fetch():
  """Fetch latest changes from remote repository"""
  try:
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
      ['git', 'fetch', 'origin'],
      cwd=repo_path,
      capture_output=True,
      text=True,
      timeout=30
    )
    if result.returncode == 0:
      print(f"✅ Git fetch successful: {result.stdout.strip()}")
      return True
    else:
      print(f"⚠️ Git fetch warning: {result.stderr.strip()}")
      return False
  except subprocess.TimeoutExpired:
    print("⚠️ Git fetch timed out")
    return False
  except Exception as e:
    print(f"⚠️ Error during git fetch: {e}")
    return False


def git_push_logs():
  """Add, commit, and push log files to repository"""
  try:
    repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add log files and trading state files
    # Logs are in logs/ directory and trading_state.json files
    log_paths = [
      'logs/',
      'system_long/trading_state.json',
      'system_long_short/trading_state.json'
    ]
    
    has_changes = False
    
    # Add log files
    for path in log_paths:
      full_path = os.path.join(repo_path, path)
      if os.path.exists(full_path):
        add_result = subprocess.run(
          ['git', 'add', path],
          cwd=repo_path,
          capture_output=True,
          text=True,
          timeout=10
        )
        if add_result.returncode == 0:
          has_changes = True
    
    if has_changes:
      # Check if there are staged changes
      diff_result = subprocess.run(
        ['git', 'diff', '--cached', '--quiet'],
        cwd=repo_path,
        capture_output=True,
        text=True
      )
      
      if diff_result.returncode == 1:  # Has staged changes
        # Commit with timestamp
        commit_message = f"Auto-commit: EOD logs and updates - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        commit_result = subprocess.run(
          ['git', 'commit', '-m', commit_message],
          cwd=repo_path,
          capture_output=True,
          text=True,
          timeout=10
        )
        
        if commit_result.returncode == 0:
          # Push to remote
          push_result = subprocess.run(
            ['git', 'push', 'origin', 'main'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
          )
          
          if push_result.returncode == 0:
            print(f"✅ Git push successful: {commit_result.stdout.strip()}")
            return True
          else:
            print(f"⚠️ Git push warning: {push_result.stderr.strip()}")
            return False
        else:
          print(f"⚠️ Git commit warning: {commit_result.stderr.strip()}")
          return False
      else:
        print("ℹ️ No changes to commit after adding log files")
        return True
    else:
      print("ℹ️ No log files found to commit")
      return True
      
  except subprocess.TimeoutExpired:
    print("⚠️ Git operation timed out")
    return False
  except Exception as e:
    print(f"⚠️ Error during git push: {e}")
    return False


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
      
      # Fetch latest changes from repository
      print("Fetching latest changes from repository...")
      git_fetch()
      
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
      
      # Push logs and changes to repository
      print("\nPushing logs and changes to repository...")
      git_push_logs()
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

  args = parser.parse_args()

  # Configuration from arguments
  ENABLE_LONGS = not args.no_longs
  ENABLE_SHORTS = not args.no_shorts
  ENABLE_SYSTEM1 = not args.no_system1
  ENABLE_SYSTEM2 = args.enable_system2
  CHECK_SHORTABILITY = args.check_shortability

  # Validate configuration
  if not ENABLE_LONGS and not ENABLE_SHORTS:
    parser.error("At least one of --no-longs or --no-shorts must not be set (need to trade something)")
  if not ENABLE_SYSTEM1 and not ENABLE_SYSTEM2:
    parser.error("At least one system must be enabled (use --enable-system2 if disabling System 1)")

  # Get API credentials from environment
  alpaca_key = os.environ.get('ALPACA_PAPER_LS_KEY')
  alpaca_secret = os.environ.get('ALPACA_PAPER_LS_SECRET')
  slack_token = os.environ.get('SLACK_BOT_TOKEN')
  slack_channel = os.environ.get('PERSONAL_SLACK_CHANNEL_ID')

  if not alpaca_key or not alpaca_secret:
    print("Error: ALPACA_PAPER_LS_KEY and ALPACA_PAPER_LS_SECRET environment variables must be set")
    return
  
  if not slack_channel:
    print("Warning: PERSONAL_SLACK_CHANNEL_ID not set, notifications will be disabled")
    slack_channel = None

  # Initialize trading system with configuration
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

  # Build configuration description
  config_desc = []
  if ENABLE_LONGS and ENABLE_SHORTS:
    config_desc.append("Long + Short")
  elif ENABLE_LONGS:
    config_desc.append("Long Only")
  else:
    config_desc.append("Short Only")

  if ENABLE_SYSTEM1 and ENABLE_SYSTEM2:
    config_desc.append("Dual System (S1 + S2)")
  elif ENABLE_SYSTEM1:
    config_desc.append("System 1 (20-10)")
  else:
    config_desc.append("System 2 (55-20)")

  print("="*60)
  print("TURTLE TRADING SCHEDULER (LONG/SHORT) STARTED")
  print("="*60)
  print(f"Current time: {datetime.now()}")
  print(f"Configuration: {' / '.join(config_desc)}")
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
    f"Configuration: {' / '.join(config_desc)}",
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
