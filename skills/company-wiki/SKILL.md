---
name: company-wiki
type: composite
description: "Build a comprehensive, multi-page company research wiki as a deployed web application. Use for: researching any publicly listed company from any region (US, Europe, Japan, Taiwan, India, or other) and producing a structured wiki covering company overview/history, individual product pages (sourced from earnings calls and investor presentations), 5-year financials, analyst reports, stock price and technical analysis, financial modelling with growth scenarios and forward P/E and P/S multiples, competitor comparison, and a sourced citations page. The wiki is built with React + Tailwind using the webdev tools and deployed on Manus hosting. Triggers: 'build a company wiki for X', 'research wiki on Y', 'make a company research site for Z', 'deep research wiki for <ticker>'."
requires:
  - wiki-builder
  - company-universe-manager
env:
  - FMP_API_KEY
---

# Company Wiki Skill

## Overview

Build a production-ready, multi-page company research wiki for any publicly listed company. The workflow has seven phases:

1. Identify the company, its exchange, and map data sources by region
2. Research product details & launches
3. Research Fiscal periods, earnings calls, investor presentations, and
4. Gather 5-year financial data and periodic revenue
5. Research analyst reports and ratings
6. Gather stock price data for technical analysis
7. Build the wiki web application
7. Deliver and iterate

For detailed regional data retrieval methods, see `references/regional-data-sources.md`.
For competitor research frameworks, see `references/competitor-research.md`.
For wiki page component patterns, see `references/page-templates.md`.
For product page data schema, see `references/product-page-structure.md`.

---

## Phase 0 - Preparation

Before you start gathering information, build the Citation.md file. Every information you gather and use for the wiki MUST have a source number in the Citation.md file. This will be later used to build the source page in the wiki.


## Phase 1 — Company Identification & Source Mapping

Always complete this sequence before any research:

1. **Find the IR website**: Search `"[Company Name] investor relations"` or navigate to the company's main website "Investors" section. The IR page is the authoritative source for presentations, filings, and earnings materials.
2. **Identify the primary ticker and exchange**: Confirm the most liquid listing and local ticker. Note any ADRs or secondary listings.
3. **Determine the company's region**: US · Europe · Japan · Taiwan · India · Other. This determines which sources to use in Phases 2–4 (see `references/regional-data-sources.md`).
4. **Map the ticker to FMP API format**: Append the correct suffix (e.g., `.T` for Tokyo, `.TW` for TWSE, `.NS` for NSE India). See FMP Ticker Formats table in `references/regional-data-sources.md`.
5. **Confirm FMP coverage**: Use the `profile-symbol` endpoint to retrieve the ISIN as a universal identifier.
6. **Idenfity the fiscal periods**: Identify the fiscal periods of the company. 
7. **Citations**: Log all the citations in the `Citations.md` and add the number with each data information.  

**Save to:** `/home/ubuntu/{ticker}_research.md`

Key fields to capture: founding year, headquarters, listing exchange and ticker, ownership (parent company if subsidiary), number of employees, global ranking in industry, major subsidiaries and manufacturing locations.

---

## Phase 2 — Earnings Calls & Product Research

**Step 1 — Locate the earnings source for the company's region:**

| Region | Primary Source | Notes |
|---|---|---|
| **US** | FMP API `latest-transcripts` or `transcript` endpoint; Seeking Alpha | Full text transcripts available |
| **Europe** | Company IR page (webcasts/PDFs); exchange filings (LSE RNS, AMF, Nasdaq Nordic) | Text transcripts often unavailable for small-caps; use video webcast |
| **Japan** | Company IR page → **"Q&A Summary" PDFs** | Do NOT search for "earnings call transcripts" — the standard format is Q&A Summary PDFs |
| **Taiwan** | **AlphaSpread** (`alphaSpread.com`) for full English text; Company IR page | AlphaSpread is the best source for TWSE companies; far better than webcasts |
| **India** | Company IR page (SEBI LODR requires full transcript PDFs); Trendlyne; BSE/NSE filings | Full PDFs are legally mandated |

**Step 2 — Download the most recent full-year earnings presentation/transcript and 2–3 prior years.**

**Step 3 — For each major product line, capture:**
- Product description and technical specifications
- Revenue contribution (% of total, absolute if disclosed)
- Key customers or end markets
- Growth commentary from management
- Capacity expansion or capex announcements
- Competitive positioning statements

**Save to:** `/home/ubuntu/{ticker}_earnings_research.md`

See `references/product-page-structure.md` for the standard product page data schema.

---

## Phase 3 — Financial Data

**Primary source (all regions):**
- Annual income statement: `https://stockanalysis.com/stocks/{ticker}/financials/` (US) or `https://stockanalysis.com/quote/{exchange_prefix}/{ticker}/financials/` (non-US)
- Quarterly data: append `?p=quarterly`
- Balance sheet: append `/balance-sheet/`

**stockanalysis.com exchange prefixes:** `tpe` (TWSE Taiwan), `tpex` (Taipei OTC), `tse` (Tokyo), `nse` / `bse` (India), `lse` (London), `xetra` (Germany), `euronext` (Paris/Amsterdam)

**Periodic revenue by region:**

| Region | Periodic Revenue Source |
|---|---|
| **Taiwan** | `https://tw.stock.yahoo.com/quote/{ticker}.TW/revenue` (monthly) |
| **US / Europe** | Quarterly from stockanalysis.com or company earnings releases |
| **Japan** | Quarterly from company IR page or JPX TDnet |
| **India** | Quarterly from BSE/NSE filings or Trendlyne |

**Key metrics to collect:**
- Annual revenue (5 years), YoY growth %
- Gross profit and gross margin %
- Operating income and operating margin %
- Net income and net margin %
- EPS (basic and diluted)
- Periodic revenue (monthly for Taiwan, quarterly for others — 8–12 periods for trend analysis)

**Save to:** `/home/ubuntu/{ticker}_financials_complete.md`

---

## Phase 4 — Analyst Reports

**Sources by region:**

| Region | Primary Source | Supplementary |
|---|---|---|
| **US** | FMP API `latest-8k`; Seeking Alpha | stockanalysis.com forecast page |
| **Europe** | Company IR; exchange filings | Seeking Alpha (if ADR exists) |
| **Japan** | Company IR; JPX TDnet; Seeking Alpha (ADR) | EDINET |
| **Taiwan** | AlphaSpread; Seeking Alpha | stockanalysis.com forecast |
| **India** | Trendlyne; BSE/NSE filings | Screener.in |
| **All** | `https://stockanalysis.com/quote/.../forecast/` | Search: `"{company}" analyst report site:goldmansachs.com OR site:morganstanley.com` |

**Capture per analyst:** bank name, analyst name, report date, rating, price target, key thesis points, key risks cited.

**Save to:** `/home/ubuntu/{ticker}_analysts.md`

---

## Phase 5 — Stock & Technical Analysis

**Sources (all regions):**
1. `https://finance.yahoo.com/quote/{ticker}/history/` — set to 5Y range for price history
2. `https://stockanalysis.com/quote/{exchange_prefix}/{ticker}/statistics/` — P/E, P/S, P/B, market cap, EV

**Capture:** current price, 52-week high/low, market cap, enterprise value, P/E (TTM), forward P/E, P/S, P/B, EV/EBITDA, key technical levels (support, resistance, 50d/200d MAs), RSI, MACD commentary.

**Save to:** `/home/ubuntu/{ticker}_technical_analysis.md`

---

## Phase 6 — Build the Wiki

### Design System

Use **East Asian Corporate Modernism** design philosophy:
- Background: pure white (`oklch(1 0 0)`)
- Primary accent: blue
- Typography: `Noto Serif Display` (headings) + `Inter` (body) + `JetBrains Mono` (financial figures)
- Layout: persistent left sidebar (264px) + main content area

Add to `client/index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+Display:wght@400;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
```

### Page Structure

| Route | Component | Content |
|---|---|---|
| `/` | `Home.tsx` | Company summary, key stats, history timeline, milestones |
| `/products/{slug}` | `Product{Name}.tsx` | Per-product page using `ProductPageTemplate.tsx` |
| `/financials` | `Financials.tsx` | Revenue/margin charts (Recharts), 5-year table |
| `/analysts` | `AnalystReports.tsx` | Analyst cards with ratings, targets, thesis |
| `/stock` | `StockAnalysis.tsx` | Price chart, valuation multiples, technical levels |
| `/competitors` | `Competitors.tsx` | Peer comparison (see Competitors section) |
| `/modelling` | `FinancialModelling.tsx` | Scenario model (see Financial Modelling section) |
| `/sources` | `Sources.tsx` | Numbered citations with dates and URLs |

See `references/page-templates.md` for detailed component patterns for each page type.

### Citation System

All data must carry a superscript citation number. Use a shared `CitationRef` component:

```tsx
// client/src/components/CitationRef.tsx
export function Cite({ n }: { n: number | number[] }) {
  const nums = Array.isArray(n) ? n : [n];
  return (
    <sup
      className="ml-0.5 text-[0.65rem] font-mono text-primary/70 cursor-pointer hover:text-primary"
      onClick={() => {
        const el = document.getElementById(`source-${nums[0]}`);
        el?.scrollIntoView({ behavior: "smooth" });
        el?.classList.add("ring-2", "ring-primary");
        setTimeout(() => el?.classList.remove("ring-2", "ring-primary"), 2000);
      }}
    >
      [{nums.join(",")}]
    </sup>
  );
}
```

The `Sources.tsx` page lists every source with:
- Sequential number (anchor `id="source-{n}"`)
- Source type badge (Earnings Presentation / Annual Report / Analyst Report / News / Website)
- Publisher name, publication date, URL as clickable link
- Short description of what information it provides

### Financial Modelling Page

Build three scenarios — Bear, Base, Bull — using actual historical revenue CAGR as the baseline:

```
Bear  = current CAGR × 0.6  (deceleration)
Base  = current CAGR × 1.0  (continuation)
Bull  = current CAGR × 1.4  (acceleration)
```

For each scenario project for FY+1 and FY+2:
- Annual revenue, gross profit (trailing 3-year avg gross margin), net income (trailing 3-year avg net margin)
- EPS (current diluted share count), forward P/E at current price, forward P/S at current price

Display as: scenario selector tabs + summary cards + cross-scenario comparison table.

Python script for computing projections: `scripts/financial_model.py`

### Competitors Page

Identify the peer set using FMP API `peers` endpoint or the company's own industry classification. For each peer collect from `stockanalysis.com`: revenue (5 years), gross margin, net margin, P/E (TTM), P/S, P/B, market cap.

Display as:
1. Interactive multi-series Recharts charts with company filter checkboxes
2. Valuation comparison table
3. Product moat matrix — rows = product/capability types, columns = companies, cells = capability level (Leader / Capable / Limited / None)
4. Moat narrative cards — each company's unique differentiator

See `references/competitor-research.md` for the competitive positioning framework and region-specific peer identification guidance.

---

## Phase 7 — Delivery

1. Run `npx tsc --noEmit` — must show zero errors before checkpoint
2. Run `webdev_save_checkpoint`
3. Attach `manus-webdev://{version_id}` in the result message
4. Suggest concrete next steps (sensitivity table, price target calculator, quarterly earnings timeline)

---

## Quick Reference: FMP Ticker Formats

| Exchange | Country | FMP Suffix | Example |
|---|---|---|---|
| NASDAQ / NYSE | US | (none) | `AMD` |
| London Stock Exchange | UK | `.L` | `IQE.L` |
| Euronext Paris | France | `.PA` | `SOI.PA` |
| Euronext Amsterdam | Netherlands | `.AS` | `ASML.AS` |
| Xetra / Frankfurt | Germany | `.DE` | `SAP.DE` |
| Nasdaq Stockholm | Sweden | `.ST` | `SIVE.ST` |
| Tokyo Stock Exchange | Japan | `.T` | `4063.T` |
| Taiwan Stock Exchange | Taiwan | `.TW` | `2308.TW` |
| NSE India | India | `.NS` | `OLAELEC.NS` |
| BSE India | India | `.BO` | `OLAELEC.BO` |
