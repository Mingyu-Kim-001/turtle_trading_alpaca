"""
Scheduler for Turtle Trading System

This script runs the appropriate workflows at the right times:
- 5:00 AM PT: EOD Analysis (prepare for next trading day)
- 6:25 AM PT: Market Open Setup
- 6:30 AM - 1:00 PM PT: Intraday Monitor (every 5 minutes)
- 1:15 PM PT: Post-Market Routine

Usage:
  python turtle_scheduler.py
"""

import schedule
import time
from datetime import datetime
from .turtle_trading import TurtleTrading
import os


# Initialize trading system globally
alpaca_key = os.environ.get('ALPACA_PAPER_KEY')
alpaca_secret = os.environ.get('ALPACA_PAPER_SECRET')
slack_token = os.environ.get('PERSONAL_SLACK_TOKEN')
slack_channel = 'C09M9NNU8JH'

system = TurtleTrading(
  api_key=alpaca_key,
  api_secret=alpaca_secret,
  slack_token=slack_token,
  slack_channel=slack_channel,
  paper=True
)


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
  
  print("="*60)
  print("TURTLE TRADING SCHEDULER STARTED")
  print("="*60)
  print(f"Current time: {datetime.now()}")
  print("\nScheduled tasks:")
  print("  - 05:00 AM PT: EOD Analysis")
  print("  - 06:25 AM PT: Market Open Setup")
  print("  - 06:30-13:00 PT: Intraday Monitor (every 5 minutes)")
  print("  - 13:15 PM PT: Post-Market Routine")
  print("\nPress Ctrl+C to stop\n")
  
  # Send startup notification
  system.slack.send_message(
    f"🚀 Turtle Trading System started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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