"""Position and portfolio management"""


class PositionManager:
  """Manage trading positions and pyramid units"""

  @staticmethod
  def calculate_position_size(total_equity, n, risk_per_unit_pct=0.001):
    """
    Calculate position size based on total equity (matching backtester logic)

    Args:
      total_equity: Total equity (cash + positions value)
      n: Current ATR value
      risk_per_unit_pct: Risk per unit as decimal (default 0.1% = 0.001)

    Returns:
      Number of units to trade
    """
    if n == 0 or total_equity <= 0:
      return 0

    unit_risk = total_equity * risk_per_unit_pct
    # Risk per unit is N (matching backtester)
    units = unit_risk / n
    return int(units)

  @staticmethod
  def calculate_overall_stop(position):
    """
    Calculate the overall stop price for entire position

    Stop moves up by 0.5N for each pyramid unit:
    - 1 unit: entry - 2.0N
    - 2 units: entry - 1.5N
    - 3 units: entry - 1.0N
    - 4 units: entry - 0.5N

    Args:
      position: Position dict with pyramid_units and initial_n

    Returns:
      Stop price as float, or None if no units
    """
    pyramid_units = position.get('pyramid_units', [])
    if not pyramid_units:
      return None

    initial_entry_price = pyramid_units[0]['entry_price']
    initial_n = position.get('initial_n', pyramid_units[0]['entry_n'])
    num_pyramids = len(pyramid_units)

    # Stop tightens by 0.5N for each pyramid unit
    stop_multiplier = 2.5 - (0.5 * num_pyramids)

    return initial_entry_price - stop_multiplier * initial_n

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
  def add_pyramid_unit(position, units, entry_price, entry_n, order_id):
    """
    Add a pyramid unit to position

    Args:
      position: Position dict
      units: Number of units
      entry_price: Entry price
      entry_n: ATR at entry (kept for backward compatibility, uses initial_n)
      order_id: Order ID

    Returns:
      Updated position dict
    """
    from datetime import datetime

    # Use initial N for all pyramid units
    initial_n = position.get('initial_n', entry_n)

    pyramid_unit = {
      'units': units,
      'entry_price': entry_price,
      'entry_n': initial_n,  # Use initial N, not current N
      'entry_value': units * entry_price,
      'entry_date': datetime.now().isoformat(),
      'order_id': order_id
    }

    position['pyramid_units'].append(pyramid_unit)
    position['stop_price'] = PositionManager.calculate_overall_stop(position)

    return position

  @staticmethod
  def create_new_position(units, entry_price, entry_n, order_id, system=1):
    """
    Create a new position

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
      'system': system,
      'pyramid_units': [pyramid_unit],
      'entry_date': datetime.now().isoformat(),
      'stop_price': entry_price - 2 * entry_n,
      'initial_n': entry_n,  # Store initial N for all pyramid calculations
      'initial_units': units  # Store initial units for consistent sizing
    }

    return position

  @staticmethod
  def calculate_position_pnl(position, exit_price):
    """
    Calculate P&L for a position

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
