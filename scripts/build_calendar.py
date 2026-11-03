import os
import csv
import json
import time
from datetime import date, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("FINNHUB_API_KEY")

TIMING = {"bmo": "Before market open", "amc": "After market close", "dmh": "During market hours"}

with open("data/companies.json") as f:
    companies = json.load(f)

start = (date.today() - timedelta(days=180)).isoformat()
end = (date.today() + timedelta(days=180)).isoformat()

earnings = []
for c in companies:
    data = requests.get("https://finnhub.io/api/v1/calendar/earnings",
                        params={"from": start, "to": end, "symbol": c["ticker"], "token": KEY}).json()
    for e in data.get("earningsCalendar", []):
        earnings.append({
            "date": e["date"],
            "ticker": c["ticker"],
            "type": "earnings",
            "title": f"{c['ticker']} Q{e['quarter']} FY{e['year']} earnings",
            "timing": TIMING.get(e.get("hour"), ""),
            "eps_estimate": e.get("epsEstimate"),
            "eps_actual": e.get("epsActual"),
            "revenue_estimate": e.get("revenueEstimate"),
            "revenue_actual": e.get("revenueActual"),
        })
    print("Done:", c["ticker"])
    time.sleep(1)

macro = []
with open("data/macro_events.csv", newline="") as f:
    for row in csv.DictReader(f):
        macro.append({
            "date": row["date"],
            "ticker": None,
            "type": row["type"],
            "title": row["title"],
            "url": row.get("url") or None,
        })

with open("data/earnings.json", "w") as f:
    json.dump(sorted(earnings, key=lambda e: e["date"]), f, indent=2)
with open("data/macro.json", "w") as f:
    json.dump(sorted(macro, key=lambda e: e["date"]), f, indent=2)

print(f"Saved {len(earnings)} earnings dates and {len(macro)} macro events")