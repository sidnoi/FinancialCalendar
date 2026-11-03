import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("FINNHUB_API_KEY")
sec_headers = {"User-Agent": os.getenv("SEC_USER_AGENT")}

quote = requests.get("https://finnhub.io/api/v1/quote", params={"symbol": "AAPL", "token": key}).json()
print("Apple price from Finnhub:", quote.get("c"))

sec = requests.get("https://www.sec.gov/files/company_tickers.json", headers=sec_headers)
print("EDGAR status:", sec.status_code)