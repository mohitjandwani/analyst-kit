# Filing conversion, XBRL & 8-K attachments

Two questions this reference answers, both decided **empirically** against live Apple
filings (June 2026):

1. **How to turn a giant filing into token-efficient text** (the "markdown converter").
2. **How to parse the XBRL and the other attachments bundled with an 8-K.**

---

## Part 1 — Filing → text conversion: the decision

**Problem.** A 10-K primary document is ~1.5 MB of inline-XBRL HTML. Measured on Apple's
FY2025 10-K (`aapl-20250927.htm`):

| Stage | Chars | Tokens (cl100k_base) | vs raw |
|---|---|---|---|
| Raw iXBRL HTML | 1,520,208 | **441,509** | 1× |
| After `parse_filing.html_to_text` | 208,066 | **44,274** | **10× smaller** |
| Top-5 BM25 sections (one query) | ~24 KB | **6,022** | **73× smaller** |

So the pipeline is two multiplicative wins: **strip (10×)** then **BM25-narrow (~7×)**.

**Decision: a stdlib iXBRL stripper for prose + the facts API for numbers.** We do *not*
take a heavy converter dependency. Rationale, and how it answers the converter question:

- The win that matters (10×) comes from **deleting iXBRL plumbing**, not from clever
  table rendering. `html_to_text` drops `<script>/<style>`, the hidden `ix:header`/
  `ix:hidden`/`display:none` machine-fact blocks, and unwraps the *visible* `ix:nonFraction`/
  `ix:nonNumeric` tags (keeping their rendered text). That alone gets you to clean prose.
- **Numbers don't come from the HTML at all.** Financial-statement tables in SEC HTML are
  deeply nested with `colspan`/`rowspan` and CSS layout; *every* generic converter
  (markdownify, html2text, trafilatura) mangles them to some degree. So we don't try —
  numbers come from SEC's pre-computed **XBRL facts API** (Part 2C), where scale/sign/units
  are already applied. Prose → stripper; numbers → facts API. This split is what lets the
  design be dependency-free without losing fidelity.
- **Determinism.** Pure stdlib + pure-Python BM25 means the index/search step has no
  network, no model, no version drift — and is unit-testable offline (`tests/`).

**Converter landscape (researched), if you ever want higher table fidelity:**

| Tool | Verdict for SEC filings |
|---|---|
| **stdlib `html.parser` strip** (what we use) | Best for *narrative*. 10× reduction, zero deps, deterministic. Tables flatten to text (acceptable — numbers come from the facts API). |
| **edgartools** (`filing.markdown()`, typed `TenK`/`TenQ`, GFM statement tables) | The strongest *library* — purpose-built for iXBRL, renders financial statements as clean markdown tables, has token-budget tooling. Use it **only if** you accept a pandas/lxml dependency and want HTML-derived statement tables. It's also the backend of `sec-edgar-mcp`. |
| **sec2md** | Promising SEC-specific markdown (handles `rowspan`/`colspan`, attaches XBRL tags) but young/low-traction; consumes edgartools. |
| markitdown / markdownify / html2text | Generic; need an lxml pre-pass to strip `ix:*` or they leak noise / drop whitespace. html2text is **GPL** (license caution for a distributed product). |
| docling | Torch-heavy; its table model is for *PDFs* — wasted on already-structured HTML. |
| trafilatura | Boilerplate remover for web articles — **risks dropping filing content**; not for this. |

> Bottom line: the bundled stripper is the right default. `edgartools` is the documented
> upgrade path if you later need HTML-rendered statement tables rather than facts-API numbers.

---

## Part 2 — XBRL & attachments

### A) The accession folder = a bundle of files

Every filing lives at `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/`
(CIK **unpadded** here). List it with `python edgar.py attachments <id> <form>` (wraps
`index.json`). Verified members of Apple's earnings 8-K (`…26-000011`):

| Member | Role |
|---|---|
| `aapl-20260430.htm` (38 KB) | **Primary doc** — the 8-K cover page, inline-XBRL tagged (dei only) |
| `a8-kex991q2202603282026.htm` (169 KB) | **EX-99.1 press release** — the earnings tables, **plain HTML** |
| `aapl-20260430_htm.xml` (7.7 KB) | **Extracted XBRL instance** — the dei facts pulled out of the iXBRL |
| `aapl-20260430.xsd` | Company extension schema (declares custom `aapl:` elements) |
| `aapl-20260430_def.xml` / `_lab.xml` / `_pre.xml` | Definition / label / presentation **linkbases** |
| `R1.htm` | SEC-**rendered** view of the cover page (1 report; a 10-K has dozens) |
| `FilingSummary.xml` | Indexes the R-reports + flags (`isOnlyDei`, `HasCalculationLinkbase`) |
| `MetaLinks.json` | Machine map of tagged concepts, labels, contexts/members |
| `*-xbrl.zip` | All XBRL files bundled |
| `{accession}.txt`, `-index.html` | Full SGML submission; human index |

**Note:** an 8-K cover page has **no `_cal.xml`** (no calculation linkbase — you only need
those to make financial statements add up). `Financial_Report.xlsx` was **absent** from
both Apple filings inspected — don't assume it exists; check `attachments`.

**Exhibit types** (the substantive content of many forms is in exhibits, not the primary):
`EX-99.1`/`EX-99.2` = press releases / supplemental (earnings tables live here on an 8-K);
`EX-10.x` = material contracts; `EX-21` = subsidiaries; `EX-23` = auditor consent;
`EX-31`/`EX-32` = SOX certifications; `EX-3`/`EX-4` = charter / security instruments.

### B) What XBRL an 8-K actually has — VERIFIED

**An 8-K carries cover-page `dei:` XBRL only. There are no `us-gaap` financial facts.**
Direct evidence from `aapl-20260430.htm` / its instance:

- Primary doc tag census: **`ix:nonFraction` = 0**, `ix:nonNumeric` = 40, namespaces = `dei`.
  (Zero numeric facts.)
- Instance has **23 distinct `dei:` tags** and no us-gaap *facts*. (`us-gaap:` appears only
  as context **dimension members** for the registered-securities block — e.g.
  `us-gaap:StatementClassOfStockAxis` → `us-gaap:CommonStockMember` — never as a fact.)
- `FilingSummary.xml` says it outright: `isOnlyDei="true"`, `HasCalculationLinkbase=false`,
  one R-report (`Cover Page`).
- **EX-99.1 earnings release**: `<ix:` count = **0**, yet it contains the "Net sales"
  tables. **The earnings numbers are plain HTML, not XBRL.**

**Consequences (the gotcha that wastes time):**
- Do **not** expect `filing.xbrl()` / an income statement from an 8-K. There isn't one.
- To get earnings-release numbers: **read EX-99.1 as prose** — hand its `url`
  (`edgar.find_exhibits`) to `parse_filing.py --url …` — **or** wait for the matching
  10-Q/10-K and pull the numbers from the **facts API** (Part C), where they're XBRL-tagged.
- The financial-statement XBRL mandate applies to **10-K/10-Q/20-F/40-F**, plus the rare
  8-K that re-files *restated audited* statements — not ordinary Item 2.02 earnings 8-Ks.

### C) The dei cover-page taxonomy

`python edgar.py cover <id> <form>` (→ `edgar.cover_page_facts` → `parse_dei_instance`)
returns the cover facts with dimension members resolved. The 23 dei concepts on the live
8-K, by group:

- **Document:** `dei:DocumentType` (`8-K`), `dei:DocumentPeriodEndDate`, `dei:AmendmentFlag`.
- **Entity identity:** `dei:EntityRegistrantName`, `dei:EntityCentralIndexKey` (`0000320193`),
  `dei:EntityFileNumber`, `dei:EntityTaxIdentificationNumber`,
  `dei:EntityIncorporationStateCountryCode`, address + phone tags.
- **Status flag:** `dei:EntityEmergingGrowthCompany` (ballot-box checkbox; 10-K adds
  `dei:EntityExTransitionPeriod` + accelerated-filer tags).
- **8-K item / communication flags:** `dei:WrittenCommunications`, `dei:SolicitingMaterial`,
  `dei:PreCommencementTenderOffer`, `dei:PreCommencementIssuerTenderOffer`.
- **Registered securities (one block per security, dimensioned):** `dei:Security12bTitle`,
  `dei:TradingSymbol` / `dei:NoTradingSymbolFlag`, `dei:SecurityExchangeName`. Apple has 7
  (common stock + 6 note series) — each scoped by a context whose `explicitMember` is the
  security (`us-gaap:CommonStockMember`, or company-custom `aapl:A1.625NotesDue2026Member`).
  The parser attaches that `member` so a symbol/title maps to the right security.

### D) Financial numbers via the facts API (the right source)

For 10-K/10-Q numbers, use SEC's pre-computed facts — **SEC has already applied scale, sign
and units**, so you skip every iXBRL gotcha in section E:

- `python edgar.py facts <id> --grep <part>` — **discover** the company's actual tags first.
- `python edgar.py concept <id> <Tag> [--tax us-gaap|dei]` — all values of one concept.
- In code: `edgar.companyfacts(cik10)`, `edgar.companyconcept(cik10, tag, taxonomy)`.

Endpoints (full shapes in `sec-edgar-direct-http.md` §5):
`companyconcept/CIK{padded}/{taxonomy}/{Tag}.json`, `companyfacts/CIK{padded}.json`,
`frames/{taxonomy}/{Tag}/{unit}/{period}.json` (one tag across all filers — peer compare).

**Parse the raw instance / iXBRL yourself only when** the facts API can't help: 8-K
cover-page dei (use `cover`); dimensional/segment detail the API flattens; a filing too
recent to be ingested yet; or pre-XBRL-mandate filings.

### E) XBRL parsing gotchas (each = a real wrong-number bug)

Grounded in real facts from Apple's 10-K and the `concept` output above:

1. **`scale` multiplies.** displayed × 10^scale = true value. `scale="6"` on revenue: a
   shown `416,161` is **$416.161 B**. Ignore `scale` and you're off by 10⁶. (Facts API
   already applied it — another reason to prefer it.)
2. **`decimals` ≠ `scale`.** `decimals="-6"` = "rounded to the nearest million" (precision
   metadata); it does **not** rescale. `decimals="INF"` = exact (common on per-share).
3. **`sign="-"` negates** the parsed magnitude (contra accounts, some expenses). Apply after
   parsing digits.
4. **`xsi:nil="true"` = absent, not zero.** Skip it; don't coerce to 0. (`parse_dei_instance`
   skips nil facts.)
5. **Multiple contexts — duration vs instant, and YTD vs quarter.** Verified live:
   `NetIncomeLoss` returns **two** facts for `end=2026-03-28` — 71,675 M (H1 YTD) and
   29,578 M (Q2 quarter); 42,097 (Q1) + 29,578 (Q2) = 71,675 (H1). Disambiguate by the
   context's **`start`/period length** (and `fp`/`form`), not just `end`. Instant contexts
   (`<instant>`) are balances; duration contexts (`start`+`end`) are flows.
6. **Dimensional/segment contexts.** A revenue fact dimensioned by `ProductOrServiceAxis=
   iPhoneMember` is *segment* revenue. For the consolidated total, take the fact whose
   context has **no segment** (the default member), or you'll double-count.
7. **Units.** Read `unitRef`: `usd`, `shares`, `usdPerShare` (EPS), `pure`, plus custom
   counting units. In the facts API this is the `units` key (`USD`, `shares`, `USD/shares`).
8. **Tag drift.** Verified via `facts AAPL --grep Revenue`: `Revenues` has 11 (stale) facts;
   the real series is `RevenueFromContractWithCustomerExcludingAssessedTax` (113) and
   `SalesRevenueNet` (210). Companies also coin custom `*.xsd` extension tags. **Discover,
   never hardcode.**

---

## Quick command map

```bash
python edgar.py attachments AAPL 8-K        # list exhibits + XBRL members of the latest 8-K
python edgar.py cover       AAPL 8-K        # dei cover-page facts (the 8-K's only XBRL)
python edgar.py facts       AAPL --grep Revenue   # discover the real revenue tag
python edgar.py concept     AAPL RevenueFromContractWithCustomerExcludingAssessedTax
# earnings numbers from an 8-K press release (plain HTML) -> read it as prose:
python parse_filing.py --url <EX-99.1 url from `attachments`> --query "net sales gross margin"
```
