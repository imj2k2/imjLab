from lumibot.strategies.strategy import Strategy
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting
from lumibot.brokers import Alpaca
from lumibot.traders import Trader
from datetime import datetime, timedelta
import talib
import numpy as np
import pandas as pd
import datetime
import configparser

# Alpaca API Keys (replace with your own)
config = configparser.ConfigParser()
config.read(".env_test")

ALPACA_CONFIG = {
    "API_KEY": config["ALPACA"]["ALPACA_API_KEY"],
    "API_SECRET": config["ALPACA"]["ALPACA_SECRET_KEY"],
    "ALPACA_IS_PAPER": "True",
}

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
        self.starting_cash = self.get_cash()  # Initial cash
        self.hedge_assets = ["GLD", "TLT", "SPXU"]  # Diversified hedging assets
    
    def log(self, message):
        """Log messages to the console."""
        print(f"[{self.get_datetime()}] {message}")

    def order(self, symbol, amount, side):
        """Place an order with the broker."""
        if amount == 0:
            return
        order = self.create_order(
                    asset=symbol,
                    quantity=amount,
                    side="side",
                    type="market",
                    time_in_force="day",
                    trail_percent=10
                )
        self.submit_order(order)
    
    def on_trading_iteration(self):
        data = self.get_historical_prices(self.symbol, self.data_window, "day").df
        
        if len(data) < self.data_window:
            return  # Ensure enough data
        
        # Compute Indicators
        atr = talib.ATR(data["high"], data["low"], data["close"], timeperiod=14).dropna()
        rsi = talib.RSI(data["close"], timeperiod=14).dropna()
        tema = talib.TEMA(data["close"], timeperiod=9).dropna()
        
        if atr.empty or rsi.empty or tema.empty:
            return  # Ensure indicators are available
        
        current_price = data["close"].iloc[-1]
        position = self.get_position(self.symbol)
        
        # Generate Buy/Sell Signal
        if rsi.iloc[-1] > 50 and tema.iloc[-1] > tema.iloc[-2]:
            signal = "BUY"
        elif rsi.iloc[-1] < 50 and tema.iloc[-1] < tema.iloc[-2]:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # Risk Management & Position Sizing
        capital = self.get_portfolio_value()
        risk_amount = capital * 0.02  # Risk 2% per trade
        position_size = max(100, min(risk_amount / (2 * atr.iloc[-1]), 10000))
        
        # Avoid trading during high volatility
        if atr.iloc[-1] / current_price > 0.03:
            self.log("High volatility detected. Skipping trade.")
            return
        
        # Circuit Breakers
        if self.get_cash() < self.starting_cash * (1 - self.max_total_drawdown):
            self.log("Max drawdown reached. Stopping trading.")
            self.stop_trading()
            return
        if self.get_portfolio_value() - self.starting_cash < -self.starting_cash * self.max_daily_loss:
            self.log("Max daily loss reached. Stopping trading.")
            self.stop_trading()
            return
        
        # Trading Logic
        if signal == "BUY" and (position is None or position.amount <= 0):
            self.order(self.symbol, position_size, side="buy")
            self.last_signal = "BUY"
            self.log(f"Buying {position_size} shares of {self.symbol}")
        elif signal == "SELL" and (position is not None and position.amount > 0):
            self.order(self.symbol, -position.amount, side="sell")  # Corrected
            self.order(self.symbol, -position_size, side="sell")
            self.last_signal = "SELL"
            self.log(f"Selling {position.amount} shares and shorting {position_size} shares of {self.symbol}")
        
        # Hedging Strategy
        if position and abs(position.unrealized_pl / max(position.cost_basis, 1e-6)) > self.hedge_threshold:
            hedge_size = position_size * 0.25
            if abs(position.unrealized_pl / max(position.cost_basis, 1e-6)) > self.hedge_threshold * 1.5:
                hedge_size = position_size * 0.5
            if abs(position.unrealized_pl / max(position.cost_basis, 1e-6)) > self.hedge_threshold * 2:
                hedge_size = position_size
            
            hedge_asset = np.random.choice(self.hedge_assets)  # Randomize hedge asset
            self.order(hedge_asset, hedge_size / 2, side="buy")
            #self.buy(hedge_asset, hedge_size / 2)
            self.log(f"Hedging with {hedge_size / 2} shares of {hedge_asset}")
        
        # Stop Loss Handling
        if position and abs(position.unrealized_pl / max(position.cost_basis, 1e-6)) > self.stop_loss_pct:
            self.order(self.symbol, -position.amount, side="sell")
            self.log(f"Stop loss triggered. Selling {position.amount} shares of {self.symbol}")

# Backtest Configuration
datetime_start = datetime.datetime(2023, 1, 1)
datetime_end = datetime.datetime(2023, 12, 31)

backtest = US30HedgingStrategy.run_backtest(YahooDataBacktesting, datetime_start, datetime_end)

# Live Deployment
# broker = Alpaca(ALPACA_CONFIG)
# live_trader = Trader(US30HedgingStrategy, broker)
# live_trader.run()
