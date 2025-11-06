"""Signal generation for long and short entry/exit opportunities"""

import pandas as pd


class SignalGenerator:
  """Generate entry and exit signals for Turtle Trading with long and short positions"""

  @staticmethod
  def check_long_entry_signal(df, current_price, proximity_threshold=0.05):
    """
    Check if there's a long entry signal (breakout above 20-day high)

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
          'proximity': proximity * 100,
          'side': 'long'
        }

    return None

  @staticmethod
  def check_short_entry_signal(df, current_price, proximity_threshold=0.05):
    """
    Check if there's a short entry signal (breakdown below 20-day low)

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      proximity_threshold: How close to breakdown (as decimal, default 5%)

    Returns:
      dict with signal info if valid, None otherwise
    """
    if df is None or len(df) < 55:
      return None

    latest = df.iloc[-1]

    if pd.notna(latest['low_20']) and pd.notna(latest['N']):
      entry_price = latest['low_20']
      # For shorts, proximity is inverted (price below breakdown is negative)
      proximity = (current_price - entry_price) / current_price

      # Check if price is within threshold of breakdown
      if -0.02 <= proximity <= proximity_threshold:
        return {
          'entry_price': entry_price,
          'current_price': current_price,
          'n': latest['N'],
          'proximity': proximity * 100,
          'side': 'short'
        }

    return None

  @staticmethod
  def check_long_exit_signal(df, current_price):
    """
    Check if there's a long exit signal (break below 10-day low)

    Args:
      df: DataFrame with indicator data
      current_price: Current market price

    Returns:
      True if exit signal triggered, False otherwise
    """
    if df is None or len(df) < 10:
      return False

    latest = df.iloc[-1]

    # Exit on 10-day low
    if pd.notna(latest['low_10']) and current_price < latest['low_10'] * 1.01:
      return True

    return False

  @staticmethod
  def check_short_exit_signal(df, current_price):
    """
    Check if there's a short exit signal (break above 10-day high)

    Args:
      df: DataFrame with indicator data
      current_price: Current market price

    Returns:
      True if exit signal triggered, False otherwise
    """
    if df is None or len(df) < 10:
      return False

    latest = df.iloc[-1]

    # Exit on 10-day high
    if pd.notna(latest['high_10']) and current_price > latest['high_10'] * 0.99:
      return True

    return False

  @staticmethod
  def check_long_pyramid_opportunity(last_entry_price, current_price, initial_n, threshold=0.5):
    """
    Check if there's a long pyramid opportunity (price moves up)

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

    # Check if price has moved up sufficiently (use small absolute tolerance based on N)
    # Using 2% of N as tolerance instead of percentage of price to avoid false triggers
    tolerance = 0.02 * initial_n
    return current_price >= pyramid_trigger - tolerance

  @staticmethod
  def check_short_pyramid_opportunity(last_entry_price, current_price, initial_n, threshold=0.5):
    """
    Check if there's a short pyramid opportunity (price moves down)

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

    pyramid_trigger = last_entry_price - threshold * initial_n

    # Check if price has moved down sufficiently (use small absolute tolerance based on N)
    # Using 2% of N as tolerance instead of percentage of price to avoid false triggers
    tolerance = 0.02 * initial_n
    return current_price <= pyramid_trigger + tolerance

  @staticmethod
  def generate_entry_signals(universe, data_provider, indicator_calculator,
               long_positions, short_positions, enable_shorts=True,
               shortable_tickers=None, proximity_threshold=0.05):
    """
    Generate entry signals for entire universe (both long and short)

    Args:
      universe: List of ticker symbols
      data_provider: DataProvider instance
      indicator_calculator: IndicatorCalculator instance
      long_positions: Dict of existing long positions
      short_positions: Dict of existing short positions
      enable_shorts: Whether to generate short signals
      shortable_tickers: Set of shortable tickers (None = all shortable)
      proximity_threshold: Proximity threshold for signals

    Returns:
      List of entry signals sorted by proximity
    """
    signals = []

    for ticker in universe:
      # Skip if already have a position (long or short)
      if ticker in long_positions or ticker in short_positions:
        continue

      df = data_provider.get_historical_data(ticker)
      if df is None or len(df) < 55:
        continue

      df = indicator_calculator.calculate_indicators(df)
      latest = df.iloc[-1]

      # Check for long entry signal
      long_signal = SignalGenerator.check_long_entry_signal(
        df, latest['close'], proximity_threshold
      )
      if long_signal:
        signals.append({
          'ticker': ticker,
          **long_signal
        })

      # Check for short entry signal (if enabled and ticker is shortable)
      if enable_shorts:
        is_shortable = (shortable_tickers is None or ticker in shortable_tickers)
        if is_shortable:
          short_signal = SignalGenerator.check_short_entry_signal(
            df, latest['close'], proximity_threshold
          )
          if short_signal:
            signals.append({
              'ticker': ticker,
              **short_signal
            })

    # Sort by proximity (closest to breakout/breakdown first)
    return sorted(signals, key=lambda x: abs(x['proximity']))
