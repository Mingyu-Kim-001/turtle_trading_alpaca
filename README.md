# Turtle Trading Alpaca

This project is a full implementation of the Turtle Trading strategy, adapted for automated trading on the Alpaca platform. It includes modules for data gathering, backtesting, and live trading, with Slack integration for real-time notifications.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [Usage](#usage)
  - [Automated Trading](#automated-trading-recommended)
  - [Manual Trading](#manual-trading)
  - [Backtesting](#backtesting)
- [Workflows](#workflows)
- [System Logic](#system-logic)
- [Risk Management](#risk-management)
- [Slack Notifications](#slack-notifications)
- [Disclaimer](#disclaimer)

## Features

- **System 1 & 2 Entries**: Implements both Turtle Trading systems (20-day and 55-day breakouts).
- **Risk-Based Position Sizing**: Calculates trade sizes based on a percentage of a dynamic risk pot.
- **Pyramiding**: Adds to winning positions up to 4 times, spaced by 0.5N.
- **Dynamic Stop-Loss**: Adjusts stop-loss orders based on the highest entry price of a pyramided position.
- **Automated Scheduling**: Uses a scheduler to run trading workflows at appropriate market times.
- **Backtesting Engine**: A vectorized backtester to evaluate strategy performance on historical data.
- **Slack Integration**: Sends real-time alerts for trades, daily summaries, and system status.
- **State Persistence**: Maintains the trading state (positions, risk pot) in a JSON file.

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
├── system/
│   ├── turtle_live_trading.py # Core live trading logic
│   ├── turtle_manual.py      # Script for manually triggering trading workflows
│   └── turtle_scheduler.py   # Scheduler for automated trading
├── graveyard/                # Old or unused scripts
├── ticker_universe.txt       # List of tickers to trade
└── README.md                 # This file
```

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install pandas numpy alpaca-py requests schedule matplotlib
    ```

2.  **Configure API Keys**:
    Create a `.config` directory and add the following JSON files:

    -   `./.config/alpaca_api_keys.json`:
        ```json
        {
          "ALPACA_PAPER_KEY": "your_paper_api_key",
          "ALPACA_PAPER_SECRET": "your_paper_api_secret"
        }
        ```

    -   `./.config/personal_slack_token.json`:
        ```json
        {
          "PERSONAL_SLACK_TOKEN": "xoxb-your-slack-token"
        }
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
python system/turtle_scheduler.py
```

The scheduler will perform the following actions at the specified times (in PT):
- **5:00 AM**: End-of-day analysis to prepare for the next trading day.
- **6:25 AM**: Market open setup.
- **6:30 AM - 1:00 PM**: Intraday monitoring (every 5 minutes).
- **1:15 PM**: Post-market routine.

### Manual Trading

You can manually trigger the trading workflows using the `turtle_manual.py` script. This is useful for testing and debugging.

```bash
# Run end-of-day analysis
python system/turtle_manual.py eod

# Run market open setup
python system/turtle_manual.py open

# Run a single intraday monitor cycle
python system/turtle_manual.py monitor

# Run the post-market routine
python system/turtle_manual.py close

# Check the current system status
python system/turtle_manual.py status

# Align the local state with the broker's state (dry run)
python system/turtle_manual.py align

# Align the local state with the broker's state (apply changes)
python system/turtle_manual.py align --apply
```

### Backtesting

The `backtesting.py` script allows you to test the Turtle Trading strategy on historical data.

1.  Make sure you have downloaded the historical data using the data gathering script.
2.  Run the backtesting script:
    ```bash
    python backtesting/backtesting.py
    ```

The script will run the backtest and generate a plot with the portfolio equity, drawdown, and number of open positions over time. It will also print a summary of the backtest results.

## Workflows

-   **End-of-Day Analysis**: Scans the ticker universe for potential entry signals for the next trading day and generates a prioritized entry queue.
-   **Market Open Setup**: Reports the account status, open positions, and pending entry signals at the start of the trading day.
-   **Intraday Monitor**: This is the main trading loop that runs every 5 minutes during market hours. It checks for stop-loss triggers, exit signals, pyramiding opportunities, and processes the entry queue.
-   **Post-Market Routine**: Calculates the daily P&L, reports the final positions, and saves the trading state for the next day.

## System Logic

### Entry

-   **System 1**: Enters a position when the price breaks above the 20-day high.
-   **System 2**: Enters a position when the price breaks above the 55-day high.
-   A filter is applied to System 1 to avoid re-entering a position shortly after a profitable exit.

### Pyramiding

-   Up to 4 pyramid levels are allowed per position.
-   A new pyramid unit is added when the price moves up by 0.5N from the last entry price.

### Exit

-   **Stop-Loss**: The entire position is exited if the price drops 2N below the highest entry price.
-   **System 1 Exit**: The position is exited if the price drops below the 10-day low.
-   **System 2 Exit**: The position is exited if the price drops below the 20-day low.

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
