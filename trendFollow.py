import alpaca_trade_api as tradeapi
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator
import matplotlib.pyplot as plt
import backtrader as bt
import os
import configparser

config = configparser.ConfigParser()
config.read(".env_test")
# Alpaca API Keys
ALPACA_API_KEY = config["ALPACA"]["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = config["ALPACA"]["ALPACA_SECRET_KEY"]
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# Initialize Alpaca API
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

# Function to Save and Load Data
def get_historic_data(ticker, file_path, start_date="2000-01-01"):
    """Fetch and save historic data to CSV, updating as needed."""
    if os.path.exists(file_path):
        data = pd.read_csv(file_path, index_col="Date", parse_dates=True)
        last_date = data.index[-1]
        today = pd.Timestamp.today()
        if last_date >= today - pd.Timedelta(days=1):
            print(f"Data for {ticker} is up-to-date.")
            return data
        else:
            print(f"Updating data for {ticker} from {last_date + pd.Timedelta(days=1)}.")
            new_data = yf.download(ticker, start=last_date + pd.Timedelta(days=1))
            if not new_data.empty:
                data = pd.concat([data, new_data])
                data.to_csv(file_path)
            return data
    else:
        print(f"Downloading new data for {ticker} starting from {start_date}.")
        data = yf.download(ticker, start=start_date)
        if not data.empty:
            data.to_csv(file_path)
        return data

# Mark Minervini's Stock Selection Criteria
def minervini_stock_screener():
    """Screen stocks based on Mark Minervini's criteria."""
    # Fetch stock universe (S&P 500 in this example)
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].tolist()
    selected_stocks = []

    for ticker in sp500:
        try:
            file_path = f"data/{ticker}.csv"
            data = get_historic_data(ticker, file_path, start_date="2022-01-01")

            if len(data) < 125:  # Ensure enough data points
                continue

            closes = data['Close'].copy()
            closes = pd.Series(closes.values.flatten(), index=closes.index)  # Ensure 1D Series

            data['SMA50'] = SMAIndicator(closes, 50).sma_indicator()
            data['SMA150'] = SMAIndicator(closes, 150).sma_indicator()
            data['SMA200'] = SMAIndicator(closes, 200).sma_indicator()

            # Minervini's Criteria
            if (
                data['Close'].iloc[-1] > data['SMA50'].iloc[-1] and
                data['SMA50'].iloc[-1] > data['SMA150'].iloc[-1] and
                data['SMA150'].iloc[-1] > data['SMA200'].iloc[-1] and
                data['Close'].iloc[-1] > data['Close'].iloc[-125:].max() * 0.75
            ):
                selected_stocks.append(ticker)
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    return selected_stocks

# Trend Following Strategy Execution
def execute_trend_following(selected_stocks):
    """Execute a trend following strategy."""
    for stock in selected_stocks:
        try:
            file_path = f"data/{stock}.csv"
            data = get_historic_data(stock, file_path, start_date="2022-01-01")

            closes = data['Close'].copy()
            closes = pd.Series(closes.values.flatten(), index=closes.index)  # Ensure 1D Series

            data['SMA50'] = SMAIndicator(closes, 50).sma_indicator()
            data['SMA200'] = SMAIndicator(closes, 200).sma_indicator()

            if (
                data['Close'].iloc[-1] > data['SMA50'].iloc[-1] and
                data['SMA50'].iloc[-1] > data['SMA200'].iloc[-1]
            ):
                # Place a market order (Paper trading)
                api.submit_order(
                    symbol=stock,
                    qty=10,  # Example quantity
                    side='buy',
                    type='market',
                    time_in_force='gtc'
                )
                print(f"Buy order placed for {stock}")
        except Exception as e:
            print(f"Error trading {stock}: {e}")

# Backtesting with Backtrader
class TrendFollowingStrategy(bt.Strategy):
    params = (('sma_period_short', 50), ('sma_period_long', 200))

    def __init__(self):
        self.sma_short = bt.indicators.SMA(self.data.close, period=self.params.sma_period_short)
        self.sma_long = bt.indicators.SMA(self.data.close, period=self.params.sma_period_long)

    def next(self):
        if self.position:
            if self.data.close[0] < self.sma_short[0]:
                self.close()  # Exit condition
        else:
            if self.data.close[0] > self.sma_short[0] > self.sma_long[0]:
                self.buy()  # Entry condition

# Backtest Runner
def run_backtest(stock):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(TrendFollowingStrategy)

    file_path = f"data/{stock}.csv"
    data = get_historic_data(stock, file_path, start_date="2022-01-01")
    bt_data = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(bt_data)

    cerebro.broker.set_cash(10000)
    cerebro.run()
    cerebro.plot()

# Main Execution
if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")

    stocks = minervini_stock_screener()
    print(f"Selected Stocks: {stocks}")
    execute_trend_following(stocks)

    # Backtesting Example
    if stocks:
        run_backtest(stocks[0])
