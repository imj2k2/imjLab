import pandas as pd
import talib
from lumibot.strategies import Strategy
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from lumibot.backtest import Backtest

class MinerviniBot(Strategy):
    parameters = {
        "capital": 100000,
        "risk_per_trade": 0.01,
        "volume_threshold": 1000000,
        "top_n": 10,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.20,
    }

    def initialize(self):
        self.screener_ran = False
        self.positions = {}

    def before_market_opens(self):
        """Run the stock screener before the market opens."""
        if not self.screener_ran:
            self.screen_stocks()

    def screen_stocks(self):
        """Screen stocks based on Minervini's criteria."""
        # Load stock universe and data (replace with your data source)
        universe = self.get_stock_universe()
        stock_data = {symbol: self.get_historical_data(symbol) for symbol in universe}

        screened_stocks = []
        for symbol, data in stock_data.items():
            if len(data) < 150:
                continue

            data["50SMA"] = talib.SMA(data["close"], timeperiod=50)
            data["150SMA"] = talib.SMA(data["close"], timeperiod=150)
            data["RS"] = data["close"] / data["close"].rolling(window=252).mean()

            if (
                data["RS"].iloc[-1] > 1.8
                and data["close"].iloc[-1] > data["50SMA"].iloc[-1]
                and data["50SMA"].iloc[-1] > data["150SMA"].iloc[-1]
                and data["volume"].iloc[-1] > self.parameters["volume_threshold"]
            ):
                screened_stocks.append(
                    {
                        "symbol": symbol,
                        "momentum": data["RS"].iloc[-1],
                    }
                )

        # Select top N stocks by momentum
        self.top_stocks = sorted(screened_stocks, key=lambda x: x["momentum"], reverse=True)[
            : self.parameters["top_n"]
        ]
        self.screener_ran = True

    def on_trading_iteration(self):
        """Place trades based on entry/exit criteria."""
        if not self.screener_ran:
            return

        capital_per_trade = self.parameters["capital"] * self.parameters["risk_per_trade"]
        for stock in self.top_stocks:
            symbol = stock["symbol"]
            data = self.get_historical_data(symbol)

            if len(data) < 50:
                continue

            # Entry criteria (e.g., breakout above resistance)
            resistance = data["close"].rolling(window=50).max().iloc[-2]
            if data["close"].iloc[-1] > resistance:
                stop_loss = data["close"].iloc[-1] * (1 - self.parameters["stop_loss_pct"])
                take_profit = data["close"].iloc[-1] * (1 + self.parameters["take_profit_pct"])
                quantity = capital_per_trade // data["close"].iloc[-1]

                self.submit_order(
                    symbol=symbol,
                    quantity=quantity,
                    side="buy",
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

    def after_market_closes(self):
        """Clean up or record data after market close."""
        self.screener_ran = False

# Backtesting example
if __name__ == "__main__":
    broker = Alpaca(api_key="your_api_key", api_secret="your_api_secret", paper=True)
    backtest = Backtest(
        strategy=MinerviniBot,
        historical_data_path="path_to_historical_data",
        broker=broker,
        capital=100000,
    )
    backtest.run()