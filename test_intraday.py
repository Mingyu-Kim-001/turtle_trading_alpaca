"""Manual test of intraday monitoring with debug output"""
import os
import sys
sys.path.insert(0, '/Users/mingyukim/Desktop/turtle_trading_alpaca')

from system_long_short.turtle_trading_ls import TurtleTradingLS

print("Initializing Turtle Trading System (Long/Short)...")

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

print("\nRunning intraday monitor...\n")
system.intraday_monitor()

print("\n=== DONE ===")
print(f"Positions: {len(system.state.long_positions)} long, {len(system.state.short_positions)} short")
print(f"Entry queue: {len(system.state.entry_queue)} signals")
