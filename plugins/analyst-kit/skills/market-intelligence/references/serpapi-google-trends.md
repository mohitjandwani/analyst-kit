# SerpAPI Google Trends — API Reference

Full reference for the SerpAPI `engine=google_trends` endpoint as used by this
skill. The facts below were **probed live on 2026-06-12** — treat them as ground
truth, do not re-derive by guessing. The only file that talks HTTP is
`scripts/trends_client.py`; import it rather than re-implementing the call.

---

## Request

```
GET https://serpapi.com/search.json
    ?engine=google_trends
    &q=<keyword>                # up to 5 comma-separated keywords (relative mode)
    &date=<range>              # see granularity table
    &api_key=$SERPAPI_API_KEY  # appended at request time, NEVER stored/committed
    # optional: geo=US, tz=<minutes>, data_type=TIMESERIES|RELATED_QUERIES|...
```

**Authentication:** `api_key` query parameter (`SERPAPI_API_KEY`). Free tier =
**100 searches/month** — this constraint drives the mandatory disk cache (below).
Never write the literal key into any committed file.

### `q` — keyword syntax (Google Trends semantics, passed through by SerpAPI)

| Operator | Meaning | Example |
|---|---|---|
| `,` | separates **independent series** (≤ 5, shared 0–100 scale) | `nike, adidas` → two series |
| `+` | **OR / union** — ONE series aggregating either query | `lingerie + victoria's secret` |
| `"…"` | exact phrase | `"victoria's secret"` |
| `-` | exclude | `victoria -beckham` |

- `+` is the primary tool for **combination keywords** that union category +
  brand demand (`lingerie + victoria's secret`) or pool spelling variants
  (`pink victoria secret + vs pink`).
- A `+` combination is a **different keyword** from its parts: its own cache
  entry, its own validation run, and outputs must record the exact string used.
- Up to **5** comma-separated series in one relative request share a single
  0–100 scale (useful for comparing keywords; fatal if a dominant keyword
  crushes a niche one — see the normalization trap).

### `date` — ranges

- Relative: `now 1-d`, `now 7-d`, `today 1-m`, `today 3-m`, `today 12-m`,
  `today 5-y`, `all`.
- Absolute custom window: `YYYY-MM-DD YYYY-MM-DD` (space-separated).

### `geo`

Two-letter country (e.g. `US`) or sub-region code. Set it to the **revenue
geography** of the segment you are modelling (US retail → `US`).

### `data_type`

- `TIMESERIES` (default) → `interest_over_time` series.
- `RELATED_QUERIES` → top/rising related queries (used once per candidate for
  disambiguation in Step 1).

---

## Granularity rules (all verified by live calls)

| Requested span | Granularity | Verified by |
|---|---|---|
| ≤ 7 days (`now 7-d`, `now 1-d`) | **hourly** | `now 7-d` → 169 points |
| custom span ≤ ~269 days | **daily** | 224-day custom range → 224 daily points; `today 3-m` → 93 daily points |
| custom span > ~269 days, ≤ 5y | **weekly** | 285-day custom range → weekly; `today 12-m` → 53 weekly; `today 5-y` → 262 weekly |
| > 5 years (`all`) | monthly (per Google docs; not probed — confirm with one call if ever needed) |

**This corrects the working assumption that ">3 months returns daily."** Daily
data is available for any *custom* `date=YYYY-MM-DD YYYY-MM-DD` window up to
~269 days (~8.8 months); beyond that Google silently drops to weekly. The exact
cutoff between 224 and 285 days was not bisected (quota), so:

- **Never request a custom daily window longer than 224 days** (verified safe).
- **Assert the returned granularity** rather than assume it — infer from the gap
  between consecutive `timestamp`s: `3600` = hourly, `86400` = daily, `604800` =
  weekly. `trends_client.assert_granularity()` does this and **fails loudly** on
  a mismatch with the request's expectation, guarding the ~269-day cliff.

**Hourly data is excluded from the methodology** — confirmed available but too
noisy to carry revenue signal, and each ≤7-day window is independently 0–100
rescaled, so it adds no information for quarterly work.

---

## Response shape

`interest_over_time.timeline_data` is a list of points:

```json
{
  "date": "Jun 7 – 13, 2026",        // human string (en-dash + thin spaces) — do NOT parse this
  "timestamp": "1780790400",          // Unix seconds, UTC, START of the bucket — parse THIS
  "partial_data": true,               // ONLY present (and true) on in-progress buckets; absent otherwise
  "values": [
    { "query": "victoria's secret", "value": "14", "extracted_value": 14 }
  ]
}
```

- Parse `timestamp` (Unix seconds, UTC, **start** of the bucket) — never the
  human `date` string.
- Use `extracted_value` (int), not `value` (string).
- ⚠️ `partial_data` sits at the **timeline-point level**, NOT inside `values[]`.
  A bucket is **confirmed iff `partial_data` is absent**.
- `RELATED_QUERIES` responses live under `related_queries` (top + rising lists).

### Error / empty shapes

- SerpAPI error → `{"error": "…"}`. `trends_client` raises `TrendsError` with the
  message.
- Unknown / too-low-volume keyword → empty `interest_over_time` (no
  `timeline_data`). `trends_client.parse_rows` raises a clear message.

---

## Weeks, partial buckets, confirmation day

- **Weeks run Sunday → Saturday** (verified: bucket "Jun 8 – 14, 2025" starts
  Sunday Jun 8). Custom ranges **snap outward to Sunday boundaries**: a request
  starting 2025-09-01 (Mon) returned a first bucket of Aug 31 – Sep 6.
- The bucket containing "now" is **always** `partial_data: true` (verified at
  hourly, daily, weekly). Partial values change on later fetches — **never feed a
  partial bucket into a model.**
- Confirmation day: on Friday 2026-06-12 the prior full week (May 31 – Jun 6) was
  already confirmed. One snapshot can't pin whether confirmation lands Wed or Thu,
  so **do not hardcode a weekday**. The rule: *a bucket is confirmed iff
  `partial_data` is absent.* (A one-time calibration — fetch `today 1-m` each
  weekday for a week and note when the prior week's flag disappears — is a
  curiosity only; no logic may depend on it.)

---

## The normalization trap

Values are **0–100 rescaled within each request**: the max point *in that window,
across all keywords in that request* = 100. Consequences:

1. Values from two different requests are **not comparable** — stitching requires
   overlap-rescaling (see `references/methodology.md`).
2. Up to 5 keywords in one request share one scale — useful for comparing
   keywords, fatal if a dominant keyword crushes a niche one to 0–2 (integer
   quantization → fetch niche keywords alone).

---

## Mandatory output provenance (data-delivery contract)

Trends values are mutable (partial buckets change; Google occasionally re-bases
history) and window-relative, so a number without provenance is worthless. **Every
delivered row — CSV, JSON, cache file, quarterly index, nowcast table — must
carry:**

| Column | Meaning |
|---|---|
| `keyword` | the **exact** `q` term used, verbatim incl. `+`/quotes/`-` |
| `is_partial` | from the point-level `partial_data` flag (true/false, never blank) |
| `fetched_at` | UTC date+time the API call was made; cache hits keep the **original** time, so staleness is visible |
| `bucket_start` | parsed from `timestamp` |
| `value` | `extracted_value` |
| `geo`, `date_range`, `granularity` | request context needed to reproduce the scale |

The cache persists `fetched_at` and the full request params alongside the raw
response so this contract survives cache hits. Aggregated outputs (quarterly index
rows) carry the same columns, with `is_partial = true` if *any* contributing bucket
was partial and `fetched_at` = oldest contributing fetch.

---

## Disk cache (mandatory — `trends_client`)

- Raw JSON is cached under the skill's `data/cache/`, keyed by a hash of
  `(q, date, geo, data_type, tz)`, wrapped in an envelope
  `{fetched_at, request_params, raw_response}`.
- **Freshness rule:** a cached response whose window has fully closed (absolute
  `date` range **and** no partial bucket) **never expires**; any response
  containing a partial bucket, or a relative range like `today 3-m`, expires
  after ~6 hours.
- Each fetch prints `[LIVE CALL]` or `[CACHE HIT]` to stderr (with the original
  `fetched_at`) so quota is trackable. Repeat runs of `quarterly_index.py` are
  free.

---

## Manual-exploration URLs (zero quota)

`trends_client.explore_url(keyword, date, geo)` (and
`fetch_trends.py --explore-urls`) build Google Trends web-UI links using the same
`q`/`+`/quote/`-` syntax. The `+` union operator is encoded as `%2B` — a *literal*
`+` in a URL query decodes to a space in browsers, which would silently destroy
the union, so `%2B` is required. These links are free and unlimited and power the
manual Step-1 exploration mode.
