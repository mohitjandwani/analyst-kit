"""Tests for the storage abstraction (LocalStore round-trips, config, layout)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from storage import LocalStore, default_config, load_store, resolve_root


@pytest.fixture
def store(tmp_path):
    s = LocalStore(tmp_path / "cu")
    s.ensure_layout()
    return s


def test_ensure_layout_creates_subdirs_and_config(store):
    for sub in ("events", "snapshots", "changes", "reports"):
        assert (store.root / sub).is_dir()
    assert (store.root / "config.json").exists()
    assert store.load_config()["backend"] == "local"


def test_events_round_trip_and_sorted(store):
    store.write_events(
        "aapl",
        [
            {"type": "investor_day", "date": "2026-09-15", "status": "confirmed"},
            {"type": "earnings", "date": "2026-07-31", "status": "estimated"},
        ],
    )
    events = store.read_events("AAPL")  # case-insensitive
    assert [e["date"] for e in events] == ["2026-07-31", "2026-09-15"]  # date-sorted
    assert store.all_event_tickers() == ["AAPL"]


def test_read_events_missing_ticker_is_empty(store):
    assert store.read_events("NOPE") == []


def test_snapshot_latest_returns_newest(store):
    store.write_snapshot("2026-06-10", {"date": "2026-06-10", "events": {}})
    store.write_snapshot("2026-06-12", {"date": "2026-06-12", "events": {"AAPL": []}})
    store.write_snapshot("2026-06-11", {"date": "2026-06-11", "events": {}})
    assert store.latest_snapshot()["date"] == "2026-06-12"


def test_latest_snapshot_none_when_empty(store):
    assert store.latest_snapshot() is None


def test_write_report_and_changes_paths(store):
    md = store.write_report("2026-06-12", "# hi\n", fmt="md")
    assert md.name == "daily-2026-06-12.md"
    assert md.read_text().startswith("# hi")
    ch = store.write_changes("2026-06-12", {"date": "2026-06-12", "changes": {}})
    assert ch.name == "2026-06-12.json"


def test_config_defaults_and_normalization(tmp_path):
    s = LocalStore(tmp_path / "cu2")
    s.ensure_layout()
    # corrupt backend value should normalize back to "local"
    (s.root / "config.json").write_text('{"backend": "bogus"}', encoding="utf-8")
    assert s.load_config()["backend"] == "local"
    assert default_config()["remote"] is None


def test_resolve_root_prefers_explicit_then_env(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANY_UNIVERSE_HOME", str(tmp_path / "envhome"))
    assert resolve_root(tmp_path / "explicit") == (tmp_path / "explicit").resolve()
    assert resolve_root(None) == (tmp_path / "envhome").resolve()


def test_load_store_returns_localstore(tmp_path):
    assert isinstance(load_store(tmp_path), LocalStore)
