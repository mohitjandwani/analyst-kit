"""Polars transform tests — the financial-correctness rules in isolation."""
import math

from pipeline import process


# --- scaling -------------------------------------------------------------

def test_pick_scale_billions(aapl_income):
    rev = [r["revenue"] for r in aapl_income]
    assert process.pick_scale(rev) == (1e9, "B")


def test_pick_scale_uses_max_abs():
    assert process.pick_scale([5_000, -2_400_000_000]) == (1e9, "B")


def test_pick_scale_empty_and_zero():
    assert process.pick_scale([]) == (1.0, "")
    assert process.pick_scale([0, None, 0]) == (1.0, "")


def test_scale_preserves_none():
    assert process.scale([2e9, None, 4e9], 1e9) == [2.0, None, 4.0]


# --- transforms ----------------------------------------------------------

def test_yoy_annual_matches_manual(aapl_income):
    rev = [r["revenue"] for r in sorted(aapl_income, key=lambda r: r["date"])]
    growth = process.yoy(rev, lag=1)
    assert growth[0] is None
    assert math.isclose(growth[1], (rev[1] / rev[0] - 1) * 100, abs_tol=1e-4)


def test_yoy_quarterly_lag4(aapl_income_q):
    rev = [r["revenue"] for r in sorted(aapl_income_q, key=lambda r: r["date"])]
    growth = process.yoy(rev, lag=4)
    assert growth[:4] == [None, None, None, None]
    assert math.isclose(growth[4], (rev[4] / rev[0] - 1) * 100, abs_tol=1e-4)


def test_yoy_guards_zero_and_none():
    assert process.yoy([0, 100], lag=1) == [None, None]
    assert process.yoy([100, None, 121], lag=1) == [None, None, None]


def test_rebase_starts_at_100():
    r = process.rebase([200, 220, 240])
    assert r[0] == 100.0 and r[2] == 120.0


def test_cagr():
    assert math.isclose(process.cagr(100, 200, 5), 14.8698, abs_tol=1e-3)
    assert process.cagr(100, 200, 0) is None


def test_margin(aapl_income):
    row = sorted(aapl_income, key=lambda r: r["date"])[-1]
    m = process.margin(row["netIncome"], row["revenue"])
    assert 0 < m < 100
    assert process.margin(10, 0) is None


# --- segments ------------------------------------------------------------

def test_segment_matrix_windows_and_drops_legacy(aapl_segmentation):
    periods, segs = process.segment_matrix(aapl_segmentation, n=5)
    assert len(periods) == 5
    # Recent AAPL reports 5 product segments; legacy all-zero ones are dropped.
    assert len(segs) == 5
    assert "iPhone" in segs
    # Ordered largest-first.
    totals = [sum(v) for v in segs.values()]
    assert totals == sorted(totals, reverse=True)


def test_segment_matrix_missing_is_zero():
    recs = [
        {"fiscalYear": 2023, "data": {"A": 10, "B": 5}},
        {"fiscalYear": 2024, "data": {"A": 12}},  # B not reported → real 0
    ]
    periods, segs = process.segment_matrix(recs, n=5)
    assert segs["B"] == [5, 0]


# --- waterfall reconciliation -------------------------------------------

def test_waterfall_steps_reconcile(aapl_income):
    row = sorted(aapl_income, key=lambda r: r["date"])[-1]
    steps = process.waterfall_steps(row)
    # Sum of every signed delta + the Revenue start must equal net income.
    total = sum(s["y"] for s in steps if "y" in s)
    assert math.isclose(total, row["netIncome"], rel_tol=1e-9)
    # Subtotals are intermediate sums; the final is a sum.
    assert steps[2]["isIntermediateSum"] and steps[4]["isIntermediateSum"]
    assert steps[-1]["isSum"]
    # Deltas are signed negatives (costs).
    assert steps[1]["y"] < 0 and steps[1]["role"] == "negative"
    # Non-operating items and taxes are split into their own steps.
    names = [s["name"] for s in steps]
    assert "Non-op income/exp" in names and "Taxes & other" in names


# --- axis resolution -----------------------------------------------------

def test_x_kind():
    assert process.x_kind("2025-09-27") == "datetime"
    assert process.x_kind("FY2025") == "category"
    assert process.x_kind("Q3'25") == "category"


def test_resolve_axis():
    assert process.resolve_axis(["category", "category"]) == "category"
    assert process.resolve_axis(["datetime", "datetime"]) == "datetime"
    # Mixed but mappable → prefer the richer datetime axis.
    assert process.resolve_axis(["category", "datetime"]) == "datetime"


def test_to_millis_and_quarter_label():
    assert process.to_millis("2025-01-01") == 1735689600000
    assert process.quarter_label("2026-04-30") == "Q2'26"


def test_fiscal_to_datetime_spans_consecutive_periods():
    recs = [{"date": "2024-03-30"}, {"date": "2024-06-29"}, {"date": "2024-09-28"}]
    spans = process.fiscal_to_datetime(recs)
    assert len(spans) == 3
    # each period's start is the previous period's end + 1 day
    assert spans[1]["start"] == spans[0]["end"] + 86_400_000
    assert spans[2]["start"] == spans[1]["end"] + 86_400_000
    # the midpoint sits inside the span
    assert spans[0]["start"] < spans[0]["mid"] < spans[0]["end"]
