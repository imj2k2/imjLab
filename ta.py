import numpy as np
import pandas as pd

class TradingIndicators:
    
    @staticmethod
    def moving_average(data, window):
        return data.rolling(window=window).mean()
    
    @staticmethod
    def exponential_moving_average(data, window):
        return data.ewm(span=window, adjust=False).mean()
    
    @staticmethod
    def macd(data, short_window=12, long_window=26, signal_window=9):
        short_ema = TradingIndicators.exponential_moving_average(data, short_window)
        long_ema = TradingIndicators.exponential_moving_average(data, long_window)
        macd_line = short_ema - long_ema
        signal_line = TradingIndicators.exponential_moving_average(macd_line, signal_window)
        return macd_line, signal_line
    
    @staticmethod
    def rsi(data, window=14):
        delta = data.diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def bollinger_bands(data, window=20, num_std=2):
        sma = TradingIndicators.moving_average(data, window)
        std = data.rolling(window=window).std()
        upper_band = sma + (num_std * std)
        lower_band = sma - (num_std * std)
        return upper_band, lower_band
    
    @staticmethod
    def atr(high, low, close, window=14):
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=window).mean()
    
    @staticmethod
    def obv(close, volume):
        obv = volume.copy()
        obv[1:] = np.where(close[1:] > close[:-1], volume[1:],
                           np.where(close[1:] < close[:-1], -volume[1:], 0))
        return obv.cumsum()
    
    @staticmethod
    def adx(high, low, close, window=14):
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        atr = TradingIndicators.atr(high, low, close, window)
        plus_di = (100 * (plus_dm.ewm(alpha=1/window).mean() / atr)).fillna(0)
        minus_di = (100 * (-minus_dm.ewm(alpha=1/window).mean() / atr)).fillna(0)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        return dx.ewm(alpha=1/window).mean()
    
    @staticmethod
    def stochastic_oscillator(close, low, high, window=14):
        lowest_low = low.rolling(window=window).min()
        highest_high = high.rolling(window=window).max()
        return 100 * ((close - lowest_low) / (highest_high - lowest_low))
    
    @staticmethod
    def fib_retracement(high, low, levels=[0.236, 0.382, 0.5, 0.618, 0.786]):
        retracements = {}
        for level in levels:
            retracements[f"{int(level*100)}%"] = high - (high - low) * level
        return retracements
    
    @staticmethod
    def donchian_channel(high, low, window=20):
        upper_band = high.rolling(window=window).max()
        lower_band = low.rolling(window=window).min()
        return upper_band, lower_band
