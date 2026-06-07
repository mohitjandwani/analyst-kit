---
name: finmind
type: capability
description: >
  Fetch and maintain Taiwan stock-market company data (prices, monthly revenue, financial
  statements, dividends, shareholding, market cap, institutional flows) via the FinMind
  API, for any company listed in Taiwan (TWSE/TPEx), referenced by stock id (data_id) or
  company name. Triggers: "fetch Taiwan stock data for X", "TSMC monthly revenue", "TWSE
  financials for <stock id>", "Taiwan dividends/shareholding for Y".
env:
  - FINMIND_TOKEN
---

# FinMind — Taiwan company data

FinMind serves Taiwan market data over a REST API. This skill wraps the most common
operations in self-contained scripts, so the two dominant requests — **download everything
for a company** and **keep it updated** — run **without reading any reference file**.

## Setup

Requires a FinMind API token in the environment:

```bash
export FINMIND_TOKEN="your_token"   # free token: register at https://finmindtrade.com/
```

Free tier = 600 requests/hour — ample for per-company pulls. If `FINMIND_TOKEN` is unset,
the scripts print this instruction; ask the user for their token.

## Common operations — just run the script (no reference reading needed)

Scripts are in `scripts/`. Output goes to `scripts/../data/<data_id>/`.

### 1 · Find a company's `data_id`
```bash
python scripts/find_company.py "台積電"     # Chinese name (substring ok)
python scripts/find_company.py 2330         # verify / echo an id
```
Prints matching `stock_id` + name + industry. FinMind stores **Chinese names only** — an
English query like "TSMC" won't match, so resolve to the id first.

### 2 · Download a company's full history
```bash
python scripts/download_company.py 2330                  # full history
python scripts/download_company.py 2330 --start 2015-01-01
```
Pulls price, valuation (PER/PBR), monthly revenue, financial statements, balance sheet,
cash flows, dividends, shareholding, institutional flows, and margin — one CSV per
dataset — plus a derived `market_cap.csv` and `metadata.json`. (Company news is single-day
only and not bulk-pullable; query it ad-hoc per `references/usage.md`.)

### 3 · Keep a company's data updated
```bash
python scripts/update_company.py 2330
```
Incrementally fetches only rows newer than what's stored (idempotent), refreshing especially
**monthly revenue, share counts, stock price, and market cap**. Run `download_company.py` first.

## Output layout

```
data/<data_id>/
  TaiwanStockPrice.csv   TaiwanStockMonthRevenue.csv   TaiwanStockShareholding.csv   ...
  market_cap.csv         # date, close, shares_issued, market_cap
  metadata.json          # stock_name, updated_at, per-dataset rows + min/max date
```

## Market cap note

FinMind's direct market-cap dataset (`TaiwanStockMarketValue`) requires a paid tier. On the
free tier the scripts compute **market_cap = close × NumberOfSharesIssued** (shares from
`TaiwanStockShareholding`) into `market_cap.csv`.

## Custom / ad-hoc queries (read references only when needed)

For anything beyond the three operations above — a specific dataset, column meanings, tier
requirements, intraday / derivatives / macro data — consult:

- [`references/datasets.md`](references/datasets.md) — full catalog: every dataset, its
  columns, and tier requirements.
- [`references/usage.md`](references/usage.md) — API mechanics: endpoints, params, error
  handling, rate limits, the long-format note for financial statements.

`scripts/finmind_client.py` exposes reusable helpers (`fetch`, `fetch_df`, `DATASETS`,
`compute_market_cap`) — import it for custom pulls instead of re-implementing the HTTP call.

## Tests

`tests/test_finmind.py` exercises real companies (e.g. 2330) end-to-end. They hit the live
API and are skipped automatically when `FINMIND_TOKEN` is unset:

```bash
export FINMIND_TOKEN="your_token"
pytest tests -q
```
