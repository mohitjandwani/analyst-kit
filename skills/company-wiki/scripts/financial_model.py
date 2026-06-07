#!/usr/bin/env python3
"""
financial_model.py — Company Wiki Financial Modelling Script

Computes Bear / Base / Bull revenue projections and forward P/E, P/S multiples
for FY+1 and FY+2 based on historical revenue data.

Usage:
    python financial_model.py

Edit the INPUT SECTION below with actual company data before running.
Output is printed as a JSON-friendly dict and as a formatted table.
"""

import json

# ─────────────────────────────────────────────
# INPUT SECTION — edit these values per company
# ─────────────────────────────────────────────

COMPANY = "Zhen Ding Technology"
TICKER = "4958.TW"
CURRENCY = "NT$"
CURRENCY_UNIT = "B"  # billions

# Historical annual revenue (most recent year last), in billions of local currency
ANNUAL_REVENUE = {
    2021: 119.4,
    2022: 135.8,
    2023: 127.6,
    2024: 155.9,
    2025: 182.5,
}

# Latest full fiscal year
BASE_YEAR = 2025

# Current stock price (local currency)
CURRENT_PRICE = 347.50

# Diluted shares outstanding (millions)
DILUTED_SHARES_M = 1_320.0

# Market cap (billions of local currency) — or compute from price × shares
MARKET_CAP = CURRENT_PRICE * DILUTED_SHARES_M / 1000  # NT$B

# Trailing 3-year average margins (%)
GROSS_MARGIN_PCT = 17.8   # e.g. average of 2023, 2024, 2025
NET_MARGIN_PCT   = 7.2    # e.g. average of 2023, 2024, 2025

# Scenario multipliers applied to the base CAGR
SCENARIO_MULTIPLIERS = {
    "bear": (0.55, 0.45),   # (FY+1 multiplier, FY+2 multiplier)
    "base": (1.00, 0.90),
    "bull": (1.40, 1.30),
}

# ─────────────────────────────────────────────
# COMPUTATION — do not edit below this line
# ─────────────────────────────────────────────

def compute_cagr(revenue_dict):
    years = sorted(revenue_dict.keys())
    n = len(years) - 1
    cagr = (revenue_dict[years[-1]] / revenue_dict[years[0]]) ** (1 / n) - 1
    return cagr

def compute_scenario(base_revenue, cagr, fy1_mult, fy2_mult, gross_margin, net_margin, shares_m, price, mkt_cap):
    fy1_growth = cagr * fy1_mult
    fy2_growth = cagr * fy2_mult

    rev_fy1 = base_revenue * (1 + fy1_growth)
    rev_fy2 = rev_fy1 * (1 + fy2_growth)

    ni_fy1 = rev_fy1 * (net_margin / 100)
    ni_fy2 = rev_fy2 * (net_margin / 100)

    eps_fy1 = (ni_fy1 * 1e9) / (shares_m * 1e6)   # NT$ per share
    eps_fy2 = (ni_fy2 * 1e9) / (shares_m * 1e6)

    fwd_pe_fy1 = price / eps_fy1 if eps_fy1 > 0 else None
    fwd_pe_fy2 = price / eps_fy2 if eps_fy2 > 0 else None

    fwd_ps_fy1 = mkt_cap / rev_fy1
    fwd_ps_fy2 = mkt_cap / rev_fy2

    return {
        "revenue_fy1": round(rev_fy1, 1),
        "revenue_fy2": round(rev_fy2, 1),
        "revenue_growth_fy1_pct": round(fy1_growth * 100, 1),
        "revenue_growth_fy2_pct": round(fy2_growth * 100, 1),
        "gross_profit_fy1": round(rev_fy1 * gross_margin / 100, 1),
        "net_income_fy1": round(ni_fy1, 1),
        "net_income_fy2": round(ni_fy2, 1),
        "eps_fy1": round(eps_fy1, 2),
        "eps_fy2": round(eps_fy2, 2),
        "fwd_pe_fy1": round(fwd_pe_fy1, 1) if fwd_pe_fy1 else "N/A",
        "fwd_pe_fy2": round(fwd_pe_fy2, 1) if fwd_pe_fy2 else "N/A",
        "fwd_ps_fy1": round(fwd_ps_fy1, 2),
        "fwd_ps_fy2": round(fwd_ps_fy2, 2),
    }


def main():
    cagr = compute_cagr(ANNUAL_REVENUE)
    base_rev = ANNUAL_REVENUE[BASE_YEAR]

    print(f"\n{'='*60}")
    print(f"  {COMPANY} ({TICKER}) — Financial Model")
    print(f"  Base Year: {BASE_YEAR}  |  Revenue: {CURRENCY}{base_rev}{CURRENCY_UNIT}")
    print(f"  Historical CAGR ({min(ANNUAL_REVENUE)}-{BASE_YEAR}): {cagr*100:.1f}%")
    print(f"  Current Price: {CURRENCY}{CURRENT_PRICE}  |  Mkt Cap: {CURRENCY}{MARKET_CAP:.1f}{CURRENCY_UNIT}")
    print(f"  Gross Margin: {GROSS_MARGIN_PCT}%  |  Net Margin: {NET_MARGIN_PCT}%")
    print(f"{'='*60}\n")

    results = {}
    for scenario, (m1, m2) in SCENARIO_MULTIPLIERS.items():
        results[scenario] = compute_scenario(
            base_rev, cagr, m1, m2,
            GROSS_MARGIN_PCT, NET_MARGIN_PCT,
            DILUTED_SHARES_M, CURRENT_PRICE, MARKET_CAP
        )

    # Print formatted table
    header = f"{'Metric':<28} {'Bear FY+1':>10} {'Base FY+1':>10} {'Bull FY+1':>10} {'Bear FY+2':>10} {'Base FY+2':>10} {'Bull FY+2':>10}"
    print(header)
    print("-" * len(header))

    metrics = [
        ("Revenue (NT$B)", "revenue_fy1", "revenue_fy2"),
        ("Revenue Growth %", "revenue_growth_fy1_pct", "revenue_growth_fy2_pct"),
        ("Net Income (NT$B)", "net_income_fy1", "net_income_fy2"),
        ("EPS (NT$)", "eps_fy1", "eps_fy2"),
        ("Fwd P/E", "fwd_pe_fy1", "fwd_pe_fy2"),
        ("Fwd P/S", "fwd_ps_fy1", "fwd_ps_fy2"),
    ]

    for label, k1, k2 in metrics:
        row = f"{label:<28}"
        for s in ["bear", "base", "bull"]:
            row += f" {str(results[s][k1]):>10}"
        for s in ["bear", "base", "bull"]:
            row += f" {str(results[s][k2]):>10}"
        print(row)

    print(f"\n{'='*60}")
    print("JSON output (paste into FinancialModelling.tsx):")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
