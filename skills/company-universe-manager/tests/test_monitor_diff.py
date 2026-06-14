"""
Tests for the date-change detection — the core of the daily monitor.

All offline: the fetch layer is injected, so these pin the diff semantics
(new / moved / status_changed / dropped) and the covered-types rule that keeps
an earnings-only fetch from spuriously dropping an investor day every day.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from monitor_dates import apply_fetched, diff_ticker, has_changes, monitor, slot_key
from storage import LocalStore

TODAY = "2026-06-12"


@pytest.fixture
def store(tmp_path):
    s = LocalStore(tmp_path / "cu")
    s.ensure_layout()
    return s


def earn(date, status="estimated", ref=None):
    e = {"type": "earnings", "date": date, "status": status, "source": "FMP"}
    if ref:
        e["ref"] = ref
    return e


# --- diff semantics ---------------------------------------------------------


def test_new_event_detected():
    diff = diff_ticker([], [earn("2026-07-31", ref="Q3")], today=TODAY)
    assert len(diff["new"]) == 1 and not diff["moved"]


def test_moved_by_ref_takes_precedence_over_status():
    stored = [earn("2026-07-30", "estimated", ref="Q3")]
    fetched = [earn("2026-07-31", "confirmed", ref="Q3")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert len(diff["moved"]) == 1
    assert diff["moved"][0]["old_date"] == "2026-07-30"
    assert diff["moved"][0]["new_date"] == "2026-07-31"
    assert not diff["status_changed"]  # date change reported, not status


def test_status_change_when_date_unchanged():
    stored = [earn("2026-07-31", "estimated", ref="Q3")]
    fetched = [earn("2026-07-31", "confirmed", ref="Q3")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert len(diff["status_changed"]) == 1
    assert diff["status_changed"][0]["old_status"] == "estimated"
    assert diff["status_changed"][0]["new_status"] == "confirmed"


def test_unchanged_event_is_not_a_change():
    stored = [earn("2026-07-31", "confirmed", ref="Q3")]
    diff = diff_ticker(stored, list(stored), today=TODAY)
    assert not has_changes(diff)
    assert len(diff["unchanged"]) == 1


def test_move_pairing_without_ref():
    """A single future earnings on each side with no ref still pairs as a move."""
    stored = [earn("2026-07-30")]
    fetched = [earn("2026-08-06")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert len(diff["moved"]) == 1 and not diff["new"] and not diff["dropped"]


def test_genuine_cancellation_is_dropped():
    """Two stored earnings; a fetch that returns only one drops the other."""
    stored = [earn("2026-07-29", ref="Q2"), earn("2026-10-28", ref="Q3")]
    fetched = [earn("2026-07-29", ref="Q2")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert [d["ref"] for d in diff["dropped"]] == ["Q3"]


def test_uncovered_type_is_never_dropped():
    """An earnings-only fetch must not drop a stored investor_day."""
    stored = [
        earn("2026-07-31", ref="Q3"),
        {"type": "investor_day", "date": "2026-09-15", "status": "confirmed", "source": "IR"},
    ]
    fetched = [earn("2026-08-01", ref="Q3")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert diff["dropped"] == []
    assert len(diff["moved"]) == 1


def test_past_event_not_dropped():
    """Only future-dated stored events can 'disappear'; past ones are history."""
    stored = [earn("2020-01-01", ref="old"), earn("2026-07-31", ref="Q3")]
    fetched = [earn("2026-07-31", ref="Q3")]
    diff = diff_ticker(stored, fetched, today=TODAY)
    assert diff["dropped"] == []


# --- apply + orchestration --------------------------------------------------


def test_apply_fetched_upserts_by_slot(store):
    store.write_events("AAPL", [earn("2026-07-30", "estimated", ref="Q3")])
    apply_fetched(store, "AAPL", [earn("2026-08-01", "confirmed", ref="Q3"), earn("2026-10-30", ref="Q4")])
    events = store.read_events("AAPL")
    assert len(events) == 2  # Q3 updated in place, Q4 appended
    q3 = next(e for e in events if e.get("ref") == "Q3")
    assert q3["date"] == "2026-08-01" and q3["status"] == "confirmed"


def test_monitor_writes_snapshot_and_changes(store):
    store.write_events("AAPL", [earn("2026-07-30", ref="Q3")])

    def fetcher(t):
        return [earn("2026-08-01", "confirmed", ref="Q3")] if t == "AAPL" else []

    summary = monitor(store, ["AAPL"], fetcher, today=TODAY)
    assert summary["tickers_with_changes"] == 1
    assert "moved" in summary["changes"]["AAPL"]
    assert store.latest_snapshot()["date"] == TODAY
    assert (store.root / "changes" / f"{TODAY}.json").exists()


def test_monitor_fetch_error_does_not_abort(store):
    store.write_events("AAPL", [earn("2026-07-30", ref="Q3")])
    store.write_events("MSFT", [earn("2026-07-22", ref="Q3")])

    def fetcher(t):
        if t == "AAPL":
            raise RuntimeError("network down")
        return [earn("2026-07-22", ref="Q3")]

    summary = monitor(store, ["AAPL", "MSFT"], fetcher, today=TODAY)
    assert "error" in summary["changes"]["AAPL"]
    assert summary["tickers_checked"] == 2  # MSFT still processed


def test_slot_key_prefers_ref():
    assert slot_key(earn("2026-07-31", ref="Q3")) == ("earnings", "ref:Q3")
    assert slot_key(earn("2026-07-31")) == ("earnings", "date:2026-07-31")
