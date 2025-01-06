import pandas as pd
import talib
import yfinance as yf
from lumibot.strategies import Strategy
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from lumibot.backtest import Backtest
from datetime import datetime, timedelta
import os

class MinerviniBot(Strategy):
    parameters = {
        "capital": 100000,
        "risk_per_trade": 0.01,
        "volume_threshold": 1000000,
        "top_n": 10,
        "trailing_stop_loss_pct": 0.05,
        "notification_email": "your_email@example.com",
    }

    def initialize(self):
        self.screener_ran = False
        self.positions = {}
        self.data_file = "screened_stocks.csv"

    def before_market_opens(self):
        """Run the stock screener before the market opens."""
        if not self.screener_ran:
            self.screen_stocks()

    def screen_stocks(self):
        """Screen stocks based on Minervini's criteria."""
        if os.path.exists(self.data_file):
            last_modified_time = datetime.fromtimestamp(os.path.getmtime(self.data_file))
            if datetime.now() - last_modified_time < timedelta(days=1):
                self.top_stocks = pd.read_csv(self.data_file).to_dict("records")
                self.screener_ran = True
                return

        universe = self.get_stock_universe()
        screened_stocks = []
        for symbol in universe:
            try:
                data = yf.download(symbol, period="1y", interval="1d")
                data["50SMA"] = talib.SMA(data["Close"], timeperiod=50)
                data["150SMA"] = talib.SMA(data["Close"], timeperiod=150)
                data["RS"] = data["Close"] / data["Close"].rolling(window=252).mean()

                if (
                    data["RS"].iloc[-1] > 1.8
                    and data["Close"].iloc[-1] > data["50SMA"].iloc[-1]
                    and data["50SMA"].iloc[-1] > data["150SMA"].iloc[-1]
                    and data["Volume"].iloc[-1] > self.parameters["volume_threshold"]
                ):
                    screened_stocks.append(
                        {
                            "symbol": symbol,
                            "momentum": data["RS"].iloc[-1],
                        }
                    )
            except Exception as e:
                self.log(f"Error screening {symbol}: {e}")

        self.top_stocks = sorted(screened_stocks, key=lambda x: x["momentum"], reverse=True)[
            : self.parameters["top_n"]
        ]
        pd.DataFrame(self.top_stocks).to_csv(self.data_file, index=False)
        self.screener_ran = True

    def get_market_sentiment(self):
        """Analyze market sentiment using the VIX index and put/call ratio."""
        try:
            vix_data = yf.download("^VIX", period="1mo", interval="1d")
            vix_level = vix_data["Close"].iloc[-1]

            pcr_data = yf.download("PCCE", period="1mo", interval="1d")  # CBOE Equity Put/Call Ratio
            pcr_level = pcr_data["Close"].iloc[-1]

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

    def on_trading_iteration(self):
        """Place trades based on entry/exit criteria and market sentiment."""
        if not self.screener_ran:
            return

        sentiment = self.get_market_sentiment()
        if sentiment == "Bearish":
            self.log("Market sentiment is bearish. No trades will be executed.")
            return

        capital_per_trade = self.parameters["capital"] * self.parameters["risk_per_trade"]
        for stock in self.top_stocks:
            symbol = stock["symbol"]
            data = yf.download(symbol, period="3mo", interval="1d")

            if len(data) < 50:
                continue

            resistance = data["Close"].rolling(window=50).max().iloc[-2]
            if data["Close"].iloc[-1] > resistance:
                trailing_stop_loss = data["Close"].iloc[-1] * (1 - self.parameters["trailing_stop_loss_pct"])
                quantity = int(capital_per_trade // data["Close"].iloc[-1])

                self.submit_order(
                    symbol=symbol,
                    quantity=quantity,
                    side="buy",
                    trailing_stop_loss=trailing_stop_loss,
                )

                self.notify(f"Bought {quantity} shares of {symbol} at {data['Close'].iloc[-1]} with trailing stop loss.")

    def after_market_closes(self):
        """Send a daily summary of positions and P/L."""
        position_summary = self.get_open_positions()
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
            self.positions = self.broker.get_positions()
            self.log(f"Resumed from positions: {self.positions}")
        except Exception as e:
            self.log(f"Error resuming positions: {e}")

    def get_stock_universe(self):
        """Define your stock universe here."""
        return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]  # Example stocks

# Backtesting example
if __name__ == "__main__":
    broker = Alpaca(api_key="your_api_key", api_secret="your_api_secret", paper=True)
    strategy = MinerviniBot(broker=broker)

    # Run live
    trader = Trader(broker=broker, strategy=strategy)
    trader.run()

    # Backtesting
    backtest = Backtest(
        strategy=MinerviniBot,
        historical_data_path="path_to_historical_data",
        broker=broker,
        capital=100000,
    )
    backtest.run()