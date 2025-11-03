"""Signal generation for entry and exit opportunities"""

import pandas as pd


class SignalGenerator:
  """Generate entry and exit signals for Turtle Trading"""

  @staticmethod
  def check_entry_signal(df, current_price, proximity_threshold=0.05):
    """
    Check if there's an entry signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      proximity_threshold: How close to breakout (as decimal, default 5%)

    Returns:
      dict with signal info if valid, None otherwise
    """
    if df is None or len(df) < 55:
      return None

    latest = df.iloc[-1]

    if pd.notna(latest['high_20']) and pd.notna(latest['N']):
      entry_price = latest['high_20']
      proximity = (entry_price - current_price) / current_price

      # Check if price is within threshold of breakout
      if -0.02 <= proximity <= proximity_threshold:
        return {
          'entry_price': entry_price,
          'current_price': current_price,
          'n': latest['N'],
          'proximity': proximity * 100
        }

    return None

  @staticmethod
  def check_exit_signal(df, current_price, system=1):
    """
    Check if there's an exit signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      system: Trading system (1 or 2)

    Returns:
      True if exit signal triggered, False otherwise
    """
    if df is None or len(df) < 10:
      return False

    latest = df.iloc[-1]

    if system == 1:
      # System 1: Exit on 10-day low
      if pd.notna(latest['low_10']) and current_price < latest['low_10'] * 1.01:
        return True
    elif system == 2:
      # System 2: Exit on 20-day low
      if pd.notna(latest['low_20']) and current_price < latest['low_20'] * 1.01:
        return True

    return False

  @staticmethod
  def check_pyramid_opportunity(last_entry_price, current_price, initial_n, threshold=0.5):
    """
    Check if there's a pyramid opportunity

    Args:
      last_entry_price: Price of last pyramid entry
      current_price: Current market price
      initial_n: Initial ATR (N value)
      threshold: Multiple of N for pyramid trigger (default 0.5)

    Returns:
      True if pyramid opportunity exists, False otherwise
    """
    if initial_n is None or initial_n == 0:
      return False

    pyramid_trigger = last_entry_price + threshold * initial_n

    # Check if price has reached trigger (with 1% margin)
    return current_price > pyramid_trigger * 0.99

  @staticmethod
  def generate_entry_signals(universe, data_provider, indicator_calculator,
               existing_positions, proximity_threshold=0.05):
    """
    Generate entry signals for entire universe

    Args:
      universe: List of ticker symbols
      data_provider: DataProvider instance
      indicator_calculator: IndicatorCalculator instance
      existing_positions: Dict of existing positions
      proximity_threshold: Proximity threshold for signals

    Returns:
      List of entry signals sorted by proximity
    """
    signals = []

    for ticker in universe:
      if ticker in existing_positions:
        continue

      df = data_provider.get_historical_data(ticker)
      if df is None or len(df) < 55:
        continue

      df = indicator_calculator.calculate_indicators(df)
      latest = df.iloc[-1]

      signal = SignalGenerator.check_entry_signal(df, latest['close'], proximity_threshold)
      if signal:
        signals.append({
          'ticker': ticker,
          **signal
        })

    # Sort by proximity (closest to breakout first)
    return sorted(signals, key=lambda x: abs(x['proximity']))
