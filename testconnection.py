import os
from alpaca.trading.client import TradingClient

# paper=True enables paper trading
trading_client = TradingClient('api-key', 'secret-key', paper=True)
config = configparser.ConfigParser()
config.read("creds.cfg")

os.environ["KEY_ID"] = config["alpaca"]["KEY_ID"]
os.environ["SECRET_KEY"] = config["alpaca"]["SECRET_KEY"]
os.environ["client"] = config["slack"]["client"]
BASE_URL = config["alpaca"]["BASE_URL"]
