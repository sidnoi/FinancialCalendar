import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("FINNHUB_API_KEY")
SEC_HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT")}

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "JPM", "GS", "XOM", "JNJ", "KO"]
CIK_OVERRIDES = {
    "XOM": "0000034088",  # ticker file points to the new holding company, which has no 10-K history yet
}

sec_map = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS).json()
cik_lookup = {row["ticker"]: str(row["cik_str"]).zfill(10) for row in sec_map.values()}

companies = []
for ticker in TICKERS:
    profile = requests.get("https://finnhub.io/api/v1/stock/profile2",
                           params={"symbol": ticker, "token": KEY}).json()
    peers = requests.get("https://finnhub.io/api/v1/stock/peers",
                         params={"symbol": ticker, "token": KEY}).json()

    companies.append({
        "ticker": ticker,
        "name": profile.get("name"),
        "sector": profile.get("finnhubIndustry"),
        "cik": CIK_OVERRIDES.get(ticker, cik_lookup.get(ticker)),
        "website": profile.get("weburl"),
        "peers": [p for p in peers if p != ticker][:5],
    })
    print("Done:", ticker)
    time.sleep(1)  # stays well under Finnhub's free rate limit

os.makedirs("data", exist_ok=True)
with open("data/companies.json", "w") as f:
    json.dump(companies, f, indent=2)

print(f"Saved {len(companies)} companies")