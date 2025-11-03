# Turtle Trading System - Technical Documentation

This directory contains the refactored Turtle Trading system implementation with a modular, testable architecture.

## 🚀 Quick Start

```python
from system.turtle_trading import TurtleTrading

# Initialize the system
system = TurtleTrading(
    api_key=your_alpaca_key,
    api_secret=your_alpaca_secret,
    slack_token=your_slack_token,
    slack_channel=your_channel_id,
    paper=True  # Use paper trading
)

# Run workflows
system.daily_eod_analysis()      # Generate entry signals
system.market_open_setup()       # Pre-market setup
system.intraday_monitor()        # Monitor and execute trades
system.post_market_routine()     # End-of-day summary
```

## 📐 Architecture Overview

The system has been refactored from a monolithic **1,875-line** file into **focused, testable modules**:

```
system/
├── core/                      # Core trading logic (650 lines)
│   ├── data_provider.py       # Market data from Alpaca API (94 lines)
│   ├── indicators.py          # Technical indicators (71 lines)
│   ├── signal_generator.py    # Entry/exit signals (118 lines)
│   ├── position_manager.py    # Position/risk management (159 lines)
│   └── order_manager.py       # Order execution (318 lines)
│
├── utils/                     # Utility modules (266 lines)
│   ├── decorators.py          # Retry logic (41 lines)
│   ├── logger.py              # Activity logging (73 lines)
│   ├── notifier.py            # Slack notifications (47 lines)
│   └── state_manager.py       # State persistence (67 lines)
│
├── turtle_trading.py          # Main orchestrator (448 lines) ⬅️ Main entry point
├── turtle_manual.py           # CLI for manual testing
└── turtle_scheduler.py        # Automated scheduler
```

**Total: 1,742 lines** (vs 1,875 in original monolith), but **much better organized!**

## 📦 Module Reference

### Core Modules

#### 1. DataProvider (`core/data_provider.py`) - 94 lines

Fetches market data from Alpaca API with automatic retry logic.

```python
from system.core import DataProvider

provider = DataProvider(api_key, api_secret)
df = provider.get_historical_data('AAPL', days=100)  # OHLCV data
price = provider.get_current_price('AAPL')           # Real-time price
```

**Tested:** Integration tests

---

#### 2. IndicatorCalculator (`core/indicators.py`) - 71 lines

Calculates technical indicators (pure math, no API calls).

```python
from system.core import IndicatorCalculator

calc = IndicatorCalculator()
df = calc.calculate_indicators(df)
# Adds: N (ATR), high_20, high_55, low_10, low_20
```

**Tested:** 5 unit tests ✅

---

#### 3. SignalGenerator (`core/signal_generator.py`) - 118 lines

Generates trading signals (pure logic, no state).

```python
from system.core import SignalGenerator

gen = SignalGenerator()
signal = gen.check_entry_signal(df, current_price)
should_exit = gen.check_exit_signal(df, current_price, system=1)
can_pyramid = gen.check_pyramid_opportunity(last_price, current_price, n)
```

**Tested:** 10 unit tests ✅

---

#### 4. PositionManager (`core/position_manager.py`) - 159 lines

Manages positions and risk (pure calculations, no API).

```python
from system.core import PositionManager

pm = PositionManager()
units = pm.calculate_position_size(risk_pot=10000, n=2.5)
position = pm.create_new_position(units, price, n, order_id)
position = pm.add_pyramid_unit(position, units, price, n, order_id)
stop = pm.calculate_overall_stop(position['pyramid_units'])
```

**Tested:** 10 unit tests ✅

---

#### 5. OrderManager (`core/order_manager.py`) - 318 lines

Executes orders with comprehensive error handling.

```python
from system.core import OrderManager

om = OrderManager(trading_client, logger, slack)
success, order_id, price = om.place_entry_order(ticker, units, target, n)
success, order_id, price = om.place_exit_order(ticker, units, target, reason)
success, order_id, price = om.place_market_exit_order(ticker, units)
```

**Tested:** Integration tests

---

### Utility Modules

#### 6. DailyLogger (`utils/logger.py`) - 73 lines

Logs to dated files.

```python
from system.utils import DailyLogger

logger = DailyLogger()
logger.log("Message", level='INFO')
logger.log_order('ENTRY', 'AAPL', 'FILLED', {...})
logger.log_state_snapshot(state, 'market_open')
```

**Output:** `logs/trading_YYYY-MM-DD.log`, `logs/orders_YYYY-MM-DD.json`

**Tested:** 5 unit tests ✅

---

#### 7. SlackNotifier (`utils/notifier.py`) - 47 lines

Sends Slack notifications.

```python
from system.utils import SlackNotifier

slack = SlackNotifier(token, channel)
slack.send_message("Trade executed", title="Alert")
slack.send_summary("Summary", {"P&L": "$1,234", "Positions": 3})
```

---

#### 8. StateManager (`utils/state_manager.py`) - 67 lines

Persists state to JSON.

```python
from system.utils import StateManager

state = StateManager()
print(state.risk_pot, state.positions, state.entry_queue)
state.update_risk_pot(pnl=250)
state.save_state()
```

**Tested:** 4 unit tests ✅

---

## 🧪 Testing

### Run Tests

```bash
# All tests (from project root)
python tests/run_tests.py

# Specific module
python -m unittest tests.test_core.test_indicators

# Specific test
python -m unittest tests.test_core.test_position_manager.TestPositionManager.test_calculate_position_size
```

### Test Coverage

| Module | Lines | Tests | Status |
|--------|-------|-------|--------|
| IndicatorCalculator | 71 | 5 | ✅ |
| PositionManager | 159 | 10 | ✅ |
| SignalGenerator | 118 | 10 | ✅ |
| DailyLogger | 73 | 5 | ✅ |
| StateManager | 67 | 4 | ✅ |
| **Total** | - | **34** | **✅** |

---

## 🛠️ Manual Testing

### CLI (`turtle_manual.py`)

```bash
python turtle_manual.py status      # Show system status
python turtle_manual.py eod         # EOD analysis
python turtle_manual.py open        # Market open
python turtle_manual.py monitor     # Single monitor cycle
python turtle_manual.py close       # Post-market
python turtle_manual.py exit-all    # Emergency exit (DANGEROUS!)
```

### Scheduler (`turtle_scheduler.py`)

```bash
python turtle_scheduler.py
```

**Schedule (Pacific Time):**
- 05:00 AM - EOD Analysis
- 06:25 AM - Market Open
- 06:30-01:00 PM - Monitor (every 5 min)
- 01:15 PM - Post-Market

---

## ⚙️ Configuration

### Environment Variables

```bash
export ALPACA_PAPER_KEY="your_key"
export ALPACA_PAPER_SECRET="your_secret"
export PERSONAL_SLACK_TOKEN="xoxb-token"
```

### Customization Points

**Risk per trade** (in `PositionManager.calculate_position_size()`):
```python
risk_per_unit=0.02  # 2% default
```

**Pyramid levels** (in `PositionManager.can_pyramid()`):
```python
max_pyramids=4  # Default
```

**Entry/Exit periods** (in `IndicatorCalculator.calculate_donchian_channels()`):
```python
entry_period=20      # System 1 entry
exit_period=10       # System 1 exit
long_entry_period=55 # System 2 entry
```

**Order margins** (in `TurtleTrading.__init__()`):
```python
entry_margin=0.99   # Stop 1% below target
exit_margin=1.01    # Stop 1% above target
```

---

## 🎯 Trading Logic

### Entry
1. Price breaks above 20-day high (System 1)
2. Calculate size: `(2% of risk_pot) / (2*N)`
3. Place stop-limit order
4. Set initial stop: `entry_price - 2*N`
5. Deduct risk from pot

### Pyramiding
1. If price moves up 0.5N from last entry
2. Add units (max 4 levels)
3. Update stop: `highest_entry - 2*N`

### Exit
1. **Stop Loss**: `price ≤ stop_price`
2. **Exit Signal**: `price < 10-day low`
3. Sell all units together
4. Return allocated risk
5. Add P&L to pot

---

## 🔧 Development

### Adding Features

1. **Identify the right module:**
   - Data fetching → `DataProvider`
   - Calculations → `IndicatorCalculator` / `PositionManager`
   - Signal logic → `SignalGenerator`
   - Order execution → `OrderManager`
   - Utilities → `utils/`

2. **Add unit tests:**
   - Create test file in `tests/test_core/` or `tests/test_utils/`
   - Follow existing test patterns
   - Ensure all tests pass

3. **Update documentation:**
   - Add inline docstrings
   - Update this README if interfaces change
   - Update main README if user-facing

### Design Principles

- **Single Responsibility**: Each module does one thing well
- **Testable**: Components can be tested in isolation
- **Pure Functions**: Avoid side effects where possible
- **Dependency Injection**: Pass dependencies, don't create them

---

## 🆘 Troubleshooting

### Import Errors

```bash
# Wrong (don't cd into system/)
cd system && python turtle_trading.py

# Right (run from project root)
cd /path/to/turtle_trading_alpaca
python system/turtle_manual.py status
```

### Test Failures

```bash
# Must run from project root
cd /path/to/turtle_trading_alpaca
python tests/run_tests.py
```

### State Issues

```bash
# Backup current state
cp trading_state.json trading_state.backup.json

# Reset state (system will reinitialize)
rm trading_state.json
```

---

## 📚 Additional Documentation

- **Main README**: `../README.md` - User guide and setup instructions
- **Refactoring Details**: `../REFACTORING.md` - Technical deep dive into architecture
- **Refactoring Summary**: `../REFACTORING_SUMMARY.md` - High-level overview of improvements
- **Test Examples**: `../tests/` - Usage examples in test files

---

## 🔄 Migration from Original

The original `turtle_live_trading.py` is **preserved** in `graveyard/turtle_live_trading_original.py` for reference.

**Import change:**
```python
# Old
from turtle_live_trading import TurtleTrading

# New
from turtle_trading import TurtleTrading
```

**Interface is identical** - all public methods work the same way!

---

## 📝 Important Notes

- **Paper trading default**: Always test thoroughly before live trading
- **Market hours**: 06:30 AM - 01:00 PM Pacific Time
- **Weekdays only**: Scheduler automatically respects market calendar
- **Connection retry**: Automatic exponential backoff on API failures
- **Error handling**: System continues on individual ticker errors
- **Slack alerts**: Real-time notifications for all important events

---

## ⚖️ Disclaimer

**Educational use only.** Always:
- Test in paper trading environment first
- Fully understand the risks involved
- Start with capital you can afford to lose
- Monitor the system regularly
- Have proper stop-loss procedures in place

**Past performance does not guarantee future results.**
