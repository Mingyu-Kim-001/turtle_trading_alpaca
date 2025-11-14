# Turtle Trading Alpaca

A complete implementation of the Turtle Trading strategy with dual system support (System 1 + System 2), adapted for automated trading on the Alpaca platform. Features both long and short positions, comprehensive backtesting with parameter optimization, and multi-channel notifications.

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
    - [Configuration (.env)](#configuration-env)
    - [Automated Trading (Recommended)](#automated-trading-recommended)
    - [Manual Trading](#manual-trading)
    - [Backtesting](#backtesting)
    - [Running Tests](#running-tests)
  - [Workflows](#workflows)
  - [System Logic](#system-logic)
    - [Dual System Strategy](#dual-system-strategy)
    - [Pyramiding](#pyramiding)
    - [Exit Rules](#exit-rules)
    - [Whipsaw Protection](#whipsaw-protection)
  - [Risk Management](#risk-management)
  - [Notifications](#notifications)
  - [Disclaimer](#disclaimer)

## Features

### Trading System
- **Dual Trading Systems**: Implements both System 1 (20-10) and System 2 (55-20)
  - System 1: 20-day entry, 10-day exit (faster trades, whipsaw protection)
  - System 2: 55-day entry, 20-day exit (trend following, captures larger moves)
  - Configurable: Run System 1 only, System 2 only, or both simultaneously
- **Long and Short Positions**: Full bidirectional trading support
  - Independent position tracking for longs and shorts
  - Hard-to-borrow (HTB) detection and exclusion lists
  - Shortability checking via Alpaca API
- **Risk-Based Position Sizing**: Dynamic position sizing based on account equity
  - Default: 0.5% risk per unit (configurable)
  - Margin-aware buying power calculation (2x for Reg T margin)
- **Pyramiding**: Adds to winning positions up to 4 units
  - Triggered at 0.5N intervals (configurable)
  - Optional: Use latest N (ATR) for dynamic pyramiding
  - Stop-loss adjusts with each pyramid level (2N from last entry)
- **Whipsaw Protection**: System 1 win filter prevents overtrading
  - Skips entries after winning trades
  - Auto-resets on opposite breakout signals
- **Automated Scheduling**: Runs trading workflows at market times (5 AM - 1:15 PM PT)

### Backtesting & Optimization
- **Unified Backtester**: Single backtester supporting all configurations
  - Long/Short/Both, System 1/System 2/Both
  - Configurable parameters: risk, stop-loss multiplier, pyramid multiplier
  - Balanced mode: Maintains equal long/short exposure
  - Results caching for efficient parameter exploration
- **Parameter Grid Search**: Automated optimization across parameter space
  - 5 risk levels × 2 system configs × 4 stop-loss levels × 3 pyramid levels
  - Parallel execution across 100 seeds for statistical significance
  - Results saved to CSV for analysis
- **Multi-Seed Backtesting**: Statistical validation with parallel execution
  - Runs 1-100 seeds in parallel using all CPU cores
  - Saves detailed logs, charts, and configurations per seed
  - Enables performance distribution analysis

### Operations & Monitoring
- **Multi-Channel Notifications**: Slack and/or Telegram support
  - Real-time trade alerts with entry/exit details
  - Daily P&L summaries
  - System status and error notifications
  - Configurable per-channel enable/disable
- **.env Configuration**: Centralized configuration management
  - API keys, notification tokens
  - Trading parameters (risk, systems, enable longs/shorts)
  - Environment variable expansion support
- **State Persistence**: JSON-based state management
  - Positions, pyramids, entry queues
  - Latest N tracking for each position
  - Daily state snapshots in logs
- **Comprehensive Testing**: 34+ unit tests covering core logic
- **Modular Architecture**: Clean separation of concerns
  - Core: Data, indicators, signals, positions, orders
  - Utils: Logging, notifications, state, config

## Project Structure

```
/
├── .env                      # Configuration file (API keys, parameters) - NOT in git
├── .gitignore                # Git ignore rules (includes .env, logs/, data/)
├── requirements.txt          # Python dependencies
│
├── backtesting/              # Backtesting suite
│   ├── turtle_unified_backtester.py       # Main unified backtester
│   ├── run_parameter_grid_search.py       # Parameter optimization (12K backtests)
│   ├── run_multiple_seeds.py              # Multi-seed parallel backtesting
│   ├── backtest_results_cache_v3.csv      # Cached backtest results
│   └── results/                           # Backtest outputs (logs, charts per seed)
│
├── data/
│   ├── alpaca_daily/         # Historical daily OHLC data from Alpaca
│   └── all_tickers.txt       # Full ticker universe
│
├── data_gathering/
│   └── get_historical_stock_price_data_from_alpaca_API.py  # Data download script
│
├── system_long_short/        # Live trading system (long + short, dual system)
│   ├── core/                 # Core trading logic
│   │   ├── data_provider.py      # Market data fetching
│   │   ├── indicators.py         # ATR, Donchian Channels (10/20/55-day)
│   │   ├── signal_generator.py   # System 1 & 2 entry/exit signals
│   │   ├── position_manager.py   # Position & pyramid management
│   │   └── order_manager.py      # Order execution & tracking
│   ├── utils/                # Utility modules
│   │   ├── config.py             # .env configuration loader
│   │   ├── decorators.py         # Retry logic for API calls
│   │   ├── logger.py             # Daily logging
│   │   ├── notifier.py           # Slack/Telegram notifications
│   │   └── state_manager.py      # State persistence (JSON)
│   ├── turtle_trading_ls.py  # Main orchestrator
│   ├── turtle_manual_ls.py   # Manual control interface
│   ├── turtle_scheduler_ls.py # Automated scheduler
│   ├── ticker_universe.txt   # Active ticker list
│   ├── trading_state_ls.json # Trading state (positions, queues)
│   ├── htb_exclusions.txt    # Hard-to-borrow exclusion list
│   └── README.md             # Detailed system documentation
│
├── tests/                    # Unit tests
│   ├── test_system_long_short/
│   │   ├── test_core/        # Tests for indicators, signals, positions
│   │   ├── test_utils/       # Tests for logging, state management
│   │   └── ...               # Whipsaw protection, order status tests
│   └── run_tests.py          # Test runner
│
├── graveyard/                # Archived code & documentation
│   ├── system_long/          # Old long-only system (archived)
│   ├── LATEST_N_TRACKING_IMPLEMENTATION.md
│   ├── BALANCED_MODE_FEATURE.md
│   ├── CACHE_V3_README.md
│   └── ...                   # Other archived implementations & docs
│
└── README.md                 # This file
```

**Key Directories:**
- `system_long_short/`: Active trading system (supports both long/short, System 1/2)
- `backtesting/`: Comprehensive backtesting and optimization tools
- `graveyard/`: Archived implementations and feature documentation

## Architecture

The system follows a clean modular architecture with separation of concerns:

### Core Modules (`system_long_short/core/`)
- **DataProvider**: Fetches market data from Alpaca API with retry logic
- **IndicatorCalculator**: Calculates ATR and Donchian Channels (10/20/55-day)
- **SignalGenerator**: Generates dual system entry/exit signals with priority
  - System 1 (20-10): Faster entries/exits, whipsaw filter
  - System 2 (55-20): Trend-following entries/exits, no filter
  - Entry priority: Pyramids > System 1 > System 2
- **PositionManager**: Manages positions, pyramids, and risk calculations
  - Separate tracking for long and short positions
  - Latest N support for dynamic pyramiding
  - System tagging (1 or 2) for proper exits
- **OrderManager**: Executes and tracks orders with error handling
  - Support for both market and limit orders
  - Order status tracking and retry logic

### Utility Modules (`system_long_short/utils/`)
- **TradingConfig**: Loads configuration from .env file
  - API credentials, notification tokens
  - Trading parameters (risk, systems, longs/shorts)
  - Environment variable expansion
- **DailyLogger**: Logs trading activities, orders, and state snapshots
- **MultiNotifier**: Sends notifications to Slack and/or Telegram
  - Individual notifiers: SlackNotifier, TelegramNotifier
  - Configurable enable/disable per channel
- **StateManager**: Persists and loads trading state (JSON)
- **Decorators**: Retry logic for API calls

### Main Orchestrator
- **TurtleTradingLS**: Coordinates all components to execute the strategy
  - End-of-day analysis (5:00 AM PT)
  - Market open setup (6:25 AM PT)
  - Intraday monitoring (6:30 AM - 1:00 PM PT, every 5 min)
  - Post-market routine (1:15 PM PT)

This architecture enables comprehensive testing, easy configuration changes, and straightforward feature additions.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    
    This installs: `alpaca-py`, `pandas`, `numpy`, `matplotlib`, `requests`, `schedule`, `slack_sdk`, `tqdm`

2.  **Create .env Configuration File**:
    Create a `.env` file in the project root with your credentials and settings:

    ```bash
    # Required: Alpaca API Credentials
    ALPACA_API_KEY="your_alpaca_paper_key"
    ALPACA_SECRET="your_alpaca_paper_secret"
    
    # Optional: Slack Notifications
    SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
    PERSONAL_SLACK_CHANNEL_ID="C01234567"
    ENABLE_SLACK_NOTIFICATIONS=True
    
    # Optional: Telegram Notifications
    TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
    TELEGRAM_CHAT_ID="your_telegram_chat_id"
    ENABLE_TELEGRAM_NOTIFICATIONS=True
    
    # Trading Configuration
    PAPER_TRADING=True                    # Use paper trading (recommended)
    RISK_PER_UNIT=0.005                   # 0.5% risk per unit (default)
    MAX_SLIPPAGE=0.005                    # 0.5% max slippage for limit orders
    
    # System Configuration
    ENABLE_LONGS=True                     # Enable long positions
    ENABLE_SHORTS=True                    # Enable short positions
    ENABLE_SYSTEM1=True                   # Enable System 1 (20-10)
    ENABLE_SYSTEM2=False                  # Enable System 2 (55-20)
    CHECK_SHORTABILITY=True               # Check if stocks are shortable
    
    # Advanced: Pyramiding Behavior
    USE_LATEST_N_FOR_PYRAMIDING=False     # Use dynamic N for pyramiding (default: False)
    
    # Ticker Universe
    UNIVERSE_FILE=system_long_short/ticker_universe.txt
    ```

    **Notes**: 
    - The `.env` file is in `.gitignore` and will not be committed
    - To find Slack channel ID: Right-click on channel → View channel details → Channel ID at bottom
    - At least one notification method (Slack or Telegram) is recommended
    - System can run without notifications but you won't get alerts

3.  **Configure Ticker Universe**:
    Edit `system_long_short/ticker_universe.txt` with one ticker symbol per line:
    ```
    AAPL
    MSFT
    GOOGL
    ...
    ```

4.  **Download Historical Data** (for backtesting):
    ```bash
    python data_gathering/get_historical_stock_price_data_from_alpaca_API.py
    ```
    This downloads daily OHLCV data for all tickers in your universe to `data/alpaca_daily/`

## Usage

### Configuration (.env)

All trading parameters are configured via the `.env` file. Edit the file to change:
- Which systems to enable (System 1, System 2, or both)
- Long/short enablement
- Risk per unit
- Notification channels

Changes take effect on next run. No code modifications needed.

### Automated Trading (Recommended)

The scheduler automates all trading workflows during market hours:

```bash
python system_long_short/turtle_scheduler_ls.py
```

**Schedule** (all times in PT):
- **5:00 AM**: End-of-day analysis (scan for entry signals)
- **6:25 AM**: Market open setup (report positions, pending entries)
- **6:30 AM - 1:00 PM**: Intraday monitoring (every 5 minutes)
  - Check stop-losses
  - Check exit signals
  - Check pyramiding opportunities
  - Process entry queue
- **1:15 PM**: Post-market routine (daily P&L, save state)

Press `Ctrl+C` to stop the scheduler gracefully.

### Manual Trading

Manually trigger individual workflows for testing/debugging:

```bash
# Run end-of-day analysis
python system_long_short/turtle_manual_ls.py eod

# Run market open setup
python system_long_short/turtle_manual_ls.py open

# Run single intraday monitor cycle
python system_long_short/turtle_manual_ls.py monitor

# Run post-market routine
python system_long_short/turtle_manual_ls.py close

# Check current system status
python system_long_short/turtle_manual_ls.py status

# Align local state with broker (dry run)
python system_long_short/turtle_manual_ls.py align

# Align local state with broker (apply changes)
python system_long_short/turtle_manual_ls.py align --apply
```

See `system_long_short/README.md` for detailed workflow documentation.

### Backtesting

#### Unified Backtester

Single backtester supporting all configurations (long/short, System 1/2, parameters):

```python
from backtesting.turtle_unified_backtester import TurtleUnifiedBacktester

# Load data
data = {...}  # dict of ticker -> DataFrame

# Create backtester with custom parameters
backtester = TurtleUnifiedBacktester(
    initial_equity=10_000,
    risk_per_unit_pct=0.005,          # 0.5% risk per unit
    enable_longs=True,
    enable_shorts=True,
    enable_system1=True,              # System 1 (20-10)
    enable_system2=False,             # System 2 (55-20)
    stop_loss_atr_multiplier=2.0,     # 2N stop-loss
    pyramid_atr_multiplier=0.5,       # 0.5N pyramid spacing
    use_margin=True,                  # 2x buying power
    seed=42                           # For reproducibility
)

# Run backtest
results = backtester.run_backtest(data, start_date='2020-01-01', end_date='2024-12-31')
backtester.plot_results()
```

#### Multi-Seed Backtesting

Run backtests across multiple seeds for statistical validation:

```bash
# System 1 only (default)
python backtesting/run_multiple_seeds.py

# Dual system (System 1 + System 2)
python backtesting/run_multiple_seeds.py --enable-system2

# With balanced long/short mode
python backtesting/run_multiple_seeds.py --balance-long-short-units

# Custom parameters
python backtesting/run_multiple_seeds.py \
    --start-seed 1 --end-seed 50 \
    --risk-per-unit 0.01 \
    --enable-system2
```

Results saved to `backtesting/results/turtle_unified_{config}_results/` with:
- `config.json` - Configuration used
- `daily_backtest_log_{config}.jsonl` - Daily logs
- `equity_over_time.png` - Equity curve
- `cash_over_time.png` - Cash levels
- `units_over_time.png` - Position units

#### Parameter Grid Search

Optimize parameters across 12,000 backtests (100 seeds × 120 parameter combinations):

```bash
# Full grid search (may take hours with parallel execution)
python backtesting/run_parameter_grid_search.py

# Subset for testing
python backtesting/run_parameter_grid_search.py --start-seed 1 --end-seed 10

# Limit CPU usage
python backtesting/run_parameter_grid_search.py --workers 4
```

**Parameter Grid:**
- Risk per unit: [1%, 3%, 5%, 8%, 10%]
- System 2 enabled: [True, False]
- Stop-loss: [2N, 2.5N, 3N, 3.5N]
- Pyramid spacing: [0.5N, 0.75N, 1N]

Results saved to `backtesting/backtest_results_cache_v3.csv` for analysis.

**Output Metrics:**
- Total return, max drawdown, Sharpe ratio
- Win rate, average win/loss
- Number of trades
- Long/short unit tracking
- System-specific performance (if both enabled)

### Running Tests

The system includes comprehensive unit tests:

```bash
# Run all tests
python tests/run_tests.py

# Run tests for long-short system
python -m unittest tests.test_system_long_short.test_core.test_indicators
python -m unittest tests.test_system_long_short.test_core.test_position_manager
python -m unittest tests.test_system_long_short.test_core.test_signal_generator

# Run specific test
python -m unittest tests.test_system_long_short.test_core.test_whipsaw_protection.TestWhipsawProtection.test_win_filter_skips_entry
```

**Test Coverage:**
- 34+ unit tests covering core trading logic
- Indicators: ATR, Donchian Channels (10/20/55-day)
- Position management: sizing, pyramiding, stop-loss
- Signal generation: System 1/2 entry/exit, priority
- Whipsaw protection: win filter, reset conditions
- State management, logging
- All tests passing ✅

## Workflows

The system operates through four main workflows that run at scheduled times during market days:

1. **End-of-Day Analysis** (5:00 AM PT)
   - Scans entire ticker universe for entry signals
   - Generates prioritized entry queue for next day
   - Checks both System 1 (20-day) and System 2 (55-day) breakouts
   - Applies whipsaw filter for System 1 signals
   - Sends summary to notification channels

2. **Market Open Setup** (6:25 AM PT)
   - Reports account equity and buying power
   - Lists all open positions with current P&L
   - Shows pending entry signals in queue
   - Validates state consistency

3. **Intraday Monitor** (6:30 AM - 1:00 PM PT, every 5 min)
   - **Priority 1**: Check stop-losses (highest priority)
   - **Priority 2**: Check exit signals (10-day for System 1, 20-day for System 2)
   - **Priority 3**: Check pyramiding opportunities (0.5N intervals)
   - **Priority 4**: Process entry queue (subject to buying power)
   - Updates position tracking and places orders

4. **Post-Market Routine** (1:15 PM PT)
   - Calculates daily P&L (realized + unrealized)
   - Reports final positions and account value
   - Saves trading state to JSON
   - Creates daily snapshot in logs

## System Logic

### Dual System Strategy

The system can run **System 1 only**, **System 2 only**, or **both systems simultaneously** (configurable via `.env`):

**System 1 (20-10) - Fast Momentum**:
- **Long Entry**: Price breaks above 20-day high
- **Short Entry**: Price breaks below 20-day low
- **Long Exit**: Price breaks below 10-day low OR stop-loss
- **Short Exit**: Price breaks above 10-day high OR stop-loss
- **Whipsaw Filter**: May skip entries after winning trades (see below)

**System 2 (55-20) - Trend Following**:
- **Long Entry**: Price breaks above 55-day high
- **Short Entry**: Price breaks below 55-day low
- **Long Exit**: Price breaks below 20-day low OR stop-loss
- **Short Exit**: Price breaks above 20-day high OR stop-loss
- **No Filter**: Always takes entries (no whipsaw protection)

**When Both Systems Enabled**:
- **Entry Priority**: System 1 checked first, then System 2
- **One Position Per Ticker**: Only one system can hold a ticker at once
- **System Tagging**: Each position remembers which system opened it
- **Exit Rules**: Positions use their entry system's exit rules
- **Key Insight**: System 2 captures larger trends that System 1 would exit early

### Pyramiding

- **Max Units**: Up to 4 units per position
- **Spacing**: 0.5N intervals (configurable)
- **Long Pyramiding**: Add units when price rises 0.5N from last entry
- **Short Pyramiding**: Add units when price falls 0.5N from last entry
- **N Calculation**: 
  - Default: Use initial N (ATR at first entry) for all pyramids
  - Optional: Use latest N (`USE_LATEST_N_FOR_PYRAMIDING=True`) for dynamic adjustment
- **Priority**: Pyramiding existing positions has higher priority than new entries

### Exit Rules

**Stop-Loss (Always Active)**:
- **Long Positions**: Last entry price - 2N
- **Short Positions**: Last entry price + 2N
- Stop moves with each pyramid (protects profits)
- Highest priority in monitoring workflow

**Signal Exit (System-Specific)**:
- **System 1 Positions**: 
  - Long: Exit when price breaks below 10-day low
  - Short: Exit when price breaks above 10-day high
- **System 2 Positions**: 
  - Long: Exit when price breaks below 20-day low
  - Short: Exit when price breaks above 20-day high
- Each position uses its entry system's exit rules

### Whipsaw Protection

**System 1 Only** (System 2 has no filter):

**Win Filter Rule**:
- ✅ **After losing trade**: Take next System 1 entry
- ❌ **After winning trade**: Skip next System 1 entry
- Purpose: Avoid overtrading in choppy markets after quick wins

**Filter Reset (Breaking Condition)**:
- **For long filter**: Reset when price breaks below 20-day low
- **For short filter**: Reset when price breaks above 20-day high
- Purpose: Market regime change → filter no longer relevant

**Example Flow**:
1. Enter AAPL long on 20-day breakout → Exit with profit
2. AAPL breaks 20-day high again → **SKIP** (filter active)
3. AAPL breaks below 20-day low → **RESET FILTER** (opposite signal)
4. AAPL breaks above 20-day high → **TAKE ENTRY** (filter cleared)

**Why This Works**:
- After a quick win, market often consolidates (chop) → skip to avoid whipsaw
- Opposite breakout signals regime change → safe to re-engage
- Prevents permanent blocking while protecting from overtrading

## Risk Management

The system implements multiple layers of risk control:

**Position Sizing**:
- **Risk Per Unit**: Default 0.5% of account equity (configurable)
- **N (ATR)**: 20-day Average True Range measures volatility
- **Unit Size**: `(Account Equity × Risk%) / (2 × N)`
- **Example**: $10,000 account, 0.5% risk, N=$2 → Unit size = $25 worth of shares

**Buying Power**:
- **Margin Account**: 2x buying power (Reg T margin)
- **Long Positions**: Full position value required
- **Short Positions**: 50% margin requirement
- **Max Positions**: 100 positions max (configurable)

**Stop-Loss**:
- **Distance**: 2N from last entry price (configurable)
- **Long**: Stop at (Last Entry - 2N)
- **Short**: Stop at (Last Entry + 2N)
- **Adjustment**: Stop moves with each pyramid level
- **Purpose**: Limits loss to ~1% per unit (0.5% risk × 2N stop)

**Pyramiding Limits**:
- **Max Units**: 4 units per position
- **Max Risk**: 4 units × 0.5% = 2% total risk per ticker
- **Spacing**: 0.5N between entries (ensures profit before adding)

**Portfolio Risk**:
- Risk is distributed across multiple positions
- No single position can exceed 2% total risk (4 units max)
- Short-term (System 1) and long-term (System 2) diversification

## Notifications

The system supports **Slack** and/or **Telegram** notifications (configurable via `.env`):

### Notification Types

**Trade Alerts**:
- Entry orders: Ticker, direction, units, price, system
- Exit orders: Ticker, reason (stop-loss, signal, manual), P&L
- Pyramid adds: Level (L2, L3, L4), trigger price
- Order failures: Reason (insufficient shares, buying power, etc.)

**Daily Summaries**:
- End-of-day: Entry signals found, queue size
- Market open: Account equity, buying power, open positions
- Post-market: Daily P&L (realized + unrealized), final equity

**System Status**:
- Scheduler start/stop
- Workflow completion (EOD, open, monitor, close)
- Errors and warnings

### Setup

**Slack** (see Setup section for .env config):
1. Create Slack bot at api.slack.com
2. Add bot to channel
3. Copy bot token and channel ID to `.env`
4. Set `ENABLE_SLACK_NOTIFICATIONS=True`

**Telegram**:
1. Create bot via @BotFather
2. Get chat ID (send message, check getUpdates)
3. Add credentials to `.env`
4. Set `ENABLE_TELEGRAM_NOTIFICATIONS=True`

**Both channels can be enabled simultaneously** for redundancy.

## Disclaimer

This trading system is provided for educational purposes only. Trading financial markets involves substantial risk and is not suitable for all investors. Always test the system thoroughly in a paper trading environment before deploying it with real capital. Past performance is not indicative of future results.
