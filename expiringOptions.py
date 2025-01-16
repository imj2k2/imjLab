from lumibot.strategies import Strategy
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
import pandas as pd
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
class DirectionalOptionsStrategy(Strategy):
    parameters = {
        "capital_allocation": 0.1,  # Fraction of capital per position
        "max_positions": 5,         # Maximum number of positions
        "profit_target": 0.25,     # Target profit percentage (e.g., 25%)
        "stop_loss": 0.15,         # Stop loss percentage (e.g., 15%)
        "supertrend_period": 7,    # Supertrend period
        "supertrend_multiplier": 3,  # Supertrend multiplier
        "alpaca_api_key": "YOUR_API_KEY",  # Alpaca API Key
        "alpaca_api_secret": "YOUR_API_SECRET"  # Alpaca API Secret
    }

    def initialize(self):
        self.sleeptime = "1h"  # Check every hour for updates
        self.stock_data = {}  # To store stock price data
        self.base_url = "https://paper-api.alpaca.markets/v2"

    def on_trading_iteration(self):
        # Define your watchlist
        watchlist = ["AAPL", "MSFT", "TSLA", "AMZN", "GOOGL"]

        for stock in watchlist:
            # Fetch historical data for the stock
            historical_data = self.get_historical_data(stock, "1D", limit=50)

            # Calculate Supertrend
            supertrend = self.calculate_supertrend(historical_data)
            latest_supertrend = supertrend.iloc[-1]

            # Check for buy/sell signals
            if latest_supertrend["Supertrend"] and stock not in self.get_positions():
                self.enter_position(stock)

            elif not latest_supertrend["Supertrend"] and stock in self.get_positions():
                self.close_position(stock)

        # Manage existing positions
        self.manage_positions()

    def enter_position(self, stock):
        # Fetch options contracts for the stock
        options_data = self.get_options_contracts(stock)
        if options_data.empty:
            self.log(f"No options contracts available for {stock}")
            return

        # Choose the nearest at-the-money call option
        atm_option = options_data.iloc[0]  # Assume sorted by relevance
        symbol = atm_option["symbol"]
        capital_per_position = self.parameters["capital_allocation"] * self.cash
        self.buy_option(symbol, capital_per_position)

    def manage_positions(self):
        for symbol, position in self.get_positions().items():
            current_price = self.get_option_price(symbol)
            entry_price = position["average_buy_price"]

            # Check for profit target
            if (current_price - entry_price) / entry_price >= self.parameters["profit_target"]:
                self.close_position(symbol)

            # Check for stop loss
            elif (entry_price - current_price) / entry_price >= self.parameters["stop_loss"]:
                self.close_position(symbol)

    def get_options_contracts(self, symbol):
        url = f"https://paper-api.alpaca.markets/v2/options/contracts"
        headers = {
            "APCA-API-KEY-ID": self.parameters["alpaca_api_key"],
            "APCA-API-SECRET-KEY": self.parameters["alpaca_api_secret"]
        }
        params = {"underlying": symbol}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            contracts = response.json().get("contracts", [])
            contracts_df = pd.DataFrame(contracts)

            # Filter for at-the-money options (or any preferred logic)
            contracts_df = contracts_df.sort_values("expiration_date")
            return contracts_df
        else:
            self.log(f"Failed to fetch options contracts for {symbol}: {response.text}")
            return pd.DataFrame()

    def calculate_supertrend(self, data):
        df = data.copy()
        hl2 = (df["high"] + df["low"]) / 2
        atr = hl2.rolling(self.parameters["supertrend_period"]).std() * self.parameters["supertrend_multiplier"]

        df["Upperband"] = hl2 + atr
        df["Lowerband"] = hl2 - atr

        df["Supertrend"] = df["close"] > df["Upperband"]

        return df

    def buy_option(self, symbol, amount):
        # Execute a market order for the specified option
        self.buy(
            symbol=symbol,
            quantity=amount // self.get_option_price(symbol)
        )

    def get_option_price(self, symbol):
        # Retrieve the latest price for the option
        return self.broker.get_option_price(symbol)


if __name__ == "__main__":
    broker = Alpaca(ALPACA_CONFIG)

    strategy = DirectionalOptionsStrategy(broker=broker)
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()