import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Step 1: Fetch Form 13F filings from SEC

def fetch_form_13f_filings():
    """
    Fetch recent Form 13F filings from SEC and return parsed data.
    """
    sec_api_key = "YOUR_SEC_API_KEY"  # Replace with your SEC API key
    base_url = "https://sec-api.com/api/v1/filings"
    params = {
        "token": sec_api_key,
        "formType": "13F-HR",
        "pageSize": 50
    }
    response = requests.get(base_url, params=params)
    filings = response.json()

    # Extract the CIK and report URLs
    data = []
    for filing in filings.get("filings", []):
        cik = filing.get("cik")
        report_url = filing.get("filingUrl")
        data.append({"CIK": cik, "Filing URL": report_url})
    return pd.DataFrame(data)

# Step 2: Identify the top 50 stocks from Form 13F filings

def parse_form_13f_holdings(filing_urls):
    """
    Parse holdings data from the provided Form 13F filing URLs.
    """
    stock_counts = {}

    for url in filing_urls:
        try:
            filing_data = requests.get(url).text
            holdings = extract_holdings_from_13f(filing_data)

            for stock in holdings:
                stock_counts[stock] = stock_counts.get(stock, 0) + 1
        except Exception as e:
            print(f"Error processing {url}: {e}")

    # Sort stocks by occurrence
    sorted_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)
    return [stock for stock, count in sorted_stocks[:50]]


def extract_holdings_from_13f(filing_data):
    """
    Extract stock tickers from Form 13F filing data.
    """
    # Simplified logic: Extract tickers using regular expressions or similar methods.
    # In practice, you would parse XML or HTML structures.
    holdings = []
    lines = filing_data.splitlines()
    for line in lines:
        if "CUSIP" in line:
            # Example of extracting stock information from CUSIP lines
            parts = line.split()
            holdings.append(parts[-1])  # Example placeholder logic
    return holdings

# Step 3: Fetch historical stock prices from Yahoo Finance

def fetch_historical_prices(tickers, start_date, end_date):
    """
    Fetch historical stock prices for a list of tickers using Yahoo Finance.
    """
    historical_data = {}

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date)
            historical_data[ticker] = data
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")

    return historical_data

# Step 4: Prepare data for LumiBot

def prepare_lumibot_data(historical_data):
    """
    Prepare historical stock data in a format compatible with LumiBot.
    """
    combined_data = pd.DataFrame()

    for ticker, data in historical_data.items():
        data = data.reset_index()
        data["Ticker"] = ticker
        combined_data = pd.concat([combined_data, data], axis=0)

    combined_data = combined_data.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume"
    })

    combined_data = combined_data[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]]
    combined_data["date"] = pd.to_datetime(combined_data["date"])

    return combined_data

# Main workflow
if __name__ == "__main__":
    filings_df = fetch_form_13f_filings()
    filing_urls = filings_df["Filing URL"].tolist()

    top_50_stocks = parse_form_13f_holdings(filing_urls)
    print("Top 50 Stocks:", top_50_stocks)

    # Define the date range for historical data
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)  # 1 year of data

    historical_data = fetch_historical_prices(top_50_stocks, start_date=start_date, end_date=end_date)
    lumibot_data = prepare_lumibot_data(historical_data)

    # Save to CSV for LumiBot integration
    lumibot_data.to_csv("lumibot_ready_data.csv", index=False)
    print("Data prepared and saved as lumibot_ready_data.csv")