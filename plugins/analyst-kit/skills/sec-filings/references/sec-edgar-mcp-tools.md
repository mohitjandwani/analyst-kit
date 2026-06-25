# SEC EDGAR MCP — complete tool inventory (Layer A)

Reference for [`stefanoamorelli/sec-edgar-mcp`](https://github.com/stefanoamorelli/sec-edgar-mcp).
Tool names/signatures are taken from the authoritative `register_tools()` list in
`sec_edgar_mcp/server.py`; the server is a thin wrapper over
[`edgartools`](https://github.com/dgunning/edgartools), which is itself a wrapper over the
raw SEC HTTP APIs documented in `sec-edgar-direct-http.md`.

- **Latest release at time of writing:** `v1.0.8`. **License:** AGPL-3.0. **Python:** ≥3.11.
- **Required env var:** `SEC_EDGAR_USER_AGENT` = `"First Last (email@example.com)"`. The
  server **raises `ValueError` and will not start** if unset (`config.py`). Set it in the
  MCP client launch config (Docker `-e`, or your `mcp.json`), not in this skill's `.env`.
- **Identifier convention:** most tools take `identifier` = a **ticker or a CIK**. CIK
  resolution is internal: numeric → treated as CIK; otherwise resolved via an in-memory
  `TickerCache` (downloads `company_tickers_exchange.json` once) with an
  `edgartools Company(ticker).cik` fallback. CIKs are normalized to zero-padded 10 digits.
- **Return convention:** every tool returns a dict with `success: true` + payload, or
  `success: false` / `error` with a message.
- **No automatic rate limiting or retry/backoff** in this repo; compliance with SEC's
  ~10 req/s policy is delegated to a valid User-Agent + edgartools. Self-throttle bulk pulls.
- **20 registered tools** total (a `get_recommended_tools` tool does **not** exist — ignore
  any reference to it).

> Caveat on exact return keys: the nested key names below were read from source through a
> summarizing fetch layer. Treat them as accurate-to-source but spot-check precise nesting
> if a downstream consumer depends on an exact key.

---

## Company tools (`tools/company.py`)

### `get_cik_by_ticker`
- **Purpose:** ticker → SEC CIK.
- **Params:** `ticker: str` (required).
- **Returns:** `{ success, cik, ticker }` (`cik` zero-padded to 10) or `{ error }`.
- **Maps to:** `TickerCache` (`company_tickers_exchange.json`), `Company(ticker).cik` fallback.

### `get_company_info`
- **Purpose:** company metadata.
- **Params:** `identifier: str` (ticker or CIK).
- **Returns:** `{ success, company: { cik, name, ticker, sic, sic_description, exchange,
  state, fiscal_year_end } }`.
- **Maps to:** `Company(identifier)` → `data.sec.gov/submissions` top-level fields.

### `search_companies`
- **Purpose:** find companies by name.
- **Params:** `query: str` (required); `limit: int = 10`.
- **Returns:** `{ success, companies: [...], count }`.
- **Maps to:** edgartools `search(query)` / `find_company(query)`.

### `get_company_facts`
- **Purpose:** available XBRL facts with most-recent values.
- **Params:** `identifier: str`.
- **Returns:** `{ success, cik, name, metrics: { <concept>: { value, unit, period, form,
  fiscal_year, fiscal_period } }, has_facts }`.
- **Maps to:** `Company(...).get_facts()` → XBRL `companyfacts`.

---

## Filing tools (`tools/filings.py`)

### `get_recent_filings`
- **Purpose:** recent filings for a company, or the cross-filer firehose.
- **Params:** `identifier: str = None` (omit for all filers); `form_type: str = None`
  (accepts a single form or a list); `days: int = 30`; `limit: int = 40`.
- **Returns:** `{ success, filings: [{ form_type, filing_date, accession_number, url, ... }], count }`.
- **Maps to:** `Company(...).get_filings(form=...)`, or `get_current_filings(form=...,
  page_size=limit)` when no `identifier`.

### `get_filing_content`
- **Purpose:** a filing's text, **paginated**.
- **Params:** `identifier: str`; `accession_number: str`; `offset: int = 0`;
  `max_chars: int = 50000`.
- **Returns:** `{ success, accession_number, form_type, filing_date, content, url, offset,
  returned_chars, total_chars, next_offset }`.
- **Maps to:** locate filing by accession → `filing.text()` (raw Archives doc).
- **Note:** loop on `next_offset` until `returned_chars < max_chars` — one call rarely
  returns a whole 10-K.

### `analyze_8k`
- **Purpose:** decode an 8-K's material-event item codes.
- **Params:** `identifier: str`; `accession_number: str`.
- **Returns:** `{ success, analysis: { date_of_report, items, events[...] } }`.
- **Maps to:** locate 8-K → `filing.obj()` structured object. (See the 8-K item table in
  `SKILL.md`.)

### `get_filing_sections`
- **Purpose:** named sections (business, risk factors, MD&A, …) from 10-K / 10-Q.
- **Params:** `identifier: str`; `accession_number: str`; `form_type: str`.
- **Returns:** `{ success, form_type, sections, available_sections }`.
- **Maps to:** `filing.obj()` structured 10-K/10-Q object. **Primary tool for Scenario 3
  (risk factors / MD&A).**

---

## Financial / XBRL tools (`tools/financial.py`, `tools/xbrl.py`)

### `get_financials`
- **Purpose:** financial statements from the latest filing.
- **Params:** `identifier: str`; `statement_type: str = "all"` (`"income"` | `"balance"` |
  `"cash"` | `"all"`).
- **Returns:** `{ success, cik, name, form_type, statements: { income_statement,
  balance_sheet, cash_flow }, filing_reference }`.
- **Maps to:** latest 10-K/10-Q → `Financials.extract(filing)` + `filing.xbrl()`.

### `get_segment_data`
- **Purpose:** revenue/segment breakdown from the latest 10-K.
- **Params:** `identifier: str`; `segment_type: str = "geographic"` (also `"business"`).
  *(Server default is `"geographic"` even though the underlying method defaults to
  `"business"` — the server default wins for callers.)*
- **Returns:** `{ success, cik, name, segment_type, segments: { revenue, cost_of_revenue,
  operating_income, operating_expenses }, filing_date, statements_found }`.
- **Maps to:** `get_filings(form="10-K").latest()` → `filing.xbrl().get_all_statements()`.
  *(Rewritten in v1.0.8 to fix empty-segment returns — require ≥ v1.0.8.)*

### `get_key_metrics`
- **Purpose:** specific named metrics from company facts.
- **Params:** `identifier: str`; `metrics: list = None` (default: `Revenues`,
  `NetIncomeLoss`, `Assets`, `Liabilities`, `StockholdersEquity`,
  `EarningsPerShareBasic`, `CommonStockSharesOutstanding`, `CashAndCashEquivalents`).
- **Returns:** `{ success, cik, name, metrics, requested_metrics, found_metrics }`.
- **Maps to:** `get_facts()` → parse `us-gaap` facts.
- **Note:** default `Revenues` may be empty for companies that tag revenue as
  `RevenueFromContractWithCustomerExcludingAssessedTax`. Use `discover_company_metrics` first.

### `compare_periods`
- **Purpose:** one metric across fiscal years (growth / CAGR).
- **Params:** `identifier: str`; `metric: str`; `start_year: int`; `end_year: int`.
- **Returns:** `{ success, cik, name, metric, period_data: [{ year, period, value, unit,
  form }], analysis: { growth_rates, cagr } }`.

### `discover_company_metrics`
- **Purpose:** discover which XBRL metrics a company exposes.
- **Params:** `identifier: str`; `search_term: str = None`.
- **Returns:** `{ success, cik, name, available_metrics: [{ name, count, latest_period }],
  count, search_term }`.
- **Note:** run this **before** assuming a GAAP tag exists.

### `get_xbrl_concepts`
- **Purpose:** specific XBRL concept values from a filing (with precision/scale).
- **Params:** `identifier: str`; `accession_number: str = None`; `concepts: list = None`;
  `form_type: str = "10-K"`.
- **Returns:** `{ success, cik, name, filing_date, form_type, accession_number, concepts,
  total_concepts, filing_reference }`.
- **Maps to:** `XBRLExtractor` — may fetch the raw iXBRL `.txt` from
  `www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}.txt` and regex-parse
  `ix:nonFraction` / `ix:nonNumeric`, with `xbrl.query()` / `xbrl.by_concept()` fallbacks.

### `discover_xbrl_concepts`
- **Purpose:** discover all XBRL concepts/namespaces present in a filing.
- **Params:** `identifier: str`; `accession_number: str = None`; `form_type: str = "10-K"`;
  `namespace_filter: str = None`.
- **Returns:** `{ success, cik, name, filing_date, form_type, accession_number,
  available_statements, financial_statements, total_facts, sample_facts }` (sample ≈ first 20).

---

## Insider-trading tools (`tools/insider.py`, `tools/insider_complex.py`)

Forms **3** (initial ownership), **4** (changes), **5** (annual). *(13F institutional
holdings are a different form handled by the separate `13f-analysis` skill — not here.)*

### `get_insider_transactions`
- **Params:** `identifier: str`; `form_types: list = None` (default `["3","4","5"]`);
  `days: int = 90`; `limit: int = 50`.
- **Returns:** `{ success, cik, name, transactions[...], count, form_types, days_back,
  filing_reference }` — owner name/title, director/officer/10%-owner flags, SEC URLs.

### `get_insider_summary`
- **Params:** `identifier: str`; `days: int = 180`.
- **Returns:** `{ success, cik, name, period_days, summary: { total_filings,
  form_3_count, form_4_count, form_5_count, recent_filings, unique_insiders, insiders } }`.

### `get_form4_details`
- **Params:** `identifier: str`; `accession_number: str`.
- **Returns:** `{ success, form4_details: { filing_date, accession_number, company_name,
  cik, url, content_preview, owner, transactions, holdings } }`.

### `analyze_form4_transactions`
- **Params:** `identifier: str`; `days: int = 90`; `limit: int = 50`.
- **Returns:** `{ success, cik, name, detailed_transactions[...], count, days_back,
  filing_reference }` — shares, prices, post-transaction holdings.

### `analyze_insider_sentiment`
- **Params:** `identifier: str`; `months: int = 6`.
- **Returns:** `{ success, cik, name, analysis: { period_months, total_form4_filings,
  filing_frequency, recent_filings } }` — frequency classified high / moderate / low.

---

## Setup recap

```json
{ "mcpServers": { "sec-edgar-mcp": {
    "command": "docker",
    "args": ["run","-i","--rm",
             "-e","SEC_EDGAR_USER_AGENT=Your Name (you@example.com)",
             "stefanoamorelli/sec-edgar-mcp:latest"]
}}}
```
The `-i` flag is required for MCP stdio JSON-RPC. An HTTP transport
(`--transport streamable-http --port 9870`) exists but is **unauthenticated** — private
networks only. `pip` / `uv` installs expose a `sec-edgar-mcp` console script
(`sec_edgar_mcp.server:main`).
