"""Tests for per-ticker event CRUD (upsert identity, remove, list, validation)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from events_manager import (
    list_events,
    normalize_event,
    remove_event,
    upsert_event,
)
from storage import LocalStore


@pytest.fixture
def store(tmp_path):
    s = LocalStore(tmp_path / "cu")
    s.ensure_layout()
    return s


def test_normalize_drops_unknown_fields_and_defaults_status():
    e = normalize_event({"type": "earnings", "date": "2026-07-31", "junk": "x"})
    assert "junk" not in e
    assert e["status"] == "estimated"


def test_upsert_adds_then_updates_same_type_date(store):
    action, _ = upsert_event(store, "AAPL", {"type": "earnings", "date": "2026-07-31"})
    assert action == "added"
    # Same (type, date) → update in place, not a duplicate
    action, saved = upsert_event(
        store, "AAPL", {"type": "earnings", "date": "2026-07-31", "status": "confirmed", "note": "x"}
    )
    assert action == "updated"
    assert saved["status"] == "confirmed" and saved["note"] == "x"
    assert len(store.read_events("AAPL")) == 1


def test_upsert_different_date_is_new_event(store):
    upsert_event(store, "AAPL", {"type": "earnings", "date": "2026-07-31"})
    upsert_event(store, "AAPL", {"type": "earnings", "date": "2026-10-30"})
    assert len(store.read_events("AAPL")) == 2


def test_remove_event(store):
    upsert_event(store, "AAPL", {"type": "earnings", "date": "2026-07-31"})
    assert remove_event(store, "AAPL", "earnings", "2026-07-31") is True
    assert remove_event(store, "AAPL", "earnings", "2026-07-31") is False
    assert store.read_events("AAPL") == []


def test_list_upcoming_filters_past(store):
    upsert_event(store, "AAPL", {"type": "earnings", "date": "2020-01-01"})
    upsert_event(store, "AAPL", {"type": "earnings", "date": "2999-01-01"})
    upcoming = list_events(store, "AAPL", upcoming_only=True)
    assert [e["date"] for e in upcoming] == ["2999-01-01"]
    assert len(list_events(store, "AAPL", upcoming_only=False)) == 2
