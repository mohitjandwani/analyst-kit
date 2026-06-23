#!/usr/bin/env python3
"""Fetch a fund's latest 13F-HR holdings from SEC EDGAR.

Simplest use — pass a CIK or an unambiguous fund name:

    python fetch_13f.py 0001067983              # Berkshire, by CIK (most reliable)
    python fetch_13f.py "Pershing Square Capital Management"

Options:
    --period YYYY-MM-DD   a specific report period instead of the latest
    --out DIR             output directory (default: ./13f-output)
    --quiet               don't print the holdings table to stdout

Writes <DIR>/<filer>_<period>.csv (ranked holdings) and prints a summary.
Values are normalized to whole USD; issuers are rolled up across share classes,
accounts, and option lines. Run find_fund.py first if you don't know the CIK.
"""
import csv
import os
import re
import sys

from edgar import aggregate, latest_13f, parse_infotable, resolve_cik


def parse_args(argv):
    opts = {"period": None, "out": "13f-output", "quiet": False, "target": None}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--period":
            i += 1
            opts["period"] = argv[i]
        elif a == "--out":
            i += 1
            opts["out"] = argv[i]
        elif a == "--quiet":
            opts["quiet"] = True
        elif a in ("-h", "--help"):
            return None
        else:
            opts["target"] = a if opts["target"] is None else opts["target"] + " " + a
        i += 1
    return opts if opts["target"] else None


def fmt(v):
    return f"${v/1e9:.2f}B" if v >= 1e9 else f"${v/1e6:.1f}M" if v >= 1e6 else f"${v:,.0f}"


def main(argv):
    opts = parse_args(argv)
    if not opts:
        print(__doc__)
        return 2

    try:
        cik, name = resolve_cik(opts["target"])
    except ValueError as e:
        print(e)
        return 1

    filing = latest_13f(cik, period=opts["period"])
    if not filing:
        where = f"for period {opts['period']}" if opts["period"] else ""
        print(f"No 13F-HR found for {name} (CIK {cik}) {where}".rstrip())
        return 1

    holdings = parse_infotable(cik, filing["accession"])
    if not holdings:
        print(f"Could not parse information table for accession {filing['accession']}.")
        return 1

    positions, normalized = aggregate(holdings)
    total = sum(p["value_usd"] for p in positions)

    os.makedirs(opts["out"], exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:60]
    path = os.path.join(opts["out"], f"{safe}_{filing['period']}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "issuer", "cusip", "value_usd", "pct_of_portfolio", "shares", "derivative"])
        for i, p in enumerate(positions, 1):
            w.writerow([i, p["issuer"], p["cusip"], p["value_usd"], f"{p['pct']:.2f}", p["shares"], p["derivative"]])

    print(f"{name}  (CIK {cik})")
    print(f"  {filing['form']}  period {filing['period']}  filed {filing['filed']}")
    print(f"  accession {filing['accession']}")
    print(f"  {len(positions)} issuers ({len(holdings)} line items)  |  total {fmt(total)}"
          + ("  [reported in $thousands -> normalized x1000]" if normalized else ""))
    print(f"  -> {path}")
    if not opts["quiet"]:
        print(f"\n  {'#':>3}  {'ISSUER':32} {'VALUE':>12} {'%':>6}  {'SHARES':>14}  DERIV")
        for i, p in enumerate(positions[:25], 1):
            print(f"  {i:>3}  {p['issuer'][:32]:32} {fmt(p['value_usd']):>12} "
                  f"{p['pct']:>5.1f}% {p['shares']:>14,}  {p['derivative']}")
        if len(positions) > 25:
            print(f"       ... {len(positions)-25} more in the CSV")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
