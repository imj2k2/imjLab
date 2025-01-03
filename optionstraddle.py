import alpaca_trade_api as tradeapi
import pandas as pd
import time
import datetime

# Alpaca API credentials
API_KEY = 'your_api_key'
API_SECRET = 'your_api_secret'
BASE_URL = 'https://paper-api.alpaca.markets'  # Paper trading URL

# Initialize the Alpaca API
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# Strategy parameters
symbol = 'SPY'  # ETF representing S&P 500
momentum_threshold = 0.01  # 1% price change in the first minute to determine momentum
qty_call = 2  # Number of calls to buy when momentum is upwards
qty_put = 1   # Number of puts to buy when momentum is upwards

# Function to fetch historical data (1-minute bars)
def get_historical_data(symbol, timeframe='minute', limit=10):
    barset = api.get_barset(symbol, timeframe, limit=limit)
    data = barset[symbol]
    df = pd.DataFrame({
        'time': [bar.t for bar in data],
        'open': [bar.o for bar in data],
        'high': [bar.h for bar in data],
        'low': [bar.l for bar in data],
        'close': [bar.c for bar in data],
        'volume': [bar.v for bar in data],
    })
    df.set_index('time', inplace=True)
    return df

# Function to calculate momentum
def calculate_momentum(df):
    # Calculate price change between the first and last minute
    initial_price = df['close'].iloc[0]
    final_price = df['close'].iloc[-1]
    momentum = (final_price - initial_price) / initial_price
    return momentum

# Function to place a simulated order
def place_order(symbol, qty, side, order_type='market'):
    try:
        if side == 'buy':
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force='gtc'
            )
            print(f"Bought {qty} shares of {symbol}")
        elif side == 'sell':
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force='gtc'
            )
            print(f"Sold {qty} shares of {symbol}")
    except Exception as e:
        print(f"Error placing order: {e}")

# Main trading logic
def execute_strategy():
    # Wait for market open (9:30 AM)
    market_open_time = datetime.time(9, 30)
    current_time = datetime.datetime.now().time()

    while current_time < market_open_time:
        time.sleep(10)  # Check every 10 seconds

    # Fetch the first 10 minutes of data (or adjust to your strategy's requirements)
    df = get_historical_data(symbol, timeframe='minute', limit=10)

    # Calculate the momentum of the stock from the first minute to the 10th minute
    momentum = calculate_momentum(df)
    print(f"Momentum: {momentum:.4f}")

    # Determine whether to go long or short based on momentum
    if momentum > momentum_threshold:  # Bullish momentum
        print("Momentum is upwards. Buying 2 calls and 1 put.")
        # Place orders for the strategy (example, using stocks to simulate options)
        place_order(symbol, qty=qty_call, side='buy')  # Simulating 2 calls
        place_order(symbol, qty=qty_put, side='buy')   # Simulating 1 put
    elif momentum < -momentum_threshold:  # Bearish momentum
        print("Momentum is downwards. Buying 1 call and 2 puts.")
        place_order(symbol, qty=1, side='buy')  # Simulating 1 call
        place_order(symbol, qty=2, side='buy')  # Simulating 2 puts

    # Wait for the next checkpoint (10:30 AM)
    time.sleep(60 * 60)  # Sleep for an hour (until 10:30 AM)

    # At 10:30 AM, take profits or adjust positions as necessary
    # This logic can be further expanded to check for profits and sell positions
    # For now, let's simulate taking profits
    print("Taking profits on one position...")
    place_order(symbol, qty=1, side='sell')  # Sell one of the positions (this can be refined)

# Main loop to start the strategy
if __name__ == "__main__":
    execute_strategy()
