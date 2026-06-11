---
name: reporting
type: composite
description: >
  Assemble charts, tables, and analyst text into a beautiful, branded PDF — either a
  multi-page portrait report (A4) or a 16:9 landscape presentation deck like Google
  Slides. Ships page templates (comparison matrix, industry breakdown, full-bleed price
  chart with technical commentary, data table with commentary) that consume output from
  the charting, thematic-investing, and sec-filings skills. Remembers your logo and
  brand colors after first use. Triggers: "generate a PDF report", "turn this analysis
  into a deck", "make a presentation of these charts", "client-ready report", "export
  to PDF", "slides comparing these companies", "branded research report", "investment
  memo PDF".
requires:
  - charting
---

# Reporting — charts + tables + text → branded PDF

A JSON **report contract** describes the document as pages that reference shipped
templates. One script assembles a self-contained HTML document (Highcharts vendored
from the sibling charting skill, inlined once — no network at render time) and prints
it to PDF with Playwright. This is a working default, not a requirement — extend the
contract or templates rather than hand-writing report HTML.

```
analysis output (chart contracts / tables / text)
        ─► report contract (JSON)
        ─► bun scripts/render.ts contract.json out/report.pdf
```

## Fast path

```bash
bun scripts/render.ts report.json out/report.pdf               # the one command
bun scripts/render.ts report.json out/report.html --html-only  # no Playwright needed
bun scripts/render.ts report.json out/report.pdf --keep-html   # keep the HTML beside the PDF
bun scripts/render.ts report.json out/report.pdf --brand x.json # one-off brand override
```

Minimal contract (`templates/examples/` has full ones for both modes):

```json
{
  "meta": { "mode": "report", "title": "Roblox (RBLX) — Bookings vs Revenue" },
  "pages": [
    { "template": "cover", "slots": { "title": "Roblox (RBLX)", "kicker": "Equity Research" } },
    { "template": "price-chart-technicals", "slots": {
        "title": "RBLX — price action",
        "chart": "./out/price-contract.json",
        "commentary": [ { "heading": "Trend", "body": "Uptrend intact above the 200-day." } ],
        "source": "Daily OHLC" } }
  ]
}
```

- `meta.mode`: `"report"` = portrait A4 document · `"presentation"` = 16:9 landscape deck.
- Paths inside the contract (chart contracts, brand, logo) resolve **relative to the
  contract file**.
- `meta.footer` text repeats on every page; page numbers are automatic (skipped on cover).

## One-time setup

```bash
cd <this skill's directory> && bun install && bunx playwright install chromium
```

`render.ts` tells you exactly this when Playwright is missing. Environments that
already provide browsers via `PLAYWRIGHT_BROWSERS_PATH` (e.g. the e2e container) skip
the browser download. If PDF printing is unavailable, fall back to `--html-only` and
convert with any HTML→PDF tool (the e2e container ships `html2pdf`).

## Branding

Brand config lives in the **project working directory** at `report-brand/brand.json`
so it survives skill reinstalls and is reused across reports:

```json
{
  "company": "MK Capital",
  "logo": "./logo.png",
  "logoPlacement": "top-left",
  "colors": { "primary": "#1a3c6e", "accent": "#e8a33d", "panel": "#f5f7fa" },
  "footerText": "MK Capital — Confidential"
}
```

- **First use**: if `./report-brand/brand.json` doesn't exist, ask the user once:
  *"Want branded reports? Upload a logo and tell me your brand colors (or say skip)."*
  On an answer, write `report-brand/brand.json` and copy the logo file in yourself.
  On "skip", proceed with the default theme and don't ask again this session.
- **Present**: use it silently; mention which brand was applied in your summary.
- **Per-prompt override** ("make this one red"): write a one-off brand JSON and pass
  `--brand`; never mutate the persisted file unless the user says to update their brand.
- Precedence: `--brand` flag > `brand` (inline object) in contract > `brand` (path) in
  contract > `./report-brand/brand.json` > built-in default.
- Logo formats: png / jpg / svg / webp; it's inlined as a data URI. Colors omitted from
  `colors` fall back to the default palette.

## Templates

| Template | Required slots | Optional slots | Typical source |
|---|---|---|---|
| `cover` | `title` | `subtitle`, `kicker`, `date` | — |
| `comparison` | `title`, `companies` (2–7) | `subtitle`, `takeaway` | thematic-investing sensitivity / exposure tables |
| `industry-breakdown` | `title`, `layers` (2–9) | `subtitle`, `takeaway` | thematic-investing value-chain map |
| `price-chart-technicals` | `title`, `chart`, `commentary` (1–4 blocks) | `subtitle`, `stats`, `source` | charting `price` builder |
| `table-commentary` | `title`, `table`, `commentary` | `subtitle`, `source` | sec-filings KPIs, any tabular data |

Slot shapes:

- **chart** — a path to a charting **contract** JSON (preferred), or
  `{ "image": "chart.png" }` as an escape hatch. Never pass charting's pre-rendered
  HTML pages; reporting renders contracts itself, print-tuned (no navigator/range
  selector, fixed height, animations off).
- **companies** — `{ "name", "ticker", "mechanism", "ratings": { "narrative",
  "revenue", "profit", "purity" } }` with each rating `"high" | "medium" | "low"`
  (rendered as colored pills).
- **layers** — `{ "name", "role", "scarcity": "scarce" | "contested" | "commoditized",
  "tickers": ["..."] }`, ordered upstream → downstream.
- **table** — `{ "columns": ["..."], "rows": [["...", "..."]] }`. Cells are
  **pre-formatted strings** — format numbers upstream (units, `$`/`%`, accounting
  negatives) per charting's data-unit conventions.
- **commentary / takeaway** — `{ "heading", "body" }`; body supports `**bold**`,
  `*italic*`, and `- ` bullet lines only.
- **stats** — `[{ "label": "52-wk range", "value": "$169 – $242" }]` chip row.

Default skeleton when the user just says "make a report": `cover` → one chart page →
`table-commentary`. For "make a deck/presentation", same content with
`meta.mode: "presentation"` and one idea per slide.

## Rules

- **Compute upstream, never in prose.** Numbers come from the data pipelines
  (charting's Polars layer, sec-filings extracts) already formatted; this skill only
  lays them out.
- **One idea per slide** in presentation mode. Respect the row caps (7 companies,
  10 table rows per slide) — the renderer errors past them; split across pages.
- **Always cite `source`** on data-bearing pages (renders in the footer).
- **Don't hand-write report HTML.** If a layout doesn't exist, add a template function
  to `scripts/render.ts` and styles to `assets/styles.css`.
- The renderer fails loudly: unknown templates, missing slots, missing chart contract
  files, and charts that produced no SVG all exit non-zero — read the message.

## Files

- `scripts/render.ts` — the whole pipeline: contract → HTML → PDF.
- `assets/styles.css` — page geometry (`@page`), template layouts, brand CSS variables.
- `assets/default-brand.json` — fallback brand.
- `templates/examples/` — a full report contract and a full presentation contract;
  copy one as your starting point.
