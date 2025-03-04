from lumibot.strategies import Strategy
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.traders import Trader
import pandas as pd
from algo_trading_indicators import TradingIndicators  # Import our indicator library

# Alpaca API (Replace with your credentials)
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
BASE_URL = "https://paper-api.alpaca.markets"

class MovingAverageStrategy(Strategy):
    def initialize(self):
        self.symbol = "AAPL"
        self.short_window = 50
        self.long_window = 200
        self.position_size = 10  # Number of shares
        self.sleeptime = "1d"  # Run daily
        self.indicators = TradingIndicators()  # Use our indicator class
    
    def on_trading_iteration(self):
        # Get historical price data
        data = self.get_historical_prices(self.symbol, 250, "day")  # Fetch last 250 days
        
        # Ensure sufficient data points
        if len(data) < self.long_window:
            return
        
        # Calculate Moving Averages
        short_ma = self.indicators.moving_average(data["close"], self.short_window)
        long_ma = self.indicators.moving_average(data["close"], self.long_window)
        
        # Trading logic - Golden Cross (Buy) & Death Cross (Sell)
        if short_ma.iloc[-1] > long_ma.iloc[-1] and not self.has_position(self.symbol):
            self.buy(self.symbol, quantity=self.position_size)
        elif short_ma.iloc[-1] < long_ma.iloc[-1] and self.has_position(self.symbol):
            self.sell(self.symbol, quantity=self.position_size)

# Backtest the strategy
backtesting = YahooDataBacktesting()
strategy = MovingAverageStrategy(name="MA_Crossover", broker=backtesting)
strategy.backtest(start_date="2020-01-01", end_date="2024-01-01")
