# Plan: `market-intelligence` skill (Google Trends via SerpAPI)

Implementation plan for a new **capability** skill that uses alternative data
(Google Trends, fetched through SerpAPI) to nowcast how a company is doing —
the flagship use case being **predicting a revenue segment for the current
quarter** (e.g. Victoria's Secret) from search-interest data.

This plan was written after empirically probing the live API on **2026-06-12**.
Section 2 contains **verified facts — treat them as ground truth and do not
re-derive them by guessing**. Everything in Section 4+ is what you build.

---

## 1. Scope

**In scope (v1):** one data source — SerpAPI `engine=google_trends`
(`TIMESERIES` + `RELATED_QUERIES`). A Python client with disk caching, a
fetch CLI, a quarter-normalization pipeline, and a SKILL.md that teaches the
agent the two-step methodology (keyword identification → quarter
normalization / revenue-segment prediction).

**Out of scope (v1):** other APIs (the skill is named `market-intelligence`
precisely so more sources can be added later), web-scraped trends, the actual
regression model fitting (the skill produces a clean quarterly *index*; the
existing `data-analysis` skill does modelling).

---

## 2. Verified API facts (probed live, 2026-06-12)

### 2.1 Request

```
GET https://serpapi.com/search.json
    ?engine=google_trends
    &q=<keyword>              # up to 5 comma-separated keywords (relative mode)
    &date=<range>             # see granularity table
    &api_key=$SERPAPI_API_KEY
    # optional: geo=US, tz=<minutes>, data_type=TIMESERIES|RELATED_QUERIES|...
```

**Keyword syntax inside one `q` term** (Google Trends semantics, passed
through by SerpAPI — document these in the reference file):

- `,` separates **independent series** (≤5, shared 0–100 scale).
- `+` inside a term is **OR/union**: `lingerie + victoria's secret` is ONE
  series aggregating searches for either query — this is the primary tool for
  building *combination* keywords per revenue segment.
- Quotes force exact phrase; `-` excludes (`victoria -beckham`).

A combined `+` term is a *different keyword* from its parts: it gets its own
cache entry and its own validation run, and outputs must record the exact
string used (§2.6).

The key lives in `SERPAPI_API_KEY` (already in the repo-root `.env`,
git-ignored). **Free tier = 100 searches/month** — this constraint drives the
caching design in §5.1. Never put the literal key in any committed file.

### 2.2 Response shape

`interest_over_time.timeline_data` is a list of points:

```json
{
  "date": "Jun 7 – 13, 2026",        // human string; en-dash + thin spaces ( ) — do NOT parse this
  "timestamp": "1780790400",          // Unix seconds, UTC, START of the bucket — parse THIS
  "partial_data": true,               // ONLY present (and true) on in-progress buckets; absent otherwise
  "values": [
    { "query": "victoria's secret", "value": "14", "extracted_value": 14 }
  ]
}
```

⚠️ `partial_data` sits at the **timeline-point level**, NOT inside `values[]`.
Use `extracted_value` (int), not `value` (string).

### 2.3 Granularity rules (all verified by live calls)

| Requested span                  | Granularity | Verified by                                  |
|---------------------------------|-------------|----------------------------------------------|
| ≤ 7 days (`now 7-d`, `now 1-d`) | **hourly**  | `now 7-d` → 169 points                       |
| custom span ≤ ~269 days         | **daily**   | 224-day custom range → 224 daily points; `today 3-m` → 93 daily points |
| custom span > ~269 days, ≤ 5 y  | **weekly**  | 285-day custom range → weekly; `today 12-m` → 53 weekly; `today 5-y` → 262 weekly |
| > 5 years (`all`)               | monthly (per Google docs; not probed — confirm with one call if v1 ever needs it) |

**This corrects the working assumption that ">3 months returns daily".** Daily
data is available for any *custom* `date=YYYY-MM-DD YYYY-MM-DD` window up to
~269 days (~8.8 months); beyond that Google silently drops to weekly. The
exact cutoff between 224 and 285 days was not bisected (quota); the skill must
**never request custom daily windows longer than 224 days** (verified safe)
and must *assert* the returned granularity rather than assume it (infer from
the gap between consecutive `timestamp`s: 3600 = hourly, 86400 = daily,
604800 = weekly).

**Hourly data is excluded from the methodology** — confirmed available but
too noisy to carry revenue signal, and each ≤7-day window is independently
0–100 rescaled, so it adds no information for quarterly work.

### 2.4 Weeks, partial buckets, confirmation day

- **Weeks run Sunday → Saturday** (verified: bucket "Jun 8 – 14, 2025" starts
  Sunday Jun 8). Custom ranges **snap outward to Sunday boundaries**: a request
  starting 2025-09-01 (Mon) returned a first bucket of Aug 31 – Sep 6.
- The bucket containing "now" is **always** flagged `partial_data: true`
  (verified at hourly, daily, and weekly granularity). Partial values change
  on later fetches — **never feed a partial bucket into a model**.
- Confirmation day: on Friday 2026-06-12, the prior full week (May 31 – Jun 6)
  was already confirmed (no flag). One snapshot cannot pin whether
  confirmation lands Wednesday or Thursday, so **do not hardcode a weekday**.
  The rule the skill must follow: *a bucket is confirmed iff `partial_data` is
  absent*. Optionally, document a one-time calibration (fetch `today 1-m` each
  weekday for one week; note the day the prior week's flag disappears) as a
  curiosity, but no logic may depend on it.

### 2.5 The normalization trap (drives the whole methodology)

Values are **0–100 rescaled within each request**: the max point *in that
window, across all keywords in that request* = 100. Consequences:

1. Values from two different requests are **not comparable** — stitching
   requires overlap-rescaling (§4 step 2).
2. Up to 5 keywords in one request share one scale — useful for comparing
   keywords, fatal if a dominant keyword crushes a niche one to 0–2 (loss of
   precision: values are integers).

### 2.6 Mandatory output provenance (data-delivery contract)

Trends values are mutable (partial buckets change; Google occasionally
re-bases history) and window-relative, so a number without provenance is
worthless. **Every delivered row — CSV, JSON, cache file, quarterly index,
nowcast table — must carry:**

| Column        | Meaning                                                            |
|---------------|--------------------------------------------------------------------|
| `keyword`     | the **exact** `q` term used, verbatim incl. `+`/quotes/`-` syntax  |
| `is_partial`  | from the point-level `partial_data` flag (true/false, never blank) |
| `fetched_at`  | UTC date+time the API call was made (cache hits keep the **original** fetch time, so staleness is visible) |
| `bucket_start`| parsed from `timestamp`                                            |
| `value`       | `extracted_value`                                                  |
| `geo`, `date_range`, `granularity` | request context needed to reproduce the scale |

The cache must persist `fetched_at` and the full request params alongside the
raw response so this contract survives cache hits. Aggregated outputs
(quarterly index rows) carry the same columns, with `is_partial = true` if
*any* contributing bucket was partial and `fetched_at` = oldest contributing
fetch.

---

## 3. Repo contract checklist (from CLAUDE.md — all mandatory)

- [ ] Folder `skills/market-intelligence/`, frontmatter `name: market-intelligence` (= folder, kebab-case).
- [ ] `type: capability` (a requirable data/methodology unit, like `financialmodellingprep`).
- [ ] `description` ≥ 40 chars **with a `Triggers:` clause** (see §5.4 for required content).
- [ ] `env:` lists `SERPAPI_API_KEY`, **and** `SERPAPI_API_KEY` is added to `.env.example`
      (validator enforces the pair). `.env.example` entry should note: free key at
      https://serpapi.com/, 100 searches/month.
- [ ] Frontmatter stays within the shapes `src/frontmatter.js` parses (block `description: >`,
      block list `env:` — copy the structure of `skills/financialmodellingprep/SKILL.md`).
- [ ] No `node_modules`/`.venv`/`__pycache__` tracked. Python scripts ⇒ registry infers `runtime: python`.
- [ ] After creating: `npm run build:registry` then `npm run validate` (never hand-edit registry.json).
- [ ] Add `"../../skills/market-intelligence"` to `plugins/us-stock-analyst` and
      `plugins/international-analyst` manifests (it has no `requires:`, so no closure to drag in).

---

## 4. The methodology the skill teaches (SKILL.md body content)

This is the intellectual core; the scripts in §5 are its mechanical arms. The
worked example throughout is Victoria's Secret (VSCO): match Google Trends to
a revenue segment, two steps.

### Step 1 — Keyword identification

Produce 3–5 keywords per revenue segment, validated against history.
Expect **iteration**: for a given company you will try many candidates and
combinations before finding ones that track revenue.

0. **Ask the user first — manual vs API exploration (mandatory gate).**
   Keyword exploration is the unbounded-cost part (each probe = 1 of 100
   monthly searches), so before spending *any* quota on candidates, SKILL.md
   must instruct the agent to ask the user (via its question tool) which mode
   to use:
   - **Manual (default/recommended):** the agent generates the candidate list
     plus ready-to-open Google Trends web-UI URLs
     (`https://trends.google.com/trends/explore?date=today%205-y&geo=US&q=lingerie%20%2B%20victoria's%20secret`
     — same `q`/`+` syntax, free, unlimited), the user eyeballs/compares in
     the browser and reports back the 3–5 winners; only those get API calls.
   - **API:** the agent explores via SerpAPI itself; it must state the
     estimated number of calls up front (candidates ÷ 5 per relative request,
     + 1 RELATED_QUERIES per surviving term), get explicit agreement on that
     budget, and pack candidates 5-per-request to stretch quota.
1. **Candidate generation.** From the segment's actual products/brands (e.g.
   VSCO segments: Victoria's Secret stores, PINK, Beauty, Digital). Include
   the brand term, brand+category terms ("victoria's secret pajamas"),
   sub-brand terms ("pink victoria secret"), and **`+` combinations** that
   union category + brand demand (`lingerie + victoria's secret`) or pool a
   sub-brand's spelling variants (`pink victoria secret + vs pink`). Prefer
   *purchase-intent-adjacent* terms over news-driven ones (a scandal spikes
   "victoria's secret" without moving revenue — note this failure mode
   explicitly in SKILL.md).
2. **Disambiguation.** Set `geo` to the segment's revenue geography (e.g.
   `geo=US` for US retail). Run `data_type=RELATED_QUERIES` once per candidate
   to check the term means what you think (e.g. "pink" alone is hopeless;
   "victoria" is ambiguous). In manual mode the user does this on the web UI's
   related-queries panel instead.
3. **Validation.** Fetch ≤5 candidates in **one** relative request over 5y
   (weekly), aggregate each to fiscal quarters (Step 2 logic), and correlate
   against the reported segment revenue series (source it via the
   `financialmodellingprep` skill / company filings — out of this skill's
   scope, just reference it). Keep keywords with stable, high correlation
   *of YoY changes* (level correlations are inflated by shared seasonality);
   2–4 years of overlapping history minimum.

### Step 2 — Quarter normalization & current-quarter prediction

The goal: one **consistent quarterly index per keyword** spanning history +
the in-progress quarter, despite per-request 0–100 rescaling.

1. **Spine.** Fetch one 5-year weekly series per keyword (1 request). All
   history is expressed on this scale.
2. **Daily refill (only where needed).** Weekly Sun–Sat buckets straddle
   fiscal-quarter boundaries. For exact quarter alignment and for the
   in-progress quarter, fetch **custom daily windows ≤ 224 days** that cover
   each fiscal year-ish chunk, then rescale each daily window onto the spine:
   `factor = mean(spine weekly values over overlap) / mean(window daily values aggregated to the same Sun–Sat weeks)`,
   computed over **all fully-confirmed overlapping weeks** (use a long
   overlap, not one week — single-week ratios are noisy and values are
   integer-quantized). Multiply the window's daily values by `factor`.
   - Cheaper v1 alternative the implementer may choose: skip daily refill for
     history and apportion straddling weekly buckets pro-rata by days; daily
     data is then only fetched for the current + prior quarter. Document
     whichever is chosen.
3. **Aggregate to fiscal quarters.** Use the company's fiscal calendar (VSCO's
   FY ends ~Jan 31; retail 4-5-4 weeks — get exact quarter dates from filings
   or `financialmodellingprep`). Quarterly index = sum (or mean) of stitched
   daily values in the quarter. **Drop partial buckets always.**
4. **Current-quarter nowcast.** With N confirmed days of the in-progress
   quarter:
   - Compute quarter-to-date index and the *same-days-elapsed* index for each
     historical year (day-of-quarter alignment, not calendar date — keeps
     holiday weeks aligned for 4-5-4 retail calendars).
   - The primary signal is **YoY: QTD(this year) / QTD(same point, last
     year)**, applied to last year's reported segment revenue; secondarily,
     scale QTD to a full-quarter estimate using the historical intra-quarter
     cumulative shape (mean fraction of the quarter's total search volume that
     had accrued by day N).
   - Report uncertainty honestly: early in the quarter (N small) the shape
     extrapolation dominates and error bars are wide; say so in output.
5. **Pitfalls section (must be in SKILL.md):** per-request rescaling (§2.5);
   partial buckets; Sunday-snap of custom ranges; news-spike contamination
   (inspect spikes > ~3σ, cross-check RELATED_QUERIES before trusting them);
   integer quantization of low-value keywords (fetch niche keywords alone,
   not alongside a dominant term); trends measure *interest*, not
   *transactions* — calibrate to revenue via regression, never read the index
   as dollars.

---

## 5. Files to build

Mirror the `finmind` skill layout (Python scripts + references, stdlib-only
preferred — `urllib.request` is fine, no `requests` dependency unless needed).

```
skills/market-intelligence/
├── SKILL.md
├── scripts/
│   ├── trends_client.py      # shared client: auth, cache, fetch, granularity assert, partial filter
│   ├── fetch_trends.py       # CLI: raw series → tidy CSV/JSON
│   └── quarterly_index.py    # CLI: spine+windows → stitched quarterly index + QTD nowcast table
├── references/
│   ├── serpapi-google-trends.md   # full API reference (params, response schema, §2 facts verbatim)
│   └── methodology.md             # the long-form math/rationale behind §4
└── tests/
    └── test_quarterly_index.py    # offline tests on recorded fixtures
```

### 5.1 `trends_client.py` (the only file that talks HTTP)

- Reads `SERPAPI_API_KEY` from env; if unset, print the same style of
  instruction `finmind` scripts use and exit non-zero.
- **Disk cache is mandatory** (100 req/month): cache raw JSON under the
  skill's working dir keyed by a hash of `(q, date, geo, data_type, tz)`,
  wrapped in an envelope `{fetched_at, request_params, raw_response}` so the
  provenance contract (§2.6) survives cache hits.
  Rule: a cached response whose window ends in the past **and** contains no
  partial bucket never expires; any response containing a partial bucket (or
  a relative range like `today 3-m`) expires after ~6 hours. Print whether
  each fetch was cache-hit or live (user must be able to track quota).
- Parse `timestamp` (never the `date` string), emit rows in the §2.6 schema:
  `(bucket_start, keyword, value, is_partial, fetched_at, geo, date_range, granularity)` —
  `keyword` is the verbatim `q` term (combinations like
  `lingerie + victoria's secret` kept as one string), `is_partial` always
  explicitly true/false.
- **Assert granularity** from consecutive-timestamp deltas and fail loudly on
  mismatch with the request's expectation (guards the ~269-day cliff).
- Handle SerpAPI error shape (`{"error": "..."}`) and empty
  `interest_over_time` (unknown keyword) with clear messages.

### 5.2 `fetch_trends.py`

Thin CLI over the client: `--keywords` (≤5; each may itself be a `+`
combination), `--date`, `--geo`, `--data-type`,
`--drop-partial/--keep-partial` (default **keep**, since `is_partial` is an
explicit column the consumer can filter on — modelling code drops, humans may
want to see today's bucket), output tidy CSV (§2.6 columns) to stdout or
`--out`. Add `--explore-urls` which prints Google Trends web-UI URLs for the
given keywords *instead of* calling the API — this powers the manual mode of
§4 Step 1.0. This CLI is what the agent uses for exploration and Step-1
validation.

### 5.3 `quarterly_index.py`

Implements §4 Step 2 end-to-end for one keyword set:
`--keyword`, `--geo`, `--fiscal-quarter-ends` (CSV of dates or a
`--fiscal-year-end MM-DD` convenience), `--years 5`. Plans its own requests
(spine + ≤224-day daily windows), stitches, aggregates, and emits: a quarterly
index table, the QTD comparison for the in-progress quarter, and the
day-of-quarter cumulative-shape estimate — as CSV + a short human-readable
summary. Keep the request plan visible (`--dry-run` prints planned API calls
without spending quota).

### 5.4 `SKILL.md`

- Frontmatter per §3. Description must say what it does (predict revenue
  segments / nowcast company performance from Google Trends search interest
  via SerpAPI) and include
  `Triggers: "google trends for X", "can search interest predict Y's revenue", "nowcast <company> sales", "build a trends-based revenue model for Z", "market intelligence on <ticker>"`.
- Body: setup (env key, free-tier quota warning), the §2 facts table
  (condensed), the §4 methodology with the VSCO worked example, script usage
  examples, and the pitfalls list. Long derivations go to
  `references/methodology.md`; SKILL.md stays operational.
- Two behavioral rules stated prominently (top of body, not buried):
  1. **Before any exploratory keyword API calls, ask the user: manual
     Google Trends exploration (free, default) or API exploration (state the
     call budget first)?** (§4 Step 1.0.)
  2. **Never deliver trends numbers without the §2.6 provenance columns** —
     keyword used verbatim, partial flag, and fetch date on every row.

### 5.5 Tests

Offline only — **tests must never call the API** (quota). Record 2–3 real
responses as JSON fixtures (the probing responses described in §2 can be
regenerated with single calls if needed) and unit-test: timestamp parsing,
partial-bucket filtering, granularity assertion, overlap-rescaling math, and
fiscal-quarter aggregation across a straddling week. Run with `pytest` from
the skill folder, like `finmind`.

---

## 6. Build order & verification

1. `.env.example` entry + skill folder + minimal SKILL.md frontmatter/body →
   `npm run build:registry && npm run validate` passes (registry should show
   `runtime: python` once scripts exist).
2. `trends_client.py` + `fetch_trends.py`. Verify live with **two** calls:
   `--keywords "victoria's secret" --date "today 12-m" --geo US` (expect 53
   weekly rows, last row flagged partial) and a 3-month fetch (expect daily).
   Save both raw responses as test fixtures.
3. `quarterly_index.py` + tests on fixtures. `--dry-run` first; then one live
   end-to-end run for VSCO US (budget ≤ 10 calls total for the whole build).
4. References + final SKILL.md.
5. Plugin manifests + re-validate.
6. Commits (conventional, one logical change each), e.g.:
   - `feat(market-intelligence): scaffold skill + serpapi env contract`
   - `feat(market-intelligence): trends client with caching + fetch CLI`
   - `feat(market-intelligence): quarterly index + current-quarter nowcast`
   - `feat(plugins): ship market-intelligence in analyst personas`

**Definition of done:** `npm run validate` + `npm run check:registry` green;
`pytest` green offline; one live VSCO run produces a quarterly index table
whose confirmed quarters are stable across two invocations (cache) and whose
QTD row excludes today's partial bucket; every emitted row carries `keyword`,
`is_partial`, and `fetched_at` (incl. on cache hits, where `fetched_at` must
be the original call time); `--explore-urls` produces working Google Trends
links for a `+`-combination keyword without spending quota; total live API
spend for the build ≤ 10 of the 100 monthly searches.
