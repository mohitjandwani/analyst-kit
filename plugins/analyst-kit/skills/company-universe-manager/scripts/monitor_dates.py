#!/usr/bin/env python3
"""
Daily key-date monitor: fetch current dates, diff against the stored events,
record what changed, and refresh the store.

Two layers, deliberately separated so the change detection is unit-testable
without a network:

  * ``diff_ticker(stored, fetched)`` and ``monitor(store, tickers, fetcher)`` are
    PURE given a ``fetcher`` callable — tests inject a fake fetcher.
  * ``fetch_fmp_earnings(...)`` is the real HTTP fetch (urllib + FMP_API_KEY),
    used only by ``main()``.

Change kinds:
  new            an event slot not previously stored
  moved          same slot, the date changed (e.g. earnings pushed a week)
  status_changed same slot+date, status changed (e.g. estimated -> confirmed)
  dropped        a future-dated stored event that disappeared from the fetch
  unchanged      matched with no change

"Slot" matching: by (type, ref) when an event carries a ``ref`` (for earnings,
the fiscal period end, so a moved announcement date for the same quarter reads
as a move, not a new+dropped pair); otherwise by (type, date). As a fallback,
a single future-dated leftover of a type on each side is paired as a move.

Pure standard library.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.request
from datetime import date
from typing import Any, Callable

from events_manager import normalize_event
from storage import load_store

FMP_BASE = "https://financialmodelingprep.com/api/v3"


# --- slot identity & diff (pure) --------------------------------------------


def slot_key(event: dict[str, Any]) -> tuple[str, str]:
    """Identity used to match an event across fetches."""
    ref = event.get("ref")
    if ref:
        return (event.get("type", ""), f"ref:{ref}")
    return (event.get("type", ""), f"date:{event.get('date', '')}")


def _record(event: dict[str, Any], **extra: Any) -> dict[str, Any]:
    rec = {
        "type": event.get("type"),
        "date": event.get("date"),
        "status": event.get("status"),
        "source": event.get("source"),
        "ref": event.get("ref"),
    }
    rec.update(extra)
    return rec


def diff_ticker(
    stored: list[dict[str, Any]],
    fetched: list[dict[str, Any]],
    today: str | None = None,
    covered_types: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Categorize the difference between stored and freshly fetched events.

    ``covered_types`` is the set of event types this fetch is authoritative for;
    only stored events of those types can be flagged ``dropped``. It defaults to
    the types present in ``fetched`` — so an earnings-only fetch never spuriously
    drops an investor day it was never going to return. An empty fetch therefore
    covers nothing and drops nothing.
    """
    today = today or date.today().isoformat()
    if covered_types is None:
        covered_types = {e.get("type", "") for e in fetched}
    out: dict[str, list[dict[str, Any]]] = {
        "new": [],
        "moved": [],
        "status_changed": [],
        "unchanged": [],
        "dropped": [],
    }

    stored_by_slot = {slot_key(e): e for e in stored}
    matched: set[tuple[str, str]] = set()
    leftover_fetched: list[dict[str, Any]] = []

    for fe in fetched:
        k = slot_key(fe)
        se = stored_by_slot.get(k)
        if se is None:
            leftover_fetched.append(fe)
            continue
        matched.add(k)
        if (se.get("date") or "") != (fe.get("date") or ""):
            out["moved"].append(_record(fe, old_date=se.get("date"), new_date=fe.get("date")))
        elif (se.get("status") or "") != (fe.get("status") or ""):
            out["status_changed"].append(
                _record(fe, old_status=se.get("status"), new_status=fe.get("status"))
            )
        else:
            out["unchanged"].append(_record(fe))

    # Only stored events of a covered type are candidates for move-pairing/drop.
    leftover_stored = [
        e
        for e in stored
        if slot_key(e) not in matched and e.get("type", "") in covered_types
    ]

    # Fallback move-pairing: for a given type, if exactly one future-dated
    # event is left over on each side, treat it as a moved date rather than a
    # new+dropped pair (the common "next earnings date slipped" case).
    leftover_stored = _pair_moves(leftover_fetched, leftover_stored, out, today)

    for fe in leftover_fetched:
        out["new"].append(_record(fe))
    for se in leftover_stored:
        if (se.get("date") or "") >= today:  # only future events can "disappear"
            out["dropped"].append(_record(se))

    return out


def _pair_moves(leftover_fetched, leftover_stored, out, today):
    """Pair single future leftovers of the same type as moves. Mutates the lists."""
    by_type_fetched: dict[str, list] = {}
    by_type_stored: dict[str, list] = {}
    for fe in leftover_fetched:
        if (fe.get("date") or "") >= today:
            by_type_fetched.setdefault(fe.get("type", ""), []).append(fe)
    for se in leftover_stored:
        if (se.get("date") or "") >= today:
            by_type_stored.setdefault(se.get("type", ""), []).append(se)

    still_stored = list(leftover_stored)
    for etype, fes in by_type_fetched.items():
        ses = by_type_stored.get(etype, [])
        if len(fes) == 1 and len(ses) == 1:
            fe, se = fes[0], ses[0]
            out["moved"].append(_record(fe, old_date=se.get("date"), new_date=fe.get("date")))
            leftover_fetched.remove(fe)
            still_stored.remove(se)
    return still_stored


def apply_fetched(store, ticker: str, fetched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upsert fetched events into the stored set; return the merged list."""
    events = store.read_events(ticker)
    index = {slot_key(e): i for i, e in enumerate(events)}
    for fe in fetched:
        norm = normalize_event(fe)
        if fe.get("ref"):
            norm["ref"] = fe["ref"]
        k = slot_key(norm)
        if k in index:
            events[index[k]] = {**events[index[k]], **norm}
        else:
            events.append(norm)
            index[k] = len(events) - 1
    store.write_events(ticker, events)
    return events


def has_changes(diff: dict[str, list]) -> bool:
    return any(diff[k] for k in ("new", "moved", "status_changed", "dropped"))


# --- orchestration (pure given a fetcher) -----------------------------------


def monitor(
    store,
    tickers: list[str],
    fetcher: Callable[[str], list[dict[str, Any]]],
    today: str | None = None,
) -> dict[str, Any]:
    """Run the monitor over tickers. ``fetcher(ticker)`` returns fresh events.

    Writes a snapshot of all events and a changes record; returns the change
    summary.
    """
    today = today or date.today().isoformat()
    per_ticker_changes: dict[str, Any] = {}
    snapshot: dict[str, Any] = {"date": today, "events": {}}

    for ticker in tickers:
        stored = store.read_events(ticker)
        try:
            fetched = fetcher(ticker) or []
        except Exception as exc:  # a single ticker's fetch failure must not abort the run
            per_ticker_changes[ticker] = {"error": str(exc)}
            snapshot["events"][ticker] = stored
            continue

        diff = diff_ticker(stored, fetched, today=today)
        merged = apply_fetched(store, ticker, fetched)
        snapshot["events"][ticker] = merged
        if has_changes(diff):
            per_ticker_changes[ticker] = {k: v for k, v in diff.items() if v and k != "unchanged"}

    store.write_snapshot(today, snapshot)
    summary = {
        "date": today,
        "tickers_checked": len(tickers),
        "tickers_with_changes": len(per_ticker_changes),
        "changes": per_ticker_changes,
    }
    store.write_changes(today, summary)
    return summary


# --- roster ------------------------------------------------------------------


def active_tickers(store) -> list[str]:
    """Active tickers from the roster CSV (active != 'false')."""
    path = store.universe_csv_path()
    if not path.exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("active", "true") or "true").lower() != "false":
                t = (row.get("ticker_symbol") or "").strip().upper()
                if t:
                    out.append(t)
    return out


# --- real fetch layer (HTTP) -------------------------------------------------


def _http_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "company-universe-manager"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted FMP host)
        return json.loads(resp.read().decode("utf-8"))


def fetch_fmp_earnings(
    ticker: str,
    api_key: str,
    today: str | None = None,
    http: Callable[[str], Any] = _http_json,
) -> list[dict[str, Any]]:
    """Upcoming earnings dates for a ticker from FMP's historical earning calendar.

    FMP returns past and (estimated) future entries; we keep today-or-later ones
    as estimated earnings events keyed by fiscal period end (``ref``).
    """
    today = today or date.today().isoformat()
    url = f"{FMP_BASE}/historical/earning_calendar/{ticker}?apikey={api_key}"
    rows = http(url)
    if not isinstance(rows, list):
        return []
    events = []
    for row in rows:
        ann = row.get("date")
        if not ann or ann < today:
            continue
        events.append(
            {
                "type": "earnings",
                "date": ann,
                "status": "estimated",
                "source": "FMP",
                "ref": row.get("fiscalDateEnding") or ann,
                "fetched_at": today,
            }
        )
    return events


def main() -> int:
    store = load_store()
    store.ensure_layout()
    tickers = active_tickers(store)
    if not tickers:
        print(json.dumps({"error": "no active tickers in roster", "root": str(store.root)}))
        return 1

    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        print(json.dumps({"error": "FMP_API_KEY not set; cannot fetch earnings dates"}))
        return 1

    def fetcher(ticker: str) -> list[dict[str, Any]]:
        return fetch_fmp_earnings(ticker, api_key)

    summary = monitor(store, tickers, fetcher)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
