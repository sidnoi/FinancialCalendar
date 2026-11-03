import os
import json
import time
from datetime import date, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()
HEADERS = {"User-Agent": os.getenv("SEC_USER_AGENT")}

FORMS_WANTED = {"10-K": "Annual report", "10-Q": "Quarterly report", "DEF 14A": "Proxy statement"}

METRICS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
    "diluted_eps": ["EarningsPerShareDiluted"],
}
BALANCE_SHEET_ITEMS = {"cash", "long_term_debt"}


def get_filings(cik, ticker):
    data = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS).json()
    recent = data["filings"]["recent"]
    cutoff = (date.today() - timedelta(days=730)).isoformat()
    events = []
    for i, form in enumerate(recent["form"]):
        filed = recent["filingDate"][i]
        if filed < cutoff:
            continue
        items = recent["items"][i] or ""
        if form in FORMS_WANTED:
            title = FORMS_WANTED[form]
        elif form == "8-K" and "2.02" in items:
            title = "Earnings release"
        else:
            continue
        accession = recent["accessionNumber"][i].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{recent['primaryDocument'][i]}"
        events.append({"date": filed, "ticker": ticker, "type": "filing",
                       "title": f"{ticker} {title} ({form})", "url": url})
    return events


def annual_values(facts, tags, unit, balance_sheet):
    gaap = facts["facts"].get("us-gaap", {})
    best = {}
    for tag in tags:
        if tag not in gaap:
            continue
        for r in gaap[tag]["units"].get(unit, []):
            if r.get("form") != "10-K":
                continue
            if not balance_sheet:
                if "start" not in r:
                    continue
                days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
                if not 350 <= days <= 380:  # full-year figures only
                    continue
            current = best.get(r["end"])
            if current is None or r["filed"] > current["filed"]:
                best[r["end"]] = {"val": r["val"], "filed": r["filed"]}
    return {end: v["val"] for end, v in sorted(best.items())[-5:]}


def get_financials(cik):
    facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=HEADERS).json()
    result = {}
    for metric, tags in METRICS.items():
        unit = "USD/shares" if metric == "diluted_eps" else "USD"
        result[metric] = annual_values(facts, tags, unit, metric in BALANCE_SHEET_ITEMS)

    shares = facts["facts"].get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares", [])
    if shares:
        latest_filed = max(r["filed"] for r in shares)
        latest_end = max(r["end"] for r in shares if r["filed"] == latest_filed)
        result["shares_outstanding"] = sum(r["val"] for r in shares
                                           if r["filed"] == latest_filed and r["end"] == latest_end)
    else:
        result["shares_outstanding"] = None
    return result


with open("data/companies.json") as f:
    companies = json.load(f)

all_events, all_financials = [], {}
for c in companies:
    if not c["cik"]:
        print("No CIK for", c["ticker"], "- skipping")
        continue
    all_events += get_filings(c["cik"], c["ticker"])
    time.sleep(0.2)
    all_financials[c["ticker"]] = get_financials(c["cik"])
    time.sleep(0.2)
    print("Done:", c["ticker"])

with open("data/events.json", "w") as f:
    json.dump(sorted(all_events, key=lambda e: e["date"]), f, indent=2)
with open("data/financials.json", "w") as f:
    json.dump(all_financials, f, indent=2)

print(f"Saved {len(all_events)} events and financials for {len(all_financials)} companies")