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

# Reporting — storyline → branded PDF

**This skill does exactly one job**: take a *storyline* — an ordered set of pages,
each with its point, plus the already-generated UI elements (chart contracts) and
data (tables, text) — and turn it into a beautiful PDF. It does **not** decide what
the report should say: the storyline arrives pre-decided (from the user, the
orchestrating agent, or an upstream skill). Reporting owns only the layout and the
rendering.

```
storyline (pages, each: point + modules + data)
        ─► report contract (JSON)
        ─► bun scripts/render.ts contract.json out/report.pdf
```

A JSON **report contract** encodes the storyline against shipped templates. One
script assembles a self-contained HTML document (Highcharts vendored from the
sibling charting skill, inlined once — no network at render time) and prints it to
PDF with Playwright.

## Designing a page — think in this order

For every page of the storyline, answer three questions **in order**:

1. **What is the main point of this page?** One sentence. It goes in the page's
   `story` slot (required on every data page) and renders as a banner under the
   title — the reader gets the conclusion before the evidence. Put the headline
   numbers the user actually asked for (entry/exit price, latest YoY, the verdict)
   in `stats` chips right below it.
2. **Which modules does the point need?** Chart, table, commentary, rating matrix,
   layer cards — pick the template whose modules match.
3. **How do the modules arrange?** Pick the mode (`report` = portrait A4 document,
   `presentation` = 16:9 deck) and let the template lay the modules out. One point
   per page — if a page is making two points, split it.

A page with lots of empty space or no `story` is a page whose point was never
decided — fix the storyline, not the CSS.

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
        "story": "Price is consolidating above the 200-day — the uptrend is intact.",
        "chart": "./out/price-contract.json",
        "levels": [ { "value": 42, "label": "Support $42", "kind": "support" } ],
        "commentary": [ { "heading": "Trend", "body": "Uptrend intact above the 200-day." } ],
        "sources": [1] } }
  ],
  "references": [
    { "label": "Daily OHLC price data, RBLX", "detail": "Exchange consolidated tape" }
  ]
}
```

- `meta.mode`: `"report"` = portrait A4 document · `"presentation"` = 16:9 landscape deck.
- Paths inside the contract (chart contracts, brand, logo) resolve **relative to the
  contract file**.
- `meta.footer` text repeats on every page; page numbers are automatic (skipped on cover).
- `references` (top-level) is **required** — the renderer auto-appends a References
  page as the always-last page. Pages cite into it with `sources: [1, 3]` (1-based);
  citations render as `[n]` links in the page footer, anchored to the reference entry.

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
| `comparison` | `title`, `story`, `companies` (2–7) | `subtitle`, `stats`, `takeaway`, `source` | thematic-investing sensitivity / exposure tables |
| `industry-breakdown` | `title`, `story`, `layers` (2–9) | `subtitle`, `stats`, `takeaway`, `source` | thematic-investing value-chain map |
| `price-chart-technicals` | `title`, `story`, `chart`, `commentary` (1–4 blocks) | `subtitle`, `stats`, `levels`, `sources` | charting `price` builder + technical-analysis levels |
| `table-commentary` | `title`, `story`, `table`, `commentary` | `subtitle`, `stats`, `sources` | sec-filings KPIs, any tabular data |

(`references` is not a template you place — the renderer always appends it last.)

Slot shapes:

- **story** — *required on every data page.* The one-sentence point of the page,
  conclusion-first (supports `**bold**`). Renders as a banner under the title.
- **stats** — `[{ "label": "Entry", "value": "$215" }]` key-number chips rendered
  under the story on any template. Put the numbers the user asked for here.
- **levels** — `[{ "value": 215, "label": "Support $215", "kind": "support" }]` on
  `price-chart-technicals`: horizontal lines drawn **on the chart** with colored
  labels. `kind`: `support`/`entry` = green, `resistance`/`exit` = red, omitted =
  gray. Always plot the levels the commentary talks about.
- **sources** — `[1, 3]`, 1-based indices into the top-level `references` array;
  rendered as linked `[n]` citations in the page footer.

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

Default skeleton when the storyline isn't fully specified: `cover` → one chart page →
`table-commentary`. For "make a deck/presentation", same storyline with
`meta.mode: "presentation"` and one point per slide.

## Rules

- **Storyline in, PDF out — nothing else.** Don't gather data, build charts, or
  invent narrative here; that happens upstream. If the storyline is missing a page's
  point, push back upstream rather than padding the page.
- **Every data page states its point.** `story` is required; the renderer errors
  without it. Headline numbers go in `stats`, not buried in prose.
- **Compute upstream, never in prose.** Numbers come from the data pipelines
  (charting's Polars layer, sec-filings extracts) already formatted; this skill only
  lays them out.
- **One point per page/slide.** Respect the row caps (7 companies,
  10 table rows per slide) — the renderer errors past them; split across pages.
- **Information-dense, not airy.** These are professional research documents — a
  half-empty page means the storyline gave that page too little to say.
- **Always cite.** Top-level `references` is required (the renderer errors without
  it); every data page should carry `sources: [n]` pointing into it. Levels the
  commentary mentions must also be drawn on the chart via `levels`.
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
