#!/usr/bin/env python3
"""
Gather raw news + material-event items for the active universe.

This is the deterministic input to the daily report: it pulls per-ticker news
(FMP) and recent 8-K material events (SEC EDGAR, via the sibling sec-filings
``edgar.py``). It does NOT summarize — the agent turns these raw items into the
report narrative before rendering.

Both sources degrade gracefully: no ``FMP_API_KEY`` → no news section; no
reachable ``edgar.py`` → no filings section. A run never aborts on one ticker.

HTTP and the EDGAR subprocess are injectable so the gathering logic can be
tested offline.

Pure standard library.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from monitor_dates import active_tickers
from storage import load_store

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _http_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "company-universe-manager"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted FMP host)
        return json.loads(resp.read().decode("utf-8"))


def fetch_fmp_news(
    tickers: list[str],
    api_key: str,
    *,
    limit: int = 50,
    from_date: str | None = None,
    http: Callable[[str], Any] = _http_json,
) -> dict[str, list[dict[str, Any]]]:
    """Per-ticker recent news from FMP's stock_news endpoint.

    Returns {ticker: [ {title, date, site, url, text}, ... ]}. On any HTTP error
    (e.g. 402 if the news tier is not enabled) returns {} rather than raising.
    """
    if not tickers or not api_key:
        return {}
    q = urllib.parse.urlencode(
        {"tickers": ",".join(tickers), "limit": str(limit), "apikey": api_key}
    )
    url = f"{FMP_BASE}/stock_news?{q}"
    try:
        rows = http(url)
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}

    out: dict[str, list[dict[str, Any]]] = {t: [] for t in tickers}
    for row in rows:
        sym = (row.get("symbol") or "").upper()
        if sym not in out:
            continue
        published = (row.get("publishedDate") or "")[:10]
        if from_date and published and published < from_date:
            continue
        out[sym].append(
            {
                "title": row.get("title"),
                "date": published,
                "site": row.get("site"),
                "url": row.get("url"),
                "text": (row.get("text") or "")[:500],
            }
        )
    return out


def _locate_edgar() -> Path | None:
    """Find the sibling sec-filings edgar.py: env override, then sibling skill."""
    override = os.environ.get("SEC_EDGAR_SCRIPT")
    if override and Path(override).exists():
        return Path(override)
    sibling = Path(__file__).resolve().parent.parent.parent / "sec-filings" / "scripts" / "edgar.py"
    return sibling if sibling.exists() else None


def _run_edgar(args: list[str]) -> str:
    edgar = _locate_edgar()
    if edgar is None:
        raise FileNotFoundError("sec-filings edgar.py not found")
    result = subprocess.run(
        [sys.executable, str(edgar), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "edgar.py failed")
    return result.stdout


def fetch_recent_8ks(
    ticker: str,
    *,
    count: int = 5,
    edgar: Callable[[list[str]], str] = _run_edgar,
) -> list[dict[str, Any]]:
    """Recent 8-K material events for a ticker via sec-filings edgar.py.

    Returns [] if edgar.py is unavailable or the ticker can't be resolved
    (e.g. a non-US/Taiwan ticker), never raises.
    """
    try:
        raw = edgar(["filings", ticker, "8-K", "-n", str(count)])
    except Exception:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    rows = data if isinstance(data, list) else data.get("filings", [])
    out = []
    for row in rows or []:
        out.append(
            {
                "date": row.get("filingDate") or row.get("date"),
                "items": row.get("items") or row.get("itemCodes"),
                "url": row.get("primaryDocUrl") or row.get("url"),
            }
        )
    return out


def gather(
    tickers: list[str],
    api_key: str | None,
    *,
    lookback_days: int = 7,
    today: str | None = None,
    news_fetcher: Callable[..., dict] | None = None,
    sec_fetcher: Callable[..., list] | None = None,
) -> dict[str, Any]:
    """Aggregate news + filings for the universe into one structure."""
    today = today or date.today().isoformat()
    from_date = (date.fromisoformat(today) - timedelta(days=lookback_days)).isoformat()

    news: dict[str, list] = {}
    if api_key:
        fetch = news_fetcher or fetch_fmp_news
        news = fetch(tickers, api_key, from_date=from_date)

    filings: dict[str, list] = {}
    sec = sec_fetcher or (lambda t: fetch_recent_8ks(t))
    for ticker in tickers:
        recent = sec(ticker)
        recent = [f for f in recent if (f.get("date") or "") >= from_date]
        if recent:
            filings[ticker] = recent

    return {
        "as_of": today,
        "lookback_days": lookback_days,
        "from_date": from_date,
        "news": {t: items for t, items in news.items() if items},
        "filings": filings,
    }


def main() -> int:
    store = load_store()
    store.ensure_layout()
    tickers = active_tickers(store)
    if not tickers:
        print(json.dumps({"error": "no active tickers in roster"}))
        return 1
    api_key = os.environ.get("FMP_API_KEY")
    result = gather(tickers, api_key)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
