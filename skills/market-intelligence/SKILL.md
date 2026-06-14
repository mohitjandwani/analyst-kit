---
name: market-intelligence
type: capability
description: >
  Nowcast how a company is doing and predict a revenue segment for the current quarter from
  Google Trends search-interest data, fetched through the SerpAPI google_trends engine. This is
  THE skill for any use of search interest as alternative data — turning consumer/web search
  demand into a quarterly signal and testing it against reported sales. Teaches a two-step
  methodology — identify keywords that track a revenue segment, then normalize the per-request
  0–100 trends scale into a consistent quarterly index plus a quarter-to-date nowcast — with
  disk-cached scripts (free tier = 100 searches/month) and a full SerpAPI reference. Triggers:
  "google trends for X", "search interest for <company/brand>", "can search interest predict
  Y's revenue", "is search interest an early signal for Z's sales", "does consumer search track
  <company> sales", "compare search interest to revenue", "use search demand as alternative
  data", "nowcast <company> sales", "build a trends-based revenue model for Z", "market
  intelligence on <ticker>".
env:
  - SERPAPI_API_KEY
---

# Market Intelligence — Google Trends revenue nowcasting (via SerpAPI)

Use **Google Trends search interest** (fetched through SerpAPI) as alternative data to
nowcast a company's current-quarter performance — flagship use case: **predicting a
revenue segment this quarter** (worked example: Victoria's Secret / VSCO). The skill is
two steps: (1) find keywords that track a revenue segment, (2) normalize the trends scale
into a consistent quarterly index and produce a quarter-to-date nowcast.

## Two behavioral rules — read first, always apply

1. **Choose an exploration mode — Manual vs API — but never block an autonomous run on the
   choice.** In an **interactive session, ask the user** (use your question tool) which to
   use: **Manual** Google Trends exploration (free, unlimited, the interactive default — you
   generate candidate keywords + ready-to-open web-UI URLs via `fetch_trends.py
   --explore-urls`, the user eyeballs them and reports back the 3–5 winners) **or API**
   exploration (you call SerpAPI yourself — first state the estimated call budget:
   candidates ÷ 5 per relative request, + 1 RELATED_QUERIES per surviving term — and get
   explicit agreement). **If you are running non-interactively / headless** — an automated
   job, `claude -p`, or any context where your question tool cannot reach a human — **do NOT
   ask: proceed in API mode directly** with a bounded budget (cap exploration at ~5–8
   candidates, state the estimated call count up front, and lean on the mandatory cache).
   Manual mode requires a human, so it is never the autonomous default; the right behavior
   when there is no one to answer is to spend a little quota, not to abandon Trends for a
   weaker proxy. Free tier is **100 searches/month**; keyword exploration is the
   unbounded-cost step.
2. **Never deliver trends numbers without provenance.** Every row you hand off — CSV, JSON,
   quarterly index, nowcast — must carry `keyword` (the exact `q` term verbatim, including
   `+`/quotes/`-`), `is_partial` (always explicit true/false), and `fetched_at` (UTC time
   of the live call; cache hits keep the **original** time so staleness is visible). The
   scripts emit these columns already — do not strip them.

## Setup

```bash
export SERPAPI_API_KEY="your_key"   # free key: https://serpapi.com/  (100 searches/month)
```

The scripts also auto-load the repo-root `.env` if present. If the key is unset they print
this instruction and exit non-zero — ask the user for their key. **The cache is mandatory**:
every repeated fetch is a cache hit (free), so quota is only spent on genuinely new
`(q, date, geo, data_type, tz)` combinations. Each fetch prints `[LIVE CALL]` or
`[CACHE HIT]` to stderr so you can track quota.

## Verified API facts (ground truth — do not re-derive by guessing)

- **Endpoint:** `GET https://serpapi.com/search.json?engine=google_trends&q=…&date=…&geo=…`.
  `data_type` = `TIMESERIES` (default) or `RELATED_QUERIES`.
- **Keyword syntax inside one `q` term:** `,` separates up to **5 independent series**
  (shared 0–100 scale); `+` is **OR/union** (`lingerie + victoria's secret` = ONE series
  for either query — the primary tool for combination keywords); quotes force exact phrase;
  `-` excludes (`victoria -beckham`). A `+` combination is a *different keyword* from its
  parts — its own cache entry, its own validation, recorded verbatim in output.
- **Granularity** (assert it, never assume — `trends_client.assert_granularity` infers it
  from consecutive-timestamp gaps and fails loudly on mismatch):

  | Requested span | Granularity |
  |---|---|
  | ≤ 7 days | hourly (excluded from this methodology — too noisy) |
  | custom `YYYY-MM-DD YYYY-MM-DD` ≤ ~269 days | **daily** |
  | > ~269 days, ≤ 5y (`today 12-m`, `today 5-y`) | **weekly** |
  | > 5 years (`all`) | monthly |

  **Never request a custom daily window longer than 224 days** (verified-safe ceiling;
  beyond ~269d Google silently down-samples to weekly).
- **Response:** `interest_over_time.timeline_data[]`; parse `timestamp` (Unix seconds, UTC,
  **start** of the bucket), never the human `date` string. Use `extracted_value` (int), not
  `value` (string). `partial_data` sits at the **timeline-point level**, NOT inside
  `values[]`, and is present (`true`) only on the in-progress bucket.
- **Weeks run Sunday → Saturday**; custom ranges snap outward to Sunday boundaries. The
  bucket containing "now" is always `partial_data: true` and **must never feed a model** —
  a bucket is confirmed iff `partial_data` is absent (do not hardcode a confirmation
  weekday).
- **The normalization trap:** values are 0–100 rescaled **within each request** (window max
  = 100). Two requests are not comparable without overlap-rescaling; a dominant keyword
  crushes a niche one to 0–2 (integer quantization → fetch niche keywords alone).

Full details in [`references/serpapi-google-trends.md`](references/serpapi-google-trends.md).

## Step 1 — Keyword identification

Goal: 3–5 keywords per revenue segment whose **YoY changes** track the reported segment
revenue. Expect iteration.

0. **Settle manual-vs-API mode first** (behavioral rule 1 above) — ask if interactive, else
   default to API mode when headless; this comes before any probe.
1. **Candidates** from the segment's actual products/brands: brand term, brand+category
   (`victoria's secret pajamas`), sub-brand (`pink victoria secret`), and **`+` combinations**
   unioning category + brand demand (`lingerie + victoria's secret`) or pooling spelling
   variants (`pink victoria secret + vs pink`). Prefer **purchase-intent** terms over
   news-driven ones — a scandal spikes the brand term without moving revenue.
2. **Disambiguation:** set `--geo` to the revenue geography (`US` for US retail). Run
   `--data-type RELATED_QUERIES` once per candidate to confirm it means what you think
   ("pink" alone is hopeless; "victoria" is ambiguous). In manual mode the user checks the
   related-queries panel on the web UI.
3. **Validation:** fetch ≤5 survivors in **one** 5y relative request, aggregate to fiscal
   quarters (Step 2), and correlate **YoY changes** (not levels — shared seasonality inflates
   level correlations) against reported segment revenue (source it via the
   `financialmodellingprep` skill / filings — out of this skill's scope). Keep stable, high
   correlation; need ≥ 2–4 years of overlap.

```bash
# manual exploration — prints web-UI URLs, ZERO quota:
python scripts/fetch_trends.py --keywords "victoria's secret" "lingerie + victoria's secret" \
    "pink victoria secret + vs pink" --geo US --explore-urls

# API validation — one request, up to 5 keywords on a shared scale:
python scripts/fetch_trends.py --keywords "victoria's secret" "lingerie + victoria's secret" \
    --date "today 5-y" --geo US --out candidates.csv
```

## Step 2 — Quarter normalization & current-quarter nowcast

`quarterly_index.py` does this end-to-end for one keyword. Logic:

1. **Spine:** one 5-year **weekly** series (1 request) — all history lives on this scale.
2. **Daily refill:** weekly Sun–Sat buckets straddle fiscal-quarter boundaries, so for exact
   alignment and the in-progress quarter, fetch custom **daily windows ≤ 224 days**, then
   rescale each onto the spine:
   `factor = mean(spine weekly over overlap) / mean(window daily→Sun–Sat weekly over overlap)`,
   computed over **all fully-confirmed overlapping weeks** (long overlap — single-week ratios
   are noisy and values are integer-quantized).
3. **Aggregate to fiscal quarters** using the company's fiscal calendar (VSCO FY ends
   ~Jan 31). Quarterly index = sum of stitched daily values in the quarter. **Partial buckets
   are always dropped.**
4. **Nowcast** the in-progress quarter from N confirmed days: QTD index vs the
   *same-days-elapsed* point in each prior year (**day-of-quarter alignment**, not calendar
   date — keeps 4-5-4 retail holiday weeks aligned). Primary signal = **YoY QTD ratio**;
   secondary = scale QTD to a full quarter via the historical cumulative shape (mean fraction
   accrued by day N). Report uncertainty honestly — early in the quarter the shape
   extrapolation dominates.

```bash
# always dry-run first — prints the request plan, spends ZERO quota:
python scripts/quarterly_index.py --keyword "victoria's secret" --geo US \
    --fiscal-year-end 01-31 --years 5 --dry-run

# live run (re-runs are free via cache):
python scripts/quarterly_index.py --keyword "victoria's secret" --geo US \
    --fiscal-year-end 01-31 --years 5 --out-prefix vsco
```

Use `--fiscal-quarter-ends YYYY-MM-DD,…` for exact retail 4-5-4 quarter-end dates from
filings; `--fiscal-year-end MM-DD` is a month-end approximation. The output is a clean
quarterly **index**, not dollars — calibrate to revenue with a regression in the
`data-analysis` skill; this skill does not fit the model.

## Pitfalls (always check)

- **Per-request rescaling** (the normalization trap) — never compare values across requests
  without overlap-rescaling.
- **Partial buckets** — never modelled; `quarterly_index.py` drops them and excludes today's
  bucket from the QTD row.
- **Sunday-snap** of custom ranges — windows widen outward to Sun–Sat.
- **News-spike contamination** — a spike > ~3σ may be a scandal/news event, not demand;
  cross-check `RELATED_QUERIES` before trusting it.
- **Integer quantization** — fetch niche keywords alone, not alongside a dominant term that
  crushes them to 0–2.
- **Interest ≠ transactions** — calibrate to revenue via regression; never read the index as
  dollars.

The long-form math/rationale (overlap-rescaling derivation, cumulative-shape extrapolation,
the confirmation-day calibration curiosity) is in
[`references/methodology.md`](references/methodology.md).

## Scripts

- `scripts/trends_client.py` — the only file that talks HTTP. Auth, mandatory disk cache
  (`{fetched_at, request_params, raw_response}` envelope), `timestamp` parsing, granularity
  assertion, provenance rows. Import it for custom pulls.
- `scripts/fetch_trends.py` — raw series → tidy CSV; `--explore-urls` for manual mode.
- `scripts/quarterly_index.py` — spine + daily windows → stitched quarterly index + QTD
  nowcast; `--dry-run` to see the plan free.

## Tests

`tests/test_quarterly_index.py` runs **offline** on recorded JSON fixtures (never calls the
API — quota). Run from the skill folder:

```bash
pytest tests -q
```
