---
name: charting
type: capability
description: >
  Build financially-correct charts from company fundamentals — pick the right chart for the
  question, normalise units (one unit per axis, $B/$M scaling, %-vs-$ dual axes, rebasing for
  comparisons), and apply finance conventions (green beat / red miss, accounting negatives,
  dashed estimates, dark totals). A thin Python+Polars layer normalises already-available data
  into a chart contract; a TypeScript layer emits Highcharts options and renders a
  self-contained HTML page. Covers revenue trends & YoY, segment mix, margins, dividends,
  earnings surprise, estimate-vs-reported, revenue→net-income waterfalls, and price
  (candlestick/Stock). Use whenever the user wants to chart, plot, graph, or visualize
  financial data. Triggers: "chart revenue over time", "plot YoY growth with event flags",
  "revenue breakdown by segment", "dividend history and yield", "earnings surprise chart",
  "estimate vs reported", "waterfall from revenue to net income", "margins over time",
  "candlestick / price chart", "compare two companies' revenue", "show visual breakdown of income statement"
---

# Charting — Highcharts charts from financial data

Build financially-correct charts: a thin **Python + Polars** layer normalises already-available
financial data into a chart **contract**; a **TypeScript** layer turns the contract into
**Highcharts** options and a **self-contained HTML page**.

> **This is a working default, not a requirement.** Use the builders and the emitted options
> as-is, or take the options object and adapt it to your needs — you don't have to build a chart
> from scratch. It exists to save you tokens and give you something correct to start from.

> **Library:** Highcharts — **Stock** for time-series (navigator, range selector, flags),
> **Core** for fundamentals. Highcharts mechanics you'll need:
> [`references/highcharts-notes.md`](references/highcharts-notes.md). React integration:
> [`references/highcharts-react.md`](references/highcharts-react.md).

## Pipeline

```
financial data ─► Polars: load · validate · normalise ─► chart contract (JSON) ─► TS: buildOptions ─► Highcharts options ─► renderChartPage ─► self-contained .html
(assumed present)                                                                  (adapt freely)
```

Data is **assumed to be available** (produced by an upstream step). The Polars layer only
**loads, validates, and normalises** it for charting — it does not fetch. Numbers cross the
boundary **already scaled**; the TS layer formats and draws.

## The chart contract (what the TS layer consumes)

```jsonc
{
  "title": "AAPL — revenue & net margin",
  "subtitle": "FY2021–FY2025",
  "axis": { "type": "category", "categories": ["FY21","FY22","FY23","FY24","FY25"] },
  // or  "axis": { "type": "datetime" }  with series points as [tsMillis, value]
  "yAxes": [
    { "id": "money", "name": "Amount", "unit": "B", "currency": "$" },
    { "id": "pct",   "name": "Net margin", "percent": true, "opposite": true },
    { "id": "eps",   "name": "EPS", "currency": "$", "decimals": 2 }   // fixed-decimals axis
  ],
  "series": [
    { "name": "Revenue",    "kind": "column", "yAxis": "money", "role": "primary",   "data": [365.8, 394.3, 383.3, 391.0, 416.2] },
    { "name": "Net margin", "kind": "line",   "yAxis": "pct",   "role": "neutral",   "data": [25.9, 25.3, 25.3, 24.0, 26.9] }
  ],
  "flags": [ { "x": "FY24", "title": "Event" } ],   // caller-provided; x matches the axis
  "meta": { "chart": "revenueMargins", "variant": "stacked", "stock": false }
}
```

- **`role`** → color in the TS layer: `primary` · `secondary` · `neutral` · `positive` ·
  `negative` · `estimate` · `total` · `segment` · `signed` · `waterfall`.
- **`kind`** → Highcharts series type: `line` · `column` · `area` · `waterfall` · `candlestick`.
- **`yAxes[]`** carry `unit` / `currency` / `percent` / `decimals` (see the units table).
- **`meta`**: `variant` (`stacked|percent|grouped`) drives column stacking; `stock: true`
  selects Highcharts Stock (navigator + range selector); `zeroLine: true` draws a 0 baseline.

## Use it

```bash
pip install -r requirements.txt        # polars, pytest
npm install                            # highcharts builders + vitest
python -m pipeline.cli                 # tests/data/*.json (dummy) → tests/contracts/*.json
npm run examples                       # tests/contracts/*.json → examples/*.html
```

```python
from pipeline import charts
contract = charts.revenue_margins(income_records)   # records → contract dict
```
```ts
import { renderChartPage, buildOptions } from "@hfa/charting";
const html = renderChartPage(contract);   // standalone .html (Highcharts via CDN)
const opts = buildOptions(contract);       // Highcharts options object — change anything you want
```

## Intent → chart

| The question | Chart | Builder | Notes |
|---|---|---|---|
| How has X trended? growth? | line / YoY line | `revenue_trend`, `revenue_yoy` | per-series **shift** for lead/lag; **event flags** for context |
| What happened *when*? | line + event flags | `revenue_trend(flags=…)` | caller-provided dashed vertical markers |
| Segment size over time? | stacked bar | `segments(variant="stacked")` | total + composition |
| Segment **mix** shift? | 100% stacked bar | `segments(variant="percent")` | reads mix even as total grows |
| Compare segment **sizes**? | grouped bar | `segments(variant="grouped")` | |
| Revenue → profit? | waterfall | `waterfall` | native Highcharts, reconciles to net income |
| Dividend history **and** yield? | dual-axis bar+line | `dividend_yield` | $/share bars + yield % line |
| Performance **and** profitability? | dual-axis bars+line | `revenue_margins` | revenue/NI bars + margin % line |
| Beat or miss? | sign-colored bars | `surprise` | green beat / red miss, zero baseline |
| Estimate vs reported? | grouped bars | `estimate_vs_reported` | estimate muted, reported bold |
| Price action + events? | candlestick / line | `price` | Stock: navigator + rangeSelector + flags |
| Compare two unequal companies? | rebased line | `compare_rebased` | both start at 100 → relative growth |

## Units conventions

Numbers are formatted by **data type**, not blindly. Full table:
[`references/data-units.md`](references/data-units.md). Headlines: one unit per axis ($B/$M/$K
by max value), **EPS / per-share always 2 dp** (`$1.00`), negatives in **accounting**
parentheses (`($2.5M)`), percent with one dp.

## Rules

1. **One unit per axis** (scaled + labelled in the axis name and ticks). Two units → **two axes**.
2. **Color carries meaning** — green up / red down, estimate grey-dashed, total slate, segments
   from a colorblind-safe palette. → [`references/aesthetics.md`](references/aesthetics.md)
3. **Compact, accounting labels** — see the units table; tooltip always available.
4. **Missing = gap** (`null`), not zero; a never-reported segment is a real `0`.
5. **Compare like with like** — rebase unequal companies to 100; growth uses YoY, not levels.

Chart selection detail: [`references/chart-types.md`](references/chart-types.md).

## Files

```
charting/
  SKILL.md  CHARTING.md
  pipeline/   process.py charts.py cli.py        ← thin Python + Polars (load/validate/normalise)
  src/        types.ts format.ts theme.ts render.ts charts/build.ts index.ts   ← TS (Highcharts)
  references/ chart-types · data-units · aesthetics · highcharts-notes · highcharts-react
  tests/      data/*.json (dummy records) · contracts/*.json (generated) · *.test.ts · test_*.py
  examples/   *.html (generated)
  requirements.txt  package.json  tsconfig.json
```

## Tests — two suites, offline

```bash
python -m pytest tests -q     # Polars normalisation (28 tests)
npm test                      # Highcharts builders + formatting (29 tests)
```

Both run against the dummy data in `tests/` (no network). They assert the things a financial
chart must get right — correct axis unit, sign-driven color, a waterfall that reconciles to net
income, two units on two axes, YoY math + leading gaps, EPS 2-dp / accounting formatting.
Regenerate contracts with `python -m pipeline.cli`.
