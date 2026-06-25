#!/usr/bin/env python3
"""Download a company's full FinMind history into one CSV per dataset.

Usage:
    python download_company.py 2330                  # full history (from 2000-01-01)
    python download_company.py 2330 --start 2015-01-01
    python download_company.py 2330 --outdir /tmp/fm

Writes to <outdir>/<data_id>/: one <Dataset>.csv per dataset, a derived
market_cap.csv (date, close, shares_issued, market_cap), and metadata.json.
The fetch/merge/market-cap logic lives in finmind_client.sync_company.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finmind_client as fm


def main():
    ap = argparse.ArgumentParser(description="Download a company's full FinMind history.")
    ap.add_argument("data_id", help="Stock id, e.g. 2330")
    ap.add_argument("--start", default=fm.DEFAULT_START, help="Start date YYYY-MM-DD (default 2000-01-01).")
    ap.add_argument("--end", default=fm.today_str(), help="End date YYYY-MM-DD (default today).")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = ap.parse_args()

    print(f"Downloading {args.data_id} ({args.start} -> {args.end})")
    cdir, _ = fm.sync_company(args.data_id, args.outdir, default_start=args.start,
                              end_date=args.end, incremental=False)
    print(f"Done -> {cdir} ({fm._existing_stock_name(cdir)})")


if __name__ == "__main__":
    main()
