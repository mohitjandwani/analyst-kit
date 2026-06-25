# Methodology — Google Trends → revenue-segment nowcast

Long-form rationale and math behind the two-step methodology summarized in
`SKILL.md`. The worked example throughout is **Victoria's Secret (VSCO)** —
matching Google Trends search interest to a reported revenue segment. VSCO's
fiscal year ends ~Jan 31 (retail 4-5-4 calendar).

> **Two behavioral rules govern everything below** (they sit at the top of
> `SKILL.md`'s body and are repeated here because they are load-bearing):
>
> 1. **Before spending ANY quota on exploratory keyword search, ask the user:
>    manual Google Trends exploration (free, default) or API exploration (state
>    the call budget first)?** (Step 1.0.)
> 2. **Never deliver trends numbers without the provenance columns** — keyword
>    verbatim, `is_partial`, and `fetched_at` on every row.

---

## Step 1 — Keyword identification

Goal: 3–5 keywords per revenue segment whose **year-over-year changes** track the
reported segment revenue. Expect heavy iteration — for a given company you will
try many candidates and `+` combinations before finding ones that track revenue.

### Step 1.0 — The mandatory user gate (manual vs API)

Keyword exploration is the **unbounded-cost** part: each probe is 1 of the 100
monthly searches, and you cannot know in advance how many candidates you will
burn through. So before spending *any* quota on candidates, **ask the user which
mode** (use the question tool):

- **Manual (default / recommended).** Generate the candidate list plus
  ready-to-open Google Trends web-UI URLs (via `fetch_trends.py --explore-urls`
  or `trends_client.explore_url`) — same `q`/`+` syntax, free, unlimited. The
  user eyeballs and compares series in the browser (including the related-queries
  panel for disambiguation) and reports back the 3–5 winners; only those get API
  calls. This costs **zero** quota for the exploration phase.

- **API.** You explore via SerpAPI yourself. You must **state the estimated number
  of calls up front** — `candidates ÷ 5` (relative requests, packing 5 keywords
  per request to stretch quota) `+ 1 RELATED_QUERIES per surviving term` — get
  **explicit agreement** on that budget, then pack candidates 5-per-request.

Never silently start spending quota on exploration.

### Step 1.1 — Candidate generation

From the segment's actual products and brands. For VSCO's segments (Victoria's
Secret stores, PINK, Beauty, Digital) candidates include:

- the **brand term** — `victoria's secret`;
- **brand + category** — `victoria's secret pajamas`, `victoria's secret perfume`;
- **sub-brand** — `pink victoria secret`;
- **`+` combinations** that union category + brand demand
  (`lingerie + victoria's secret`) or pool a sub-brand's spelling variants
  (`pink victoria secret + vs pink`).

Prefer **purchase-intent-adjacent** terms over news-driven ones. A scandal spikes
the bare brand term `victoria's secret` without moving revenue — a classic failure
mode. Category/product/intent terms are sturdier revenue proxies.

### Step 1.2 — Disambiguation

Set `geo` to the segment's revenue geography (`US` for US retail). Run
`data_type=RELATED_QUERIES` **once per candidate** to confirm the term means what
you think:

- `pink` alone is hopeless (color, music artist, …);
- `victoria` is ambiguous (place names, the show, Beckham);
- the related-queries panel reveals whether searchers mean the brand.

In manual mode the user inspects the related-queries panel on the web UI instead.

### Step 1.3 — Validation

Fetch ≤ 5 survivors in **one** relative request over 5y (weekly — cheaper than
daily and enough for correlation), aggregate each to fiscal quarters (Step 2
logic), and correlate against the reported segment revenue series (source it via
the `financialmodellingprep` skill / company filings — **out of this skill's
scope**, just reference it).

Correlate **YoY changes**, not levels: both search interest and retail revenue
share strong seasonality, so a *level* correlation is inflated and misleading. A
keyword earns its place only if its year-over-year movement tracks revenue's
year-over-year movement, with **2–4 years of overlapping history minimum**.

---

## Step 2 — Quarter normalization & current-quarter nowcast

The goal: one **consistent quarterly index per keyword** spanning history plus the
in-progress quarter, despite per-request 0–100 rescaling. `quarterly_index.py`
implements all of this for one keyword.

### Step 2.1 — Spine

Fetch one **5-year weekly** series per keyword (1 request). All history is
expressed on this single scale. Because every request is independently 0–100
rescaled (the normalization trap), the spine is the canonical reference everything
else is rescaled *onto*.

### Step 2.2 — Daily refill (overlap rescaling)

Weekly Sun–Sat buckets straddle fiscal-quarter boundaries, so for exact quarter
alignment and for the in-progress quarter we fetch **custom daily windows ≤ 224
days** (the verified-safe ceiling before Google down-samples to weekly), then
rescale each daily window onto the spine.

**The factor.** For one daily window, aggregate its confirmed daily values to
Sun–Sat weekly sums, then over **all fully-confirmed overlapping weeks**:

```
factor = mean(spine weekly value over overlap) / mean(window daily→weekly sum over overlap)
```

Multiply every daily value in the window by `factor`. Use a **long overlap** (many
weeks), never a single week: single-week ratios are noisy and the underlying
values are integer-quantized (0–100), so one week's ratio can be off by tens of
percent. `overlap_factor()` requires several fully-confirmed (7-day) overlapping
weeks and rescales the window so its weekly means match the spine's exactly over
the overlap.

Windows are tiled to overlap each other by ~3 weeks (`plan_daily_windows`) so a
factor is always computable, and the most recent window wins on any day covered by
two windows (its scale is freshest relative to the current quarter).

> **Cheaper v1 alternative** (documented option, not the implemented default):
> skip daily refill for deep history and apportion straddling weekly buckets
> pro-rata by days, fetching daily data only for the current + prior quarter. This
> implementation does the full daily refill over the recent ~2 years (where
> quarter alignment and the nowcast matter most) and leans on the weekly spine for
> older history.

### Step 2.3 — Aggregate to fiscal quarters

Use the company's fiscal calendar. `--fiscal-year-end MM-DD` approximates quarters
as month-ends three months apart from the FYE (VSCO: Apr 30, Jul 31, Oct 31, Jan
31). For exact retail 4-5-4 quarter-end dates, pass them with
`--fiscal-quarter-ends YYYY-MM-DD,…` (source from filings / `financialmodellingprep`).

Quarterly index = **sum of stitched daily values in the quarter**. **Partial
buckets are always dropped** from the index; a quarter is flagged `is_partial` if
it is the in-progress quarter or contains any partial bucket, and its `fetched_at`
is the oldest contributing fetch (provenance contract).

The fiscal-year *number* follows the convention that FY starts the month after the
FYE: for a Jan-31 FYE, the quarter ending Apr 2026 is FY2027 Q1 (the fiscal year
that ends Jan 2027).

### Step 2.4 — Current-quarter nowcast

With N **confirmed** days of the in-progress quarter (today's partial bucket is
excluded):

- Compute the **quarter-to-date (QTD) index** = sum of the N confirmed days.
- For each historical year, compute the **same-days-elapsed** QTD using
  **day-of-quarter alignment** (the i-th day of the quarter, not the calendar
  date). This keeps holiday weeks aligned across a 4-5-4 retail calendar where the
  calendar dates of quarter boundaries drift year to year.

Two signals:

1. **Primary — YoY QTD ratio:** `QTD(this year) / QTD(same point, last year)`.
   Applied to last year's reported segment revenue, this is the most robust
   nowcast because it cancels intra-quarter shape and most seasonality.
2. **Secondary — full-quarter extrapolation:** scale QTD to a full-quarter
   estimate using the historical **cumulative shape** — the mean fraction of the
   quarter's total search volume that had accrued by day N across prior years
   (`full_estimate = QTD / mean_fraction`).

**Report uncertainty honestly.** Early in the quarter (small N) the cumulative-
shape extrapolation dominates and error bars are wide; the script prints an
explicit warning when fewer than ~20 confirmed days have elapsed and says to trust
the YoY ratio over the point estimate. The output is a clean **index**, not
dollars — calibrate it to revenue with a regression in the `data-analysis` skill;
**never read the index as dollars.**

---

## Pitfalls (cross-cutting)

- **Per-request rescaling (normalization trap).** Values from different requests
  are not comparable without overlap-rescaling onto the spine.
- **Partial buckets.** Never modelled; dropped from indices and excluded from the
  QTD row. A bucket is confirmed iff `partial_data` is absent (do not hardcode a
  confirmation weekday).
- **Sunday-snap.** Custom ranges widen outward to Sun–Sat boundaries — account for
  it when aligning windows.
- **News-spike contamination.** Inspect spikes > ~3σ; a scandal/news event inflates
  interest without moving revenue. Cross-check `RELATED_QUERIES` before trusting a
  spike.
- **Integer quantization.** Low-value keywords get crushed toward 0–2 when fetched
  alongside a dominant term. Fetch niche keywords **alone** to preserve precision.
- **Interest ≠ transactions.** Trends measure *attention*, not *purchases*.
  Calibrate to revenue via regression; the index alone is not a revenue figure.

---

## Curiosity: confirmation-day calibration (optional, no logic depends on it)

A one-time calibration can characterize when Google confirms the prior week: fetch
`today 1-m` each weekday for one week and note the day the prior week's
`partial_data` flag disappears. On 2026-06-12 (a Friday) the prior full week was
already confirmed, suggesting confirmation lands Wed/Thu, but a single snapshot
cannot pin it — and again, **no logic may depend on a hardcoded weekday**; the only
rule is *confirmed iff `partial_data` absent*.
