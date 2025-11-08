# %%
# get historical stock price data from Alpaca API
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import pandas as pd
from pandas_datareader import data as pdr
import requests
import json
from typing import List
from tqdm import tqdm


def get_historical_daily_stock_price_data_from_Alpaca_API(ticker, start_date, end_date):
    """
    Fetch historical daily stock price data from Alpaca API.
    Read .config/alpaca_api_keys.json for API keys.

    Parameters:
    ticker (str): Stock ticker symbol.
    start_date (str): Start date in 'YYYY-MM-DD' format.
    end_date (str): End date in 'YYYY-MM-DD' format.
    timeframe (str): Data timeframe ('1Min', '5Min', '15Min', '1Hour', '1Day').

    Returns:
    pd.DataFrame: DataFrame containing historical stock price data.
    """
    
    # # Validate parameters
    # valid_timeframes = ['1Min', '5Min', '15Min', '1Hour', '1Day']
    
    # if timeframe not in valid_timeframes:
    #     raise ValueError(f"Invalid timeframe. Choose from {valid_timeframes}.")
    _timeframe = '1Day'


    
    # Read API keys from JSON file
    with open('.config/alpaca_api_keys.json', 'r') as file:
        api_keys = json.load(file)
    
    if 'ALPACA_PAPER_KEY' in api_keys:
        api_key = api_keys['ALPACA_PAPER_KEY']
    else:
        raise ValueError("ALPACA_PAPER_KEY is missing or empty")

    if 'ALPACA_PAPER_SECRET' in api_keys:
        api_secret = api_keys['ALPACA_PAPER_SECRET']
    else:
        raise ValueError("ALPACA_PAPER_SECRET is missing or empty")

    headers = {
        'APCA-API-KEY-ID': api_key,
        'APCA-API-SECRET-KEY': api_secret
    }


    # if the total row count exceeds 1000, split the request into multiple parts
    # Alpaca API has a limit of 1000 rows per request
    # Calculate the number of days between start_date and end_date
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    df_result = pd.DataFrame()
    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
    while start_dt <= datetime.strptime(end_date, '%Y-%m-%d'):
        end_dt = min(start_dt + timedelta(days=999), datetime.strptime(end_date, '%Y-%m-%d'))
        params = {
          'start': datetime.strftime(start_dt, '%Y-%m-%d'),
          'end': datetime.strftime(end_dt, '%Y-%m-%d'),
          'timeframe': _timeframe,
        } 

        # Make the API request
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            raise Exception(f"API request failed with status code {response.status_code}")

        data = response.json().get('bars', [])
        
        if not data:
            print(f"No historical data found for the given parameters: ticker {ticker}, start {start_dt}, end {end_dt}.")
            start_dt = end_dt + timedelta(days=1)
            continue

        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Convert timestamp to datetime
        # df['t'] = pd.to_datetime(df['t'], unit='s')
        
        # Rename columns for clarity
        df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
        df_result = pd.concat([df_result, df], ignore_index=True)
        start_dt = end_dt + timedelta(days=1)
        time.sleep(1)  # To avoid hitting rate limits
    
    return df_result



def get_sp500_tickers() -> List[str]:
    """
    Retrieves the ticker symbols for all S&P 500 companies.

    This function fetches the list of S&P 500 companies from Wikipedia,
    which is a widely used and practical source for this data.

    Returns:
        A list of S&P 500 ticker symbols, or an empty list if retrieval fails.
    """
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        df = pd.read_html(url, attrs={'id': 'constituents'}, storage_options=headers)[0]
        tickers = df['Symbol'].tolist()
        return tickers
    except Exception as e:
        print(f"Error fetching S&P 500 list: {e}")
        return []
# %%
snp500_tickers = get_sp500_tickers()
for ticker in tqdm(snp500_tickers):
    df = get_historical_daily_stock_price_data_from_Alpaca_API(ticker, '2016-01-01', '2025-09-28')
    df.to_csv(f'data/alpaca_daily/{ticker}_alpaca_daily.csv')
# %%
etfs = ['IAU', 'SLV', 'USO', 'XLE', 'VDE', 'SCO', 'CPER', 'PDBC', 'BND', 'AGG', 'HYG', 'TIP', 'FXE', 'FXY', 'UUP', 'VNQ', 'DBMF']
for etf in tqdm(etfs):
    df = get_historical_daily_stock_price_data_from_Alpaca_API(etf, '2016-01-01', '2025-09-28')
    df.to_csv(f'data/alpaca_daily/{etf}_alpaca_daily.csv')
# %%
# one-time
# get all the tickers in local - data/alpaca_daily/*_alpaca_daily.csv
import os
all_tickers = [filename.split('_alpaca_daily.csv')[0] for filename in os.listdir('data/alpaca_daily') if filename.endswith('_alpaca_daily.csv')]
with open('data/all_tickers.txt', 'w') as f:
    for ticker in all_tickers:
        f.write(f"{ticker}\n")
# %%
