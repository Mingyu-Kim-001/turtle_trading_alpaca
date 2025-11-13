"""Position and portfolio management for long and short positions"""


class PositionManager:
  """Manage trading positions and pyramid units for both long and short"""

  @staticmethod
  def calculate_position_size(total_equity, n, risk_per_unit_pct=0.001, fractional=True):
    """
    Calculate position size based on total equity (matching backtester logic)

    Args:
      total_equity: Total equity (cash + positions value)
      n: Current ATR value
      risk_per_unit_pct: Risk per unit as decimal (default 0.1% = 0.001)
      fractional: Whether to allow fractional shares (default True)

    Returns:
      Number of units to trade (fractional or integer)
    """
    if n == 0 or total_equity <= 0:
      return 0

    unit_risk = total_equity * risk_per_unit_pct
    # Risk per unit is N (matching backtester)
    units = unit_risk / n

    if fractional:
      # Round to 9 decimal places (Alpaca's max precision)
      return round(units, 9)
    else:
      return int(units)

  @staticmethod
  def calculate_margin_required(units, entry_price, margin_pct=0.5):
    """
    Calculate margin required for short position

    Args:
      units: Number of units
      entry_price: Entry price
      margin_pct: Margin percentage (default 50% = 0.5)

    Returns:
      Margin required
    """
    position_value = units * entry_price
    return position_value * margin_pct

  @staticmethod
  def calculate_long_stop(position, latest_n=None):
    """
    Calculate stop price for long position

    Stop moves up by 0.5N for each pyramid unit:
    - 1 unit: entry - 2.0N
    - 2 units: entry + 0.5N - 2.0N = entry - 1.5N
    - 3 units: entry + 1.0N - 2.0N = entry - 1.0N
    - 4 units: entry + 1.5N - 2.0N = entry - 0.5N

    Args:
      position: Position dict with pyramid_units and initial_n
      latest_n: If provided, use this N instead of initial_n for stop calculation

    Returns:
      Stop price as float, or None if no units
    """
    pyramid_units = position.get('pyramid_units', [])
    if not pyramid_units:
      return None

    # Use latest_n if provided, otherwise use initial_n
    if latest_n is not None:
      n_value = latest_n
    else:
      n_value = position.get('initial_n', pyramid_units[0]['entry_n'])

    # Use the last pyramid entry price as reference
    last_entry_price = pyramid_units[-1]['entry_price']

    # Stop is always 2N below last entry
    return last_entry_price - 2 * n_value

  @staticmethod
  def calculate_short_stop(position, latest_n=None):
    """
    Calculate stop price for short position

    Stop moves down by 0.5N for each pyramid unit:
    - 1 unit: entry + 2.0N
    - 2 units: entry - 0.5N + 2.0N = entry + 1.5N
    - 3 units: entry - 1.0N + 2.0N = entry + 1.0N
    - 4 units: entry - 1.5N + 2.0N = entry + 0.5N

    Args:
      position: Position dict with pyramid_units and initial_n
      latest_n: If provided, use this N instead of initial_n for stop calculation

    Returns:
      Stop price as float, or None if no units
    """
    pyramid_units = position.get('pyramid_units', [])
    if not pyramid_units:
      return None

    # Use latest_n if provided, otherwise use initial_n
    if latest_n is not None:
      n_value = latest_n
    else:
      n_value = position.get('initial_n', pyramid_units[0]['entry_n'])

    # Use the last pyramid entry price as reference
    last_entry_price = pyramid_units[-1]['entry_price']

    # Stop is always 2N above last entry
    return last_entry_price + 2 * n_value

  @staticmethod
  def can_pyramid(position, max_pyramids=4):
    """
    Check if position can add more pyramid levels

    Args:
      position: Position dict with pyramid_units
      max_pyramids: Maximum pyramid levels allowed

    Returns:
      True if can add more, False otherwise
    """
    return len(position.get('pyramid_units', [])) < max_pyramids

  @staticmethod
  def add_pyramid_unit(position, units, entry_price, entry_n, order_id, latest_n=None):
    """
    Add a pyramid unit to position (works for both long and short)

    Args:
      position: Position dict
      units: Number of units
      entry_price: Entry price
      entry_n: ATR at entry (kept for backward compatibility, uses initial_n)
      order_id: Order ID
      latest_n: If provided, use this N for stop calculation and store it in the unit

    Returns:
      Updated position dict
    """
    from datetime import datetime

    # Use initial N for all pyramid units
    initial_n = position.get('initial_n', entry_n)
    side = position.get('side', 'long')

    pyramid_unit = {
      'units': units,
      'entry_price': entry_price,
      'entry_n': initial_n,  # Use initial N, not current N
      'entry_value': units * entry_price,
      'entry_date': datetime.now().isoformat(),
      'order_id': order_id
    }

    # If latest_n was provided (use_latest_n_for_pyramiding mode), store it
    if latest_n is not None and latest_n != initial_n:
      pyramid_unit['latest_n'] = latest_n
      pyramid_unit['n_diff_pct'] = ((latest_n - initial_n) / initial_n * 100) if initial_n > 0 else 0

    position['pyramid_units'].append(pyramid_unit)

    # Update stop price based on position side
    # Pass latest_n if provided to use for stop calculation
    if side == 'long':
      position['stop_price'] = PositionManager.calculate_long_stop(position, latest_n)
    else:  # short
      position['stop_price'] = PositionManager.calculate_short_stop(position, latest_n)

    return position

  @staticmethod
  def create_new_long_position(units, entry_price, entry_n, order_id, system=1):
    """
    Create a new long position

    Args:
      units: Number of units
      entry_price: Entry price
      entry_n: ATR at entry
      order_id: Order ID
      system: Trading system (1 or 2)

    Returns:
      New position dict
    """
    from datetime import datetime

    pyramid_unit = {
      'units': units,
      'entry_price': entry_price,
      'entry_n': entry_n,
      'entry_value': units * entry_price,
      'entry_date': datetime.now().isoformat(),
      'order_id': order_id
    }

    position = {
      'side': 'long',
      'system': system,
      'pyramid_units': [pyramid_unit],
      'entry_date': datetime.now().isoformat(),
      'stop_price': entry_price - 2 * entry_n,
      'initial_n': entry_n,  # Store initial N for all pyramid calculations
      'initial_units': units  # Store initial units for consistent sizing
    }

    return position

  @staticmethod
  def create_new_short_position(units, entry_price, entry_n, order_id, system=1):
    """
    Create a new short position

    Args:
      units: Number of units
      entry_price: Entry price
      entry_n: ATR at entry
      order_id: Order ID
      system: Trading system (1 or 2)

    Returns:
      New position dict
    """
    from datetime import datetime

    pyramid_unit = {
      'units': units,
      'entry_price': entry_price,
      'entry_n': entry_n,
      'entry_value': units * entry_price,
      'entry_date': datetime.now().isoformat(),
      'order_id': order_id
    }

    position = {
      'side': 'short',
      'system': system,
      'pyramid_units': [pyramid_unit],
      'entry_date': datetime.now().isoformat(),
      'stop_price': entry_price + 2 * entry_n,  # Stop ABOVE for shorts
      'initial_n': entry_n,
      'initial_units': units
    }

    return position

  @staticmethod
  def calculate_long_position_pnl(position, exit_price):
    """
    Calculate P&L for a long position

    Args:
      position: Position dict with pyramid_units
      exit_price: Exit price

    Returns:
      Tuple of (total_units, entry_value, exit_value, pnl, pnl_pct)
    """
    total_units = sum(p['units'] for p in position['pyramid_units'])
    entry_value = sum(p['entry_value'] for p in position['pyramid_units'])
    exit_value = total_units * exit_price
    pnl = exit_value - entry_value
    pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

    return total_units, entry_value, exit_value, pnl, pnl_pct

  @staticmethod
  def calculate_short_position_pnl(position, exit_price):
    """
    Calculate P&L for a short position

    Args:
      position: Position dict with pyramid_units
      exit_price: Exit price

    Returns:
      Tuple of (total_units, entry_value, exit_value, pnl, pnl_pct)
    """
    total_units = sum(p['units'] for p in position['pyramid_units'])
    entry_value = sum(p['entry_value'] for p in position['pyramid_units'])

    # For shorts, P&L = units * (entry_price - exit_price)
    avg_entry_price = entry_value / total_units if total_units > 0 else 0
    pnl = total_units * (avg_entry_price - exit_price)
    pnl_pct = (pnl / entry_value) * 100 if entry_value > 0 else 0

    # Exit value for display (what we pay to close)
    exit_value = total_units * exit_price

    return total_units, entry_value, exit_value, pnl, pnl_pct

  @staticmethod
  def calculate_allocated_risk(position):
    """
    Calculate total risk allocated to a position

    Args:
      position: Position dict with pyramid_units

    Returns:
      Total allocated risk
    """
    total_risk = 0
    for pyramid in position['pyramid_units']:
      risk_allocated = pyramid['units'] * 2 * pyramid['entry_n']
      total_risk += risk_allocated

    return total_risk
