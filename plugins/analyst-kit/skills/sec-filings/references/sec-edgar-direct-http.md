# SEC EDGAR — raw HTTP reference & edge-case catalog (Layer B)

The fallback layer. Use when the MCP server is absent, a tool returns empty, or you need
a document/field the tools don't expose. **Every shape below was verified live** against
the real SEC APIs (June 2026). Three hosts do everything:

| Host | Serves | Auth |
|---|---|---|
| `data.sec.gov` | structured JSON: submission history, XBRL facts | `User-Agent` header |
| `www.sec.gov/Archives` | raw filing documents (HTML / iXBRL / `.txt`) + folder index | `User-Agent` header |
| `efts.sec.gov` | full-text search (2001-present) | `User-Agent` header |

**Mandatory on every request:** `User-Agent: <app> <contact-email>`. Missing → **403**.

```bash
UA="analyst-kit research you@example.com"
curl -s -H "User-Agent: $UA" "https://data.sec.gov/submissions/CIK0000320193.json"
```

---

## 1. Ticker → CIK

```
GET https://www.sec.gov/files/company_tickers.json
```
- Shape: a **dict keyed by stringified index**, not a list:
  `{ "0": {cik_str, ticker, title}, "1": {...}, ... }` (~10,400 entries).
- `cik_str` is an **int with no zero-padding** (e.g. `320193`). Pad to 10 for `data.sec.gov`.
- Alternative with exchange info: `https://www.sec.gov/files/company_tickers_exchange.json`
  (this is what the MCP `TickerCache` uses).

```python
import json, urllib.request
req = urllib.request.Request(
    "https://www.sec.gov/files/company_tickers.json",
    headers={"User-Agent": "analyst-kit you@example.com"})
m = json.load(urllib.request.urlopen(req))
by_ticker = {v["ticker"]: v["cik_str"] for v in m.values()}
cik10 = f"CIK{by_ticker['AAPL']:010d}"   # -> "CIK0000320193"
```

---

## 2. Submissions feed — the filing index

```
GET https://data.sec.gov/submissions/CIK{0-padded-10}.json
```
**Top-level keys (verified):** `cik, entityType, sic, sicDescription, name, tickers,
exchanges, ein, lei, description, category, fiscalYearEnd, stateOfIncorporation,
addresses, phone, flags, formerNames, filings`.

**`filings.recent` is column-oriented** — parallel arrays, zip by index (newest-first):
```
accessionNumber, filingDate, reportDate, acceptanceDateTime, act, form,
fileNumber, filmNumber, items, core_type, size, isXBRL, isInlineXBRL,
isXBRLNumeric, primaryDocument, primaryDocDescription
```
```python
r = sub["filings"]["recent"]
rows = [dict(zip(r, vals)) for vals in zip(*r.values())]   # row-oriented view
tenks = [x for x in rows if x["form"] == "10-K"]           # exact match
```

### ⚠️ The 1000-filing cap + pagination (most common silent bug)
`filings.recent` holds **at most ~1000 filings** (verified: exactly 1000 for AAPL). Older
history is in **overflow files** under `filings.files[]`:
```json
"files": [{ "name": "CIK0000320193-submissions-001.json",
            "filingCount": 1234, "filingFrom": "1994-01-26", "filingTo": "2015-05-11" }]
```
```
GET https://data.sec.gov/submissions/CIK0000320193-submissions-001.json
```
- **The overflow file is a FLAT dict of the same arrays** (`accessionNumber`, `form`, …) —
  there is **no `filings.recent` wrapper**. Parse it differently from the main file.
- For a high-volume filer, 1000 filings can be **< 1 year** (insider Form 4s dominate). If
  the user asks for an older 10-K and you only read `recent`, you will wrongly report
  "not found." Always check `files[]` when the requested date predates `recent`'s tail.

---

## 3. Fetch the actual filing document

From a row's `accessionNumber` + `primaryDocument`:
```python
acc    = "0000320193-25-000079"
doc    = "aapl-20250927.htm"
nodash = acc.replace("-", "")                # 000032019325000079
cik    = 320193                              # unpadded in the Archives path
url    = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{doc}"   # -> 200, the 10-K HTML
```
- **Folder listing** (all exhibits + the XBRL zip + full submission `.txt`):
  `https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/index.json`
  → `directory.item[]` of `{ name, type, size }` (verified: 93 items for that 10-K).
- **Full raw submission** (everything concatenated, SGML-wrapped):
  `.../{nodash}/{acc}.txt`.
- Note the **Archives path uses the unpadded CIK**; the `data.sec.gov` path uses the padded one.

---

## 4. Full-text search (`efts.sec.gov`)

```
GET https://efts.sec.gov/LATEST/search-index?q=%22material+weakness%22&forms=8-K&startdt=2024-01-01&enddt=2024-03-31
```
Elasticsearch-shaped JSON. Top keys: `took, timed_out, _shards, hits, aggregations, query`.
- `hits.total` = `{ value, relation }`. **`relation:"gte"` ⇒ capped at 10000** (not exact);
  `"eq"` ⇒ exact. (Verified: a query returned `{value:409, relation:"eq"}`.)
- `hits.hits[]` — **100 results per page**. Paginate with `&from=100`, `&from=200`, ….
- Each hit:
  - `_id` = `"{accessionNumber}:{primaryDocFilename}"` — split on `:` to build the doc URL.
  - `_source` keys (verified): `ciks, period_ending, file_num, display_names, xsl,
    sequence, root_forms, file_date, biz_states, sics, form, adsh, film_num,
    biz_locations, file_type, file_description, inc_states, items`.
  - `display_names` = `["SUN COMMUNITIES INC  (SUI)  (CIK 0000912593)"]`.

**Query params:**
| Param | Purpose |
|---|---|
| `q` | phrase (URL-encode; wrap in `%22…%22` for an exact phrase) |
| `forms` | comma-separated form filter, e.g. `10-K`, `8-K` |
| `startdt` / `enddt` | ISO date bounds `YYYY-MM-DD` |
| `entityName` | scope to a company (name, ticker, or CIK — accepts **unpadded** CIK) |
| `from` | pagination offset (multiples of 100) |

**Verified gotchas:**
- The date params are **`startdt`/`enddt`**. There is **no `dateRange=custom`** param —
  passing `dateRange=custom` returns **HTTP 500**.
- Full-text search **only covers filings from 2001 onward**. Older filings exist in EDGAR
  but are not full-text indexed — find them via the submissions feed instead.
- This is the right tool for "which companies disclosed X" / "find the filing that mentions
  Y" when you don't already know the company or accession number.

---

## 5. XBRL financial data (`data.sec.gov/api/xbrl`)

Structured numeric facts — use for revenue/EPS/segment numbers instead of parsing prose.

### Single concept for one company
```
GET https://data.sec.gov/api/xbrl/companyconcept/CIK{padded}/us-gaap/{Tag}.json
# e.g. .../CIK0000320193/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json
```
- Top keys: `cik, taxonomy, tag, label, description, entityName, units`.
- `units` is keyed by unit (`"USD"`, `"shares"`, `"USD/shares"`, …); each value is a list
  of facts: `{ start, end, val, accn, fy, fp, form, filed, frame }` (verified: 113 USD
  facts for that Apple tag).

### All facts for a company
```
GET https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json
# facts.us-gaap.<Tag>.units.USD[] — large; thousands of concepts
```

### One concept across all filers for a period (peer comparison)
```
GET https://data.sec.gov/api/xbrl/frames/us-gaap/{Tag}/USD/CY2024Q4I.json
# period codes: CY2024 (annual), CY2024Q4 (quarterly), CY2024Q4I (instant, e.g. balances)
```

### ⚠️ XBRL tag drift (the silent wrong-number bug)
The same economic concept uses **different GAAP tags** across companies and years:
- Apple's revenue is **`RevenueFromContractWithCustomerExcludingAssessedTax`**, **not**
  `Revenues` (verified — `Revenues` is empty for Apple).
- Net income: `NetIncomeLoss`. EPS: `EarningsPerShareBasic` / `…Diluted`.
- **Always discover available tags first** (MCP `discover_company_metrics`, or read
  `companyfacts` keys) before hardcoding a tag. A missing tag returns 404 / empty, which
  is easy to misread as "no revenue."

Other XBRL notes:
- `fp` ∈ `{FY, Q1, Q2, Q3, Q4}`; `fy` is the fiscal year (int). A `10-K` row carries the
  full-year value; quarterly values come from `10-Q` rows.
- `frame` (e.g. `"CY2026Q1"`) is present only on facts that map cleanly to a calendar
  frame — companies with odd fiscal calendars may omit it.

---

## 6. Date semantics (don't confuse these three)

| Field | Meaning | Use for |
|---|---|---|
| `filingDate` | when the filing was submitted | "filed this week" |
| `reportDate` | the period the filing covers (period-end) | "Q3 2024 10-Q", "FY2025 10-K" |
| `acceptanceDateTime` | exact accept timestamp (with time) | intraday "filed today", ordering same-day |

A 10-K for fiscal year ending 2025-09-27 was **filed** 2025-10-31: `reportDate` =
2025-09-27, `filingDate` = 2025-10-31. Pick the field that matches the user's phrasing.

---

## 7. Edge-case catalog (each line = a real failure mode)

**Identity & lookup**
- Missing `User-Agent` → **403** on all hosts. Non-negotiable.
- Unpadded CIK in a `data.sec.gov` path → **404**. Pad to 10 (`efts` & Archives accept unpadded).
- Dotted tickers stored dash-form: `BRK.B` → **`BRK-B`**. Normalize `.`→`-` before lookup.
- Multi-class tickers share one CIK: `GOOGL` & `GOOG` → **`1652044`**. The company files
  once; don't expect per-class filings.
- Bogus/unknown CIK → **404** (not an empty 200).
- Some tickers in the map are funds/trusts, not the operating company the user means —
  confirm `title` matches intent.

**Filing lists**
- `filings.recent` capped at ~1000; older history only via `filings.files[]` overflow
  files (flat dict, no `recent` wrapper). See §2.
- Form matching is **exact**: `"10-K" != "10-K/A"` (amendment); `"DEF 14A"` contains a
  space; `"10-K405"` is a legacy variant. Decide whether amendments count.
- Arrays are newest-first; "latest" = first match, not last.

**Documents**
- `primaryDocument` is the main doc, but the substantive content for some forms lives in
  **exhibits** (e.g. 8-K earnings tables are in EX-99.1). Check `index.json` if the primary
  doc looks thin.
- Modern filings are **inline XBRL** (`isInlineXBRL: 1`): the financial data is embedded in
  the primary `.htm` — there's no separate instance document to fetch.
- Very old filings (pre-2001) may be plain `.txt` with no HTML and no XBRL.

**Full-text search**
- `dateRange=custom` → **500**; use `startdt`/`enddt`.
- Only 2001-present indexed.
- `hits.total.relation == "gte"` means the count is **capped at 10000** — narrow the query
  (tighter dates / `forms` / `entityName`) to get exact counts and all results.
- 100 hits/page — you **must** paginate with `from=` to see everything.

**XBRL**
- Tag drift: don't assume `Revenues`; discover the company's actual tag (§5).
- A concept absent from a filing returns 404/empty — that's "not tagged here," not "zero."
- Units vary (`USD`, `shares`, `pure`, `USD/shares`); read the right `units` key.

**Operational**
- No built-in rate limiting anywhere — self-throttle to **< 10 req/s**.
- Responses are large (a single `companyfacts` or submissions file is 100s of KB–MBs);
  stream/limit, and prefer `companyconcept` (one tag) over `companyfacts` (everything) when
  you know the metric.
- 8-K item codes (`recent.items`, e.g. `"2.02,9.01"`) are the cheapest materiality triage —
  decode them (table in `SKILL.md`) before fetching prose.

---

## 8. Quick recipes

**Latest 10-K text (no MCP):**
1. `company_tickers.json` → CIK → pad to 10.
2. `submissions/CIK{padded}.json` → first row where `form == "10-K"`.
3. build Archives URL from `accessionNumber` + `primaryDocument` → fetch `.htm`.

**"Anything material this week?":**
1. submissions feed → rows where `form == "8-K"` and `filingDate` within 7 days.
2. read `items` per row; decode codes; fetch the `.htm` only for the ones that matter.

**"What risks does X declare?":**
1. latest 10-K (recipe above).
2. locate **Item 1A — Risk Factors** in the document (MCP `get_filing_sections` does this
   structurally; on raw HTML, anchor on the "Item 1A" heading through "Item 1B"/"Item 2").

**"Find companies that disclosed a material weakness in Q1 2024":**
1. `efts` search: `q="material weakness"&forms=8-K&startdt=2024-01-01&enddt=2024-03-31`.
2. paginate `from=` while `hits.total` exceeds the page; dedupe by `ciks`.
