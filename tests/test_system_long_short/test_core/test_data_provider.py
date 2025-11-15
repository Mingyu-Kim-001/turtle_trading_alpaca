"""Comprehensive tests for DataProvider"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from system_long_short.core.data_provider import DataProvider


class TestDataProviderHistoricalData(unittest.TestCase):
  """Test historical data fetching"""

  def setUp(self):
    """Set up test fixtures"""
    self.api_key = 'test-api-key'
    self.api_secret = 'test-api-secret'

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_historical_data_success(self, mock_client_class):
    """Test successful historical data fetch"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Create mock response in proper Alpaca format
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    mock_df = pd.DataFrame({
      'timestamp': dates,
      'open': np.random.uniform(100, 110, 100),
      'high': np.random.uniform(110, 120, 100),
      'low': np.random.uniform(90, 100, 100),
      'close': np.random.uniform(100, 110, 100),
      'volume': np.random.randint(1000000, 5000000, 100),
      'symbol': ['AAPL'] * 100
    })

    mock_bars = Mock()
    mock_bars.df = mock_df
    mock_client.get_stock_bars.return_value = mock_bars

    # Test
    provider = DataProvider(self.api_key, self.api_secret)
    df = provider.get_historical_data('AAPL', days=100)

    # Verify
    self.assertIsNotNone(df)
    self.assertGreater(len(df), 0)
    self.assertIn('open', df.columns)
    self.assertIn('high', df.columns)
    self.assertIn('low', df.columns)
    self.assertIn('close', df.columns)
    self.assertIn('volume', df.columns)
    # Verify index is 'date' (renamed from 'timestamp')
    self.assertEqual(df.index.name, 'date')
    mock_client.get_stock_bars.assert_called_once()

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_historical_data_empty_response(self, mock_client_class):
    """Test handling of empty data response"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Create empty response
    mock_bars = Mock()
    mock_bars.df = pd.DataFrame()
    mock_client.get_stock_bars.return_value = mock_bars

    provider = DataProvider(self.api_key, self.api_secret)
    df = provider.get_historical_data('INVALID', days=100)

    self.assertIsNone(df)

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_historical_data_api_error(self, mock_client_class):
    """Test handling of API errors"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_stock_bars.side_effect = Exception("API Error")

    provider = DataProvider(self.api_key, self.api_secret)
    df = provider.get_historical_data('ERROR', days=100)

    self.assertIsNone(df)

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_historical_data_with_end_date(self, mock_client_class):
    """Test getting historical data with end date"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    dates = pd.date_range(start='2024-01-01', periods=50, freq='D')
    mock_df = pd.DataFrame({
      'timestamp': dates,
      'open': np.random.uniform(100, 110, 50),
      'high': np.random.uniform(110, 120, 50),
      'low': np.random.uniform(90, 100, 50),
      'close': np.random.uniform(100, 110, 50),
      'volume': np.random.randint(1000000, 5000000, 50),
      'symbol': ['MSFT'] * 50
    })

    mock_bars = Mock()
    mock_bars.df = mock_df
    mock_client.get_stock_bars.return_value = mock_bars

    provider = DataProvider(self.api_key, self.api_secret)
    end_date = datetime(2024, 2, 1)
    df = provider.get_historical_data('MSFT', days=50, end_date=end_date)

    self.assertIsNotNone(df)
    # Verify the end date was passed to API
    call_args = mock_client.get_stock_bars.call_args[0][0]
    self.assertEqual(call_args.end, end_date)


class TestDataProviderCurrentPrice(unittest.TestCase):
  """Test current price fetching"""

  def setUp(self):
    """Set up test fixtures"""
    self.api_key = 'test-api-key'
    self.api_secret = 'test-api-secret'

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_price_success(self, mock_client_class):
    """Test successful current price fetch"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Create mock trade response
    mock_trade = Mock()
    mock_trade.price = 150.75
    mock_client.get_stock_latest_trade.return_value = {'AAPL': mock_trade}

    provider = DataProvider(self.api_key, self.api_secret)
    price = provider.get_current_price('AAPL')

    self.assertEqual(price, 150.75)
    mock_client.get_stock_latest_trade.assert_called_once()

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_price_ticker_not_found(self, mock_client_class):
    """Test when ticker is not in response"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Response doesn't contain requested ticker
    mock_client.get_stock_latest_trade.return_value = {}

    provider = DataProvider(self.api_key, self.api_secret)
    price = provider.get_current_price('INVALID')

    self.assertIsNone(price)

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_price_api_error(self, mock_client_class):
    """Test handling of API errors"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_stock_latest_trade.side_effect = Exception("API Error")

    provider = DataProvider(self.api_key, self.api_secret)
    price = provider.get_current_price('ERROR')

    self.assertIsNone(price)


class TestDataProviderBatchPrices(unittest.TestCase):
  """Test batch price fetching"""

  def setUp(self):
    """Set up test fixtures"""
    self.api_key = 'test-api-key'
    self.api_secret = 'test-api-secret'

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_prices_batch_success(self, mock_client_class):
    """Test successful batch price fetch"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Create mock trades
    mock_trade_aapl = Mock()
    mock_trade_aapl.price = 150.0
    mock_trade_msft = Mock()
    mock_trade_msft.price = 300.0
    mock_trade_googl = Mock()
    mock_trade_googl.price = 2800.0

    mock_client.get_stock_latest_trade.return_value = {
      'AAPL': mock_trade_aapl,
      'MSFT': mock_trade_msft,
      'GOOGL': mock_trade_googl
    }

    provider = DataProvider(self.api_key, self.api_secret)
    prices = provider.get_current_prices_batch(['AAPL', 'MSFT', 'GOOGL'])

    self.assertEqual(len(prices), 3)
    self.assertEqual(prices['AAPL'], 150.0)
    self.assertEqual(prices['MSFT'], 300.0)
    self.assertEqual(prices['GOOGL'], 2800.0)

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_prices_batch_partial_response(self, mock_client_class):
    """Test batch fetch when some tickers are missing"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_trade = Mock()
    mock_trade.price = 150.0

    # Only AAPL in response
    mock_client.get_stock_latest_trade.return_value = {'AAPL': mock_trade}

    provider = DataProvider(self.api_key, self.api_secret)
    prices = provider.get_current_prices_batch(['AAPL', 'MSFT', 'INVALID'])

    self.assertEqual(prices['AAPL'], 150.0)
    self.assertIsNone(prices['MSFT'])
    self.assertIsNone(prices['INVALID'])

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_prices_batch_empty_list(self, mock_client_class):
    """Test batch fetch with empty ticker list"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    provider = DataProvider(self.api_key, self.api_secret)
    prices = provider.get_current_prices_batch([])

    self.assertEqual(prices, {})
    mock_client.get_stock_latest_trade.assert_not_called()

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_get_current_prices_batch_api_error(self, mock_client_class):
    """Test batch fetch with API error"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_stock_latest_trade.side_effect = Exception("API Error")

    provider = DataProvider(self.api_key, self.api_secret)
    prices = provider.get_current_prices_batch(['AAPL', 'MSFT'])

    # Should return None for all tickers on error
    self.assertIsNone(prices['AAPL'])
    self.assertIsNone(prices['MSFT'])


class TestDataProviderEdgeCases(unittest.TestCase):
  """Test edge cases and data transformations"""

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_data_provider_initialization(self, mock_client_class):
    """Test that DataProvider initializes correctly"""
    provider = DataProvider('test-key', 'test-secret')
    
    # Verify client was created
    mock_client_class.assert_called_once_with('test-key', 'test-secret')
    self.assertIsNotNone(provider.data_client)

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_dataframe_index_is_sorted(self, mock_client_class):
    """Test that returned DataFrame has sorted date index"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Create unsorted dates
    dates = pd.to_datetime(['2024-01-15', '2024-01-10', '2024-01-20', '2024-01-05'])
    mock_df = pd.DataFrame({
      'timestamp': dates,
      'open': [100, 101, 102, 103],
      'high': [105, 106, 107, 108],
      'low': [95, 96, 97, 98],
      'close': [100, 101, 102, 103],
      'volume': [1000000, 1100000, 1200000, 1300000],
      'symbol': ['TEST'] * 4
    })

    mock_bars = Mock()
    mock_bars.df = mock_df
    mock_client.get_stock_bars.return_value = mock_bars

    provider = DataProvider('test-key', 'test-secret')
    df = provider.get_historical_data('TEST', days=20)

    # Verify index is sorted
    self.assertIsNotNone(df)
    self.assertTrue(df.index.is_monotonic_increasing, "Index should be sorted")

  @patch('system_long_short.core.data_provider.StockHistoricalDataClient')
  def test_handles_date_object_end_date(self, mock_client_class):
    """Test that date objects (not datetime) are handled correctly"""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
    mock_df = pd.DataFrame({
      'timestamp': dates,
      'open': np.full(10, 100.0),
      'high': np.full(10, 105.0),
      'low': np.full(10, 95.0),
      'close': np.full(10, 100.0),
      'volume': np.full(10, 1000000),
      'symbol': ['TEST'] * 10
    })

    mock_bars = Mock()
    mock_bars.df = mock_df
    mock_client.get_stock_bars.return_value = mock_bars

    provider = DataProvider('test-key', 'test-secret')
    end_date = date(2024, 1, 10)  # date object, not datetime
    df = provider.get_historical_data('TEST', days=10, end_date=end_date)

    self.assertIsNotNone(df)


if __name__ == '__main__':
  unittest.main()
