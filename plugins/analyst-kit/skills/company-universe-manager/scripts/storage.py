#!/usr/bin/env python3
"""
Storage abstraction for the company universe.

The universe (a roster of companies) and its key dates (earnings, investor days,
ex-dividend, etc.) live behind a single ``UniverseStore`` contract so the source
of truth can be either a local folder or, eventually, a remote backend.

Only ``LocalStore`` is implemented in Python. A "remote" backend (e.g. a Google
Sheet reached over MCP) is *agent-mediated*: MCP tools live in the agent's tool
namespace and cannot be called from a subprocess, so the Python layer always
reads and writes the local folder as the working copy, and the agent syncs that
folder to/from the remote per the SKILL.md procedure. ``config.json`` records
which backend is canonical so the agent knows whether a remote sync is required.

Store layout (under the root, default ~/company-universe):

    config.json                   backend selection + remote descriptor
    universe.csv                  roster (managed by csv_manager.py)
    events/<TICKER>.json          per-ticker list of dated events
    snapshots/<YYYY-MM-DD>.json   point-in-time capture of all events
    changes/<YYYY-MM-DD>.json     date changes detected that day
    reports/daily-<YYYY-MM-DD>.*  generated reports

Pure standard library.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

# Roster column order is owned by csv_manager.py; storage only needs the path.
DEFAULT_ROOT = "~/company-universe"
ENV_HOME = "COMPANY_UNIVERSE_HOME"

# Canonical subdirectories of the store root.
SUBDIRS = ("events", "snapshots", "changes", "reports")

VALID_BACKENDS = ("local", "remote")


def resolve_root(root: str | os.PathLike | None = None) -> Path:
    """Resolve the store root: explicit arg > $COMPANY_UNIVERSE_HOME > default."""
    raw = root or os.environ.get(ENV_HOME) or DEFAULT_ROOT
    return Path(raw).expanduser().resolve()


class UniverseStore:
    """Contract for a universe backend.

    A future native remote backend (e.g. a Google Sheets adapter that does not
    go through MCP) should subclass this and implement the same methods so the
    monitor/report scripts work against it unchanged.
    """

    # --- roster ---------------------------------------------------------
    def universe_csv_path(self) -> Path:
        raise NotImplementedError

    # --- events ---------------------------------------------------------
    def read_events(self, ticker: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def write_events(self, ticker: str, events: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def all_event_tickers(self) -> list[str]:
        raise NotImplementedError

    # --- snapshots / changes -------------------------------------------
    def write_snapshot(self, day: str, data: dict[str, Any]) -> Path:
        raise NotImplementedError

    def latest_snapshot(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def write_changes(self, day: str, data: dict[str, Any]) -> Path:
        raise NotImplementedError

    # --- reports --------------------------------------------------------
    def write_report(self, day: str, content: str, fmt: str = "md") -> Path:
        raise NotImplementedError

    # --- config ---------------------------------------------------------
    def load_config(self) -> dict[str, Any]:
        raise NotImplementedError


class LocalStore(UniverseStore):
    """Filesystem-backed store under a root directory."""

    def __init__(self, root: str | os.PathLike | None = None):
        self.root = resolve_root(root)

    # --- lifecycle ------------------------------------------------------
    def ensure_layout(self) -> None:
        """Create the root and all canonical subdirectories if absent."""
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in SUBDIRS:
            (self.root / sub).mkdir(exist_ok=True)
        cfg = self.root / "config.json"
        if not cfg.exists():
            cfg.write_text(json.dumps(default_config(), indent=2) + "\n", encoding="utf-8")

    # --- roster ---------------------------------------------------------
    def universe_csv_path(self) -> Path:
        return self.root / "universe.csv"

    # --- events ---------------------------------------------------------
    def _events_path(self, ticker: str) -> Path:
        return self.root / "events" / f"{ticker.upper()}.json"

    def read_events(self, ticker: str) -> list[dict[str, Any]]:
        path = self._events_path(ticker)
        if not path.exists():
            return []
        return _read_json(path).get("events", [])

    def write_events(self, ticker: str, events: list[dict[str, Any]]) -> None:
        (self.root / "events").mkdir(parents=True, exist_ok=True)
        payload = {"ticker": ticker.upper(), "events": _sort_events(events)}
        _write_json(self._events_path(ticker), payload)

    def all_event_tickers(self) -> list[str]:
        events_dir = self.root / "events"
        if not events_dir.exists():
            return []
        return sorted(p.stem.upper() for p in events_dir.glob("*.json"))

    # --- snapshots / changes -------------------------------------------
    def write_snapshot(self, day: str, data: dict[str, Any]) -> Path:
        (self.root / "snapshots").mkdir(parents=True, exist_ok=True)
        path = self.root / "snapshots" / f"{day}.json"
        _write_json(path, data)
        return path

    def latest_snapshot(self) -> dict[str, Any] | None:
        snaps_dir = self.root / "snapshots"
        if not snaps_dir.exists():
            return None
        files = sorted(snaps_dir.glob("*.json"))
        if not files:
            return None
        return _read_json(files[-1])

    def write_changes(self, day: str, data: dict[str, Any]) -> Path:
        (self.root / "changes").mkdir(parents=True, exist_ok=True)
        path = self.root / "changes" / f"{day}.json"
        _write_json(path, data)
        return path

    # --- reports --------------------------------------------------------
    def write_report(self, day: str, content: str, fmt: str = "md") -> Path:
        (self.root / "reports").mkdir(parents=True, exist_ok=True)
        path = self.root / "reports" / f"daily-{day}.{fmt}"
        path.write_text(content, encoding="utf-8")
        return path

    # --- config ---------------------------------------------------------
    def load_config(self) -> dict[str, Any]:
        cfg = self.root / "config.json"
        if not cfg.exists():
            return default_config()
        data = _read_json(cfg)
        # Normalize: guarantee the keys downstream code relies on.
        merged = default_config()
        merged.update(data)
        if merged.get("backend") not in VALID_BACKENDS:
            merged["backend"] = "local"
        return merged


def default_config() -> dict[str, Any]:
    """The config a fresh store starts with: local backend, no remote."""
    return {
        "backend": "local",
        "remote": None,
    }


def load_store(root: str | os.PathLike | None = None) -> LocalStore:
    """Factory: the Python layer always returns a LocalStore (the working copy).

    The agent inspects ``store.load_config()['backend']`` to decide whether a
    remote sync is also required around script runs.
    """
    return LocalStore(root)


# --- helpers -----------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable order: by date then type, with undated/blank dates last."""
    return sorted(
        events,
        key=lambda e: (e.get("date") or "9999-99-99", e.get("type") or ""),
    )


def main() -> int:
    """Minimal CLI: initialize a store and report its config/paths."""
    import sys

    args = sys.argv[1:]
    action = args[0] if args else "info"
    root = args[1] if len(args) > 1 else None
    store = load_store(root)

    if action == "init":
        store.ensure_layout()
        print(f"Store initialized at {store.root}")
        return 0

    if action == "info":
        cfg = store.load_config()
        print(f"root:    {store.root}")
        print(f"backend: {cfg.get('backend')}")
        print(f"remote:  {cfg.get('remote')}")
        print(f"exists:  {store.root.exists()}")
        print(f"tickers with events: {len(store.all_event_tickers())}")
        return 0

    print(f"Usage: storage.py [init|info] [root]\nUnknown action: {action}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
