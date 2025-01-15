import pandas as pd
import talib
import yfinance as yf
from lumibot.strategies import Strategy
from lumibot.entities import Order
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting
from datetime import datetime, timedelta
import os
import time
import configparser
import numpy as np

config = configparser.ConfigParser()
config.read(".env_test")

ALPACA_CONFIG = {
    # Put your own Alpaca key here:
    
    # If you want to go live, you must change this
    "ALPACA_IS_PAPER": "True",
}


class MinerviniBot(Strategy):
    parameters = {
        "capital": 100000,
        "risk_per_trade": 0.01,
        "volume_threshold": 100000,
        "top_n": 10,
        "trailing_stop_loss_pct": 0.05,
        "notification_email": "your_email@example.com",
    }

    def initialize(self):
        self.screener_ran = False
        self.custom_positions = {}
        self.data_file = "screened_stocks.csv"

    def log(self, message):
        """Log messages to the console or a file."""
        print(message)
    
    def before_market_opens(self):
        """Run the stock screener before the market opens."""
        if not self.screener_ran:
            self.screen_stocks()

    def fetch_data_with_retries(self, symbol, retries=3, delay=5):
        for attempt in range(retries):
            try:
                data = yf.download(symbol, period="2y", interval="1d")
                if not data.empty:
                    if isinstance(data.columns, pd.MultiIndex):
                        data.columns = data.columns.get_level_values(0)  # Use the second level (e.g., 'Close', 'Volume')
                    return data
            except Exception as e:
                self.log(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            time.sleep(delay)
        self.log(f"Failed to fetch data for {symbol} after {retries} retries.")
        return None

    def screen_stocks(self):
        if os.path.exists(self.data_file):
            if os.path.getsize(self.data_file) == 0:
                os.remove(self.data_file)
            else:
                last_modified_time = datetime.fromtimestamp(os.path.getmtime(self.data_file))
                if datetime.now() - last_modified_time < timedelta(days=1):
                    try:
                        self.top_stocks = pd.read_csv(self.data_file).to_dict("records")
                        if len(self.top_stocks) == 0:
                            os.remove(self.data_file)
                        else:
                            self.screener_ran = True
                            return
                    except pd.errors.EmptyDataError:
                        os.remove(self.data_file)

        universe = self.get_stock_universe()
        screened_stocks = []
        for symbol in universe:
            try:
                data = self.fetch_data_with_retries(symbol)
                if data is None:
                    self.log(f"No data fetched for {symbol}. Skipping.")
                    continue
                self.log(f"Fetched data for {symbol}: {data.head()}")
                self.log(f"Before dropna for {symbol}: {data[['Close', 'Volume']].head()}")
                data = data.dropna(subset=["Close", "Volume"])
                self.log(f"After dropna for {symbol}: {data[['Close', 'Volume']].head()}")
                self.log(f"Calculating SMA and RS for {symbol}. Data length: {len(data)}")
                close_prices = data["Close"].values
                data["50SMA"] = talib.SMA(close_prices, timeperiod=50)
                data["150SMA"] = talib.SMA(close_prices, timeperiod=150)
                data["RS"] = data["Close"] / data["Close"].rolling(window=252).mean()
                print(len(data))
                self.log(f"SMA and RS for {symbol}: {data[['50SMA', '150SMA', 'RS']].tail()}")
                self.log(f"Checking validity for {symbol}.")
                if not self.is_valid_stock(data, self.parameters["volume_threshold"]):
                    self.log(f"{symbol} did not pass the screening criteria.")
                    continue
                self.log(f"{symbol} passed the screening criteria." )       
                screened_stocks.append(
                        {
                            "symbol": symbol,
                            "momentum": data["RS"].iloc[-1],
                        }
                )
            except Exception as e:
                self.log(f"Error screening {symbol}: {e}")

        self.top_stocks = sorted(screened_stocks, key=lambda x: x["momentum"], reverse=True)[:self.parameters["top_n"]]
        pd.DataFrame(self.top_stocks).to_csv(self.data_file, index=False)
        self.screener_ran = True

    def is_valid_stock(self, data, volume_threshold):
        try:
            rs = data["RS"].iloc[-1]
            close = data["Close"].iloc[-1]
            sma_50 = data["50SMA"].iloc[-1]
            sma_150 = data["150SMA"].iloc[-1]
            volume = data["Volume"].iloc[-1]
            self.log(f"{volume} and {volume_threshold} volume for the screening criteria." )
            return (
                rs > 1.2
                and close > sma_50
                and sma_50 > sma_150
                and volume > volume_threshold
            )
        except Exception as e:
            self.log(f"Error validating stock data: {e}")
            return False


    def get_market_sentiment(self):
        """Analyze market sentiment using the VIX index and put/call ratio."""
        try:
            # Fetch VIX data
            vix_data = yf.download("^VIX", period="1mo", interval="1d")
            self.log(f"Fetched vix data : {vix_data.head()}")
            pcr_data = yf.download("PCCE", period="1mo", interval="1d")
            self.log(f"Fetched vix data : {pcr_data.head()}") 
            # if vix_data.empty or "Close" not in vix_data.columns:
            #     self.log("VIX data is invalid or missing.")
            #     return "Neutral"
            # vix_level = vix_data["Close"].iloc[-1]

            # # Fetch Put/Call Ratio data
            #  # CBOE Equity Put/Call Ratio
            # if pcr_data.empty or "Close" not in pcr_data.columns:
            #     self.log("Put/Call Ratio data is invalid or missing.")
            #     return "Neutral"
            # pcr_level = pcr_data["Close"].iloc[-1]
            if not vix_data.empty or not pcr_data.empty:
                if isinstance(vix_data.columns, pd.MultiIndex):
                        vix_data.columns = vix_data.columns.get_level_values(0)  # Use the second level (e.g., 'Close', 'Volume')
                        pcr_data.columns = pcr_data.columns.get_level_values(0)  # Use the second level (e.g., 'Close', 'Volume')
                self.log(f"VIX data : {vix_data['Close'].iloc[-1]}")
                self.log(f"PCCE data : {pcr_data['Close'].iloc[-1]}")
                vix_level = vix_data["Close"].iloc[-1]
                pcr_level = pcr_data["Close"].iloc[-1]
            # Determine market sentiment
                sentiment = "Neutral"
                if vix_level > 20 and pcr_level > 1.0:
                    sentiment = "Bearish"
                elif vix_level < 15 and pcr_level < 0.8:
                    sentiment = "Bullish"

                self.log(f"VIX Level: {vix_level}, Put/Call Ratio: {pcr_level}, Sentiment: {sentiment}")
                return sentiment
        except Exception as e:
            self.log(f"Error retrieving market sentiment data: {e}")
            return "Neutral"


    def calculate_position_size(self, stock_data, capital_per_trade):
        """Calculate position size based on stock volatility (ATR)."""
        if len(stock_data) < 14:
            self.log(f"Insufficient data to calculate ATR for {stock_data['Ticker'].iloc[0]}. Skipping.")
            return 0

        # Convert columns to numpy arrays for TA-Lib
        high = stock_data["High"].to_numpy().flatten()
        low = stock_data["Low"].to_numpy().flatten()
        close = stock_data["Close"].to_numpy().flatten()
        print(stock_data.columns)
        print(high.shape)  # Should output something like (N,) for a 1D array
        print(low.shape)
        print(close.shape)
        # Calculate ATR
        atr = talib.ATR(high, low, close, timeperiod=14)
        
        if np.isnan(atr[-1]):
            self.log(f"ATR value is NaN for {stock_data['Ticker'].iloc[0]}. Skipping.")
            return 0

        # Calculate position size based on ATR
        atr_value = atr[-1]
        position_size = capital_per_trade / atr_value

        self.log(f"Calculated ATR: {atr_value:.2f}, Position size: {position_size:.2f}")
        return position_size

    def on_trading_iteration(self):
        """Place trades based on entry/exit criteria and market sentiment."""
        if not self.screener_ran:
            return

        sentiment = self.get_market_sentiment()
        self.log(f"Market sentiment data type: {type(sentiment)}")
        self.log(f"Market sentiment data: {sentiment}")
        if not sentiment:
            #self.log("Error retrieving market sentiment. No trades will be executed")
            self.log(f"Market sentiment data type: {type(sentiment)}")
            self.log(f"Market sentiment data: {sentiment}")
            if sentiment == "Bearish":
                self.log("Market sentiment is bearish. No trades will be executed.")
                return

        available_capital = self.parameters["capital"]
        capital_per_trade = available_capital * self.parameters["risk_per_trade"]
        total_allocated_capital = 0

        for stock in self.top_stocks:
            if total_allocated_capital >= available_capital:
                break

            symbol = stock["symbol"]
            data = yf.download(symbol, period="3mo", interval="1d")


            if len(data) < 50:
                self.log(f"Insufficient data for {symbol}. Skipping.")
                continue

            resistance = data["Close"].rolling(window=50).max().iloc[-2]
            if resistance.isna().any():
                self.log(f"Resistance value is NaN for {symbol}. Skipping.")
                continue
            # Extract scalar values for comparison
            close_value = data["Close"].iloc[-1].iloc[0]
            resistance_value = resistance.iloc[0]
            # self.log(f"Close value: {data['Close'].iloc[-1]}, Resistance value: {resistance}")
            # self.log(f"Close type: {type(data['Close'].iloc[-1])}, Resistance type: {type(resistance)}")
            if close_value > resistance_value:
                position_size = self.calculate_position_size(data, capital_per_trade)
                total_cost = position_size * close_value

                if total_cost + total_allocated_capital > available_capital:
                    break

                trailing_stop_loss = close_value * (1 - self.parameters["trailing_stop_loss_pct"])
                quantity = int(position_size)

                order = self.create_order(
                    asset=symbol,
                    quantity=quantity,
                    side="buy",
                    trail_price=trailing_stop_loss,  # Use 'trailing_stop' instead of 'trailing_stop_loss'
                )

                # Submit the order
                self.submit_order(order)

                total_allocated_capital += total_cost

                self.notify(f"Bought {quantity} shares of {symbol} at {close_value} with trailing stop loss.")

    def after_market_closes(self):
        """Send a daily summary of positions and P/L."""
        position_summary = self.get_positions()
        for pos in position_summary:
            self.log(f"Position details: {pos}")

        total_pl = sum([pos["unrealized_pl"] for pos in position_summary])

        summary = f"Daily Position Summary:\n{position_summary}\nTotal P/L: {total_pl}"
        self.notify(summary)
        self.screener_ran = False

    def notify(self, message):
        """Send notifications via email or other services."""
        # Implement your email/SMS notification here
        self.log(message)

    def resume_from_positions(self):
        """Resume from existing positions in case of a system failure."""
        try:
            self.custom_positions = self.broker.get_positions()
            self.log(f"Resumed from positions: {self.custom_positions}")
        except Exception as e:
            self.log(f"Error resuming positions: {e}")

    def get_stock_universe(self):
        """Define your stock universe here."""
        #return ["AMZN","AVGO","CRM","AMD","DHR","PGR","APH","REGN","AMH","ARKG","AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]  # Example stocks
        return ["ITCI","ESLT","MFBP","ARIS","KTOS","CVU","IBEX","EBKOF","AMH","ARKG","AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]  # Example stocks

# Backtesting example
if __name__ == "__main__":
    broker = Alpaca(ALPACA_CONFIG)
    strategy = MinerviniBot(broker=broker)

    # Run live
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()

    # Pick the dates that you want to start and end your backtest
# and the allocated budget
    backtesting_start = datetime(2024, 6, 1)
    backtesting_end = datetime(2024, 12, 31)

    # Run the backtest
    result = MinerviniBot.run_backtest(
        YahooDataBacktesting,
        backtesting_start,
        backtesting_end,
    )

    # # Backtesting
    # backtest = Backtest(
    #     strategy=MinerviniBot,
    #     historical_data_path="path_to_historical_data",
    #     broker=broker,
    #     capital=100000,
    # )
    # backtest.run()
