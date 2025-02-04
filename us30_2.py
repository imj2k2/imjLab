import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from lumibot.strategies.strategy import Strategy
from lumibot.backtesting import BacktestingBroker, YahooDataBacktesting


class US30HedgingStrategy(Strategy):
    def initialize(self):
        self.sleeptime = 86400  # Run daily
        self.symbol = "DIA"
        self.hedge_assets = ["GLD", "TLT", "SPXU"]
        self.max_risk_per_trade = 0.02
        self.stop_loss_threshold = 0.05
        self.max_daily_loss = 0.05
        self.max_total_drawdown = 0.30
        self.daily_loss = 0
        self.initial_portfolio_value = self.portfolio_value
        self.hedge_positions = {asset: 0 for asset in self.hedge_assets}

    def on_trading_iteration(self):
        current_date = self.get_datetime().date()
        if self.first_iteration:
            self.daily_loss = 0
            self.initial_portfolio_value = self.portfolio_value

        # Fetch historical data
        data = self.get_historical_prices(self.symbol, 15, "day")
        if data is None or len(data) < 15:
            return

        # Calculate technical indicators
        data['TEMA'] = self.calculate_tema(data['close'], 9)
        data['RSI'] = self.calculate_rsi(data['close'], 14)
        data['ATR'] = self.calculate_atr(data, 14)

        # Generate signals
        if data['RSI'].iloc[-1] > 50 and data['TEMA'].iloc[-1] > data['TEMA'].iloc[-2]:
            self.log_message(f"[{current_date}] Buying {self.symbol}")
            self.enter_position(self.symbol, "buy")
        elif data['RSI'].iloc[-1] < 50 and data['TEMA'].iloc[-1] < data['TEMA'].iloc[-2]:
            self.log_message(f"[{current_date}] Selling {self.symbol}")
            self.enter_position(self.symbol, "sell")

        # Risk management
        self.manage_risk()

    def enter_position(self, symbol, side):
        position = self.get_position(symbol)
        if position and position.quantity > 0:
            return  # Already in position

        cash = self.get_cash()
        price = self.get_last_price(symbol)
        risk_amount = self.portfolio_value * self.max_risk_per_trade
        quantity = int(risk_amount / price)

        if side == "buy":
            order = self.create_order(symbol, quantity, "buy")
        else:
            order = self.create_order(symbol, quantity, "sell")

        self.submit_order(order)

    def manage_risk(self):
        current_value = self.portfolio_value
        drawdown = (self.initial_portfolio_value - current_value) / self.initial_portfolio_value

        if drawdown >= self.max_total_drawdown:
            self.log_message("Max total drawdown reached. Stopping trading.")
            self.sell_all()
            self.stop()
            return

        if self.daily_loss >= self.max_daily_loss * self.initial_portfolio_value:
            self.log_message("Max daily loss reached. Stopping trading.")
            self.sell_all()
            self.stop()
            return

        position = self.get_position(self.symbol)
        if position:
            unrealized_loss = position.unrealized_pl / self.portfolio_value
            if unrealized_loss >= self.stop_loss_threshold:
                self.log_message("Stop loss triggered. Exiting position.")
                self.sell_all()
            else:
                self.hedge_position(unrealized_loss)

    def hedge_position(self, unrealized_loss):
        if unrealized_loss >= 0.04:
            hedge_ratio = 1.0
        elif unrealized_loss >= 0.03:
            hedge_ratio = 0.5
        elif unrealized_loss >= 0.02:
            hedge_ratio = 0.25
        else:
            hedge_ratio = 0.0

        for asset in self.hedge_assets:
            target_quantity = int(self.get_position(self.symbol).quantity * hedge_ratio)
            current_quantity = self.get_position(asset).quantity if self.get_position(asset) else 0
            if target_quantity > current_quantity:
                self.log_message(f"Hedging with {asset}")
                order = self.create_order(asset, target_quantity - current_quantity, "buy")
                self.submit_order(order)
            elif target_quantity < current_quantity:
                order = self.create_order(asset, current_quantity - target_quantity, "sell")
                self.submit_order(order)

    def calculate_tema(self, series, period):
        ema1 = series.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        return 3 * (ema1 - ema2) + ema3

    def calculate_rsi(self, series, period):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, data, period):
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean()

if __name__ == "__main__":
    backtesting_start = datetime(2023, 1, 1)
    backtesting_end = datetime(2023, 12, 31)

    US30HedgingStrategy.backtest(
        YahooDataBacktesting,
        backtesting_start,
        backtesting_end,
        #initial_cash=100000,
        #generate_tearsheet=True
    )
