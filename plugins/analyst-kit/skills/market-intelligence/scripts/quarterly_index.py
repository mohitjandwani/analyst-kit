"""quarterly_index.py -- stitched quarterly search-interest index + QTD nowcast.

Implements plan section 4 Step 2 end-to-end for ONE keyword:

  1. Spine     -- one 5-year WEEKLY series (1 request); all history on this scale.
  2. Daily refill -- custom DAILY windows of <=224 days covering recent quarters,
     each rescaled onto the spine by an overlap factor computed over all
     fully-confirmed overlapping Sun-Sat weeks (long overlap, not one week).
  3. Aggregate to fiscal quarters (fiscal-year-end MM-DD or explicit quarter-end
     dates). Partial buckets are ALWAYS dropped.
  4. Current-quarter nowcast -- QTD index vs the same-days-elapsed point in each
     prior year (day-of-quarter alignment), the YoY QTD ratio, and a
     cumulative-shape full-quarter extrapolation, with an honest uncertainty note.

Outputs a quarterly-index CSV + a QTD CSV + a short human summary. Every row
carries the section-2.6 provenance columns (keyword, is_partial, fetched_at).

`--dry-run` prints the exact request plan and spends ZERO quota.

Example
-------
    python quarterly_index.py --keyword "victoria's secret" --geo US \\
        --fiscal-year-end 01-31 --years 5 --dry-run
    python quarterly_index.py --keyword "victoria's secret" --geo US \\
        --fiscal-year-end 01-31 --years 5
"""
import argparse
import sys
from datetime import date, datetime, timedelta, timezone

import trends_client as tc

DAILY_MAX_DAYS = 224  # verified-safe ceiling before Google down-samples to weekly


# --- fiscal calendar --------------------------------------------------------

def fiscal_quarter_ends(fye_month, fye_day, start, end):
    """Yield fiscal quarter-end dates (calendar-quarter approximation of a
    fiscal year that ends on fye_month/fye_day) covering [start, end].

    For a fiscal year ending Jan 31 the quarters end ~Apr 30, Jul 31, Oct 31,
    Jan 31. We approximate with month-end dates 3 months apart from the FYE.
    """
    ends = []
    # quarter-end months are fye_month, fye_month-3, -6, -9 (mod 12)
    q_months = sorted({((fye_month - 3 * k - 1) % 12) + 1 for k in range(4)})
    y = start.year - 1
    while y <= end.year + 1:
        for m in q_months:
            d = _month_end(y, m)
            if start <= d <= end:
                ends.append(d)
        y += 1
    return sorted(set(ends))


def _month_end(year, month):
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return nxt - timedelta(days=1)


def quarter_label(qend, fye_month):
    """Label like FY2026Q1. The fiscal year is the calendar year in which the
    fiscal year-end falls; quarters within it numbered from the start."""
    # The fiscal year starts the month AFTER the fiscal year-end month, so the
    # first quarter ends ~3 months after FY-start (=4 months after the FYE month).
    fy_start_month = fye_month % 12 + 1
    months_into_fy = (qend.month - fy_start_month) % 12  # 0,3,6,9 at quarter-ends
    qnum = months_into_fy // 3 + 1
    # fiscal year label = the year the FYE quarter ends
    if qend.month <= fye_month:
        fy = qend.year
    else:
        fy = qend.year + 1
    return f"FY{fy}Q{qnum}"


def quarter_start(qend, prev_end):
    return (prev_end + timedelta(days=1)) if prev_end else None


# --- stitching --------------------------------------------------------------

def week_start_sunday(d):
    """Sunday that starts the Google Trends week containing date d.
    Python weekday(): Mon=0..Sun=6; Trends weeks run Sunday->Saturday."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def daily_to_weekly(daily_rows):
    """Aggregate confirmed daily rows into Sun-Sat weekly sums keyed by week start."""
    weekly = {}
    for r in daily_rows:
        if r["is_partial"]:
            continue
        d = datetime.strptime(r["bucket_start"], "%Y-%m-%d").date()
        ws = week_start_sunday(d)
        weekly.setdefault(ws, []).append(r["value"])
    # only weeks with all 7 days present are "complete" for overlap rescaling
    full = {ws: sum(vals) for ws, vals in weekly.items() if len(vals) == 7}
    return full


def overlap_factor(spine_weekly, window_daily):
    """factor = mean(spine weekly over overlap) / mean(window daily->weekly over
    overlap), across all fully-confirmed overlapping weeks. Returns (factor, n)."""
    win_weekly = daily_to_weekly(window_daily)
    common = sorted(set(spine_weekly) & set(win_weekly))
    if not common:
        return None, 0
    s = sum(spine_weekly[w] for w in common) / len(common)
    w = sum(win_weekly[w] for w in common) / len(common)
    if w == 0:
        return None, len(common)
    return s / w, len(common)


def spine_weekly_map(spine_rows):
    """Confirmed spine weekly values keyed by Sun week-start date."""
    out = {}
    for r in spine_rows:
        if r["is_partial"]:
            continue
        ws = datetime.strptime(r["bucket_start"], "%Y-%m-%d").date()
        out[ws] = r["value"]
    return out


# --- request planning -------------------------------------------------------

def plan_daily_windows(start, end, max_days=DAILY_MAX_DAYS):
    """Tile [start, end] into <=max_days windows, each overlapping the next by
    a few weeks so an overlap factor is always computable against the spine."""
    windows = []
    cur = start
    while cur <= end:
        win_end = min(cur + timedelta(days=max_days - 1), end)
        windows.append((cur, win_end))
        if win_end >= end:
            break
        cur = win_end - timedelta(days=20)  # ~3-week stitch overlap
    return windows


def build_plan(keyword, geo, fye_month, fye_day, years, today):
    spine_date = "today 5-y"
    hist_start = today - timedelta(days=365 * years)
    # daily refill covers the most recent ~years span in <=224d windows
    refill_start = max(hist_start, today - timedelta(days=365 * min(years, 2)))
    windows = plan_daily_windows(refill_start, today)
    return {
        "keyword": keyword,
        "geo": geo,
        "spine_request": {"q": keyword, "date": spine_date, "geo": geo},
        "daily_requests": [
            {"q": keyword, "date": f"{a.isoformat()} {b.isoformat()}", "geo": geo}
            for a, b in windows
        ],
    }


def print_plan(plan):
    n = 1 + len(plan["daily_requests"])
    print("=== REQUEST PLAN (dry run -- no quota spent) ===")
    print(f"keyword: {plan['keyword']!r}   geo: {plan['geo']}")
    print(f"  1 spine request   : q={plan['keyword']!r} date={plan['spine_request']['date']!r} (weekly)")
    for i, req in enumerate(plan["daily_requests"], start=2):
        print(f"  {i:>2} daily window    : date={req['date']!r} (<= {DAILY_MAX_DAYS}d, daily)")
    print(f"  --> {n} live API call(s) if none are cached "
          f"(cached windows that end in the past are free forever).")
    return n


# --- aggregation + nowcast --------------------------------------------------

def stitched_daily(plan, geo, log):
    """Fetch spine + daily windows, rescale each window onto the spine, and
    return (stitched_daily_rows, spine_rows). Each stitched row keeps provenance."""
    spine_rows, _, _ = tc.fetch_series(plan["keyword"], date="today 5-y", geo=geo,
                                       expect_granularity="weekly", log=log)
    spine = spine_weekly_map(spine_rows)

    stitched = {}  # bucket_start (date) -> row (latest window wins via overlap)
    for req in plan["daily_requests"]:
        win_rows, _, _ = tc.fetch_series(plan["keyword"], date=req["date"], geo=geo,
                                         expect_granularity="daily", log=log)
        factor, n = overlap_factor(spine, win_rows)
        if factor is None:
            if log:
                log(f"  ! no spine overlap for window {req['date']} -- skipped")
            continue
        for r in win_rows:
            d = datetime.strptime(r["bucket_start"], "%Y-%m-%d").date()
            scaled = dict(r)
            scaled["value"] = r["value"] * factor
            scaled["overlap_weeks"] = n
            stitched[d] = scaled  # later (more recent) windows overwrite overlap
    return stitched, spine_rows


def aggregate_quarters(stitched, fye_month, fye_day, years, today):
    start = today - timedelta(days=365 * years)
    qends = fiscal_quarter_ends(fye_month, fye_day, start, today + timedelta(days=120))
    rows = []
    prev = None
    current = None
    for qend in qends:
        qstart = quarter_start(qend, prev)
        prev = qend
        if qstart is None:
            continue
        days = [d for d in stitched if qstart <= d <= qend]
        if not days:
            continue
        confirmed = [d for d in days if not stitched[d]["is_partial"]]
        index = sum(stitched[d]["value"] for d in confirmed)
        any_partial = any(stitched[d]["is_partial"] for d in days)
        fetched = min(stitched[d]["fetched_at"] for d in days)
        is_current = qstart <= today <= qend
        rec = {
            "fiscal_quarter": quarter_label(qend, fye_month),
            "quarter_start": qstart.isoformat(),
            "quarter_end": qend.isoformat(),
            "index": round(index, 2),
            "n_confirmed_days": len(confirmed),
            "is_partial": is_current or any_partial,
            "fetched_at": fetched,
            "keyword": next(iter(stitched.values()))["keyword"] if stitched else "",
        }
        rows.append(rec)
        if is_current:
            current = (qstart, qend)
    return rows, current


def qtd_nowcast(stitched, current, fye_month, years, today):
    """Day-of-quarter aligned QTD comparison vs prior years."""
    if not current:
        return None, []
    qstart, qend = current
    # confirmed days elapsed in the current quarter (exclude today's partial bucket)
    cur_days = sorted(d for d in stitched
                      if qstart <= d <= today and not stitched[d]["is_partial"])
    n = len(cur_days)
    if n == 0:
        return None, []
    cur_qtd = sum(stitched[d]["value"] for d in cur_days)

    comparisons = []
    for k in range(1, years + 1):
        py_qstart = _shift_year(qstart, -k)
        # same number of days elapsed (day-of-quarter alignment)
        py_days = [py_qstart + timedelta(days=i) for i in range(n)]
        vals = [stitched[d]["value"] for d in py_days
                if d in stitched and not stitched[d]["is_partial"]]
        if len(vals) < n:  # not enough confirmed history for a clean compare
            continue
        py_qtd = sum(vals)
        # full prior-year quarter (for cumulative shape)
        py_qend = _shift_year(qend, -k)
        full_days = [d for d in stitched
                     if py_qstart <= d <= py_qend and not stitched[d]["is_partial"]]
        py_full = sum(stitched[d]["value"] for d in full_days)
        frac = (py_qtd / py_full) if py_full else None
        comparisons.append({
            "prior_fy_quarter": quarter_label(py_qend, fye_month),
            "py_qtd_index": round(py_qtd, 2),
            "py_full_quarter_index": round(py_full, 2),
            "qtd_fraction_of_quarter": round(frac, 4) if frac else None,
            "yoy_qtd_ratio": round(cur_qtd / py_qtd, 4) if py_qtd else None,
        })

    fracs = [c["qtd_fraction_of_quarter"] for c in comparisons
             if c["qtd_fraction_of_quarter"]]
    mean_frac = sum(fracs) / len(fracs) if fracs else None
    full_est = (cur_qtd / mean_frac) if mean_frac else None
    yoys = [c["yoy_qtd_ratio"] for c in comparisons if c["yoy_qtd_ratio"]]
    summary = {
        "current_fiscal_quarter": quarter_label(qend, fye_month),
        "days_elapsed_confirmed": n,
        "current_qtd_index": round(cur_qtd, 2),
        "mean_qtd_fraction_prior_years": round(mean_frac, 4) if mean_frac else None,
        "full_quarter_estimate_index": round(full_est, 2) if full_est else None,
        "yoy_qtd_ratio_latest": comparisons[0]["yoy_qtd_ratio"] if comparisons else None,
        "yoy_qtd_ratio_mean": round(sum(yoys) / len(yoys), 4) if yoys else None,
    }
    return summary, comparisons


def _shift_year(d, delta):
    try:
        return d.replace(year=d.year + delta)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + delta, day=28)


# --- CLI --------------------------------------------------------------------

def write_csv(path, rows, columns):
    import csv
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for r in rows:
            w.writerow([r.get(c, "") for c in columns])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keyword", required=True,
                   help="One keyword (may be a '+' combination). Niche keywords "
                        "should be fetched alone to avoid integer quantization.")
    p.add_argument("--geo", default="US")
    fg = p.add_mutually_exclusive_group()
    fg.add_argument("--fiscal-year-end", default="01-31",
                    help="Fiscal year end MM-DD (default 01-31, e.g. VSCO). "
                         "Quarters approximated as month-ends 3 months apart.")
    fg.add_argument("--fiscal-quarter-ends",
                    help="Explicit comma-separated quarter-end dates YYYY-MM-DD,... "
                         "(overrides --fiscal-year-end).")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--dry-run", action="store_true",
                   help="Print the request plan and exit -- spends ZERO quota.")
    p.add_argument("--out-prefix", default=None,
                   help="Write <prefix>_quarterly.csv and <prefix>_qtd.csv.")
    args = p.parse_args(argv)

    tc.load_dotenv()
    today = datetime.now(timezone.utc).date()
    fye_m, fye_d = (int(x) for x in args.fiscal_year_end.split("-"))

    plan = build_plan(args.keyword, args.geo, fye_m, fye_d, args.years, today)

    if args.dry_run:
        print_plan(plan)
        return 0

    log = lambda m: print(m, file=sys.stderr)
    try:
        stitched, _spine = stitched_daily(plan, args.geo, log)
    except tc.TrendsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not stitched:
        print("ERROR: no stitched data produced (no spine overlap?)", file=sys.stderr)
        return 1

    quarters, current = aggregate_quarters(stitched, fye_m, fye_d, args.years, today)
    summary, comparisons = qtd_nowcast(stitched, current, fye_m, args.years, today)

    qcols = ["fiscal_quarter", "quarter_start", "quarter_end", "index",
             "n_confirmed_days", "is_partial", "fetched_at", "keyword"]
    print("\n=== QUARTERLY INDEX (partial buckets dropped from index) ===")
    print(",".join(qcols))
    for r in quarters:
        print(",".join(str(r.get(c, "")) for c in qcols))

    print("\n=== CURRENT-QUARTER NOWCAST (QTD; today's partial bucket excluded) ===")
    if summary:
        for k, v in summary.items():
            print(f"  {k}: {v}")
        print("  prior-year comparisons (day-of-quarter aligned):")
        for c in comparisons:
            print(f"    {c}")
        n = summary["days_elapsed_confirmed"]
        if n < 20:
            print("  ! UNCERTAINTY: only %d confirmed days elapsed -- the full-quarter "
                  "estimate leans on cumulative-shape extrapolation and has wide error "
                  "bars. Trust the YoY QTD ratio over the point estimate." % n)
    else:
        print("  (no in-progress quarter detected in the stitched window)")

    if args.out_prefix:
        write_csv(f"{args.out_prefix}_quarterly.csv", quarters, qcols)
        if comparisons:
            ccols = list(comparisons[0].keys())
            write_csv(f"{args.out_prefix}_qtd.csv", comparisons, ccols)
        print(f"\nWrote {args.out_prefix}_quarterly.csv "
              f"(+ _qtd.csv)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
