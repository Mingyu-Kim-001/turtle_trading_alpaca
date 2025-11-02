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
      df: DataFrame with OHLC data
      period: Lookback period for ATR

    Returns:
      DataFrame with ATR column added (named 'N' for Turtle Trading)
    """
    df = df.copy()
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
    Calculate Donchian Channels for entry and exit signals

    Args:
      df: DataFrame with OHLC data
      entry_period: Period for System 1 entry (default 20)
      exit_period: Period for System 1 exit (default 10)
      long_entry_period: Period for System 2 entry (default 55)

    Returns:
      DataFrame with Donchian channel columns added
    """
    df = df.copy()
    df['high_20'] = df['high'].rolling(window=entry_period).max()
    df['high_55'] = df['high'].rolling(window=long_entry_period).max()
    df['low_10'] = df['low'].rolling(window=exit_period).min()
    df['low_20'] = df['low'].rolling(window=entry_period).min()
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
