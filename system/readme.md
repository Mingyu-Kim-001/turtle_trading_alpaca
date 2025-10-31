# Turtle Trading Live System

A complete implementation of the Turtle Trading algorithm using Alpaca API with Slack notifications.

## Features

- **System 1 Entry**: Breakout above 20-day high
- **Position Sizing**: Risk-based position sizing (2% of risk pot per trade)
- **Pyramiding**: Up to 4 levels with 0.5N spacing
- **Stop Loss**: 2N below highest pyramid entry
- **Exit Signal**: Below 10-day low
- **Risk Management**: Unified risk pot tracking across all positions
- **Slack Notifications**: Real-time trade notifications and daily summaries

## Setup

### 1. Install Dependencies

```bash
pip install pandas numpy alpaca-py requests schedule
```

### 2. Configure API Keys

Create configuration files:

**`./.config/alpaca_api_keys.json`**:
```json
{
  "ALPACA_PAPER_KEY": "your_paper_api_key",
  "ALPACA_PAPER_SECRET": "your_paper_api_secret"
}
```

**`./.config/personal_slack_token.json`**:
```json
{
  "PERSONAL_SLACK_TOKEN": "xoxb-your-slack-token"
}
```

### 3. Create Ticker Universe

Create `ticker_universe.txt` with your tickers (one per line):
```
AAPL
MSFT
GOOGL
AMZN
...
```

Or the system will use a default universe on first run.

### 4. Initialize State

The system will automatically create `trading_state.json` to track:
- Risk pot (default: $100,000)
- Open positions
- Entry queue

## Usage

### Automated Trading (Recommended)

Run the scheduler to automate all workflows:

```bash
python turtle_scheduler.py
```

This runs:
- **5:00 AM PT**: EOD Analysis (prepare signals for next day)
- **6:25 AM PT**: Market Open Setup
- **6:30 AM - 1:00 PM PT**: Intraday Monitor (every 5 minutes)
- **1:15 PM PT**: Post-Market Routine

### Manual Testing

Test individual workflows:

```bash
# Run EOD analysis
python turtle_manual.py eod

# Market open setup
python turtle_manual.py open

# Single monitor cycle
python turtle_manual.py monitor

# Post-market routine
python turtle_manual.py close

# Check system status
python turtle_manual.py status
```

## Workflows

### 1. End-of-Day Analysis
- Scans all tickers for potential entry signals
- Identifies stocks near 20-day breakout
- Generates prioritized entry queue for next day
- Sends summary to Slack

### 2. Market Open Setup
- Reports account status
- Lists open positions
- Shows pending entry signals

### 3. Intraday Monitor (Every 5 Minutes)
- **Check Stops**: Exit if price hits stop loss
- **Check Exits**: Exit if below 10-day low
- **Check Pyramids**: Add units if price moves up 0.5N
- **Process Entries**: Execute breakout orders from queue

### 4. Post-Market Routine
- Calculate daily P&L
- Report final positions
- Save state for next day

## System Logic

### Entry
1. Wait for price to break above 20-day high
2. Calculate position size: `(2% of risk_pot) / (2*N)`
3. Execute market order
4. Set initial stop: `entry_price - 2*N`
5. Deduct risk allocation from risk pot

### Pyramiding
1. Monitor existing positions
2. If price moves up 0.5N from last entry:
   - Calculate additional units using same formula
   - Update overall stop to: `highest_entry - 2*N`
3. Maximum 4 pyramid levels per position

### Exit
1. **Stop Loss**: Exit if price ≤ stop_price
2. **Exit Signal**: Exit if price < 10-day low
3. Sell all pyramid units together
4. Return allocated risk to risk pot
5. Add P&L to risk pot

## Risk Management

### Risk Pot
- Initial: $100,000 (configurable)
- Represents total risk capacity
- Each entry allocates: `units * 2 * N`
- Risk returned on exit
- P&L added/subtracted on exit

### Position Sizing
- Each unit risks 2% of current risk pot
- Size = `(risk_pot * 0.02) / (2 * N)`
- Ensures consistent dollar risk per trade

### Stop Loss
- Always 2N below highest pyramid entry
- Updated with each pyramid addition
- Protects entire position

## Slack Notifications

### Entry Notifications 🟢
- Ticker, type (initial/pyramid)
- Units, price, cost
- Stop price, remaining risk pot

### Exit Notifications 🟢/🔴
- Ticker, reason (stop/signal)
- Exit price, P&L
- Updated risk pot

### Daily Summaries 📊
- Daily P&L
- Open positions
- Account status

## File Structure

```
.
├── turtle_live_trading.py    # Main trading system
├── turtle_scheduler.py       # Automated scheduler
├── turtle_manual.py          # Manual testing script
├── trading_state.json        # State persistence (auto-created)
├── ticker_universe.txt       # Your ticker list
├── .config/
│   ├── alpaca_api_keys.json
│   └── personal_slack_token.json
└── README.md
```

## Important Notes

### Paper Trading
- Set `paper=True` in TurtleTrading initialization
- Uses Alpaca paper trading account
- Test thoroughly before going live!

### Market Hours
- System uses Pacific Time (PT)
- Market hours: 6:30 AM - 1:00 PM PT
- Scheduler only runs on weekdays

### Buying Power
- System respects broker buying power limits
- Processes entry queue in priority order
- Stops when buying power exhausted

### Data Requirements
- Needs 55+ days of historical data per ticker
- Uses Alpaca's historical data API
- Indicators calculated fresh each day

## Monitoring

### Check System Status
```bash
python turtle_manual.py status
```

Shows:
- Account equity, cash, buying power
- Risk pot level
- Open positions with details
- Pending entry signals

### Logs
- All actions logged to console
- Slack notifications for key events
- State persisted to `trading_state.json`

## Troubleshooting

### "Insufficient buying power"
- Reduce universe size
- Increase initial capital
- Check if too many positions open

### "Order not filled"
- Market orders usually fill immediately
- Check if stock is tradable on Alpaca
- Verify market hours

### State file corruption
- Backup `trading_state.json` regularly
- Can reset by deleting and restarting
- System will initialize with default state

## Safety Features

1. **Paper Trading Default**: Always starts in paper mode
2. **State Persistence**: All positions/risk tracked
3. **Error Handling**: Continues on individual ticker errors
4. **Slack Alerts**: Notified of errors immediately
5. **Buying Power Check**: Never over-commits capital

## Customization

### Risk Per Trade
Change `unit_risk = self.state.risk_pot * 0.02` to adjust (0.02 = 2%)

### Initial Risk Pot
Change in `StateManager.__init__` or edit `trading_state.json`

### Pyramid Levels
Change `if len(pyramid_units) < 4` to adjust max pyramids

### Entry/Exit Periods
Modify in `calculate_indicators()`:
- `high_20`: Entry breakout period
- `low_10`: Exit period

## Next Steps

1. Test with manual commands first
2. Verify Slack notifications work
3. Monitor for 1-2 weeks in paper trading
4. Review P&L and adjust if needed
5. Consider going live with small capital

## Disclaimer

This system is for educational purposes. Always:
- Test thoroughly in paper trading
- Understand the risks
- Start with capital you can afford to lose
- Monitor system regularly
- Have stop-loss procedures in place

**Past performance does not guarantee future results.**