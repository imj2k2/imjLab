from lumibot.strategies.strategy import Strategy
from lumibot.backtesting import YahooDataBacktesting
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

class EhlersStochasticStrategy(Strategy):
    
    def initialize(self, 
                   length=20, 
                   cutoff_length=10, 
                   overbought=0.8, 
                   oversold=0.2):
        self.length = length
        self.cutoff_length = cutoff_length
        self.overbought = overbought
        self.oversold = oversold
        self.symbol = "AAPL"  # Change to your preferred asset
        self.sleeptime = "1d"  # Run strategy once per day
    
    def EhlersStochastic(self, data):
        close = data['close']
        smoothed = close.ewm(span=self.cutoff_length).mean()
        min_val = smoothed.rolling(self.length).min()
        max_val = smoothed.rolling(self.length).max()
        
        ehlers_stoch = (smoothed - min_val) / (max_val - min_val)
        return ehlers_stoch
    
    def on_trading_iteration(self):
        # Fetch historical data
        hist_data = self.get_historical_prices(self.symbol, lookback=self.length * 2)
        df = pd.DataFrame(hist_data)
        
        # Ensure we have enough data
        if len(df) < self.length:
            return
        
        # Compute Ehlers Stochastic
        df['Ehlers_Stoch'] = self.EhlersStochastic(df)
        latest_value = df['Ehlers_Stoch'].iloc[-1]
        
        # Check Buy Signal
        if latest_value < self.oversold and not self.has_position(self.symbol):
            self.market_order(self.symbol, 10, "buy")  # Buy 10 shares
        
        # Check Sell Signal
        elif latest_value > self.overbought and self.has_position(self.symbol):
            self.market_order(self.symbol, 10, "sell")  # Sell 10 shares
        
# Run Backtest
start = datetime(2020, 1, 1)
end = datetime(2023, 1, 1)

strategy = EhlersStochasticStrategy()
data_source = YahooDataBacktesting()
strategy.backtest(data_source, start, end, initial_cash=10000)
