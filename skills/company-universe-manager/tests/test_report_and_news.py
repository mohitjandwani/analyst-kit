"""Tests for the report builder (pure) and news gather (graceful degradation)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from build_report import build_contract, build_markdown
from fetch_news import gather

TODAY = "2026-06-12"

CHANGES = {
    "date": TODAY,
    "changes": {
        "AAPL": {"moved": [{"type": "earnings", "old_date": "2026-07-30", "new_date": "2026-08-01"}]},
        "MSFT": {"new": [{"type": "earnings", "date": "2026-07-22"}]},
    },
}
UPCOMING = [{"date": "2026-06-25", "ticker": "AAPL", "type": "investor_day", "status": "confirmed"}]


def test_markdown_has_both_tables_and_change_rows():
    md = build_markdown(TODAY, CHANGES, UPCOMING)
    assert "## What changed today" in md
    assert "AAPL | earnings | date moved | 2026-07-30 | 2026-08-01" in md
    assert "2026-06-25 | AAPL | investor_day | confirmed" in md


def test_markdown_handles_no_changes():
    md = build_markdown(TODAY, {"date": TODAY, "changes": {}}, [])
    assert "_No earnings-date or investor-event changes detected._" in md


def test_contract_shape_is_renderable():
    c = build_contract(TODAY, CHANGES, UPCOMING)
    assert c["meta"]["title"].endswith(TODAY)
    assert c["references"]  # non-empty references required by reporting
    templates = [p["template"] for p in c["pages"]]
    assert templates[0] == "cover"
    assert "table-commentary" in templates
    # every table-commentary page carries the required slots
    for p in c["pages"]:
        if p["template"] == "table-commentary":
            s = p["slots"]
            assert {"title", "story", "table", "commentary"} <= set(s)
            assert s["table"]["columns"] and s["table"]["rows"]


def test_contract_change_rows_flattened():
    c = build_contract(TODAY, CHANGES, UPCOMING)
    changed = next(p for p in c["pages"] if p["slots"].get("title") == "What changed today")
    rows = changed["slots"]["table"]["rows"]
    assert any(r[0] == "AAPL" and r[1] == "earnings" for r in rows)


def test_gather_drops_empty_news_and_honors_no_key():
    def fake_news(tickers, api_key, *, from_date=None):
        return {"AAPL": [{"title": "x", "date": "2026-06-11"}], "MSFT": []}

    def fake_sec(t):
        return [{"date": "2026-06-10", "items": ["2.02"], "url": "u"}] if t == "AAPL" else []

    out = gather(["AAPL", "MSFT"], "key", today=TODAY, news_fetcher=fake_news, sec_fetcher=fake_sec)
    assert "AAPL" in out["news"] and "MSFT" not in out["news"]
    assert out["filings"]["AAPL"][0]["items"] == ["2.02"]

    no_key = gather(["AAPL"], None, today=TODAY, sec_fetcher=fake_sec)
    assert no_key["news"] == {}
    assert "AAPL" in no_key["filings"]
