"""Offline tests for the market-intelligence skill.

These NEVER call the SerpAPI / Google Trends API (quota is 100/month). They run
entirely against recorded JSON response envelopes in tests/fixtures/, produced
once by two live calls on 2026-06-12 (see plan section 6):
  - vsco_12m_weekly.json : q="victoria's secret" date="today 12-m" geo=US (weekly)
  - vsco_3m_daily.json   : q="victoria's secret" date="today 3-m"  geo=US (daily)

Run from the skill folder:  pytest tests -q
"""
import json
import os
import sys
from datetime import date

import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
sys.path.insert(0, SCRIPTS)

import trends_client as tc  # noqa: E402
import quarterly_index as qi  # noqa: E402


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


WEEKLY = load_fixture("vsco_12m_weekly.json")
DAILY = load_fixture("vsco_3m_daily.json")


# --- parsing / provenance ---------------------------------------------------

def test_parse_weekly_rows_and_provenance():
    rows, gran = tc.parse_rows(WEEKLY)
    assert gran == "weekly"
    assert len(rows) == 53
    # every row carries the section-2.6 provenance columns
    for r in rows:
        assert r["keyword"] == "victoria's secret"
        assert isinstance(r["is_partial"], bool)
        assert r["fetched_at"].endswith("Z")
        assert r["geo"] == "US"
        assert r["date_range"] == "today 12-m"
        assert r["granularity"] == "weekly"


def test_timestamp_parsed_not_date_string():
    rows, _ = tc.parse_rows(WEEKLY)
    # bucket_start derives from the Unix timestamp; weeks start on Sunday.
    first = date.fromisoformat(rows[0]["bucket_start"])
    assert first.weekday() == 6  # Sunday (Mon=0..Sun=6)
    assert rows[0]["bucket_start"] == "2025-06-08"


def test_extracted_value_is_int():
    rows, _ = tc.parse_rows(WEEKLY)
    assert all(isinstance(r["value"], int) for r in rows)


# --- partial-bucket handling ------------------------------------------------

def test_last_weekly_bucket_is_partial():
    rows, _ = tc.parse_rows(WEEKLY)
    assert rows[-1]["is_partial"] is True
    assert all(r["is_partial"] is False for r in rows[:-1])


def test_drop_partial_removes_in_progress_bucket():
    kept, _ = tc.parse_rows(WEEKLY, drop_partial=False)
    dropped, _ = tc.parse_rows(WEEKLY, drop_partial=True)
    assert len(kept) - len(dropped) == 1
    assert all(r["is_partial"] is False for r in dropped)


def test_daily_last_bucket_is_today_partial():
    rows, gran = tc.parse_rows(DAILY)
    assert gran == "daily"
    assert rows[-1]["is_partial"] is True  # today's in-progress bucket


# --- granularity assertion --------------------------------------------------

def test_assert_granularity_infers_weekly_and_daily():
    wrows, _ = tc.parse_rows(WEEKLY)
    drows, _ = tc.parse_rows(DAILY)
    assert tc.assert_granularity(wrows) == "weekly"
    assert tc.assert_granularity(drows) == "daily"


def test_assert_granularity_mismatch_raises():
    drows, _ = tc.parse_rows(DAILY)
    # a daily response handed in where weekly was expected must fail loudly
    with pytest.raises(tc.TrendsError):
        tc.assert_granularity(drows, expected="weekly")


# --- overlap rescaling (Step 2) ---------------------------------------------

def test_overlap_factor_rescales_daily_onto_spine():
    spine_rows, _ = tc.parse_rows(WEEKLY)
    daily_rows, _ = tc.parse_rows(DAILY)
    spine = qi.spine_weekly_map(spine_rows)
    factor, n = qi.overlap_factor(spine, daily_rows)
    assert factor is not None and factor > 0
    assert n >= 4  # several fully-confirmed overlapping Sun-Sat weeks

    # after scaling, the daily->weekly sums should match the spine on overlap
    win_weekly = qi.daily_to_weekly(daily_rows)
    common = sorted(set(spine) & set(win_weekly))
    mean_spine = sum(spine[w] for w in common) / len(common)
    mean_scaled = sum(win_weekly[w] * factor for w in common) / len(common)
    assert mean_scaled == pytest.approx(mean_spine, rel=1e-9)


def test_daily_to_weekly_only_keeps_full_weeks():
    daily_rows, _ = tc.parse_rows(DAILY)
    weekly = qi.daily_to_weekly(daily_rows)
    # all retained weeks must be Sunday-keyed
    assert all(ws.weekday() == 6 for ws in weekly)


# --- fiscal-quarter aggregation across a straddling week --------------------

def test_fiscal_quarter_ends_for_jan31_fye():
    ends = qi.fiscal_quarter_ends(1, 31, date(2025, 1, 1), date(2026, 6, 30))
    months = sorted({d.month for d in ends})
    # Jan-31 FYE -> quarter-ends approximated at end of Jan, Apr, Jul, Oct
    assert months == [1, 4, 7, 10]


def test_quarter_label_numbering():
    # For a Jan-31 FYE: the quarter ending Apr is Q1, Jul Q2, Oct Q3, Jan Q4.
    assert qi.quarter_label(date(2026, 4, 30), 1).endswith("Q1")
    assert qi.quarter_label(date(2026, 1, 31), 1).endswith("Q4")


def test_aggregate_drops_partial_buckets_in_index():
    # Build a synthetic stitched dict spanning a fiscal-quarter boundary with a
    # straddling Sun-Sat week and a partial bucket; the index must exclude the
    # partial day but still flag the quarter partial.
    stitched = {}
    base = "victoria's secret"
    # quarter ending 2026-01-31; days around the boundary
    for d, v, partial in [
        (date(2026, 1, 29), 10.0, False),
        (date(2026, 1, 30), 12.0, False),
        (date(2026, 1, 31), 8.0, False),
        (date(2026, 2, 1), 9.0, False),
        (date(2026, 2, 2), 11.0, True),   # partial -> must be dropped from index
    ]:
        stitched[d] = {
            "value": v, "is_partial": partial, "keyword": base,
            "fetched_at": "2026-06-12T12:00:00Z", "bucket_start": d.isoformat(),
        }
    quarters, current = qi.aggregate_quarters(stitched, 1, 31, 5, date(2026, 6, 12))
    by_label = {q["fiscal_quarter"]: q for q in quarters}
    # Jan-31 quarter index = 10+12+8 = 30 (Feb days fall in the next quarter)
    q_jan = [q for q in quarters if q["quarter_end"] == "2026-01-31"][0]
    assert q_jan["index"] == 30.0
    # the Feb quarter: only the confirmed Feb 1 (9.0) counts; Feb 2 is partial
    q_apr = [q for q in quarters if q["quarter_end"] == "2026-04-30"][0]
    assert q_apr["index"] == 9.0
    assert q_apr["is_partial"] is True  # contains a partial bucket


# --- explore URLs (manual mode, zero quota) ---------------------------------

def test_explore_url_preserves_plus_union_operator():
    url = tc.explore_url("lingerie + victoria's secret", date="today 5-y", geo="US")
    assert url.startswith("https://trends.google.com/trends/explore?")
    assert "geo=US" in url
    # the '+' union operator must be percent-encoded as %2B: a literal '+' in a
    # URL query decodes to a SPACE in browsers, which would destroy the union.
    assert "lingerie%20%2B%20victoria" in url
    assert "+" not in url.split("q=")[1].split("&")[0]  # no raw '+' in the q value


# --- cache freshness logic --------------------------------------------------

def test_cache_envelope_with_partial_expires(monkeypatch):
    # a weekly envelope containing a partial bucket is mutable -> expirable
    assert tc._has_partial(WEEKLY["raw_response"]) is True
    stale = dict(WEEKLY)
    stale["fetched_at"] = "2000-01-01T00:00:00Z"
    assert tc._cache_expired(stale) is True


def test_cache_envelope_absolute_closed_window_never_expires():
    # a synthetic absolute-range envelope with no partial bucket is fresh forever
    env = {
        "fetched_at": "2000-01-01T00:00:00Z",
        "request_params": {"q": "x", "date": "2024-01-01 2024-03-01", "geo": "US"},
        "raw_response": {"interest_over_time": {"timeline_data": [
            {"timestamp": "1704067200", "values": [{"query": "x", "extracted_value": 5}]}
        ]}},
    }
    assert tc._cache_expired(env) is False
