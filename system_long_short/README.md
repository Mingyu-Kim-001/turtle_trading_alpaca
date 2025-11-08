# Turtle Trading System with Long and Short Positions (Dual System)

Real-time implementation of the Turtle Trading strategy with support for both long and short positions, using **both System 1 (20-10) and System 2 (55-20)** for optimal performance.

## Overview

This system implements the **dual Turtle Trading system** with short selling support, allowing the system to profit from both upward and downward trends with two complementary trading systems:

- **System 1 (20-10)**: More frequent entries with quicker exits
- **System 2 (55-20)**: Longer-term trend following with extended hold times
- **Pyramids positions** up to 4 units (long upward, short downward)
- **Manages risk** with 2N stop losses and system-specific exit signals
- **Sizes positions** consistently based on 1% risk per unit

## Features

### System 1 (20-10) - Faster Trades
**Long Positions**:
- Entry: Price breaks above 20-day high
- Exit: Price breaks below 10-day low OR stop loss at entry - 2N
- Pyramiding: Add units at entry + 0.5N intervals (up to 4 units)
- Stop loss: Moves up with each pyramid (last entry - 2N)

**Short Positions**:
- Entry: Price breaks below 20-day low
- Exit: Price breaks above 10-day high OR stop loss at entry + 2N
- Pyramiding: Add units at entry - 0.5N intervals (up to 4 units)
- Stop loss: Moves down with each pyramid (last entry + 2N)

### System 2 (55-20) - Trend Following
**Long Positions**:
- Entry: Price breaks above 55-day high
- Exit: Price breaks below 20-day low OR stop loss at entry - 2N
- Pyramiding: Add units at entry + 0.5N intervals (up to 4 units)
- Stop loss: Moves up with each pyramid (last entry - 2N)

**Short Positions**:
- Entry: Price breaks below 55-day low
- Exit: Price breaks above 20-day high OR stop loss at entry + 2N
- Pyramiding: Add units at entry - 0.5N intervals (up to 4 units)
- Stop loss: Moves down with each pyramid (last entry + 2N)

### System Priority
- **System 1 is checked first** for each ticker (more frequent signals)
- **System 2 is checked only if** System 1 has no signal
- **One position per ticker** - only one system can hold a position at a time
- This ensures higher turnover from System 1 while capturing major trends with System 2

### Why Dual System is Superior

**The key insight**: A 55-day high is also a 20-day high, but the systems differ in EXIT timing:

1. **System 2 holds trends longer**
   - System 1 exits on 10-day reversal (quick exit)
   - System 2 exits on 20-day reversal (lets winners run)
   - This captures larger trends that System 1 would exit prematurely

2. **More entry opportunities**
   - System 1 may skip entries after winning trades (win filter)
   - System 2 has NO win filter - always takes entries
   - Captures breakouts that System 1 misses

3. **Diversified trade duration**
   - System 1: Quick trades, higher turnover
   - System 2: Trend-following, bigger winners
   - Results in smoother equity curve

**Backtesting shows the dual system significantly outperforms single-system approaches** due to the combination of quick profits (System 1) and large trend captures (System 2).

### Risk Management
- Position sizing: 1% of equity per unit risk
- Stop loss: 2N from entry price (N = 20-day ATR)
- Margin requirement: 50% of position value for shorts
- Max positions: 10 total (long + short combined)

## Directory Structure

```
system_long_short/
├── core/
│   ├── __init__.py
│   ├── data_provider.py      # Market data fetching
│   ├── indicators.py          # ATR and Donchian channels
│   ├── signal_generator.py    # Long/short entry/exit signals
│   ├── position_manager.py    # Position and pyramid management
│   └── order_manager.py       # Order execution (long/short)
├── utils/
│   ├── __init__.py
│   ├── logger.py              # Daily logging
│   ├── notifier.py            # Slack notifications
│   ├── state_manager.py       # State persistence (long/short)
│   └── decorators.py          # Utility decorators
├── turtle_trading_ls.py       # Main system orchestrator
├── turtle_scheduler_ls.py     # Automated scheduler
├── turtle_manual_ls.py        # Manual control script
└── README.md                  # This file
```

## Installation

1. **Install dependencies**:
```bash
pip install alpaca-py pandas numpy slack-sdk schedule
```

2. **Set environment variables**:
```bash
export ALPACA_PAPER_LS_KEY="your_alpaca_api_key"
export ALPACA_PAPER_LS_SECRET="your_alpaca_api_secret"
export PERSONAL_SLACK_TOKEN="your_slack_bot_token"
```

3. **Create ticker universe file** (optional):
```bash
# ticker_universe.txt - one ticker per line
AAPL
MSFT
GOOGL
AMZN
...
```

## Usage

### Automated Trading (Recommended)

Run the scheduler to execute workflows automatically:

```bash
cd system_long_short
python turtle_scheduler_ls.py
```

**Schedule**:
- 5:00 AM PT: EOD analysis (generate entry signals)
- 6:25 AM PT: Market open setup
- 6:30 AM - 1:00 PM PT: Intraday monitoring (every 5 minutes)
- 1:15 PM PT: Post-market routine

### Manual Control

For testing or manual intervention:

```bash
cd system_long_short
python turtle_manual_ls.py
```

**Available commands**:
1. Daily EOD Analysis
2. Market Open Setup
3. Intraday Monitor (single run)
4. Post-Market Routine
5. Check Long Position Stops
6. Check Short Position Stops
7. Check Exit Signals
8. Process Entry Queue
9. Emergency Exit All Positions

### Programmatic Usage

```python
from system_long_short import TurtleTradingLS

# Initialize system
system = TurtleTradingLS(
    api_key='your_key',
    api_secret='your_secret',
    slack_token='your_slack_token',
    slack_channel='your_channel_id',
    paper=True,
    enable_shorts=True,
    check_shortability=False  # Set True to check Alpaca shortable list
)

# Run workflows
system.daily_eod_analysis()       # Generate entry signals
system.market_open_setup()        # Pre-market setup
system.intraday_monitor()         # Monitor positions and execute trades
system.post_market_routine()      # Daily summary report
```

## Configuration

### Short Selling

**Enable/Disable Shorts**:
```python
system = TurtleTradingLS(
    enable_shorts=True,  # Set to False for long-only
    check_shortability=False
)
```

**Check Shortability** (recommended):
```python
system = TurtleTradingLS(
    enable_shorts=True,
    check_shortability=True  # Verifies tickers are shortable and easy-to-borrow
)
```

This checks:
- `asset.shortable` - Ticker allows short selling
- `asset.easy_to_borrow` - Ticker is not hard-to-borrow (HTB)

**Hard-to-Borrow (HTB) Exclusion List**:

Create `system_long_short/htb_exclusions.txt` to manually exclude problematic stocks:

```txt
# Hard-to-Borrow Exclusion List
GME
AMC
BBBY
```

Tickers in this file will NEVER be shorted, regardless of other checks. Update this based on your experience with:
- High borrow rates
- Limited share availability
- Short squeeze risk
- Frequent locate failures

### Position Sizing

Default: 1% risk per unit (risk_per_unit_pct=0.001)

To modify, edit `position_manager.py`:
```python
def calculate_position_size(total_equity, n, risk_per_unit_pct=0.001):
    # Adjust risk_per_unit_pct here
```

### Entry/Exit Margins

Adjust order margins in initialization:
```python
system = TurtleTradingLS(
    entry_margin=0.99,  # Entry orders at 99% of breakout price
    exit_margin=1.01    # Exit orders at 101% of signal price
)
```

## State Management

The system persists state in `trading_state_ls.json`:

```json
{
  "long_positions": {
    "AAPL": {
      "side": "long",
      "system": 2,
      "pyramid_units": [...],
      "stop_price": 150.00,
      "initial_n": 2.50,
      "initial_units": 100
    }
  },
  "short_positions": {
    "TSLA": {
      "side": "short",
      "system": 1,
      "pyramid_units": [...],
      "stop_price": 260.00,
      "initial_n": 5.00,
      "initial_units": 50
    }
  },
  "entry_queue": [
    {
      "ticker": "NVDA",
      "side": "long",
      "system": 1,
      "entry_price": 500.00,
      "n": 10.50
    }
  ],
  "pending_pyramid_orders": {},
  "pending_entry_orders": {},
  "last_updated": "2025-01-15T14:30:00"
}
```

**Note**: Each position tracks which system (1 or 2) it belongs to, ensuring correct exit signals are used.

## Backtesting

Compare performance with the backtester:

```bash
cd backtesting
python turtle_long_short_backtester.py
```

The backtester will:
- Run the strategy on historical data
- Generate performance metrics
- Create plots showing equity, cash, and position units over time
- Save results to `backtesting/turtle_long_short_plots/`

## Key Differences from Long-Only System

| Feature | Long-Only | Long-Short (Dual System) |
|---------|-----------|--------------------------|
| **Trading Systems** | Single system (20-10) | Dual system (20-10 + 55-20) |
| **Positions** | Single `positions` dict | Separate `long_positions` and `short_positions` |
| **Entry Signals** | 20-day high breakout only | System 1: 20-day high/low, System 2: 55-day high/low |
| **Exit Signals** | 10-day low only | System 1: 10-day, System 2: 20-day |
| **Stop Loss** | Entry - 2N | Long: Entry - 2N, Short: Entry + 2N |
| **Pyramiding** | Upward (entry + 0.5N) | Long: upward, Short: downward (entry - 0.5N) |
| **Margin** | Full position value | Long: full, Short: 50% margin requirement |
| **State File** | `trading_state.json` | `trading_state_ls.json` |
| **Position Tracking** | No system field | Each position tagged with `system: 1` or `system: 2` |

## Hard-to-Borrow (HTB) Detection

The system uses a **layered approach** to avoid hard-to-borrow stocks:

### Layer 1: Alpaca's `easy_to_borrow` Flag
When `check_shortability=True`, the system filters out tickers where:
```python
asset.shortable == False or asset.easy_to_borrow == False
```

**Limitations**:
- This flag is updated periodically, not real-time
- HTB status can change intraday
- Doesn't reflect current borrow rates

### Layer 2: Manual HTB Exclusion List
The `htb_exclusions.txt` file provides manual control:
```txt
GME   # Frequent short squeeze risk
AMC   # High borrow rates
TSLA  # Volatile, can be HTB during earnings
```

### Layer 3: Order Execution Feedback
If a short order fails due to share unavailability:
- Error is logged
- Order fails gracefully
- Ticker should be added to `htb_exclusions.txt`

### Recommended Workflow

1. **Enable shortability checking**:
   ```python
   system = TurtleTradingLS(check_shortability=True)
   ```

2. **Monitor failed short orders** in logs:
   ```
   [ERROR] Error placing short entry order for GME: insufficient shares available
   ```

3. **Add problematic tickers** to `htb_exclusions.txt`

4. **Review exclusion list monthly** - HTB status can change

### What the System Does NOT Detect

❌ Real-time share availability
❌ Current borrow rates/fees
❌ Locate requirements
❌ Intraday HTB status changes

**Bottom line**: The system filters out most HTB stocks, but cannot guarantee 100% detection. Monitor your short order execution and update `htb_exclusions.txt` based on experience.

## Risk Warnings

⚠️ **IMPORTANT**: This system is for educational and research purposes.

- **Short selling carries unlimited risk** - prices can theoretically rise indefinitely
- **Margin requirements** can change, leading to margin calls
- **Liquidity** may be limited for short positions
- **Borrowing costs** for shorts are not modeled in the backtest
- **Hard-to-borrow securities** may not be available for shorting (see HTB Detection above)
- **Short squeezes** can result in significant losses

**Always test thoroughly with paper trading before using real capital.**

## Monitoring and Logs

- **Daily logs**: Stored in `./logs/` directory
- **Slack notifications**: Real-time alerts for entries, exits, and errors
- **State snapshots**: Logged at key workflow points (EOD, market open, intraday, market close)

## Troubleshooting

### Issue: Short entry orders fail
**Solution**:
- Check if ticker is shortable: `check_shortability=True`
- Verify sufficient margin in account
- Check if stock is hard-to-borrow

### Issue: Positions not exiting
**Solution**:
- Check stop loss logic in logs
- Verify price data is updating correctly
- Use manual control to force exit if needed

### Issue: State file corruption
**Solution**:
- Backup files are created automatically
- Use `trading_state_backup_*.json` to restore
- Or delete state file to start fresh (will lose position tracking)

## Testing

Before deploying to production:

1. **Backtest thoroughly**: Run `turtle_long_short_backtester.py` on historical data
2. **Paper trade**: Use `paper=True` to test with Alpaca paper account
3. **Monitor closely**: Watch the first few weeks carefully
4. **Start small**: Use conservative position sizing initially
5. **Verify shortability**: If using shorts, ensure tickers are borrowable

## Support

For issues or questions:
1. Check logs in `./logs/` directory
2. Review Slack notifications for error details
3. Use manual control script for debugging
4. Consult backtester results for expected behavior

## License

This project is for educational purposes only. Use at your own risk.
