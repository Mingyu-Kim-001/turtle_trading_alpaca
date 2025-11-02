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

  def get_historical_data(self, ticker, days=100, end_date=None):
    """
    Get historical daily data for a ticker

    Args:
      ticker: Stock ticker symbol
      days: Number of days of history to fetch
      end_date: Optional end date (datetime.date or datetime). Defaults to now.

    Returns:
      DataFrame with OHLCV data, or None if error
    """
    try:
      if end_date is None:
        end = datetime.now()
      elif isinstance(end_date, datetime):
        end = end_date
      else:
        # Convert date to datetime
        end = datetime.combine(end_date, datetime.min.time())

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

  @retry_on_connection_error(max_retries=3, initial_delay=2, backoff=2)
  def get_current_prices_batch(self, tickers):
    """
    Get current prices for multiple tickers in a single API call (batch)

    Args:
      tickers: List of stock ticker symbols

    Returns:
      Dictionary mapping ticker -> price (float), or None for failed tickers
    """
    if not tickers:
      return {}

    try:
      end = datetime.now()
      start = end - timedelta(minutes=15)

      # Alpaca API supports multi-symbol requests
      request_params = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end
      )

      bars = self.data_client.get_stock_bars(request_params)
      df = bars.df

      if df.empty:
        return {ticker: None for ticker in tickers}

      # Extract latest price for each ticker
      prices = {}
      for ticker in tickers:
        try:
          if isinstance(df.index, pd.MultiIndex):
            ticker_data = df.loc[ticker]
            if not ticker_data.empty:
              latest_price = ticker_data['close'].iloc[-1]
              prices[ticker] = float(latest_price)
            else:
              prices[ticker] = None
          else:
            # Single ticker case (shouldn't happen with batch, but handle it)
            prices[ticker] = float(df['close'].iloc[-1])
        except (KeyError, IndexError):
          prices[ticker] = None

      # Ensure all requested tickers are in result
      for ticker in tickers:
        if ticker not in prices:
          prices[ticker] = None

      return prices
    except Exception as e:
      print(f"Error getting batch prices for {len(tickers)} tickers: {e}")
      # Return None for all tickers on error
      return {ticker: None for ticker in tickers}
