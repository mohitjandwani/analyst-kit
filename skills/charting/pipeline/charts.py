#!/usr/bin/env python3
"""Final-data builders — one per chart.

Each takes financial records and returns a chart-contract dict (see SKILL.md):
numbers already scaled to one unit per axis, series tagged with a semantic `role`
(the TS side maps roles → colors), axis already resolved. This is the contract the
TypeScript Highcharts builders consume.
"""
from __future__ import annotations

from typing import Sequence

import polars as pl

from . import process


def _contract(title, subtitle, axis, yaxes, series, meta, flags=None) -> dict:
    c = {"title": title, "subtitle": subtitle, "axis": axis,
         "yAxes": yaxes, "series": series, "meta": meta}
    if flags:
        c["flags"] = flags
    return c


def _symbol(records: list[dict]) -> str:
    return records[0].get("symbol", "") if records else ""


# --- 1. revenue + net income + margin (dual axis) ------------------------

def revenue_margins(income_records, *, n=5, currency="$") -> dict:
    df = process.lookback(process.frame(income_records), n)
    periods = [f"FY{y}" for y in df["fiscalYear"].to_list()]
    rev, ni = df["revenue"].to_list(), df["netIncome"].to_list()
    divisor, suffix = process.pick_scale(rev + ni)
    marg = [None if m is None else round(m, 2)
            for m in (process.margin(a, b) for a, b in zip(ni, rev))]
    sym = _symbol(income_records)
    return _contract(
        f"{sym} — revenue, net income & margin", f"{periods[0]}–{periods[-1]}",
        {"type": "category", "categories": periods},
        [{"id": "money", "name": "Amount", "unit": suffix, "currency": currency},
         {"id": "pct", "name": "Net margin", "percent": True, "opposite": True}],
        [{"name": "Revenue", "kind": "column", "yAxis": "money", "role": "primary",
          "data": process.scale(rev, divisor)},
         {"name": "Net income", "kind": "column", "yAxis": "money", "role": "secondary",
          "data": process.scale(ni, divisor)},
         {"name": "Net margin", "kind": "line", "yAxis": "pct", "role": "neutral",
          "data": marg}],
        {"currency": currency, "unit": suffix, "chart": "revenueMargins", "symbol": sym},
    )


# --- 2 & 9. line / YoY / lead-lag shift / rebased comparison -------------

def _shift(values, k: int):
    n = len(values)
    if k > 0:
        return [None] * k + list(values[: max(0, n - k)])
    if k < 0:
        return list(values[-k:]) + [None] * (-k)
    return list(values)


def _line(periods, series_defs, *, percent, currency, title, subtitle, value_label,
          axis_type="category", flags=None, meta=None) -> dict:
    """series_defs: [{name, values, role, shift?}]."""
    prepped = [(sd, _shift(sd["values"], sd.get("shift", 0))) for sd in series_defs]
    if percent:
        data_lists = [[None if x is None else round(x, 4) for x in v] for _, v in prepped]
        yaxes = [{"id": "y", "name": value_label, "percent": True}]
        suffix = ""
    else:
        flat = [x for _, v in prepped for x in v if x is not None]
        divisor, suffix = process.pick_scale(flat)
        data_lists = [process.scale(v, divisor) for _, v in prepped]
        yaxes = [{"id": "y", "name": value_label, "unit": suffix, "currency": currency}]
    series = []
    for (sd, _), data in zip(prepped, data_lists):
        name = sd["name"] + (f" (shift {sd['shift']:+d})" if sd.get("shift") else "")
        series.append({"name": name, "kind": "line", "yAxis": "y",
                       "role": sd.get("role", "primary"), "data": data})
    axis = ({"type": "category", "categories": list(periods)}
            if axis_type == "category" else {"type": "datetime"})
    return _contract(title, subtitle, axis, yaxes, series,
                     {**(meta or {}), "unit": suffix, "chart": meta.get("chart", "line") if meta else "line"},
                     flags)


def revenue_trend(income_records, *, n=8, currency="$", flags=None) -> dict:
    df = process.lookback(process.frame(income_records), n)
    periods = [f"FY{y}" for y in df["fiscalYear"].to_list()]
    sym = _symbol(income_records)
    return _line(periods, [{"name": "Revenue", "values": df["revenue"].to_list(), "role": "primary"}],
                 percent=False, currency=currency, title=f"{sym} — revenue",
                 subtitle=f"{periods[0]}–{periods[-1]}", value_label="Revenue",
                 flags=flags, meta={"chart": "revenueTrend", "currency": currency, "symbol": sym})


def revenue_yoy(income_records, *, n=12, lag=1, currency="$", flags=None) -> dict:
    df = process.lookback(process.frame(income_records), n)
    periods = [f"FY{y}" for y in df["fiscalYear"].to_list()]
    growth = process.yoy(df["revenue"].to_list(), lag=lag)
    sym = _symbol(income_records)
    return _line(periods, [{"name": "Revenue", "values": growth, "role": "primary"}],
                 percent=True, currency=currency, title=f"{sym} — revenue YoY growth",
                 subtitle=f"{periods[0]}–{periods[-1]}", value_label="YoY growth",
                 flags=flags, meta={"chart": "revenueYoY", "symbol": sym})


def metrics_yoy(records, *, metrics: Sequence[str], lag=4, title=None, currency="$",
                flags=None, trim=True) -> dict:
    """YoY % growth lines for one or more metric columns of the same records.

    `records` are raw rows `{"date": "YYYY-MM-DD", "<metric>": <absolute value>, …}`
    in any order (sorted here); `lag` is periods per year (4 = quarterly, 1 = annual).
    Periods label as Q1'24-style quarters when lag=4, else FY<year>. With `trim`,
    the leading lag window (where every metric's growth is None) is dropped, so
    "last 3 years of quarterly YoY" = feed 4 years of raw data, get 12 points back.
    """
    df = process.frame(records)
    dates = df["date"].to_list()
    growths = {m: process.yoy(df[m].to_list(), lag=lag) for m in metrics}
    start = 0
    if trim:
        start = next((i for i in range(len(dates))
                      if any(growths[m][i] is not None for m in metrics)), len(dates))
    periods = [process.quarter_label(d) if lag == 4 else f"FY{str(d)[:4]}"
               for d in dates[start:]]
    roles = ["primary", "secondary", "neutral", "estimate"]
    series_defs = [{"name": m.replace("_", " ").capitalize() + " YoY",
                    "values": growths[m][start:], "role": roles[i % len(roles)]}
                   for i, m in enumerate(metrics)]
    sym = _symbol(records)
    return _line(periods, series_defs, percent=True, currency=currency,
                 title=title or (f"{sym} — YoY growth" if sym else "YoY growth"),
                 subtitle=f"{periods[0]}–{periods[-1]}" if periods else "",
                 value_label="YoY growth", flags=flags,
                 meta={"chart": "metricsYoY", "symbol": sym, "zeroLine": True})


def compare_rebased(named_income: Sequence[tuple[str, list[dict]]], *, n=5) -> dict:
    """Multiple companies' revenue rebased to 100 — relative growth, not size."""
    roles = ["primary", "secondary", "neutral", "estimate"]
    series_defs, periods = [], None
    for i, (sym, records) in enumerate(named_income):
        df = process.lookback(process.frame(records), n)
        if periods is None:
            periods = [f"FY{y}" for y in df["fiscalYear"].to_list()]
        series_defs.append({"name": sym, "values": process.rebase(df["revenue"].to_list()),
                            "role": roles[i % len(roles)]})
    out = _line(periods, series_defs, percent=True, currency="",
                title="Revenue rebased to 100", subtitle=f"{periods[0]}–{periods[-1]}",
                value_label="Indexed (base 100)", meta={"chart": "compareRebased"})
    # It's an index, not a percent — relabel the axis unit.
    out["yAxes"][0].pop("percent", None)
    return out


def compare_price_rebased(named_price: Sequence[tuple[str, list[dict]]]) -> dict:
    """Multiple companies' price rebased to 100 (datetime lines).

    The right way to compare price across companies (overlaid candlesticks are
    unreadable): each series is rebased to 100 at the window start, so the chart
    shows relative performance regardless of absolute share price.
    """
    roles = ["primary", "secondary", "neutral", "estimate"]
    series = []
    start = end = None
    for i, (sym, recs) in enumerate(named_price):
        rows = sorted(recs, key=lambda r: r["date"])
        idx = process.rebase([r["close"] for r in rows], 100)
        series.append({
            "name": sym, "kind": "line", "yAxis": "idx", "role": roles[i % len(roles)],
            "data": [[process.to_millis(r["date"]), v] for r, v in zip(rows, idx)],
        })
        start = rows[0]["date"] if start is None else min(start, rows[0]["date"])
        end = rows[-1]["date"] if end is None else max(end, rows[-1]["date"])
    return _contract(
        " vs ".join(s for s, _ in named_price) + " — price rebased to 100", f"{start} – {end}",
        {"type": "datetime"},
        [{"id": "idx", "name": "Indexed (base 100)"}],
        series,
        {"chart": "comparePriceRebased", "stock": True},
    )


# --- 3. revenue segments over time (stacked / percent / grouped) ---------

def segments(seg_records, *, variant="stacked", n=5, currency="$") -> dict:
    periods, segs = process.segment_matrix(seg_records, n)
    flat = [v for lst in segs.values() for v in lst]
    divisor, suffix = process.pick_scale(flat)
    sym = _symbol(seg_records)
    series = [{"name": name, "kind": "column", "yAxis": "money", "role": "segment",
               "data": process.scale(vals, divisor)} for name, vals in segs.items()]
    if variant == "percent":
        yaxes = [{"id": "money", "name": "Share of revenue", "percent": True}]
    else:
        yaxes = [{"id": "money", "name": "Revenue", "unit": suffix, "currency": currency}]
    return _contract(
        f"{sym} — revenue by segment", f"{periods[0]}–{periods[-1]}",
        {"type": "category", "categories": periods}, yaxes, series,
        {"currency": currency, "unit": suffix, "chart": "segments", "variant": variant, "symbol": sym},
    )


# --- 4. waterfall: revenue → net income ----------------------------------

def waterfall(row: dict, *, currency="$") -> dict:
    steps = process.waterfall_steps(row)
    divisor, suffix = process.pick_scale(
        [row["revenue"], row["grossProfit"], row["operatingIncome"], row["netIncome"]])
    data = []
    for s in steps:
        p = {"name": s["name"], "role": s["role"]}
        if "y" in s:
            p["y"] = round(s["y"] / divisor, 4)
        if s.get("isIntermediateSum"):
            p["isIntermediateSum"] = True
        if s.get("isSum"):
            p["isSum"] = True
        data.append(p)
    fy = row.get("fiscalYear") or row.get("calendarYear") or ""
    sym = row.get("symbol", "")
    return _contract(
        f"{sym} — revenue → net income", f"FY{fy}",
        {"type": "category", "categories": [s["name"] for s in steps]},
        [{"id": "money", "name": "Amount", "unit": suffix, "currency": currency}],
        [{"name": "Bridge", "kind": "waterfall", "yAxis": "money", "role": "waterfall", "data": data}],
        {"currency": currency, "unit": suffix, "chart": "waterfall", "symbol": sym},
    )


# --- 5. dividend history + yield (dual axis) -----------------------------

def dividend_yield(div_records, *, n_years=5, currency="$") -> dict:
    df = pl.DataFrame(div_records).with_columns(year=pl.col("date").str.slice(0, 4))
    agg = (df.group_by("year")
           .agg(div=pl.col("dividend").sum(), yld=pl.col("yield").sum())
           .sort("year"))
    if n_years:
        agg = agg.tail(n_years)
    periods = agg["year"].to_list()
    divs = agg["div"].to_list()
    ylds = [round(y, 3) for y in agg["yld"].to_list()]
    divisor, suffix = process.pick_scale(divs)
    sym = _symbol(div_records)
    return _contract(
        f"{sym} — dividend history & yield", f"{periods[0]}–{periods[-1]}",
        {"type": "category", "categories": periods},
        [{"id": "div", "name": "Dividend / share", "unit": suffix, "currency": currency, "decimals": 2},
         {"id": "yld", "name": "Dividend yield", "percent": True, "opposite": True}],
        [{"name": "Dividend / share", "kind": "column", "yAxis": "div", "role": "primary",
          "data": process.scale(divs, divisor)},
         {"name": "Dividend yield", "kind": "line", "yAxis": "yld", "role": "neutral",
          "data": ylds}],
        {"currency": currency, "unit": suffix, "chart": "dividendYield", "symbol": sym},
    )


# --- 6. earnings surprise over time --------------------------------------

def surprise(earnings_records, *, n=8, metric="eps") -> dict:
    rows = sorted([e for e in earnings_records if e.get(f"{metric}Actual") is not None],
                  key=lambda x: x["date"])
    if n:
        rows = rows[-n:]
    periods = [process.quarter_label(e["date"]) for e in rows]
    data = []
    for e in rows:
        a, est = e[f"{metric}Actual"], e[f"{metric}Estimated"]
        if a is None or est in (None, 0):
            data.append(None)
            continue
        sp = round((a - est) / abs(est) * 100, 2)
        data.append({"y": sp, "role": "positive" if sp >= 0 else "negative"})
    sym = _symbol(earnings_records)
    return _contract(
        f"{sym} — {metric.upper()} surprise", f"{periods[0]}–{periods[-1]}" if periods else "",
        {"type": "category", "categories": periods},
        [{"id": "pct", "name": f"{metric.upper()} surprise", "percent": True}],
        [{"name": "Surprise %", "kind": "column", "yAxis": "pct", "role": "signed", "data": data}],
        {"chart": "surprise", "metric": metric, "zeroLine": True, "symbol": sym},
    )


# --- 7. estimate vs reported ---------------------------------------------

def estimate_vs_reported(earnings_records, *, n=8, metric="revenue", currency="$") -> dict:
    rows = sorted([e for e in earnings_records if e.get(f"{metric}Actual") is not None],
                  key=lambda x: x["date"])
    if n:
        rows = rows[-n:]
    periods = [process.quarter_label(e["date"]) for e in rows]
    est = [e[f"{metric}Estimated"] for e in rows]
    rep = [e[f"{metric}Actual"] for e in rows]
    divisor, suffix = process.pick_scale(est + rep)
    label = "Revenue" if metric == "revenue" else "EPS"
    sym = _symbol(earnings_records)
    # EPS is a per-share figure → always 2 decimals (see references/data-units.md table).
    yaxis = {"id": "v", "name": label, "unit": suffix, "currency": currency}
    if metric == "eps":
        yaxis["decimals"] = 2
    return _contract(
        f"{sym} — {label}: estimate vs reported", f"{periods[0]}–{periods[-1]}" if periods else "",
        {"type": "category", "categories": periods},
        [yaxis],
        [{"name": "Estimate", "kind": "column", "yAxis": "v", "role": "estimate",
          "data": process.scale(est, divisor)},
         {"name": "Reported", "kind": "column", "yAxis": "v", "role": "primary",
          "data": process.scale(rep, divisor)}],
        {"currency": currency, "unit": suffix, "chart": "estimateVsReported",
         "variant": "grouped", "metric": metric, "symbol": sym},
    )


# --- 8. price (candlestick when primary, else line) ----------------------

def price(price_records, *, primary=True, currency="$", flags=None) -> dict:
    rows = sorted(price_records, key=lambda x: x["date"])
    sym = _symbol(price_records)
    if primary:
        data = [[process.to_millis(r["date"]), r["open"], r["high"], r["low"], r["close"]]
                for r in rows]
        series = [{"name": "Price", "kind": "candlestick", "yAxis": "price",
                   "role": "primary", "data": data}]
    else:
        data = [[process.to_millis(r["date"]), r["close"]] for r in rows]
        series = [{"name": "Price", "kind": "line", "yAxis": "price",
                   "role": "primary", "data": data}]
    out_flags = None
    if flags:
        out_flags = [{"x": process.to_millis(f["date"]), "title": f["title"]} for f in flags]
    return _contract(
        f"{sym} — price", f"{rows[0]['date']}–{rows[-1]['date']}" if rows else "",
        {"type": "datetime"},
        [{"id": "price", "name": "Price", "currency": currency, "decimals": 2}],
        series,
        {"currency": currency, "chart": "price", "stock": True, "primary": primary, "symbol": sym},
        out_flags,
    )


# --- price (candlestick) + quarterly revenue on one datetime axis ----------

def price_with_revenue(price_records, income_records, *, mode="period",
                       point_date="period_end", currency="$") -> dict:
    """Price (candlestick) + revenue on one datetime axis. The revenue rendering is
    chosen from context via ``mode``:

    * ``"period"``   — revenue **columns spanning each fiscal period** (sized to the
      quarter). Read revenue magnitude *over* the time it covers.
    * ``"reaction"`` — revenue **markers on the earnings/release date** (``filingDate``),
      so you can see how the price reacted when the number landed.
    * ``"growth"``   — revenue **YoY % as a line with prominent dots** (% axis).

    ``point_date`` decides where a marker/dot sits for ``"growth"``: ``"period_end"``
    (the period's close) or ``"earnings"`` (the release date). ``"reaction"`` always
    uses the earnings date. Only periods inside the price window are shown.
    """
    prows = sorted(price_records, key=lambda r: r["date"])
    pmin, pmax = prows[0]["date"], prows[-1]["date"]
    candle = [[process.to_millis(r["date"]), r["open"], r["high"], r["low"], r["close"]]
              for r in prows]
    qall = sorted(income_records, key=lambda r: r["date"])
    sym = _symbol(price_records) or _symbol(income_records)
    price_axis = {"id": "price", "name": "Price", "currency": currency,
                  "decimals": 2, "opposite": True}
    price_series = {"name": "Price", "kind": "candlestick", "yAxis": "price",
                    "role": "primary", "data": candle, "opts": {"zIndex": 2}}

    def in_window(d):
        return bool(d) and pmin <= d[:10] <= pmax

    if mode == "growth":
        growth = process.yoy([r["revenue"] for r in qall], lag=4)  # quarterly YoY
        use_earn = point_date == "earnings"
        pts = []
        for r, g in zip(qall, growth):
            d = r.get("filingDate") if use_earn else r["date"]
            if g is not None and in_window(d):
                pts.append([process.to_millis(d), round(g, 2)])
        rev_series = {"name": "Revenue YoY", "kind": "line", "yAxis": "rev", "role": "secondary",
                      "data": pts, "opts": {"lineWidth": 2, "zIndex": 3,
                                            "marker": {"enabled": True, "radius": 5}}}
        rev_axis = {"id": "rev", "name": "Revenue YoY", "percent": True}
        sub = f"YoY % · dots on {'earnings date' if use_earn else 'period end'}"
    elif mode == "reaction":
        win = [r for r in qall if in_window(r.get("filingDate"))]
        divisor, suffix = process.pick_scale([r["revenue"] for r in win])
        pts = [[process.to_millis(r["filingDate"]), round(r["revenue"] / divisor, 4)] for r in win]
        rev_series = {"name": "Revenue (at release)", "kind": "line", "yAxis": "rev",
                      "role": "secondary", "data": pts,
                      "opts": {"lineWidth": 0, "zIndex": 3, "marker": {"enabled": True, "radius": 6}}}
        rev_axis = {"id": "rev", "name": "Revenue", "unit": suffix, "currency": currency}
        sub = "revenue plotted on the earnings date"
    else:  # "period"
        qwin = [r for r in qall if in_window(r["date"])]
        spans = process.fiscal_to_datetime(qwin)
        divisor, suffix = process.pick_scale([r["revenue"] for r in qwin])
        rev_data = [[s["mid"], round(r["revenue"] / divisor, 4)] for s, r in zip(spans, qwin)]
        pr = sorted(s["span"] for s in spans)[len(spans) // 2] if spans else 7_776_000_000
        rev_series = {"name": "Quarterly revenue", "kind": "column", "yAxis": "rev",
                      "role": "secondary", "data": rev_data,
                      "opts": {"pointRange": pr, "opacity": 0.5, "zIndex": 1}}
        rev_axis = {"id": "rev", "name": "Revenue", "unit": suffix, "currency": currency}
        sub = "revenue over each fiscal period"

    return _contract(
        f"{sym} — price & revenue", f"{pmin} – {pmax} · {sub}",
        {"type": "datetime"}, [rev_axis, price_axis], [price_series, rev_series],
        {"currency": currency, "chart": "priceWithRevenue", "mode": mode, "stock": True, "symbol": sym},
    )
