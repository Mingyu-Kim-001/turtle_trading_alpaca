# Turtle Trading Alpaca

This project is a full implementation of the Turtle Trading strategy, adapted for automated trading on the Alpaca platform. It includes modules for data gathering, backtesting, and live trading, with Slack integration for real-time notifications.

## Table of Contents

- [Turtle Trading Alpaca](#turtle-trading-alpaca)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Architecture](#architecture)
    - [Core Modules (`system_long/core/`)](#core-modules-system_longcore)
    - [Utility Modules (`system_long/utils/`)](#utility-modules-system_longutils)
    - [Main Orchestrator](#main-orchestrator)
  - [Setup](#setup)
  - [Usage](#usage)
    - [Automated Trading (Recommended)](#automated-trading-recommended)
    - [Manual Trading](#manual-trading)
    - [Backtesting](#backtesting)
    - [Running Tests](#running-tests)
  - [Workflows](#workflows)
  - [System Logic](#system-logic)
    - [Entry](#entry)
    - [Pyramiding](#pyramiding)
    - [Exit](#exit)
  - [Risk Management](#risk-management)
  - [Slack Notifications](#slack-notifications)
  - [Disclaimer](#disclaimer)

## Features

- **Dual Trading Systems**: Implements both System 1 (20-10) and System 2 (55-20) for optimal performance
  - System 1: 20-day entry, 10-day exit (faster trades, higher turnover)
  - System 2: 55-day entry, 20-day exit (trend following, larger profits)
- **Long and Short Positions**: Full support for both long and short selling
- **Risk-Based Position Sizing**: Calculates trade sizes based on a percentage of a dynamic risk pot (1% per unit)
- **Pyramiding**: Adds to winning positions up to 4 times, spaced by 0.5N
- **Dynamic Stop-Loss**: Adjusts stop-loss orders based on the highest entry price of a pyramided position (2N stops)
- **System-Specific Exits**: Each position uses the exit rules of its entry system
- **Automated Scheduling**: Uses a scheduler to run trading workflows at appropriate market times
- **Backtesting Engine**: Vectorized backtesters for both single and dual system strategies
- **Slack Integration**: Sends real-time alerts for trades, daily summaries, and system status
- **State Persistence**: Maintains the trading state (positions, risk pot) in a JSON file
- **Modular Architecture**: Refactored into focused, testable components for better maintainability
- **Comprehensive Testing**: 34+ unit tests covering core trading logic

## Project Structure

```
/
├── .config/                  # Configuration files for API keys and tokens
├── backtesting/
│   └── backtesting.py        # Script for running backtests on historical data
├── data/
│   ├── alpaca_daily/         # Daily historical stock data from Alpaca
│   └── state/                # JSON files for persisting trading state
├── data_gathering/           # Scripts to download historical data
├── logs/                     # Daily logs for trading activities, orders, and state
│   ├── system_long/          # Logs for long-only system
│   └── system_long_short/    # Logs for long-short system
├── system_long/              # Long-only modular trading system
│   ├── core/                 # Core trading logic modules
│   │   ├── data_provider.py      # Market data fetching from Alpaca
│   │   ├── indicators.py         # Technical indicator calculations
│   │   ├── signal_generator.py   # Entry/exit signal generation
│   │   ├── position_manager.py   # Position and pyramid management
│   │   └── order_manager.py      # Order execution and tracking
│   ├── utils/                # Utility modules
│   │   ├── decorators.py         # Retry and error handling decorators
│   │   ├── logger.py             # Daily logging functionality
│   │   ├── notifier.py           # Slack notification system
│   │   └── state_manager.py      # State persistence management
│   ├── turtle_trading.py     # Main orchestrator (refactored)
│   ├── turtle_manual.py      # Script for manually triggering workflows
│   ├── turtle_scheduler.py   # Scheduler for automated trading
│   ├── ticker_universe.txt   # Ticker list for long-only system
│   └── trading_state.json    # State file for long-only system
├── system_long_short/        # Long and short modular trading system
│   ├── core/                 # Core modules (long/short variants)
│   ├── utils/                # Utility modules
│   ├── turtle_trading_ls.py  # Main orchestrator
│   ├── turtle_manual_ls.py   # Manual control script
│   ├── turtle_scheduler_ls.py # Scheduler
│   ├── ticker_universe.txt   # Ticker list for long-short system
│   ├── trading_state_ls.json # State file for long-short system
│   ├── htb_exclusions.txt    # Hard-to-borrow exclusion list
│   └── README.md             # Detailed documentation
├── tests/                    # Comprehensive unit tests
│   ├── test_system_long/    # Tests for system_long
│   │   ├── test_core/       # Tests for core trading modules
│   │   └── test_utils/      # Tests for utility modules
│   ├── test_system_long_short/ # Tests for system_long_short
│   └── run_tests.py         # Test runner
├── graveyard/                # Old or unused scripts
│   └── turtle_live_trading_original.py  # Original monolithic implementation (preserved)
├── REFACTORING.md           # Detailed refactoring documentation
├── REFACTORING_SUMMARY.md   # Refactoring summary
└── README.md                 # This file
```

**Important**: Each system (`system_long` and `system_long_short`) has its own:
- Log directory: `logs/system_long/` and `logs/system_long_short/`
- State file: `trading_state.json` and `trading_state_ls.json`
- Ticker universe: `ticker_universe.txt` (in respective system directories)
- Configuration files (HTB exclusions for long-short only)

This ensures the two systems never interfere with each other.

## Architecture

The system has been refactored into a modular architecture with clear separation of concerns:

### Core Modules (`system_long/core/` and `system_long_short/core/`)
- **DataProvider**: Fetches market data from Alpaca API with retry logic
- **IndicatorCalculator**: Calculates ATR and Donchian Channels (10-day, 20-day, 55-day)
- **SignalGenerator**: Generates dual system entry/exit signals with system priority
  - System 1 (20-10): Faster entries/exits
  - System 2 (55-20): Trend-following entries/exits
- **PositionManager**: Manages positions, pyramids, and risk calculations for both long/short
- **OrderManager**: Executes and tracks orders with error handling for both sides

### Utility Modules (`system_long/utils/`)
- **DailyLogger**: Logs trading activities, orders, and state snapshots
- **SlackNotifier**: Sends real-time notifications to Slack
- **StateManager**: Persists and loads trading state
- **Decorators**: Retry logic for API calls

### Main Orchestrator
- **TurtleTrading**: Coordinates all components to execute the strategy

This architecture makes the system easier to test, maintain, and extend.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install pandas numpy alpaca-py requests schedule matplotlib
    ```

2.  **Configure API Keys**:

    ```bash
    export ALPACA_PAPER_KEY="your_key"
    export ALPACA_PAPER_SECRET="your_secret"
    export PERSONAL_SLACK_TOKEN="xoxb-token"
    ```

3.  **Define Ticker Universe**:
    Create a `ticker_universe.txt` file in the root directory with one ticker symbol per line. If this file is not found, a default list of tickers will be used.

4.  **Download Historical Data**:
    Run the data gathering script to download the necessary historical data for your tickers.
    ```bash
    python data_gathering/get_historical_stock_price_data_from_alpaca_API.py
    ```

## Usage

### Automated Trading (Recommended)

The `turtle_scheduler.py` script automates all the trading workflows. It runs on a schedule during market days.

```bash
# Long-only system
python system_long/turtle_scheduler.py

# Long-short system
python system_long_short/turtle_scheduler_ls.py
```

The scheduler will perform the following actions at the specified times (in PT):
- **5:00 AM**: End-of-day analysis to prepare for the next trading day.
- **6:25 AM**: Market open setup.
- **6:30 AM - 1:00 PM**: Intraday monitoring (every 5 minutes).
- **1:15 PM**: Post-market routine.

### Manual Trading

You can manually trigger the trading workflows using the `turtle_manual.py` script. This is useful for testing and debugging.

```bash
# Long-only system
# Run end-of-day analysis
python system_long/turtle_manual.py eod

# Run market open setup
python system_long/turtle_manual.py open

# Run a single intraday monitor cycle
python system_long/turtle_manual.py monitor

# Run the post-market routine
python system_long/turtle_manual.py close

# Check the current system status
python system_long/turtle_manual.py status

# Align the local state with the broker's state (dry run)
python system_long/turtle_manual.py align

# Align the local state with the broker's state (apply changes)
python system_long/turtle_manual.py align --apply

# Long-short system
# See system_long_short/README.md for usage
python system_long_short/turtle_manual_ls.py
```

### Backtesting

The project includes multiple backtesting scripts to evaluate different strategies:

**Dual System Backtester** (Recommended - matches live system):
```bash
# Long-short with both System 1 (20-10) and System 2 (55-20)
python backtesting/turtle_long_short_dual_system_backtester.py
```

**Single System Backtesters**:
```bash
# Long-short with System 2 only (55-20)
python backtesting/turtle_long_short_55_20_backtester.py

# Long-only original
python backtesting/backtesting.py
```

**Prerequisites**:
1. Download historical data using the data gathering script
2. Ensure data is in `data/alpaca_daily/` directory

**Output**:
- Performance metrics (total return, win rate, avg win/loss, etc.)
- Equity curves showing portfolio value over time
- Position tracking (long units, short units, net exposure)
- Trade-by-trade breakdown by system
- Plots saved to `backtesting/turtle_*_plots/` directories

**Backtesting shows the dual system significantly outperforms single-system approaches** due to complementary entry/exit timing.

### Running Tests

The refactored system includes comprehensive unit tests:

```bash
# Run all tests
python tests/run_tests.py

# Run tests for long-only system
python -m unittest tests.test_system_long.test_core.test_indicators

# Run tests for long-short system
python -m unittest tests.test_system_long_short.test_core.test_indicators

# Run specific test
python -m unittest tests.test_system_long.test_core.test_position_manager.TestPositionManager.test_calculate_position_size
```

**Test Coverage:**
- 34+ unit tests covering core trading logic
- Tests for indicators, position management, signals, logging, and state management
- All tests currently passing ✅

## Workflows

-   **End-of-Day Analysis**: Scans the ticker universe for potential entry signals for the next trading day and generates a prioritized entry queue.
-   **Market Open Setup**: Reports the account status, open positions, and pending entry signals at the start of the trading day.
-   **Intraday Monitor**: This is the main trading loop that runs every 5 minutes during market hours. It checks for stop-loss triggers, exit signals, pyramiding opportunities, and processes the entry queue.
-   **Post-Market Routine**: Calculates the daily P&L, reports the final positions, and saves the trading state for the next day.

## System Logic

### Dual System Strategy

The `system_long_short` implementation uses **both System 1 and System 2** simultaneously:

**System 1 (20-10) - Faster Trading**:
- Entry: 20-day high breakout (long) or 20-day low breakdown (short)
- Exit: 10-day low (long) or 10-day high (short)
- Win filter: May skip entries after profitable trades

**System 2 (55-20) - Trend Following**:
- Entry: 55-day high breakout (long) or 55-day low breakdown (short)
- Exit: 20-day low (long) or 20-day high (short)
- No win filter: Always takes entries

**Entry Priority**:
- System 1 signals are checked first for each ticker
- System 2 signals are checked only if System 1 has no signal
- Only one position per ticker (first system to trigger gets it)

### Pyramiding

-   Up to 4 pyramid levels are allowed per position
-   Long positions: Add units when price moves up by 0.5N from the last entry
-   Short positions: Add units when price moves down by 0.5N from the last entry
-   All pyramids use the initial N value for consistency

### Exit

-   **Stop-Loss**: 2N from the last pyramid entry price
  - Long: Last entry - 2N
  - Short: Last entry + 2N
-   **Signal Exit**: Based on the position's entry system
  - System 1 positions: Exit on 10-day reversal
  - System 2 positions: Exit on 20-day reversal
-   Each position remembers which system opened it and uses the appropriate exit rules

## Risk Management

-   **Risk Pot**: A dynamic risk pot is used to manage the total risk capacity. Each trade allocates a portion of the risk pot.
-   **Position Sizing**: The size of each position is calculated to risk 2% of the current risk pot.
-   **Stop-Loss**: A 2N stop-loss is always maintained for each position, protecting against significant losses.

## Slack Notifications

The system sends real-time notifications to a Slack channel for various events:

-   **Entry/Exit Orders**: Alerts for placed, filled, or failed orders.
-   **Daily Summaries**: A summary of the daily P&L, open positions, and account status.
-   **System Status**: Notifications for system startup, shutdown, and errors.

## Disclaimer

This trading system is provided for educational purposes only. Trading financial markets involves substantial risk and is not suitable for all investors. Always test the system thoroughly in a paper trading environment before deploying it with real capital. Past performance is not indicative of future results.
