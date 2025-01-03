import alpaca_trade_api as tradeapi
import yfinance as yf
import pandas as pd
import numpy as np
from ta.trend import SMAIndicator
import matplotlib.pyplot as plt
import backtrader as bt

# Alpaca API Keys
ALPACA_API_KEY = "your_api_key"
ALPACA_SECRET_KEY = "your_secret_key"
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# Initialize Alpaca API
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

# Mark Minervini's Stock Selection Criteria
def minervini_stock_screener():
    """Screen stocks based on Mark Minervini's criteria."""
    # Fetch stock universe (S&P 500 in this example)
    sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].tolist()
    selected_stocks = []

    for ticker in sp500:
        try:
            data = yf.download(ticker, period="6mo", interval="1d")
            if len(data) < 125:  # Ensure enough data points
                continue

            data['SMA50'] = SMAIndicator(data['Close'], 50).sma_indicator()
            data['SMA150'] = SMAIndicator(data['Close'], 150).sma_indicator()
            data['SMA200'] = SMAIndicator(data['Close'], 200).sma_indicator()

            # Minervini's Criteria
            recent = data.iloc[-1]
            if (
                recent['Close'] > recent['SMA50'] > recent['SMA150'] > recent['SMA200'] and
                data['Close'][-1] > data['Close'][-1] * 1.25 and
                recent['Close'] > data['Close'].max() * 0.75
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
            data = api.get_barset(stock, 'day', limit=200)[stock]
            closes = [bar.c for bar in data]
            
            sma50 = SMAIndicator(pd.Series(closes), 50).sma_indicator()
            sma200 = SMAIndicator(pd.Series(closes), 200).sma_indicator()

            if closes[-1] > sma50[-1] > sma200[-1]:
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

    data = bt.feeds.PandasData(dataname=yf.download(stock, '2022-01-01', '2023-01-01'))
    cerebro.adddata(data)

    cerebro.broker.set_cash(10000)
    cerebro.run()
    cerebro.plot()

# Main Execution
if __name__ == "__main__":
    stocks = minervini_stock_screener()
    print(f"Selected Stocks: {stocks}")
    execute_trend_following(stocks)

    # Backtesting Example
    if stocks:
        run_backtest(stocks[0])
