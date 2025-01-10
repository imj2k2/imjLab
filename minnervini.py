import pandas as pd
import talib
import yfinance as yf
from lumibot.strategies import Strategy
from lumibot.traders import Trader
from lumibot.brokers import Alpaca
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting
from datetime import datetime, timedelta
import os
import time

ALPACA_CONFIG = {
    # Put your own Alpaca key here:
    "API_KEY": "",
    # Put your own Alpaca secret here:
    "API_SECRET": "",
    # If you want to go live, you must change this
    "ALPACA_IS_PAPER": "True",
}


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
                data = yf.download(symbol, period="1y", interval="1d")
                if not data.empty:
                    return data
            except Exception as e:
                self.log(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            time.sleep(delay)
        self.log(f"Failed to fetch data for {symbol} after {retries} retries.")
        return None

    def screen_stocks(self):
        """Screen stocks based on Minervini's criteria."""
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
                #data = yf.download(symbol, period="1y", interval="1d")
                data = self.fetch_data_with_retries(symbol)
                # Check for valid data
                if data.empty or "Close" not in data.columns or data["Close"].isnull().all():
                    self.log(f"Data for {symbol} is invalid or missing. Skipping.")
                    continue

                data = data.dropna(subset=["Close"])  # Ensure no NaN values
                close_prices = data["Close"].values  
                data["50SMA"] = talib.SMA(close_prices, timeperiod=50)
                data["150SMA"] = talib.SMA(close_prices, timeperiod=150)
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
            # Fetch VIX data
            vix_data = yf.download("^VIX", period="1mo", interval="1d")
            if vix_data.empty or "Close" not in vix_data.columns:
                self.log("VIX data is invalid or missing.")
                return "Neutral"
            vix_level = vix_data["Close"].iloc[-1]

            # Fetch Put/Call Ratio data
            pcr_data = yf.download("PCCE", period="1mo", interval="1d")  # CBOE Equity Put/Call Ratio
            if pcr_data.empty or "Close" not in pcr_data.columns:
                self.log("Put/Call Ratio data is invalid or missing.")
                return "Neutral"
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
        atr = talib.ATR(stock_data["High"], stock_data["Low"], stock_data["Close"], timeperiod=14).iloc[-1]
        position_size = capital_per_trade / atr
        return position_size

    def on_trading_iteration(self):
        """Place trades based on entry/exit criteria and market sentiment."""
        if not self.screener_ran:
            return

        sentiment = self.get_market_sentiment()
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
                continue

            resistance = data["Close"].rolling(window=50).max().iloc[-2]
            if data["Close"].iloc[-1] > resistance:
                position_size = self.calculate_position_size(data, capital_per_trade)
                total_cost = position_size * data["Close"].iloc[-1]

                if total_cost + total_allocated_capital > available_capital:
                    break

                trailing_stop_loss = data["Close"].iloc[-1] * (1 - self.parameters["trailing_stop_loss_pct"])
                quantity = int(position_size)

                self.submit_order(
                    symbol=symbol,
                    quantity=quantity,
                    side="buy",
                    trailing_stop_loss=trailing_stop_loss,
                )

                total_allocated_capital += total_cost

                self.notify(f"Bought {quantity} shares of {symbol} at {data['Close'].iloc[-1]} with trailing stop loss.")

    def after_market_closes(self):
        """Send a daily summary of positions and P/L."""
        position_summary = self.get_positions()
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
        return ["AMZN","AVGO","CRM","AMD","DHR","PGR","APH","REGN","AMH","ARKG","AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]  # Example stocks

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
