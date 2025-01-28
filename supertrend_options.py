from lumibot.strategy import Strategy
from lumibot.traders import Alpaca
import pandas as pd

class DirectionalOptionsStrategy(Strategy):
    parameters = {
        "capital_allocation": 0.1,  # Fraction of capital per position
        "max_positions": 5,         # Maximum number of positions
        "profit_target": 0.25,     # Target profit percentage (e.g., 25%)
        "stop_loss": 0.15,         # Stop loss percentage (e.g., 15%)
        "supertrend_period": 7,    # Supertrend period
        "supertrend_multiplier": 3  # Supertrend multiplier
    }

    def initialize(self):
        self.sleeptime = "1h"  # Check every hour for updates
        self.stock_data = {}  # To store stock price data

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
        capital_per_position = self.parameters["capital_allocation"] * self.cash
        self.buy_option(stock, capital_per_position)

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
    trader = Alpaca(
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        base_url="https://paper-api.alpaca.markets"
    )

    strategy = DirectionalOptionsStrategy(trader=trader)
    strategy.run()

