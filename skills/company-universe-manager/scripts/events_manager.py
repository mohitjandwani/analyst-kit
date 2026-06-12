#!/usr/bin/env python3
"""
Per-ticker key-date (event) CRUD for the company universe.

A company has many dated events; they live in ``events/<TICKER>.json`` (managed
through ``storage.LocalStore``). An event is identified for upsert purposes by
the pair ``(type, date)`` — re-adding the same type+date updates that event in
place rather than duplicating it, which is what the monitor relies on when a
date is re-confirmed.

Event record:
    {
        "type":       earnings | investor_day | ex_dividend | agm |
                      conference | guidance | lockup_expiry |
                      index_rebalance | other,
        "date":       "YYYY-MM-DD",
        "status":     confirmed | estimated | tentative,
        "source":     short source label (e.g. "FMP", "SEC-8K", "IR-page"),
        "source_url": reference URL (optional),
        "fetched_at": "YYYY-MM-DD" the value was recorded (optional),
        "note":       free text (optional)
    }

Pure standard library.
"""

from __future__ import annotations

import sys
from datetime import date
from typing import Any

from storage import load_store

EVENT_TYPES = (
    "earnings",
    "investor_day",
    "ex_dividend",
    "agm",
    "conference",
    "guidance",
    "lockup_expiry",
    "index_rebalance",
    "other",
)

STATUSES = ("confirmed", "estimated", "tentative")

# Fields an event may carry; anything else is dropped on upsert.
EVENT_FIELDS = ("type", "date", "status", "source", "source_url", "fetched_at", "note")


def _key(event: dict[str, Any]) -> tuple[str, str]:
    """Identity of an event for upsert: (type, date)."""
    return (event.get("type", ""), event.get("date", ""))


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only known fields; default status to 'estimated'."""
    event = {k: raw[k] for k in EVENT_FIELDS if k in raw and raw[k] != ""}
    event.setdefault("status", "estimated")
    return event


def upsert_event(store, ticker: str, event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Add a new event or update the existing (type, date) match.

    Returns (action, event) where action is 'added' or 'updated'.
    """
    event = normalize_event(event)
    events = store.read_events(ticker)
    target = _key(event)
    for i, existing in enumerate(events):
        if _key(existing) == target:
            merged = {**existing, **event}
            events[i] = merged
            store.write_events(ticker, events)
            return "updated", merged
    events.append(event)
    store.write_events(ticker, events)
    return "added", event


def remove_event(store, ticker: str, event_type: str, event_date: str) -> bool:
    """Delete the event matching (type, date). Returns True if one was removed."""
    events = store.read_events(ticker)
    kept = [e for e in events if _key(e) != (event_type, event_date)]
    if len(kept) == len(events):
        return False
    store.write_events(ticker, kept)
    return True


def list_events(store, ticker: str, upcoming_only: bool = False) -> list[dict[str, Any]]:
    """Return a ticker's events, optionally only those dated today or later."""
    events = store.read_events(ticker)
    if upcoming_only:
        today = date.today().isoformat()
        events = [e for e in events if (e.get("date") or "") >= today]
    return events


def _parse_kv(args: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            out[key] = value
    return out


def _validate(event: dict[str, Any]) -> str | None:
    if event.get("type") not in EVENT_TYPES:
        return f"type must be one of {', '.join(EVENT_TYPES)}"
    if event.get("status") not in STATUSES:
        return f"status must be one of {', '.join(STATUSES)}"
    d = event.get("date", "")
    try:
        date.fromisoformat(d)
    except ValueError:
        return f"date must be YYYY-MM-DD, got {d!r}"
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage:\n"
            "  events_manager.py add <ticker> type=earnings date=2026-07-31 "
            "[status=confirmed source=FMP source_url=... note=...]\n"
            "  events_manager.py list <ticker> [--upcoming]\n"
            "  events_manager.py remove <ticker> <type> <date>\n"
            "\nSet COMPANY_UNIVERSE_HOME to target a store other than ~/company-universe.",
            file=sys.stderr,
        )
        return 1

    action = sys.argv[1]
    ticker = sys.argv[2].upper()
    store = load_store()
    store.ensure_layout()

    if action == "add":
        event = normalize_event(_parse_kv(sys.argv[3:]))
        err = _validate(event)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
        event.setdefault("fetched_at", date.today().isoformat())
        what, saved = upsert_event(store, ticker, event)
        print(f"{what} {ticker} {saved['type']} {saved['date']} ({saved['status']})")
        return 0

    if action == "list":
        upcoming = "--upcoming" in sys.argv
        events = list_events(store, ticker, upcoming_only=upcoming)
        if not events:
            print(f"No events for {ticker}")
            return 0
        print(f"{'Date':<12} {'Type':<16} {'Status':<10} Source")
        print("-" * 56)
        for e in events:
            print(
                f"{e.get('date',''):<12} {e.get('type',''):<16} "
                f"{e.get('status',''):<10} {e.get('source','')}"
            )
        return 0

    if action == "remove":
        if len(sys.argv) < 5:
            print("ERROR: remove requires <type> <date>", file=sys.stderr)
            return 1
        ok = remove_event(store, ticker, sys.argv[3], sys.argv[4])
        print("removed" if ok else "no matching event")
        return 0 if ok else 1

    print(f"ERROR: unknown action {action!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
