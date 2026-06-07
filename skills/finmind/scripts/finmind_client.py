"""Shared FinMind helpers used by the finmind skill scripts.

Single source of truth for: the per-company dataset list, the authenticated
HTTP call (with retry + quota handling), and the local market-cap computation.
All credentials come from the FINMIND_TOKEN environment variable -- never hardcode.
"""
import os
import time
import json
from datetime import date, datetime

import requests
import pandas as pd

BASE_URL = "https://api.finmindtrade.com/api/v4/data"
DEFAULT_START = "2000-01-01"

# Datasets that make up a company's "full history". All are free-tier (with data_id).
# `dedupe` = columns used to drop duplicate rows on incremental update.
# Single-day-only datasets (tick / minute K) are intentionally excluded.
DATASETS = [
    {"name": "TaiwanStockPrice",                         "dedupe": ["date"]},
    {"name": "TaiwanStockPER",                           "dedupe": ["date"]},
    {"name": "TaiwanStockMonthRevenue",                  "dedupe": ["date", "revenue_month"]},
    {"name": "TaiwanStockShareholding",                  "dedupe": ["date"]},
    {"name": "TaiwanStockFinancialStatements",           "dedupe": ["date", "type"]},
    {"name": "TaiwanStockBalanceSheet",                  "dedupe": ["date", "type"]},
    {"name": "TaiwanStockCashFlowsStatement",            "dedupe": ["date", "type"]},
    {"name": "TaiwanStockDividend",                      "dedupe": ["date"]},
    {"name": "TaiwanStockDividendResult",                "dedupe": ["date"]},
    {"name": "TaiwanStockInstitutionalInvestorsBuySell", "dedupe": ["date", "name"]},
    {"name": "TaiwanStockMarginPurchaseShortSale",       "dedupe": ["date"]},
    # NOTE: TaiwanStockNews is intentionally excluded -- it is a single-day dataset
    # (rejects end_date / a date range), so it cannot be bulk-fetched here. Query it
    # ad-hoc with a single start_date if you need recent news (see references/usage.md).
]


class FinMindError(Exception):
    """Raised on a non-retryable FinMind API failure (tier block, bad param, quota)."""


def get_token():
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        raise FinMindError(
            "FINMIND_TOKEN not set. Run: export FINMIND_TOKEN='your_token' "
            "(free token from https://finmindtrade.com/)."
        )
    return token


def today_str():
    return date.today().isoformat()


def fetch(dataset, data_id=None, start_date=None, end_date=None, token=None, max_retries=4):
    """Call GET /data and return the `data` list. Retries transient errors, raises FinMindError otherwise."""
    token = token or get_token()
    params = {"dataset": dataset}
    if data_id:
        params["data_id"] = str(data_id)
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    headers = {"Authorization": f"Bearer {token}"}

    backoff = 5
    for attempt in range(max_retries):
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=60)
        if resp.status_code == 402:
            raise FinMindError(
                "HTTP 402: FinMind quota/rate limit exceeded (free tier = 600 req/hr). "
                "Wait an hour or upgrade tier."
            )
        try:
            payload = resp.json()
        except ValueError:
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise FinMindError(f"{dataset}: non-JSON response (HTTP {resp.status_code})")

        if payload.get("status") == 200:
            return payload.get("data", [])

        msg = str(payload.get("msg", ""))
        transient = "limit" in msg.lower() or resp.status_code in (429, 500, 502, 503)
        if transient and attempt < max_retries - 1:
            time.sleep(backoff)
            backoff *= 2
            continue
        raise FinMindError(f"{dataset}: status={payload.get('status')} msg={msg}")

    raise FinMindError(f"{dataset}: exhausted {max_retries} retries")


def fetch_df(dataset, **kwargs):
    return pd.DataFrame(fetch(dataset, **kwargs))


def company_dir(outdir, data_id):
    return os.path.join(outdir, str(data_id))


def compute_market_cap(price_df, shareholding_df):
    """market_cap = close * NumberOfSharesIssued.

    Shares (from TaiwanStockShareholding) are forward-filled onto each trading day's
    close price. Used because TaiwanStockMarketValue is a paid-tier dataset.
    """
    cols = ["date", "close", "shares_issued", "market_cap"]
    if price_df is None or shareholding_df is None or price_df.empty or shareholding_df.empty:
        return pd.DataFrame(columns=cols)
    if "NumberOfSharesIssued" not in shareholding_df.columns or "close" not in price_df.columns:
        return pd.DataFrame(columns=cols)

    p = price_df[["date", "close"]].copy()
    s = shareholding_df[["date", "NumberOfSharesIssued"]].copy()
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    s["shares_issued"] = pd.to_numeric(s["NumberOfSharesIssued"], errors="coerce")
    p["date"] = pd.to_datetime(p["date"], errors="coerce")
    s["date"] = pd.to_datetime(s["date"], errors="coerce")
    p = p.dropna(subset=["date", "close"]).sort_values("date")
    s = s.dropna(subset=["date", "shares_issued"])
    s = s[s["shares_issued"] > 0].sort_values("date")
    if p.empty or s.empty:
        return pd.DataFrame(columns=cols)

    merged = pd.merge_asof(p, s[["date", "shares_issued"]], on="date", direction="backward")
    merged["market_cap"] = merged["close"] * merged["shares_issued"]
    merged = merged.dropna(subset=["market_cap"])
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    return merged[cols].reset_index(drop=True)


def write_metadata(cdir, data_id, stock_name, frames):
    """Write metadata.json summarising each dataset (row count + date span)."""
    meta = {
        "data_id": str(data_id),
        "stock_name": stock_name or "",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": {},
    }
    for name, df in frames.items():
        if df is not None and not df.empty and "date" in df.columns:
            meta["datasets"][name] = {
                "rows": int(len(df)),
                "min_date": str(df["date"].min()),
                "max_date": str(df["date"].max()),
            }
        else:
            rows = 0 if df is None else int(len(df))
            meta["datasets"][name] = {"rows": rows, "min_date": None, "max_date": None}

    with open(os.path.join(cdir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


def resolve_stock_name(data_id, token=None):
    """Look up a stock's Chinese name from TaiwanStockInfo (returns '' if not found)."""
    try:
        info = fetch_df("TaiwanStockInfo", token=token or get_token())
        match = info[info["stock_id"].astype(str) == str(data_id)]
        if not match.empty:
            return str(match.iloc[0]["stock_name"])
    except FinMindError:
        pass
    return ""


def _existing_stock_name(cdir):
    path = os.path.join(cdir, "metadata.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8")).get("stock_name", "")
        except (ValueError, OSError):
            return ""
    return ""


def _merge(existing, new, dedupe_cols):
    """Concatenate existing + new rows, drop duplicates on dedupe_cols, sort by date."""
    if existing.empty:
        combined = new
    elif new.empty:
        combined = existing
    else:
        combined = pd.concat([existing, new], ignore_index=True)
    if combined.empty:
        return combined
    subset = [c for c in dedupe_cols if c in combined.columns] or None
    combined = combined.drop_duplicates(subset=subset, keep="last")
    if "date" in combined.columns:
        combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def sync_company(data_id, outdir, default_start=DEFAULT_START, end_date=None,
                 incremental=False, token=None, sleep=0.3, log=print):
    """Fetch every dataset for a company, merge with any stored CSV, and write the results.

    Shared core of download_company.py and update_company.py:
      - incremental=False  -> pull each dataset from `default_start` (full download).
      - incremental=True   -> pull each dataset from its last stored date (update).

    The merge/dedupe makes both modes idempotent. Also writes market_cap.csv and
    metadata.json. Returns (company_dir, frames_by_dataset).
    """
    token = token or get_token()
    end_date = end_date or today_str()
    cdir = company_dir(outdir, data_id)
    os.makedirs(cdir, exist_ok=True)

    frames = {}
    for ds in DATASETS:
        name = ds["name"]
        path = os.path.join(cdir, f"{name}.csv")
        existing = pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
        before = len(existing)

        start = default_start
        if incremental and not existing.empty and "date" in existing.columns:
            start = str(existing["date"].max())  # refetch last day to catch same-day revisions

        try:
            new = pd.DataFrame(fetch(name, data_id=data_id, start_date=start, end_date=end_date, token=token))
        except FinMindError as e:
            log(f"  ! {name}: {e}")
            frames[name] = existing
            continue

        combined = _merge(existing, new, ds["dedupe"])
        combined.to_csv(path, index=False)
        frames[name] = combined
        if incremental:
            log(f"  ✓ {name}: +{len(combined) - before} new (total {len(combined)})")
        else:
            log(f"  ✓ {name}: {len(combined)} rows")
        time.sleep(sleep)

    mc = compute_market_cap(frames.get("TaiwanStockPrice"), frames.get("TaiwanStockShareholding"))
    mc.to_csv(os.path.join(cdir, "market_cap.csv"), index=False)
    log(f"  ✓ market_cap: {len(mc)} rows")

    stock_name = _existing_stock_name(cdir) or resolve_stock_name(data_id, token)
    write_metadata(cdir, data_id, stock_name, frames)
    return cdir, frames
