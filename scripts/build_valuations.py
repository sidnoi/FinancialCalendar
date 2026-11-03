import os
import io
import csv
import json
import time
import statistics
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("FINNHUB_API_KEY")

EQUITY_RISK_PREMIUM = 0.05
TERMINAL_GROWTH = 0.025
TAX_RATE = 0.21
YEARS = 5
FINANCIAL_SECTORS = ("bank", "financial", "insurance")
PEER_OVERRIDES = {
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
}


def finnhub(path, **params):
    params["token"] = KEY
    time.sleep(1)
    return requests.get(f"https://finnhub.io/api/v1/{path}", params=params).json()


metrics_cache = {}
def get_metrics(ticker):
    if ticker not in metrics_cache:
        metrics_cache[ticker] = finnhub("stock/metric", symbol=ticker, metric="all").get("metric", {})
    return metrics_cache[ticker]


def get_pe(ticker):
    m = get_metrics(ticker)
    return m.get("peTTM") or m.get("peBasicExclExtraTTM")


def risk_free_rate():
    try:
        text = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10", timeout=15).text
        rows = list(csv.reader(io.StringIO(text)))[1:]
        values = [float(r[1]) for r in rows if r[1] not in (".", "")]
        return values[-1] / 100
    except Exception:
        print("Couldn't fetch the 10-year yield, using 4%")
        return 0.04


def latest(series):
    if not series:
        return None
    return series[max(series)]


def revenue_growth(series):
    values = [series[k] for k in sorted(series)]
    if len(values) < 2 or values[0] <= 0:
        return 0.05
    cagr = (values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1
    return max(0.0, min(cagr, 0.15))  # keep between 0% and 15%


def dcf_per_share(fcf, growth, wacc, terminal_growth, cash, debt, shares):
    present_value = 0
    for year in range(1, YEARS + 1):
        fcf = fcf * (1 + growth)
        present_value += fcf / (1 + wacc) ** year
    terminal_value = fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    present_value += terminal_value / (1 + wacc) ** YEARS
    return (present_value + cash - debt) / shares


rf = risk_free_rate()
print(f"Risk-free rate: {rf:.2%}")

with open("data/companies.json") as f:
    companies = json.load(f)
with open("data/financials.json") as f:
    financials = json.load(f)

valuations = {}
for c in companies:
    t = c["ticker"]
    fin = financials.get(t, {})
    price = finnhub("quote", symbol=t).get("c")
    raw_beta = get_metrics(t).get("beta") or 1.0
    beta = 0.67 * raw_beta + 0.33  # Blume adjustment, pulls noisy betas towards 1
    pe = get_pe(t)

    peers = PEER_OVERRIDES.get(t, c["peers"])
    peer_pes = [get_pe(p) for p in peers]
    peer_pes = [p for p in peer_pes if p and 0 < p < 100]  # drop loss-makers and outliers
    peer_median_pe = statistics.median(peer_pes) if peer_pes else None
    eps = price / pe if price and pe else None
    pe_value = peer_median_pe * eps if peer_median_pe and eps else None

    shares = fin.get("shares_outstanding")
    if not shares:
        profile = finnhub("stock/profile2", symbol=t)
        if profile.get("shareOutstanding"):
            shares = profile["shareOutstanding"] * 1e6
    cash = latest(fin.get("cash")) or 0
    debt = latest(fin.get("long_term_debt")) or 0
    ocf = latest(fin.get("operating_cash_flow"))
    capex = latest(fin.get("capex")) or 0
    is_financial = any(word in (c["sector"] or "").lower() for word in FINANCIAL_SECTORS)

    dcf_value = wacc = growth = fcf = None
    if not is_financial and ocf and shares and price:
        fcf = ocf - capex
        cost_of_equity = rf + beta * EQUITY_RISK_PREMIUM
        cost_of_debt = (rf + 0.015) * (1 - TAX_RATE)
        market_cap = price * shares
        wacc = (market_cap * cost_of_equity + debt * cost_of_debt) / (market_cap + debt)
        growth = revenue_growth(fin.get("revenue", {}))
        if fcf > 0 and wacc > TERMINAL_GROWTH:
            dcf_value = dcf_per_share(fcf, growth, wacc, TERMINAL_GROWTH, cash, debt, shares)

    def upside(value):
        return round(value / price - 1, 4) if value and price else None

    valuations[t] = {
        "price": price,
        "pe": pe,
        "peer_median_pe": peer_median_pe,
        "pe_implied_value": round(pe_value, 2) if pe_value else None,
        "pe_upside": upside(pe_value),
        "dcf_value": round(dcf_value, 2) if dcf_value else None,
        "dcf_upside": upside(dcf_value),
        "method": "pe_only" if is_financial else "dcf_and_pe",
        "inputs": {
            "fcf": fcf, "growth": growth, "wacc": wacc, "terminal_growth": TERMINAL_GROWTH,
            "cash": cash, "debt": debt, "shares": shares, "beta": beta, "risk_free": rf,
        },
    }
    print(f"{t}: price {price}, DCF {valuations[t]['dcf_value']}, P/E implied {valuations[t]['pe_implied_value']}")

with open("data/valuations.json", "w") as f:
    json.dump(valuations, f, indent=2)

print(f"Saved valuations for {len(valuations)} companies")