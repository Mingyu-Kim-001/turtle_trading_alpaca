"""Technical indicator calculations for Turtle Trading"""

import numpy as np
import pandas as pd


class IndicatorCalculator:
  """Calculate technical indicators for trading signals"""

  @staticmethod
  def calculate_atr(df, period=20):
    """
    Calculate Average True Range (ATR)

    Args:
      df: DataFrame with OHLC data (will be modified in-place)
      period: Lookback period for ATR

    Returns:
      DataFrame with ATR column added (named 'N' for Turtle Trading)
    """
    # Note: No copy() - caller is responsible for copying if needed
    df['prev_close'] = df['close'].shift(1)
    df['TR'] = np.maximum(
      df['high'] - df['low'],
      np.maximum(
        np.abs(df['high'] - df['prev_close']),
        np.abs(df['low'] - df['prev_close'])
      )
    )
    df['N'] = df['TR'].rolling(window=period).mean()
    return df

  @staticmethod
  def calculate_donchian_channels(df, entry_period=20, exit_period=10, long_entry_period=55):
    """
    Calculate Donchian Channels for dual system (System 1: 20-10, System 2: 55-20)

    IMPORTANT: Channels are calculated using PREVIOUS N days (excluding current day).
    This is the correct Turtle Trading behavior - you enter when price breaks ABOVE
    the high of the previous 20 days, not when today's high equals the 20-day high.

    Args:
      df: DataFrame with OHLC data (will be modified in-place)
      entry_period: Period for System 1 entry (default 20)
      exit_period: Period for System 1 exit (default 10)
      long_entry_period: Period for System 2 entry (default 55)

    Returns:
      DataFrame with Donchian channel columns added:
        - high_20, low_20: System 1 entry, System 2 exit
        - high_10, low_10: System 1 exit
        - high_55, low_55: System 2 entry
    """
    # Note: No copy() - caller is responsible for copying if needed
    # System 1 entry (20-day) - exclude current day with shift(1)
    df['high_20'] = df['high'].shift(1).rolling(window=entry_period).max()
    df['low_20'] = df['low'].shift(1).rolling(window=entry_period).min()

    # System 1 exit (10-day) - exclude current day with shift(1)
    df['high_10'] = df['high'].shift(1).rolling(window=exit_period).max()
    df['low_10'] = df['low'].shift(1).rolling(window=exit_period).min()

    # System 2 entry (55-day), exits use 20-day (already calculated above)
    df['high_55'] = df['high'].shift(1).rolling(window=long_entry_period).max()
    df['low_55'] = df['low'].shift(1).rolling(window=long_entry_period).min()

    return df

  @staticmethod
  def calculate_indicators(df):
    """
    Calculate all indicators needed for Turtle Trading

    Args:
      df: DataFrame with OHLC data

    Returns:
      DataFrame with all indicators added
    """
    df = IndicatorCalculator.calculate_atr(df)
    df = IndicatorCalculator.calculate_donchian_channels(df)
    return df

  @staticmethod
  def get_latest_completed_n(df):
    """
    Get N (ATR) from the last completed daily bar, excluding today's incomplete bar.

    This ensures N is calculated only from complete daily data, matching the shift(1)
    behavior used in Donchian channels. During market hours, today's incomplete bar
    is excluded to prevent N from changing throughout the trading day.

    Args:
      df: DataFrame with calculated indicators (must have 'N' column and date index)

    Returns:
      Latest completed N value, or None if not available
    """
    if df is None or len(df) == 0 or 'N' not in df.columns:
      return None

    from datetime import datetime
    import pytz

    # Get the last bar's date
    last_bar_date = df.index[-1]

    # Convert to date (handle both date and datetime)
    if hasattr(last_bar_date, 'date'):
      last_bar_date = last_bar_date.date()
    elif hasattr(last_bar_date, 'to_pydatetime'):
      last_bar_date = last_bar_date.to_pydatetime().date()

    # Get today's date in market timezone (US/Eastern)
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    today = now_eastern.date()

    # If last bar is from today, it might be incomplete during market hours
    if last_bar_date == today:
      # Check if market is currently open (9:30 AM - 4:00 PM ET)
      market_time = now_eastern.time()
      from datetime import time
      market_open = time(9, 30)
      market_close = time(16, 0)

      if market_open <= market_time <= market_close:
        # Market is open, last bar is incomplete - use second-to-last bar
        if len(df) < 2:
          return None
        return df.iloc[-2]['N']

    # Last bar is complete (either not today, or market is closed)
    return df.iloc[-1]['N']
