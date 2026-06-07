#!/usr/bin/env python3
"""Incrementally update a company's stored FinMind data.

Usage:
    python update_company.py 2330
    python update_company.py 2330 --outdir /tmp/fm

For each dataset, fetches only rows from the last stored date forward, then
de-duplicates and rewrites -- keeping monthly revenue, share counts, stock price,
and the derived market cap current without re-downloading history. Idempotent.
Run download_company.py first to create the initial dataset. The fetch/merge
logic lives in finmind_client.sync_company.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finmind_client as fm


def main():
    ap = argparse.ArgumentParser(description="Incrementally update a company's FinMind data.")
    ap.add_argument("data_id", help="Stock id, e.g. 2330")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    args = ap.parse_args()

    cdir = fm.company_dir(args.outdir, args.data_id)
    if not os.path.isdir(cdir):
        print(f"No existing data for {args.data_id} at {cdir}. Run download_company.py first.")
        sys.exit(1)

    print(f"Updating {args.data_id} in {cdir}")
    fm.sync_company(args.data_id, args.outdir, incremental=True)
    print(f"Done -> {cdir}")


if __name__ == "__main__":
    main()
