"""Data provider for fetching market data from Alpaca API"""

import pandas as pd
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
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
    Get current price for a ticker using latest trade data

    Args:
      ticker: Stock ticker symbol

    Returns:
      Current price as float, or None if error
    """
    try:
      # Use latest trade request for real-time price
      request = StockLatestTradeRequest(symbol_or_symbols=ticker)
      latest_trade = self.data_client.get_stock_latest_trade(request)

      if ticker in latest_trade:
        return float(latest_trade[ticker].price)
      else:
        return None

    except Exception as e:
      print(f"Error getting current price for {ticker}: {e}")
      return None

  @retry_on_connection_error(max_retries=3, initial_delay=2, backoff=2)
  def get_current_prices_batch(self, tickers):
    """
    Get current prices for multiple tickers using latest trade data (REAL-TIME)

    Args:
      tickers: List of stock ticker symbols

    Returns:
      Dictionary mapping ticker -> price (float), or None for failed tickers
    """
    if not tickers:
      return {}

    try:
      # Use latest trade request for real-time prices (batch)
      request = StockLatestTradeRequest(symbol_or_symbols=tickers)
      latest_trades = self.data_client.get_stock_latest_trade(request)

      # Extract prices for each ticker
      prices = {}
      for ticker in tickers:
        try:
          if ticker in latest_trades:
            prices[ticker] = float(latest_trades[ticker].price)
          else:
            prices[ticker] = None
        except (KeyError, AttributeError) as e:
          prices[ticker] = None

      return prices

    except Exception as e:
      print(f"Error getting batch prices for {len(tickers)} tickers: {e}")
      # Return None for all tickers on error
      return {ticker: None for ticker in tickers}
