#!/usr/bin/env python3
"""Polars transforms shared by every chart builder.

These encode the financial-correctness rules (one unit per axis, YoY momentum,
rebasing for comparison, segment pivots, waterfall reconciliation, axis
resolution). They are pure functions over lists / Polars frames so they can be
unit-tested in isolation (`pipeline/tests/test_process.py`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Sequence

import polars as pl

# Largest-first; the first threshold the abs-max clears wins.
_MAGNITUDES: list[tuple[float, str]] = [
    (1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"), (1.0, ""),
]


# --- scaling: one unit per axis ------------------------------------------

def pick_scale(values: Sequence[float | None]) -> tuple[float, str]:
    """Pick ONE (divisor, suffix) for a whole series group from its max abs value."""
    vals = [abs(v) for v in values if v is not None]
    if not vals:
        return 1.0, ""
    peak = max(vals)
    for divisor, suffix in _MAGNITUDES:
        if peak >= divisor:
            return divisor, suffix
    return 1.0, ""


def scale(values: Sequence[float | None], divisor: float, ndigits: int = 4) -> list[float | None]:
    return [None if v is None else round(v / divisor, ndigits) for v in values]


# --- transforms ----------------------------------------------------------

def yoy(values: Sequence[float | None], lag: int = 1) -> list[float | None]:
    """Year-over-year % change (Polars), lag = periods/year. Leading gaps are None;
    a zero or missing prior period yields None rather than inf."""
    s = pl.Series("v", [None if v is None else float(v) for v in values], dtype=pl.Float64)
    df = pl.DataFrame({"v": s}).with_columns(prior=pl.col("v").shift(lag)).with_columns(
        yoy=pl.when(
            pl.col("prior").is_null() | (pl.col("prior") == 0) | pl.col("v").is_null()
        )
        .then(None)
        .otherwise((pl.col("v") / pl.col("prior") - 1) * 100)
    )
    return [None if v is None else round(v, 4) for v in df["yoy"].to_list()]


def rebase(values: Sequence[float | None], base: float = 100.0) -> list[float | None]:
    """Index a series to `base` at its first non-null point (compare unequal sizes)."""
    anchor = next((v for v in values if v not in (None, 0)), None)
    if anchor is None:
        return [None for _ in values]
    return [None if v is None else round(v / anchor * base, 4) for v in values]


def cagr(first: float, last: float, years: float) -> float | None:
    if years <= 0 or first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


def margin(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


# --- frames / windowing --------------------------------------------------

def frame(records: list[dict]) -> pl.DataFrame:
    """Records → Polars frame sorted oldest → newest by `date`."""
    return pl.DataFrame(records, infer_schema_length=None).sort("date")


def lookback(df: pl.DataFrame, n: int | None) -> pl.DataFrame:
    """Keep the most recent `n` rows (5y annual / 8q quarterly default upstream)."""
    return df if not n else df.tail(n)


def segment_matrix(seg_records: list[dict], n: int | None) -> tuple[list[str], dict[str, list[float]]]:
    """Pivot revenue segmentation into period × segment, newest `n` periods.

    Windows to the last `n` fiscal years *first*, then pivots — so legacy segments
    a company no longer reports don't survive as all-zero columns. Segments absent
    in a kept period become a real 0 (not a gap). Segments are ordered largest-first
    so the stack reads top-down by size.
    """
    recs = sorted(seg_records, key=lambda x: x["fiscalYear"])
    if n:
        keep_years = sorted({r["fiscalYear"] for r in recs})[-n:]
        recs = [r for r in recs if r["fiscalYear"] in keep_years]
    rows = []
    for r in recs:
        for seg, val in (r.get("data") or {}).items():
            rows.append({"period": f"FY{r['fiscalYear']}", "segment": seg, "value": val})
    long = pl.DataFrame(rows)
    wide = (long.pivot(index="period", on="segment", values="value", aggregate_function="sum")
            .sort("period").fill_null(0))
    # Drop segments that are zero across the whole window, order the rest by total size.
    seg_cols = [c for c in wide.columns if c != "period"]
    totals = {c: abs(wide[c].sum()) for c in seg_cols}
    ordered = [c for c in sorted(seg_cols, key=lambda c: totals[c], reverse=True) if totals[c] > 0]
    periods = wide["period"].to_list()
    segments = {c: wide[c].to_list() for c in ordered}
    return periods, segments


def waterfall_steps(row: dict) -> list[dict]:
    """Revenue → net income bridge as native-Highcharts waterfall points.

    `delta` points carry a signed `y`; sum points (`isIntermediateSum`/`isSum`)
    let Highcharts compute the running level. The deltas must reconcile to net
    income — verified in tests.
    """
    revenue = row["revenue"]
    gross = row["grossProfit"]
    op_income = row["operatingIncome"]
    pretax = row.get("incomeBeforeTax", op_income)  # fall back if not reported
    net = row["netIncome"]
    return [
        {"name": "Revenue", "y": revenue, "role": "total"},
        {"name": "COGS", "y": -(revenue - gross), "role": "negative"},
        {"name": "Gross profit", "isIntermediateSum": True, "role": "total"},
        {"name": "Op expenses", "y": -(gross - op_income), "role": "negative"},
        {"name": "Op income", "isIntermediateSum": True, "role": "total"},
        # Non-operating items (interest, FX, other) bridge operating income to pre-tax income.
        {"name": "Non-op income/exp", "y": pretax - op_income,
         "role": "positive" if pretax >= op_income else "negative"},
        # Taxes + any residual adjustments bridge pre-tax income to reported net income.
        {"name": "Taxes & other", "y": net - pretax, "role": "negative"},
        {"name": "Net income", "isSum": True, "role": "total"},
    ]


# --- axis resolution (data-driven) ---------------------------------------

def x_kind(value) -> str:
    """Classify an x value as 'datetime' or 'category'."""
    if isinstance(value, (date, datetime)):
        return "datetime"
    if isinstance(value, str):
        # ISO date like 2025-09-27 → datetime; fiscal label like FY2025 → category.
        try:
            datetime.strptime(value[:10], "%Y-%m-%d")
            return "datetime"
        except ValueError:
            return "category"
    return "category"


def resolve_axis(x_kinds: Sequence[str]) -> str:
    """All-category → category; all-datetime → datetime; mixed-but-mappable → datetime.

    The mixed case (e.g. a quarterly category series + a daily price series) is
    reconciled by mapping categories to period-end dates; we prefer the richer
    datetime axis so Stock features (navigator, rangeSelector, flags) stay usable.
    """
    uniq = set(x_kinds)
    if uniq == {"category"}:
        return "category"
    if uniq == {"datetime"}:
        return "datetime"
    return "datetime"  # mixed but mappable


def to_millis(d: str) -> int:
    """ISO date → epoch milliseconds (UTC midnight) for a datetime axis.

    UTC-pinned so fixtures are byte-identical regardless of the machine's timezone.
    """
    dt = datetime.strptime(d[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fiscal_to_datetime(records: list[dict]) -> list[dict]:
    """Map each fiscal period to a real time span on a datetime axis.

    A statement's ``date`` is the period **end**; the **start** is the previous
    period's end + 1 day (and, for the first period, ~one quarter before its end).
    Returns ``{start, end, mid, span}`` epoch-ms per period so a fiscal column can
    be placed and sized correctly against a daily price series.
    """
    recs = sorted(records, key=lambda r: r["date"])
    out: list[dict] = []
    prev_end: int | None = None
    for r in recs:
        end = to_millis(r["date"])
        start = prev_end + 86_400_000 if prev_end is not None else end - 90 * 86_400_000
        out.append({"start": start, "end": end, "mid": (start + end) // 2, "span": end - start})
        prev_end = end
    return out


def quarter_label(d: str) -> str:
    """ISO date → fiscal-ish quarter label like Q2'26 (calendar quarter of the date)."""
    dt = datetime.strptime(d[:10], "%Y-%m-%d")
    q = (dt.month - 1) // 3 + 1
    return f"Q{q}'{dt.year % 100:02d}"
