# Turtle Trading Alpaca

This project is a full implementation of the Turtle Trading strategy, adapted for automated trading on the Alpaca platform. It includes modules for data gathering, backtesting, and live trading, with Slack integration for real-time notifications.

## Table of Contents

- [Turtle Trading Alpaca](#turtle-trading-alpaca)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Architecture](#architecture)
    - [Core Modules](#core-modules)
    - [Utility Modules](#utility-modules)
    - [Main Orchestrator](#main-orchestrator)
  - [Setup](#setup)
  - [Usage](#usage)
    - [Automated Trading (Recommended)](#automated-trading-recommended)
    - [Manual Trading](#manual-trading)
    - [Backtesting](#backtesting)
    - [Running Tests](#running-tests)
  - [Workflows](#workflows)
  - [System Logic](#system-logic)
    - [Dual System Strategy](#dual-system-strategy)
    - [Pyramiding](#pyramiding)
    - [Exit](#exit)
  - [Configuration Options](#configuration-options)
  - [Risk Management](#risk-management)
  - [Git Integration](#git-integration)
  - [Slack Notifications](#slack-notifications)
  - [Disclaimer](#disclaimer)

## Features

- **Flexible Trading System**: Single unified system with configurable options:
  - **Position Types**: Long-only, short-only, or long+short positions
  - **Trading Systems**: System 1 only (20-10), System 2 only (55-20), or dual system (20-10 + 55-20)
  - System 1: 20-day entry, 10-day exit (faster trades, higher turnover, with win filter)
  - System 2: 55-day entry, 20-day exit (trend following, larger profits, no win filter)
- **Risk-Based Position Sizing**: Calculates trade sizes based on 1% risk per unit (0.5% default)
- **Pyramiding**: Adds to winning positions up to 4 times, spaced by 0.5N
- **Dynamic Stop-Loss**: Adjusts stop-loss orders based on the highest entry price of a pyramided position (2N stops)
- **System-Specific Exits**: Each position uses the exit rules of its entry system (when dual system enabled)
- **Automated Scheduling**: Uses a scheduler to run trading workflows at appropriate market times
- **Unified Backtesting Engine**: Single backtester supporting all configuration combinations
- **Hard-to-Borrow (HTB) Detection**: Multi-layered approach to avoid problematic short positions
- **Slack Integration**: Sends real-time alerts for trades, daily summaries, and system status
- **State Persistence**: Maintains the trading state (positions, risk pot) in JSON files
- **Git Integration**: Automatic git fetch at market open and git push of logs at end of day
- **Modular Architecture**: Refactored into focused, testable components for better maintainability
- **Comprehensive Testing**: Unit tests covering core trading logic

## Project Structure

```
/
├── backtesting/                    # Backtesting scripts and results
│   ├── turtle_unified_backtester.py            # Unified backtester (all configurations)
│   ├── turtle_long_short_backtester.py         # Legacy: Long-short System 2 only
│   ├── turtle_long_short_dual_system_backtester.py  # Legacy: Dual system
│   └── turtle_unified_*_results/              # Backtest results and plots
├── data/
│   ├── alpaca_daily/              # Daily historical stock data from Alpaca
│   └── all_tickers.txt            # Master ticker list
├── data_gathering/                # Scripts to download historical data
│   └── get_historical_stock_price_data_from_alpaca_API.py
├── logs/                          # Daily logs for trading activities, orders, and state
│   └── system_long_short/         # Logs for the trading system
├── system_long_short/             # Unified modular trading system (configurable)
│   ├── core/                      # Core trading logic modules
│   │   ├── data_provider.py       # Market data fetching from Alpaca
│   │   ├── indicators.py          # ATR and Donchian channels calculation
│   │   ├── signal_generator.py    # Dual system entry/exit signal generation
│   │   ├── position_manager.py    # Position and pyramid management (long/short)
│   │   └── order_manager.py       # Order execution and tracking (long/short)
│   ├── utils/                     # Utility modules
│   │   ├── decorators.py          # Retry and error handling decorators
│   │   ├── logger.py              # Daily logging functionality
│   │   ├── notifier.py            # Slack notification system
│   │   └── state_manager.py       # State persistence management
│   ├── turtle_trading_ls.py       # Main orchestrator (TurtleTradingLS class)
│   ├── turtle_manual_ls.py        # Interactive manual control script
│   ├── turtle_scheduler_ls.py     # Scheduler with git integration
│   ├── ticker_universe.txt        # Active ticker list
│   ├── ticker_universe_whole.txt  # Full ticker list
│   ├── trading_state_ls.json      # State file (positions, entry queue, etc.)
│   ├── htb_exclusions.txt         # Hard-to-borrow exclusion list
│   └── README.md                  # Detailed system documentation
├── tests/                          # Unit tests
│   ├── test_system_long_short/    # Tests for system_long_short
│   │   ├── test_core/             # Tests for core trading modules
│   │   └── test_utils/            # Tests for utility modules
│   └── run_tests.py               # Test runner
├── graveyard/                     # Old or unused scripts
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

**Note**: The system is now unified under `system_long_short/` with configuration options to enable/disable:
- Long positions (`enable_longs`)
- Short positions (`enable_shorts`)
- System 1 (`enable_system1`)
- System 2 (`enable_system2`)

This allows running as long-only, short-only, long+short, System 1 only, System 2 only, or dual system - all from a single codebase.

## Architecture

The system has been refactored into a modular architecture with clear separation of concerns:

### Core Modules (`system_long_short/core/`)
- **DataProvider**: Fetches market data from Alpaca API with retry logic and batch fetching capabilities
- **IndicatorCalculator**: Calculates ATR and Donchian Channels (10-day, 20-day, 55-day)
- **SignalGenerator**: Generates dual system entry/exit signals with configurable system priority
  - System 1 (20-10): Faster entries/exits with win filter
  - System 2 (55-20): Trend-following entries/exits without win filter
  - Configurable to use either system independently or both together
- **PositionManager**: Manages positions, pyramids, and risk calculations for both long and short positions
- **OrderManager**: Executes and tracks orders with error handling for both long and short sides

### Utility Modules (`system_long_short/utils/`)
- **DailyLogger**: Logs trading activities, orders, and state snapshots to daily log files
- **SlackNotifier**: Sends real-time notifications to Slack with formatted summaries
- **StateManager**: Persists and loads trading state (positions, entry queue, pending orders)
- **Decorators**: Retry logic for API calls with exponential backoff

### Main Orchestrator
- **TurtleTradingLS** (`system_long_short/turtle_trading_ls.py`): Main class that coordinates all components
  - Configurable for long-only, short-only, or long+short trading
  - Configurable for System 1 only, System 2 only, or dual system operation
  - Handles zombie order reconciliation, pending order tracking, and state rebuilding

This architecture makes the system easier to test, maintain, and extend. The unified design with configuration flags eliminates code duplication while supporting all trading modes.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install manually:
   ```bash
   pip install alpaca-py pandas numpy requests schedule matplotlib slack-sdk tqdm
   ```

2. **Configure API Keys**:
   ```bash
   export ALPACA_PAPER_LS_KEY="your_alpaca_api_key"
   export ALPACA_PAPER_LS_SECRET="your_alpaca_api_secret"
   export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
   ```

   **Note**: The system uses Alpaca paper trading by default. For live trading, change `paper=True` to `paper=False` in the initialization and ensure you're using live API keys.

3. **Define Ticker Universe**:
   Create a `ticker_universe.txt` file in the `system_long_short/` directory with one ticker symbol per line. If this file is not found, a default list of tickers will be used. A full list is provided in `ticker_universe_whole.txt` as a reference.

4. **Configure Hard-to-Borrow Exclusions** (for short selling):
   Create `system_long_short/htb_exclusions.txt` to manually exclude tickers that should not be shorted:
   ```txt
   # Hard-to-Borrow Exclusions
   GME
   AMC
   BBBY
   ```

5. **Download Historical Data** (for backtesting):
   Run the data gathering script to download the necessary historical data for your tickers:
   ```bash
   python data_gathering/get_historical_stock_price_data_from_alpaca_API.py
   ```

## Usage

### Automated Trading (Recommended)

The scheduler script automates all trading workflows and runs on a schedule during market days:

```bash
python -m system_long_short.turtle_scheduler_ls
```

The scheduler performs the following actions at the specified times (Pacific Time):
- **5:00 AM**: End-of-day analysis to prepare for the next trading day
- **6:25 AM**: Market open setup (includes git fetch for version control)
- **6:30 AM - 1:00 PM**: Intraday monitoring (every 5 minutes)
- **1:15 PM**: Post-market routine (includes git push of logs and state)

### Manual Trading

You can manually trigger trading workflows using the interactive manual control script:

```bash
python -m system_long_short.turtle_manual_ls
```

**Available commands**:
1. **Daily EOD Analysis**: Scan ticker universe and generate entry signals
2. **Market Open Setup**: Display account status and pending signals
3. **Intraday Monitor**: Single monitoring cycle (checks stops, exits, pyramids, entries)
4. **Post-Market Routine**: Generate daily summary report
5. **Check Long Position Stops**: Manually check long stop losses
6. **Check Short Position Stops**: Manually check short stop losses
7. **Check Exit Signals**: Check for exit signals on open positions
8. **Process Entry Queue**: Process pending entry signals
9. **Emergency Exit All Positions**: Market order exit for all positions
10. **Rebuild State from Broker**: Reconstruct state from Alpaca (useful for recovery)

### Programmatic Usage

You can also use the system programmatically with custom configurations:

```python
from system_long_short import TurtleTradingLS
import os

# Initialize with configuration
system = TurtleTradingLS(
    api_key=os.environ.get('ALPACA_PAPER_LS_KEY'),
    api_secret=os.environ.get('ALPACA_PAPER_LS_SECRET'),
    slack_token=os.environ.get('SLACK_BOT_TOKEN'),
    slack_channel='YOUR_CHANNEL_ID',
    paper=True,
    # Configuration options:
    enable_longs=True,        # Enable long positions
    enable_shorts=True,       # Enable short positions
    enable_system1=True,      # Enable System 1 (20-10)
    enable_system2=False,     # Enable System 2 (55-20)
    check_shortability=False  # Check Alpaca shortable list
)

# Run workflows
system.daily_eod_analysis()       # Generate entry signals
system.market_open_setup()        # Pre-market setup
system.intraday_monitor()         # Monitor and execute trades
system.post_market_routine()      # Daily summary report
```

### Backtesting

The project includes a unified backtester that supports all trading configurations:

**Unified Backtester** (Recommended):
```bash
python backtesting/turtle_unified_backtester.py
```

The unified backtester supports all combinations of:
- **Position types**: Long-only, short-only, or long+short
- **Trading systems**: System 1 only (20-10), System 2 only (55-20), or dual system (both)
- **Shortability checking**: Optional filtering of shortable tickers

**Configuration examples**:
```python
# Example 1: Long+Short with System 1 only
backtester = TurtleUnifiedBacktester(
    enable_longs=True,
    enable_shorts=True,
    enable_system1=True,
    enable_system2=False
)

# Example 2: Long-only with Dual System
backtester = TurtleUnifiedBacktester(
    enable_longs=True,
    enable_shorts=False,
    enable_system1=True,
    enable_system2=True
)

# Example 3: Long+Short with Dual System (recommended)
backtester = TurtleUnifiedBacktester(
    enable_longs=True,
    enable_shorts=True,
    enable_system1=True,
    enable_system2=True
)
```

**Legacy Backtesters** (still available):
```bash
# Long-short with System 2 only (55-20)
python backtesting/turtle_long_short_backtester.py

# Long-short with dual system (20-10 + 55-20)
python backtesting/turtle_long_short_dual_system_backtester.py
```

**Prerequisites**:
1. Download historical data using the data gathering script
2. Ensure data is in `data/alpaca_daily/` directory

**Output**:
- Performance metrics (total return, CAGR, win rate, avg win/loss, Sharpe ratio, max drawdown)
- Equity curves showing portfolio value over time
- Position tracking (long units, short units, net exposure, cash)
- Trade-by-trade breakdown by system (when dual system enabled)
- Yearly breakdowns with individual plots
- Daily backtest logs in JSONL format
- Plots saved to `backtesting/turtle_unified_*_results/` directories

**Key insight**: Backtesting consistently shows that the **dual system (System 1 + System 2) significantly outperforms single-system approaches** due to:
- System 2 holds trends longer (20-day exits vs 10-day)
- System 2 has no win filter, capturing more opportunities
- Complementary trade durations create smoother equity curves

### Running Tests

The system includes unit tests for core trading logic:

```bash
# Run all tests
python tests/run_tests.py

# Run tests for specific modules
python -m unittest tests.test_system_long_short.test_core.test_indicators
python -m unittest tests.test_system_long_short.test_core.test_position_manager
python -m unittest tests.test_system_long_short.test_core.test_signal_generator

# Run specific test
python -m unittest tests.test_system_long_short.test_core.test_position_manager.TestPositionManager.test_calculate_position_size
```

**Test Coverage:**
- Unit tests covering core trading logic
- Tests for indicators (ATR, Donchian channels)
- Tests for position management (sizing, pyramiding, stops)
- Tests for signal generation (entry/exit signals for both systems)
- Tests for utility modules (logging, state management)

## Workflows

The system operates through four main workflows:

- **End-of-Day Analysis** (5:00 AM PT): Scans the ticker universe for potential entry signals for the next trading day. Generates a prioritized entry queue with System 1 and/or System 2 signals based on configuration. Applies win filter for System 1 signals.

- **Market Open Setup** (6:25 AM PT): Reports account status (equity, buying power), open positions (long/short), and pending entry signals. Performs git fetch to sync latest repository changes.

- **Intraday Monitor** (6:30 AM - 1:00 PM PT, every 5 minutes): The main trading loop that:
  1. Checks status of pending orders (fills and cancellations)
  2. Updates entry queue with fresh signals
  3. Checks stop losses for long and short positions
  4. Checks exit signals (system-specific: 10-day for S1, 20-day for S2)
  5. Checks pyramiding opportunities (up to 4 units per position)
  6. Processes entry queue (with priority handling when dual system enabled)

- **Post-Market Routine** (1:15 PM PT): Calculates daily P&L, reports final positions, logs daily summary, and saves trading state. Commits and pushes log files and state to git repository for version control.

## System Logic

### Dual System Strategy

When both systems are enabled (`enable_system1=True` and `enable_system2=True`), the implementation uses a sophisticated dual system approach:

**System 1 (20-10) - Faster Trading**:
- **Entry**: 20-day high breakout (long) or 20-day low breakdown (short)
- **Exit**: 10-day low (long) or 10-day high (short)
- **Win filter**: May skip entries after profitable trades (to avoid overtrading)
- **Characteristics**: Higher turnover, quicker exits, more selective

**System 2 (55-20) - Trend Following**:
- **Entry**: 55-day high breakout (long) or 55-day low breakdown (short)
- **Exit**: 20-day low (long) or 20-day high (short)
- **No win filter**: Always takes entries (to capture all major breakouts)
- **Characteristics**: Longer holding periods, bigger winners, trend-following

**Entry Priority** (when both systems enabled):
1. **Pyramiding existing positions** (highest priority)
2. **System 1 signals** checked first for each ticker
3. **System 2 signals** checked if System 1 has no signal
4. Only **one position per ticker** (first system to trigger gets it)

**Why Dual System is Superior**:
1. **System 2 holds trends longer** - Exits on 20-day reversal vs System 1's 10-day, letting winners run further
2. **More entry opportunities** - System 2 has no win filter, capturing breakouts System 1 might skip
3. **Diversified trade duration** - System 1 provides quick profits with high turnover, System 2 captures major trends
4. **Complementary signals** - A 55-day high is also a 20-day high, but they differ in exit timing
5. **Smoother equity curves** - Different holding periods reduce correlation between trades

**Single System Modes**:
You can also run with a single system:
- **System 1 only** (`enable_system1=True, enable_system2=False`): More active trading
- **System 2 only** (`enable_system1=False, enable_system2=True`): Pure trend following

### Pyramiding

- Up to 4 pyramid levels are allowed per position
- Long positions: Add units when price moves up by 0.5N from the last entry
- Short positions: Add units when price moves down by 0.5N from the last entry
- All pyramids use the initial N value for consistency

### Exit

Two types of exits are used:

**1. Stop-Loss Exit** (2N from last pyramid entry):
- **Long**: Last entry price - 2N
- **Short**: Last entry price + 2N
- Stop adjusts with each pyramid level (trailing up for longs, down for shorts)

**2. Signal Exit** (system-specific):
- **System 1 positions**: Exit on 10-day reversal
  - Long: Price breaks below 10-day low
  - Short: Price breaks above 10-day high
- **System 2 positions**: Exit on 20-day reversal
  - Long: Price breaks below 20-day low
  - Short: Price breaks above 20-day high
- Each position tracks which system opened it (`system: 1` or `system: 2` in state)

## Configuration Options

The system supports flexible configuration through initialization parameters:

```python
system = TurtleTradingLS(
    # API credentials
    api_key='your_key',
    api_secret='your_secret',
    slack_token='your_slack_token',
    slack_channel='channel_id',
    
    # Trading mode
    paper=True,                      # True for paper trading, False for live
    
    # Position types
    enable_longs=True,               # Enable long positions
    enable_shorts=True,              # Enable short positions
    
    # Trading systems
    enable_system1=True,             # Enable System 1 (20-10)
    enable_system2=False,            # Enable System 2 (55-20)
    
    # Short selling configuration
    check_shortability=False,        # Check Alpaca's shortable list
    
    # Order execution
    entry_margin=0.99,               # Entry orders at 99% of breakout price
    exit_margin=1.01,                # Exit orders at 101% of signal price
    max_slippage=0.005,              # Max 0.5% slippage on limit orders
    
    # Ticker universe
    universe_file='system_long_short/ticker_universe.txt'
)
```

**Common Configurations**:
1. **Conservative (Long-only, System 2)**: Lower turnover, trend-following only
2. **Balanced (Long+Short, System 1)**: Active trading with both directions
3. **Aggressive (Long+Short, Dual System)**: Maximum opportunities, higher turnover
4. **Research (Long-only, Dual System)**: Study system behavior without short complexity

## Risk Management

- **Position Sizing**: Each position is sized to risk 0.5% of total equity per unit (configurable via `risk_per_unit_pct`)
  - Formula: `units = (equity * risk_per_unit_pct) / (2 * N)`
  - This ensures consistent dollar risk across all positions

- **Stop-Loss**: A 2N stop-loss is always maintained for each position
  - Protects against losses exceeding 1% of equity per unit
  - Adjusts with pyramid levels (trails favorably)

- **Max Positions**: Configurable limit (default: 100) on total positions (long + short combined)
  - Prevents over-concentration
  - Ensures adequate diversification

- **Margin Requirements** (for shorts):
  - 50% margin requirement for short positions
  - System checks buying power before entering shorts
  - Prevents margin calls by pre-validating available capital

- **Hard-to-Borrow (HTB) Management**:
  - Manual exclusion list (`htb_exclusions.txt`)
  - Optional Alpaca shortable check (`check_shortability=True`)
  - Graceful handling of locate failures

## Git Integration

The scheduler includes automatic git integration for version control of logs and trading state:

**Git Fetch at Market Open** (6:25 AM PT):
- Automatically fetches the latest changes from the remote repository before market open
- Ensures you're working with the latest code and configuration
- Non-blocking: Continues with market open setup even if fetch fails

**Git Push at End of Day** (1:15 PM PT):
- Automatically commits and pushes logs and state after post-market routine
- Creates a daily backup of trading activity and positions

**What gets committed**:
- All files in the `logs/system_long_short/` directory:
  - Daily trading logs
  - Order logs (placed and filled orders)
  - State snapshots at key workflow points
- Trading state file: `system_long_short/trading_state_ls.json`

**Features**:
- **Non-blocking**: Git operations won't crash the scheduler if they fail
- **Selective commits**: Only logs and trading state are committed, not code changes
- **Informative output**: Status messages for each git operation in logs
- **Automatic commit messages**: Timestamped messages for each daily commit
- **Error handling**: Gracefully handles merge conflicts and network issues

**Setup**:
Ensure git credentials are configured (SSH keys or credential helper) so push operations can run without prompts:
```bash
# Option 1: SSH keys (recommended)
ssh-keygen -t ed25519 -C "your_email@example.com"
# Add the public key to your GitHub/GitLab account

# Option 2: Credential helper
git config --global credential.helper store
```

## Slack Notifications

The system sends real-time notifications to a Slack channel for various trading events and status updates:

**Trade Notifications**:
- 🟢 **Long Entry Executed**: Ticker, units, price, cost, stop price, total equity
- 🔴 **Short Entry Executed**: Ticker, units, price, margin requirement, stop price
- 🟢/🔴 **Long/Short Exit Executed**: Ticker, units, exit price, P&L, total equity
- **Pyramid Executed**: Additional units added to existing position

**Daily Summaries**:
- 🔔 **Market Open**: Account equity, buying power, open positions, entry queue size
- 📊 **Daily Summary**: Daily P&L, final equity, positions count, orders placed/filled
- 📈 **Entry Signals Generated**: Count of potential signals by direction (long/short)

**System Events**:
- 📊 **EOD Analysis**: Start of end-of-day analysis, signal generation results
- ⚠️ **Warnings**: HTB stock warnings, zombie order detection, order failures
- 🚨 **Emergency Exit**: Results of emergency exit all positions command

**Message Format**:
```
🟢 LONG ENTRY EXECUTED
━━━━━━━━━━━━━━━━━━━━━━━━━
Ticker: AAPL
Type: Long initial entry (S1)
Units: 100
Price: $150.25
Cost: $15,025.00
Stop Price: $145.00
Total Equity: $102,345.67
```

**Setup**:
1. Create a Slack app and bot
2. Add bot to your channel
3. Set `SLACK_BOT_TOKEN` environment variable
4. Pass channel ID to TurtleTradingLS initialization

## Disclaimer

⚠️ **IMPORTANT - READ CAREFULLY**

This trading system is provided **for educational and research purposes only**.

**Risk Warnings**:
- Trading financial markets involves **substantial risk** and is not suitable for all investors
- **Short selling carries unlimited risk** - prices can theoretically rise indefinitely
- **Past performance is not indicative of future results**
- The system may have bugs or unexpected behavior
- Market conditions can change rapidly, rendering strategies ineffective

**Testing Requirements**:
- **ALWAYS test thoroughly** in a paper trading environment first
- Run backtests on historical data to understand system behavior
- Paper trade for at least 1-3 months before considering live trading
- Start with small position sizes and gradually scale up
- Never risk more capital than you can afford to lose

**Limitations**:
- Backtests do not account for slippage, commissions, or market impact
- Short borrowing costs are not modeled
- Hard-to-borrow detection is not 100% reliable
- System may behave differently in live markets vs backtests

**No Warranty**:
This software is provided "as is" without warranty of any kind, express or implied. The authors and contributors are not responsible for any losses incurred through the use of this system.

**By using this system, you acknowledge that you understand these risks and accept full responsibility for your trading decisions.**
