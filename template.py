import pandas as pd
import talib
import yfinance as yf
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from datetime import datetime, timedelta
import os
import time
import configparser
import numpy as np

config = configparser.ConfigParser()
config.read(".env_test")

ALPACA_CONFIG = {
    # Put your own Alpaca key here:
    "API_KEY": config["ALPACA"]["ALPACA_API_KEY"],
    "API_SECRET": config["ALPACA"]["ALPACA_SECRET_KEY"],
    "ALPACA_IS_PAPER": "True",
}

class myBot(Strategy):
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
        print(message)

    def before_market_opens(self):
        if not self.screener_ran:
            self.screen_stocks()

    def fetch_data_with_retries(self, symbol, retries=3, delay=5):
        for attempt in range(retries):
            try:
                data = yf.download(symbol, period="2y", interval="1d")
                if not data.empty:
                    if isinstance(data.columns, pd.MultiIndex):
                        data.columns = data.columns.get_level_values(0)
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

                data = data.dropna(subset=["Close", "Volume"])
                close_prices = data["Close"].values
                data["50SMA"] = talib.SMA(close_prices, timeperiod=50)
                data["150SMA"] = talib.SMA(close_prices, timeperiod=150)
                data["RS"] = data["Close"] / data["Close"].rolling(window=252).mean()

                if not self.is_valid_stock(data, self.parameters["volume_threshold"]):
                    continue

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
            return
        except Exception as e:
            self.log(f"Error validating stock data: {e}")
            return False

    def on_trading_iteration(self):
        if not self.screener_ran:
            return

        

    def get_stock_universe(self):
        return ["ITCI", "ESLT", "MFBP", "ARIS", "KTOS", "CVU", "IBEX", "EBKOF", "AMH", "ARKG", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]

if __name__ == "__main__":
    broker = Alpaca(ALPACA_CONFIG)
    strategy = myBot(broker=broker)
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()
