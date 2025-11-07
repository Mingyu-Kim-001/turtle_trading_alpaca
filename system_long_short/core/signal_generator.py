"""Signal generation for long and short entry/exit opportunities"""

import pandas as pd


class SignalGenerator:
  """Generate entry and exit signals for Turtle Trading with long and short positions"""

  @staticmethod
  def check_long_entry_signal(df, current_price, proximity_threshold=0.05, system=1):
    """
    Check if there's a long entry signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      proximity_threshold: How close to breakout (as decimal, default 5%)
      system: 1 for 20-day breakout, 2 for 55-day breakout

    Returns:
      dict with signal info if valid, None otherwise
    """
    if df is None or len(df) < 55:
      return None

    latest = df.iloc[-1]
    channel_key = 'high_20' if system == 1 else 'high_55'

    if pd.notna(latest[channel_key]) and pd.notna(latest['N']):
      entry_price = latest[channel_key]
      proximity = (entry_price - current_price) / current_price

      # Check if price is within threshold of breakout
      if -0.02 <= proximity <= proximity_threshold:
        return {
          'entry_price': entry_price,
          'current_price': current_price,
          'n': latest['N'],
          'proximity': proximity * 100,
          'side': 'long',
          'system': system
        }

    return None

  @staticmethod
  def check_short_entry_signal(df, current_price, proximity_threshold=0.05, system=1):
    """
    Check if there's a short entry signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      proximity_threshold: How close to breakdown (as decimal, default 5%)
      system: 1 for 20-day breakdown, 2 for 55-day breakdown

    Returns:
      dict with signal info if valid, None otherwise
    """
    if df is None or len(df) < 55:
      return None

    latest = df.iloc[-1]
    channel_key = 'low_20' if system == 1 else 'low_55'

    if pd.notna(latest[channel_key]) and pd.notna(latest['N']):
      entry_price = latest[channel_key]
      # For shorts, proximity is inverted (price below breakdown is negative)
      proximity = (current_price - entry_price) / current_price

      # Check if price is within threshold of breakdown
      if -0.02 <= proximity <= proximity_threshold:
        return {
          'entry_price': entry_price,
          'current_price': current_price,
          'n': latest['N'],
          'proximity': proximity * 100,
          'side': 'short',
          'system': system
        }

    return None

  @staticmethod
  def check_long_exit_signal(df, current_price, system=1):
    """
    Check if there's a long exit signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      system: 1 for 10-day low exit, 2 for 20-day low exit

    Returns:
      True if exit signal triggered, False otherwise
    """
    if df is None or len(df) < 20:
      return False

    latest = df.iloc[-1]
    channel_key = 'low_10' if system == 1 else 'low_20'

    # Exit when price breaks below the channel
    if pd.notna(latest[channel_key]) and current_price < latest[channel_key] * 1.01:
      return True

    return False

  @staticmethod
  def check_short_exit_signal(df, current_price, system=1):
    """
    Check if there's a short exit signal

    Args:
      df: DataFrame with indicator data
      current_price: Current market price
      system: 1 for 10-day high exit, 2 for 20-day high exit

    Returns:
      True if exit signal triggered, False otherwise
    """
    if df is None or len(df) < 20:
      return False

    latest = df.iloc[-1]
    channel_key = 'high_10' if system == 1 else 'high_20'

    # Exit when price breaks above the channel
    if pd.notna(latest[channel_key]) and current_price > latest[channel_key] * 0.99:
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
    Generate entry signals for entire universe using dual system (20-10 and 55-20)

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
      List of entry signals sorted by proximity, with system info
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

      # Check System 1 (20-day) long entry signal first
      s1_long_signal = SignalGenerator.check_long_entry_signal(
        df, latest['close'], proximity_threshold, system=1
      )
      if s1_long_signal:
        signals.append({
          'ticker': ticker,
          **s1_long_signal
        })
      # If no System 1 signal, check System 2 (55-day) long entry
      elif not s1_long_signal:
        s2_long_signal = SignalGenerator.check_long_entry_signal(
          df, latest['close'], proximity_threshold, system=2
        )
        if s2_long_signal:
          signals.append({
            'ticker': ticker,
            **s2_long_signal
          })

      # Check for short entry signals (if enabled and ticker is shortable)
      if enable_shorts:
        is_shortable = (shortable_tickers is None or ticker in shortable_tickers)
        if is_shortable:
          # Check System 1 (20-day) short entry signal first
          s1_short_signal = SignalGenerator.check_short_entry_signal(
            df, latest['close'], proximity_threshold, system=1
          )
          if s1_short_signal:
            signals.append({
              'ticker': ticker,
              **s1_short_signal
            })
          # If no System 1 signal, check System 2 (55-day) short entry
          elif not s1_short_signal:
            s2_short_signal = SignalGenerator.check_short_entry_signal(
              df, latest['close'], proximity_threshold, system=2
            )
            if s2_short_signal:
              signals.append({
                'ticker': ticker,
                **s2_short_signal
              })

    # Sort by proximity (closest to breakout/breakdown first)
    return sorted(signals, key=lambda x: abs(x['proximity']))
