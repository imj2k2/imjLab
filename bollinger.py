import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
import schedule
import time
from datetime import datetime, timedelta
import os

# Alpaca API credentials
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'
BASE_URL = 'https://paper-api.alpaca.markets'

# Initialize Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Parameters
SYMBOLS = ['AAPL', 'MSFT', 'GOOGL']  # List of stock symbols
RISK_PER_TRADE = 0.01  # Risk 1% per trade
ATR_PERIOD = 14
SUPER_TREND_MULTIPLIER = 3
RSI_PERIOD = 14
BB_PERIOD = 20
BB_MULTIPLIER = 2
MIN_VOLUME = 1000000

# Backtesting parameters
START_DATE = '2023-06-01'
END_DATE = '2024-06-01'
INITIAL_CAPITAL = 100000

# Fetch historical data
def fetch_data(symbol, timeframe='day', start=None, end=None):
    file_path = f"data/{symbol}_{timeframe}_{start}_{en}.csv"
    if os.path.exists(file_path):
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    else:
        bars = api.get_bars(symbol, timeframe, start=start, end=end).df
        bars.to_csv(file_path)
        data = bars
    return data

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

def calculate_position_size(capital, atr, price):
    risk_amount = capital * RISK_PER_TRADE
    stop_loss = atr
    position_size = risk_amount / stop_loss
    return position_size

def backtest(data):
    capital = INITIAL_CAPITAL
    position = 0
    trades = []

    for i in range(1, len(data)):
        current_price = data['close'].iloc[i]
        atr = data['atr'].iloc[i]
        buy_signal, sell_signal = check_signals(data.iloc[:i+1])

        if buy_signal and position == 0:
            position_size = calculate_position_size(capital, atr, current_price)
            position = position_size * current_price
            capital -= position
            trades.append({
                'date': data.index[i],
                'type': 'buy',
                'price': current_price,
                'size': position_size
            })

        elif sell_signal and position > 0:
            capital += position
            position = 0
            trades.append({
                'date': data.index[i],
                'type': 'sell',
                'price': current_price
            })

    final_value = capital + position
    return trades, final_value

def run_backtest():
    for symbol in SYMBOLS:
        print(f"Running backtest for {symbol}...")
        data = fetch_data(symbol, start=START_DATE, end=END_DATE)
        data = calculate_indicators(data)

        trades, final_value = backtest(data)

        print(f"Final Portfolio Value for {symbol}: ${final_value:.2f}")
        print("Trade History:")
        for trade in trades:
            print(trade)

def scheduled_backtest():
    print("Scheduled backtest is running...")
    run_backtest()

if __name__ == "__main__":
    while True:
        print("\nSelect an option:")
        print("1. Run Backtest")
        print("2. Start Live Trading")
        print("3. Exit")
        choice = input("Enter your choice: ")

        if choice == "1":
            run_backtest()
        elif choice == "2":
            print("Starting live trading (not implemented in this script)...")
            # Placeholder for live trading functionality
        elif choice == "3":
            print("Exiting program.")
            break
        else:
            print("Invalid choice. Please select a valid option.")

    # Optionally, enable scheduling
    schedule.every().day.at("00:00").do(scheduled_backtest)  # Run daily backtests
    print("Scheduler started. Running scheduled tasks...")
    while True:
        schedule.run_pending()
        time.sleep(1)
