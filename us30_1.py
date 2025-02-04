from lumibot.strategies.strategy import Strategy
from lumibot.backtesting import YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.traders import Trader
from datetime import datetime, timedelta
import talib
import numpy as np
import pandas as pd
import datetime

# Alpaca API Keys (replace with your own)
API_KEY = "your_alpaca_api_key"
API_SECRET = "your_alpaca_api_secret"
BASE_URL = "https://paper-api.alpaca.markets"

class US30HedgingStrategy(Strategy):
    def initialize(self):
        self.symbol = "DIA"  # ETF equivalent for US30 on Alpaca
        self.stop_loss_pct = 0.05  # 5% SL safeguard
        self.hedge_threshold = 0.02  # 2% adverse move triggers hedge
        self.trailing_stop = 0.01  # 1% trailing stop
        self.last_signal = None  # Track last signal
        self.data_window = 50  # Data window for indicators
        self.max_daily_loss = 0.05  # 5% daily loss limit
        self.max_total_drawdown = 0.3  # 30% total drawdown limit

    def on_trading_iteration(self):
        data = self.get_historical_prices(self.symbol, self.data_window, "day")
        close_prices = data["close"].values
        
        if len(close_prices) < self.data_window:
            return  # Ensure enough data
        
        # Compute Indicators
        atr = talib.ATR(data["high"], data["low"], data["close"], timeperiod=14)
        qqe = talib.RSI(close_prices, timeperiod=14)
        tema = talib.TEMA(close_prices, timeperiod=9)
        cmf = (2 * data["close"] - data["high"] - data["low"]) / (data["high"] - data["low"])
        
        # Determine Market Cycle
        if qqe[-1] > 50 and tema[-1] > tema[-2]:
            market_cycle = "Markup"
        elif qqe[-1] < 50 and tema[-1] < tema[-2]:
            market_cycle = "Markdown"
        else:
            market_cycle = "Sideways"
        
        # Adaptive Hedging Based on ATR & Market Cycle
        volatility_factor = atr[-1] / close_prices[-1]  # ATR % of price
        hedge_multiplier = 1.0  # Default hedge size
        
        if volatility_factor > 0.03 or market_cycle == "Markdown":
            hedge_multiplier = 1.5  # More aggressive hedge
        elif volatility_factor < 0.02 and market_cycle == "Markup":
            hedge_multiplier = 0.5  # Reduce hedge size
        
        hedge_size = self.position_size * hedge_multiplier
        
        # Check Alternative Hedge Assets
        gld_data = self.get_historical_prices("GLD", self.data_window, "day")
        tlt_data = self.get_historical_prices("TLT", self.data_window, "day")
        gld_trend = talib.TEMA(gld_data["close"], timeperiod=9)
        tlt_trend = talib.TEMA(tlt_data["close"], timeperiod=9)
        
        if gld_trend[-1] > gld_trend[-2]:  
            self.buy("GLD", hedge_size / 2)  
        if tlt_trend[-1] > tlt_trend[-2]:  
            self.buy("TLT", hedge_size / 2)
        
        # If GLD/TLT are not trending up, use Inverse ETFs (SH, DOG)
        if gld_trend[-1] < gld_trend[-2] and tlt_trend[-1] < tlt_trend[-2]:  
            self.buy("SH", hedge_size / 2)  # S&P 500 inverse ETF  
            self.buy("DOG", hedge_size / 2)  # Dow 30 inverse ETF  
        
        # Trailing Hedge Take-Profit
        hedge_position = self.get_position(self.symbol)
        
        if hedge_position and hedge_position.unrealized_pl / hedge_position.cost_basis > 0.03:
            self.sell(self.symbol, hedge_position.amount / 2)  # Take partial profits
        if hedge_position and hedge_position.unrealized_pl / hedge_position.cost_basis > 0.05:
            self.sell(self.symbol, hedge_position.amount)  # Close full hedge

# Run Backtest
data = YahooDataBacktesting()
backtest = Trader(US30HedgingStrategy, data, start_date="2023-01-01", end_date="2024-01-01")
backtest.run()

# Deploy Live
broker = Alpaca(API_KEY, API_SECRET, BASE_URL)
live_trader = Trader(US30HedgingStrategy, broker)
live_trader.run()
