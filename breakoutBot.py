import pandas as pd
import numpy as np
import talib
import yfinance as yf
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from lumibot.brokers import Alpaca
from lumibot.traders import Trader
from datetime import datetime, timedelta
import schedule
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

# Fetch historical stock data and continuously update it
def fetch_data(symbol, start, end):
    df = yf.download(symbol, start=start, end=end)
    df['50_MA'] = talib.SMA(df['Close'], timeperiod=50)
    df['100_MA'] = talib.SMA(df['Close'], timeperiod=100)
    df['200_MA'] = talib.SMA(df['Close'], timeperiod=200)
    df['RSI'] = talib.RSI(df['Close'], timeperiod=14)
    df['ATR'] = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=14)
    df['10d_Vol_Avg'] = df['Volume'].rolling(window=10).mean()
    return df.dropna()

# Continuous data fetching
def update_data(symbols, data_storage_path):
    for symbol in symbols:
        try:
            # Load existing data if available
            try:
                df = pd.read_csv(f"{data_storage_path}/{symbol}.csv", index_col='Date', parse_dates=True)
                last_date = df.index[-1]
            except FileNotFoundError:
                df = pd.DataFrame()
                last_date = datetime.now() - timedelta(days=200)

            # Fetch new data from last_date to today
            new_data = yf.download(symbol, start=last_date + timedelta(days=1), end=datetime.now())
            new_data['50_MA'] = talib.SMA(new_data['Close'], timeperiod=50)
            new_data['100_MA'] = talib.SMA(new_data['Close'], timeperiod=100)
            new_data['200_MA'] = talib.SMA(new_data['Close'], timeperiod=200)
            new_data['RSI'] = talib.RSI(new_data['Close'], timeperiod=14)
            new_data['ATR'] = talib.ATR(new_data['High'], new_data['Low'], new_data['Close'], timeperiod=14)
            new_data['10d_Vol_Avg'] = new_data['Volume'].rolling(window=10).mean()

            # Append new data to existing data
            df = pd.concat([df, new_data])
            df = df[~df.index.duplicated(keep='last')]

            # Save updated data to CSV
            df.to_csv(f"{data_storage_path}/{symbol}.csv")
        except Exception as e:
            print(f"Error updating data for {symbol}: {e}")

# Schedule data updates
symbols = ["AAPL", "MSFT", "TSLA"]  # Example symbols
data_storage_path = "./data"
schedule.every().day.at("18:00").do(update_data, symbols=symbols, data_storage_path=data_storage_path)

# Screen stocks for breakouts and breakdowns
def screen_stocks(symbols, start, end):
    breakout_stocks = []
    breakdown_stocks = []
    for symbol in symbols:
        df = fetch_data(symbol, start, end)
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Uptrend breakout
        if (
            (latest['Close'] > latest['50_MA'] and prev['Close'] <= prev['50_MA']) or
            (latest['Close'] > latest['100_MA'] and prev['Close'] <= prev['100_MA']) or
            (latest['Close'] > latest['200_MA'] and prev['Close'] <= prev['200_MA'])
        ) and latest['Volume'] > latest['10d_Vol_Avg']:
            breakout_stocks.append(symbol)
        
        # Downtrend breakdown
        if (
            (latest['Close'] < latest['50_MA'] and prev['Close'] >= prev['50_MA']) or
            (latest['Close'] < latest['100_MA'] and prev['Close'] >= prev['100_MA']) or
            (latest['Close'] < latest['200_MA'] and prev['Close'] >= prev['200_MA'])
        ) and latest['Volume'] > latest['10d_Vol_Avg']:
            breakdown_stocks.append(symbol)
    
    return breakout_stocks, breakdown_stocks

# Define Lumibot strategy
class BreakoutStrategy(Strategy):
    def initialize(self):
        self.atr_multiplier = 1.5
        self.max_risk = 0.01  # 1% of portfolio

    def on_trading_iteration(self):
        cash = self.get_cash()
        symbols = ["AAPL", "MSFT", "TSLA"]  # Example stocks
        breakout_stocks, breakdown_stocks = screen_stocks(symbols, datetime.now() - timedelta(days=200), datetime.now())
        
        for symbol in breakout_stocks:
            df = fetch_data(symbol, datetime.now() - timedelta(days=200), datetime.now())
            latest = df.iloc[-1]
            
            atr = latest['ATR']
            stop_loss = latest['Close'] - self.atr_multiplier * atr
            position_size = (self.max_risk * cash) / (latest['Close'] - stop_loss)
            
            self.submit_order(symbol, quantity=int(position_size), side='buy', stop_loss=stop_loss)
        
        for symbol in breakdown_stocks:
            df = fetch_data(symbol, datetime.now() - timedelta(days=200), datetime.now())
            latest = df.iloc[-1]
            
            atr = latest['ATR']
            stop_loss = latest['Close'] + self.atr_multiplier * atr
            position_size = (self.max_risk * cash) / (stop_loss - latest['Close'])
            
            self.submit_order(symbol, quantity=int(position_size), side='sell', stop_loss=stop_loss)

# Set up Alpaca broker for trading
broker = Alpaca(API_KEY, API_SECRET, BASE_URL)
strategy = BreakoutStrategy(broker=broker)

# Backtesting
#backtest = Backtesting(strategy, start_date='2023-01-01', end_date='2024-01-01', initial_cash=100000)
#backtest.run()
result = strategy.run_backtest(
    YahooDataBacktesting,
    start_date='2023-01-01', end_date='2024-01-01'
)

# Keep the scheduler running
while True:
    schedule.run_pending()
    time.sleep(1)
