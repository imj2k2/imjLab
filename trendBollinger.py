import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Alpaca API credentials
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'
BASE_URL = 'https://paper-api.alpaca.markets'

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Parameters
SYMBOL = 'BTC/USD'  # Trading pair
RISK_PER_TRADE = 0.01  # Risk 1% per trade
ATR_PERIOD = 14
SUPER_TREND_MULTIPLIER = 3
RSI_PERIOD = 14
BB_PERIOD = 20
BB_MULTIPLIER = 2
MIN_VOLUME = 1000000

def fetch_data(symbol, timeframe='1D', limit=100):
    bars = api.get_crypto_bars(symbol, timeframe).limit(limit).df
    return bars

def calculate_indicators(df):
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(ATR_PERIOD).mean()

    # Supertrend
    df['basic_upper'] = (df['high'] + df['low']) / 2 + SUPER_TREND_MULTIPLIER * df['atr']
    df['basic_lower'] = (df['high'] + df['low']) / 2 - SUPER_TREND_MULTIPLIER * df['atr']
    df['final_upper'] = df['basic_upper']
    df['final_lower'] = df['basic_lower']

    for i in range(1, len(df)):
        if df['close'][i-1] > df['final_upper'][i-1]:
            df.loc[i, 'final_upper'] = max(df['basic_upper'][i], df['final_upper'][i-1])
        if df['close'][i-1] < df['final_lower'][i-1]:
            df.loc[i, 'final_lower'] = min(df['basic_lower'][i], df['final_lower'][i-1])

    df['supertrend'] = np.where(df['close'] > df['final_lower'], 1, -1)

    # RSI
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(RSI_PERIOD).mean()
    avg_loss = pd.Series(loss).rolling(RSI_PERIOD).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(BB_PERIOD).mean()
    df['bb_upper'] = df['bb_middle'] + BB_MULTIPLIER * df['close'].rolling(BB_PERIOD).std()
    df['bb_lower'] = df['bb_middle'] - BB_MULTIPLIER * df['close'].rolling(BB_PERIOD).std()

    return df

def check_signals(df):
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    buy_signal = (
        last_row['supertrend'] == 1 and
        prev_row['supertrend'] == -1 and
        last_row['rsi'] < 30 and
        last_row['close'] < last_row['bb_lower']
    )

    sell_signal = (
        last_row['supertrend'] == -1 and
        prev_row['supertrend'] == 1 and
        last_row['rsi'] > 70 and
        last_row['close'] > last_row['bb_upper']
    )

    return buy_signal, sell_signal

def calculate_position_size(account, atr, price):
    risk_amount = account.cash * RISK_PER_TRADE
    stop_loss = atr
    position_size = risk_amount / stop_loss
    return min(position_size, account.cash / price)

def execute_trade(signal, symbol, atr, price):
    account = api.get_account()
    position_size = calculate_position_size(account, atr, price)

    if signal == 'buy':
        api.submit_order(
            symbol=symbol,
            qty=position_size,
            side='buy',
            type='market',
            time_in_force='gtc'
        )
    elif signal == 'sell':
        api.submit_order(
            symbol=symbol,
            qty=position_size,
            side='sell',
            type='market',
            time_in_force='gtc'
        )

def run_bot():
    data = fetch_data(SYMBOL)
    data = calculate_indicators(data)

    buy_signal, sell_signal = check_signals(data)

    if buy_signal:
        execute_trade('buy', SYMBOL, data['atr'].iloc[-1], data['close'].iloc[-1])
    elif sell_signal:
        execute_trade('sell', SYMBOL, data['atr'].iloc[-1], data['close'].iloc[-1])

# Run the bot continuously
while True:
    try:
        run_bot()
        time.sleep(60)  # Wait for a minute before checking again
    except Exception as e:
        print(f"Error: {e}")
