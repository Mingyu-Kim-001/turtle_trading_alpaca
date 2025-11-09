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
               long_positions, short_positions,
               enable_longs=True, enable_shorts=True,
               enable_system1=True, enable_system2=False,
               shortable_tickers=None, proximity_threshold=0.05,
               last_trade_was_win=None):
    """
    Generate entry signals for entire universe

    Implements proper Turtle Trading system logic with System 2 priority:
    - System 1: Skip entry if last System 1 trade for this ticker was a winner
    - System 2: Always take entries (no filter)
    - Priority: System 2 > System 1 (handled in processing, not here)
    - Systems checked independently based on enable flags

    Args:
      universe: List of ticker symbols
      data_provider: DataProvider instance
      indicator_calculator: IndicatorCalculator instance
      long_positions: Dict of existing long positions
      short_positions: Dict of existing short positions
      enable_longs: Whether to generate long signals
      enable_shorts: Whether to generate short signals
      enable_system1: Whether to generate System 1 (20-10) signals
      enable_system2: Whether to generate System 2 (55-20) signals
      shortable_tickers: Set of shortable tickers (None = all shortable)
      proximity_threshold: Proximity threshold for signals
      last_trade_was_win: Dict tracking if last System 1 trade was a win {(ticker, side): bool}

    Returns:
      List of entry signals with system info (priority applied during processing)
    """
    signals = []
    last_trade_was_win = last_trade_was_win or {}

    for ticker in universe:
      # Skip if already have a position (long or short)
      if ticker in long_positions or ticker in short_positions:
        continue

      df = data_provider.get_historical_data(ticker)
      if df is None or len(df) < 55:
        continue

      df = indicator_calculator.calculate_indicators(df)
      latest = df.iloc[-1]

      # Check long signals if enabled
      if enable_longs:
        # Check System 2 (55-day) long entry signal if enabled
        if enable_system2:
          s2_long_signal = SignalGenerator.check_long_entry_signal(
            df, latest['close'], proximity_threshold, system=2
          )
          if s2_long_signal:
            # System 2 always takes entries (no win filter)
            signals.append({
              'ticker': ticker,
              **s2_long_signal
            })

        # Check System 1 (20-day) long entry signal if enabled
        if enable_system1:
          s1_long_signal = SignalGenerator.check_long_entry_signal(
            df, latest['close'], proximity_threshold, system=1
          )
          # Only add System 1 long signal if last trade wasn't a win
          if s1_long_signal and not last_trade_was_win.get((ticker, 'long'), False):
            signals.append({
              'ticker': ticker,
              **s1_long_signal
            })

      # Check for short entry signals (if enabled and ticker is shortable)
      if enable_shorts:
        is_shortable = (shortable_tickers is None or ticker in shortable_tickers)
        if is_shortable:
          # Check System 2 (55-day) short entry signal if enabled
          if enable_system2:
            s2_short_signal = SignalGenerator.check_short_entry_signal(
              df, latest['close'], proximity_threshold, system=2
            )
            if s2_short_signal:
              # System 2 always takes entries (no win filter)
              signals.append({
                'ticker': ticker,
                **s2_short_signal
              })

          # Check System 1 (20-day) short entry signal if enabled
          if enable_system1:
            s1_short_signal = SignalGenerator.check_short_entry_signal(
              df, latest['close'], proximity_threshold, system=1
            )
            # Only add System 1 short signal if last trade wasn't a win
            if s1_short_signal and not last_trade_was_win.get((ticker, 'short'), False):
              signals.append({
                'ticker': ticker,
                **s1_short_signal
              })

    # Sort by system (System 2 first, then System 1) then by proximity
    # System 2 has higher priority, so it gets processed first
    # Negate system number so System 2 (2) comes before System 1 (1): -2 < -1
    return sorted(signals, key=lambda x: (-x['system'], abs(x['proximity'])))
