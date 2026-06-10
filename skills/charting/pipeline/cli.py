#!/usr/bin/env python3
"""Pipeline CLI — chart contracts without hand-written code.

    python -m pipeline.cli        # tests/data/*.json -> tests/contracts/*.json (fixtures)
    python -m pipeline.cli yoy data.json --metrics revenue,bookings --lag 4 -o contract.json

The `yoy` subcommand is the agent fast-path: raw records in, chart contract out.
All growth math runs in Polars (`process.yoy`) — an agent should never compute
YoY/growth rates "by hand". `data.json` is a list of records like
`[{"date": "2023-03-31", "revenue": 655300000, "bookings": 773800000}, ...]`
with absolute values (the pipeline scales units).

Thin by design. This skill assumes the financial data is already available (some
upstream step produces it); the Polars layer only loads, validates, and normalizes
it into the chart contract. Fetching data is out of scope.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import charts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tests", "data")
CONTRACTS = os.path.join(ROOT, "tests", "contracts")


def _load(name: str) -> list:
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def build_contracts() -> dict[str, dict]:
    """Normalize the dummy records into one chart contract per chart."""
    inc = _load("aapl_income_annual.json")
    seg = _load("aapl_segmentation.json")
    div = _load("aapl_dividends.json")
    ear = _load("aapl_earnings.json")
    price = _load("aapl_price.json")
    msft_price = _load("msft_price.json")
    inc_q = _load("aapl_income_quarter.json")
    msft = _load("msft_income_annual.json")
    latest = sorted(inc, key=lambda r: r["date"])[-1]
    return {
        "revenue_margins": charts.revenue_margins(inc),
        "revenue_trend": charts.revenue_trend(inc, flags=[{"x": "FY2020", "title": "COVID"}]),
        "revenue_yoy": charts.revenue_yoy(inc),
        "compare_rebased": charts.compare_rebased([("AAPL", inc), ("MSFT", msft)]),
        "segments_stacked": charts.segments(seg, variant="stacked"),
        "segments_percent": charts.segments(seg, variant="percent"),
        "segments_grouped": charts.segments(seg, variant="grouped"),
        "waterfall": charts.waterfall(latest),
        "dividend_yield": charts.dividend_yield(div),
        "surprise_eps": charts.surprise(ear, metric="eps"),
        "estimate_vs_reported_revenue": charts.estimate_vs_reported(ear, metric="revenue"),
        "estimate_vs_reported_eps": charts.estimate_vs_reported(ear, metric="eps"),
        "price_candlestick": charts.price(price, primary=True,
                                          flags=[{"date": "2025-05-02", "title": "FY25 Q2"}]),
        "price_with_revenue": charts.price_with_revenue(price, inc_q, mode="period"),
        "price_revenue_reaction": charts.price_with_revenue(price, inc_q, mode="reaction"),
        "price_revenue_growth": charts.price_with_revenue(price, inc_q, mode="growth"),
        "compare_price_rebased": charts.compare_price_rebased([("AAPL", price), ("MSFT", msft_price)]),
    }


def regen_fixtures() -> None:
    os.makedirs(CONTRACTS, exist_ok=True)
    for name, payload in build_contracts().items():
        with open(os.path.join(CONTRACTS, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"  {name:32s} {len(payload['series'])} series")


def cmd_yoy(argv: list[str]) -> None:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.cli yoy",
        description="Raw records → YoY-growth chart contract (math runs in Polars).")
    p.add_argument("data", help="JSON file: [{\"date\": \"YYYY-MM-DD\", \"<metric>\": value, …}]")
    p.add_argument("--metrics", required=True,
                   help="comma-separated metric columns, e.g. revenue,bookings")
    p.add_argument("--lag", type=int, default=4,
                   help="periods per year: 4 = quarterly (default), 1 = annual")
    p.add_argument("--title", help="chart title (default: '<symbol> — YoY growth')")
    p.add_argument("-o", "--out", help="write the contract here (default: stdout)")
    a = p.parse_args(argv)

    with open(a.data, encoding="utf-8") as f:
        records = json.load(f)
    contract = charts.metrics_yoy(
        records, metrics=[m.strip() for m in a.metrics.split(",") if m.strip()],
        lag=a.lag, title=a.title)
    text = json.dumps(contract, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {a.out}")
    else:
        print(text)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "yoy":
        cmd_yoy(args[1:])
    else:
        regen_fixtures()


if __name__ == "__main__":
    main()
