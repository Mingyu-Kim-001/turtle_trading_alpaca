"""Data provider for fetching market data from Alpaca API"""

import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from ..utils.decorators import retry_on_connection_error


class DataProvider:
  """Handles all data fetching operations from Alpaca API"""

  def __init__(self, api_key, api_secret):
    """
    Initialize data provider

    Args:
      api_key: Alpaca API key
      api_secret: Alpaca API secret
    """
    self.data_client = StockHistoricalDataClient(api_key, api_secret)

  def get_historical_data(self, ticker, days=100):
    """
    Get historical daily data for a ticker

    Args:
      ticker: Stock ticker symbol
      days: Number of days of history to fetch

    Returns:
      DataFrame with OHLCV data, or None if error
    """
    try:
      end = datetime.now()
      start = end - timedelta(days=days)

      request_params = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start,
        end=end
      )

      bars = self.data_client.get_stock_bars(request_params)
      df = bars.df

      if df.empty:
        return None

      df = df.reset_index()
      df = df.rename(columns={'timestamp': 'date'})

      if isinstance(df.columns, pd.MultiIndex):
        df = df[ticker]

      df = df.set_index('date').sort_index()

      return df
    except Exception as e:
      print(f"Error getting data for {ticker}: {e}")
      return None

  @retry_on_connection_error(max_retries=3, initial_delay=2, backoff=2)
  def get_current_price(self, ticker):
    """
    Get current price for a ticker

    Args:
      ticker: Stock ticker symbol

    Returns:
      Current price as float, or None if error
    """
    try:
      end = datetime.now()
      start = end - timedelta(minutes=15)

      request_params = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end
      )

      bars = self.data_client.get_stock_bars(request_params)
      df = bars.df

      if df.empty:
        return None

      if isinstance(df.index, pd.MultiIndex):
        latest_price = df.loc[ticker, 'close'].iloc[-1]
      else:
        latest_price = df['close'].iloc[-1]

      return float(latest_price)
    except Exception as e:
      print(f"Error getting current price for {ticker}: {e}")
      return None
