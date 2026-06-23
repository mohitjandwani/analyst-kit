# Chart catalog

For each chart: when to use it, the **input records** the builder expects (generic financial
fields — the data is assumed already available), the **builder** (`pipeline/charts.py`), and the
**options** it sets. Pick the builder; the TypeScript `buildOptions` reads the contract and
produces the matching Highcharts series.

## 1. Line / YoY — trend, growth, lead/lag, event flags
- **Use when:** "how has revenue/EPS/margin trended", "YoY growth", "did the launch move it".
- **Input:** income records (`fiscalYear`, `revenue`, …). **Builders:** `revenue_trend`, `revenue_yoy`.
- `revenue_yoy` plots % change (lag 1 annual / 4 quarterly), first period `null`.
- `flags=[{x,title}]` → labelled dashed `xAxis.plotLines`. Per-series `shift` offsets a series
  for lead/lag (legend shows `(shift +2)`).

## 2 & 3. Segment bars — revenue by product/region
- **Use when:** "revenue breakdown by segment", "is Services a bigger share".
- **Input:** segmentation records (`fiscalYear`, `data: {segment: value}`). **Builder:** `segments(variant=…)`.
- `variant="stacked"` (total + composition), `"percent"` (100% mix, % axis), `"grouped"` (sizes
  side-by-side). Windows to the last *n* years, unions segments, fills missing with `0`, orders
  largest-first.

## 4. Waterfall — revenue → net income
- **Use when:** "how does revenue turn into profit", "bridge revenue to net income".
- **Input:** one income record (`revenue`, `grossProfit`, `operatingIncome`, `netIncome`). **Builder:** `waterfall`.
- Native Highcharts `waterfall`; `total`/sum steps are slate checkpoints, deltas float green
  (add) / red (subtract). The deltas reconcile to net income.

## 5. Dividend history + yield — dual axis
- **Use when:** "dividend history and yield".
- **Input:** dividend records (`date`, `dividend`, `yield`). **Builder:** `dividend_yield`.
- $/share **bars** (left, 2 dp) + yield **% line** (right, `opposite`), each axis tinted.

## 6. Revenue + net income + margin — dual axis
- **Use when:** "recent performance and margins".
- **Input:** income records. **Builder:** `revenue_margins`.
- Revenue + net income **columns** (left $ axis) + net **margin % line** (right % axis); margin
  computed `net/revenue`.

## 7. Earnings surprise — sign-colored bars
- **Use when:** "earnings surprise over time", "beat or miss".
- **Input:** earnings records (`epsActual`, `epsEstimated`, `date`). **Builder:** `surprise`.
- Bar = `(actual − estimate)/|estimate|×100`; sign drives color (green beat / red miss), zero
  baseline.

## 8. Estimate vs reported — grouped bars
- **Use when:** "estimate vs reported", "consensus vs actual".
- **Input:** earnings records (`{metric}Actual`, `{metric}Estimated`). **Builder:** `estimate_vs_reported`.
- Estimate **muted grey**, reported **primary**. `metric="revenue"` (scaled $B) or `"eps"`
  (per share, 2 dp).

## 9. Price — candlestick / line (Highcharts Stock)
- **Use when:** "price chart", "candlestick", "price with events".
- **Input:** OHLC records (`date`, `open`, `high`, `low`, `close`). **Builder:** `price(primary=…)`.
- **Candlestick when price is the primary series; line when it's context** (`primary=False`).
  Datetime axis, navigator + rangeSelector, caller flags. Up green / down red.

## Comparing two companies — rebase
- **Builder:** `compare_rebased`. Rebase each series to 100 at a common start; plot as lines.
  Never stack or dual-axis two companies' raw levels.

---
No builder fits? Default to a labelled line (trend) or grouped column (comparison) and say why —
never an unlabelled or mixed-unit chart.
