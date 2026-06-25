#!/usr/bin/env python3
"""Resolve a Taiwan company name or id to a FinMind data_id (stock_id).

Usage:
    python find_company.py "台積電"     # by Chinese name (substring ok)
    python find_company.py 2330         # verify / echo an id

Matches an exact stock id first, then a substring on the Chinese stock_name or
industry. FinMind only stores Chinese names, so an English query (e.g. "TSMC")
will not match -- resolve to the id another way, then use it here.

The TaiwanStockInfo table (~4k stocks) is cached locally and refreshed weekly.
"""
import argparse
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finmind_client as fm

CACHE_MAX_AGE_DAYS = 7


def load_info(outdir, token):
    cache = os.path.join(outdir, "_taiwan_stock_info.csv")
    fresh = os.path.exists(cache) and (time.time() - os.path.getmtime(cache)) < CACHE_MAX_AGE_DAYS * 86400
    if fresh:
        return pd.read_csv(cache, dtype=str)
    df = fm.fetch_df("TaiwanStockInfo", token=token).astype(str)
    os.makedirs(outdir, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def main():
    ap = argparse.ArgumentParser(description="Resolve a Taiwan company name/id to a FinMind data_id.")
    ap.add_argument("query", help="Stock id (e.g. 2330) or Chinese name substring (e.g. 台積電).")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = ap.parse_args()

    token = fm.get_token()
    info = load_info(args.outdir, token).drop_duplicates(subset=["stock_id"])
    q = args.query.strip()

    hit = info[info["stock_id"] == q]
    if hit.empty:
        mask = (
            info["stock_name"].str.contains(q, case=False, na=False, regex=False)
            | info["industry_category"].str.contains(q, case=False, na=False, regex=False)
        )
        hit = info[mask]

    if hit.empty:
        print(f"No match for '{q}'. FinMind uses Chinese names — try the stock id or the Chinese name.")
        sys.exit(2)

    cols = ["stock_id", "stock_name", "industry_category", "type"]
    print(hit[cols].to_string(index=False))
    if len(hit) == 1:
        print(f"\ndata_id={hit.iloc[0]['stock_id']}")


if __name__ == "__main__":
    main()
