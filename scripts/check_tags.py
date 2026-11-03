import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT")}

with open("data/companies.json") as f:
    xom = next(c for c in json.load(f) if c["ticker"] == "XOM")
print("CIK in companies.json:", xom["cik"])

facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{xom['cik']}.json", headers=HEADERS).json()
gaap = facts["facts"].get("us-gaap", {})
print("Entity:", facts.get("entityName"))
print("Number of us-gaap tags:", len(gaap))
print("Has cash tag:", "CashAndCashEquivalentsAtCarryingValue" in gaap)