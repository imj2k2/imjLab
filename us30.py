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
        
        # Dynamic Position Sizing
        capital = self.get_cash()
        risk_amount = capital * 0.02  # Risk 2% per trade
        position_size = risk_amount / (2 * atr[-1])
        self.position_size = max(100, min(position_size, 10000))
        
        # Generate Buy/Sell Signal
        if qqe[-1] > 50 and tema[-1] > tema[-2] and cmf[-1] > 0:
            signal = "BUY"
        elif qqe[-1] < 50 and tema[-1] < tema[-2] and cmf[-1] < 0:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        current_price = close_prices[-1]
        position = self.get_position(self.symbol)
        
        # Check Market Conditions
        atr_pct = atr[-1] / close_prices[-1]
        if atr_pct > 0.03:
            return  # Skip trades during high volatility
        
        # Trading Hours Filter
        now = self.get_datetime().time()
        if now < datetime.time(9, 30) or now > datetime.time(16, 0):
            return
        
        # Circuit Breakers
        if self.get_cash() < self.get_starting_cash() * (1 - self.max_total_drawdown):
            self.stop_trading()
        if self.get_daily_pnl() < -self.get_starting_cash() * self.max_daily_loss:
            self.pause_trading()
        
        # Trading Logic
        if signal == "BUY" and not position:
            self.buy(self.symbol, self.position_size)
            self.last_signal = "BUY"
        elif signal == "SELL" and position:
            if position.amount > 0:
                self.sell(self.symbol, position.amount)
            self.short(self.symbol, self.position_size)
            self.last_signal = "SELL"
        
        # Tiered Hedging
        if position and abs(position.unrealized_pl / position.cost_basis) > self.hedge_threshold:
            hedge_size = self.position_size * 0.25
            if abs(position.unrealized_pl / position.cost_basis) > self.hedge_threshold * 1.5:
                hedge_size = self.position_size * 0.5
            if abs(position.unrealized_pl / position.cost_basis) > self.hedge_threshold * 2:
                hedge_size = self.position_size
            
            if position.amount > 0:
                self.short(self.symbol, hedge_size)
            else:
                self.buy(self.symbol, hedge_size)
        
        # Alternative Hedge Assets
        if abs(position.unrealized_pl / position.cost_basis) > self.hedge_threshold * 1.5:
            self.buy("GLD", hedge_size / 2)
            self.buy("TLT", hedge_size / 2)
        
        # Stop Loss
        if position and abs(position.unrealized_pl / position.cost_basis) > self.stop_loss_pct:
            self.sell(self.symbol, position.amount)

# Run Backtest
data = YahooDataBacktesting()
backtest = Trader(US30HedgingStrategy, data, start_date="2023-01-01", end_date="2024-01-01")
backtest.run()

# Deploy Live
broker = Alpaca(API_KEY, API_SECRET, BASE_URL)
live_trader = Trader(US30HedgingStrategy, broker)
live_trader.run()