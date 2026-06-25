# Highcharts mechanics

How the TS layer (`src/charts/build.ts`, `src/render.ts`) wires Highcharts. For the React
integration, see [`highcharts-react.md`](highcharts-react.md).

## Core vs Stock
- **Core** (`highcharts.js`) for fundamentals: `line`, `column`, `area`, and **`waterfall`**
  (waterfall is in core — no extra module). Constructor: `Highcharts.chart(...)`.
- **Stock** (`stock/highstock.js`) for price/time-series: includes `candlestick`/`ohlc`,
  `navigator`, `rangeSelector`. Constructor: `Highcharts.stockChart(...)`.
- `meta.stock` in the contract selects the bundle + constructor (`render.ts scriptsFor`).
- Modules added to every page: `modules/exporting.js`, `modules/accessibility.js`.

## Category vs datetime axis
- **Category**: `xAxis: { type: 'category', categories: [...] }`; series `data` is a plain list
  aligned to the categories.
- **Datetime**: `xAxis: { type: 'datetime' }`; series points are `[epochMillis, value]`
  (candlestick: `[ts, open, high, low, close]`). The Python layer emits ms via
  `process.to_millis` (UTC-pinned for deterministic fixtures).

## Native waterfall
Provide signed `y` for deltas and mark checkpoints with `isIntermediateSum: true` / `isSum:
true` — Highcharts computes the running level. Series `upColor` (rise) / `color` (fall) color
the deltas; sum points get a per-point `color` (slate). Don't fake it with transparent base
bars.

## Dual axis
`yAxis` is an **array**; a series picks its axis with `yAxis: <index>`. The secondary axis sets
`opposite: true`. `buildOptions` maps each contract `yAxes[].id` to the array index.

## Stacking
`series.stacking: 'normal'` (stacked) or `'percent'` (100% stacked); omit for grouped. Driven by
`meta.variant`. In percent stacking, the axis shows 0–100% and tooltips expose `point.percentage`
— so data labels are **off** for the percent variant (they'd show absolute, not share).

## JSON-safe formatters (the key constraint)
A self-contained page embeds the options object. `JSON.stringify` **drops functions**, so
formatter functions can't survive a naive serialize. The skill instead:
1. builders attach a serializable **descriptor** `{__fn__:'fmt', opts:{…}}` (`src/format.ts`
   `fmtRef`) wherever a label formatter is needed;
2. `render.ts optionsToJs` walks the options and emits a JS source string, turning each
   descriptor into `function(){ return AK.fmt(this.value ?? this.y, opts) }`;
3. the page embeds `HELPERS_JS` (defines `AK.fmt`) before the chart call.

This keeps builders **pure and JSON-testable** (Vitest asserts the descriptor) while the page
gets real functions for compact/accounting labels. Tooltips avoid functions entirely via
`valuePrefix`/`valueSuffix`/`valueDecimals` (static strings).

## Event flags
Caller events render as labelled dashed `xAxis.plotLines` — `value` is the **category index**
on a category axis, or **epoch ms** on a datetime axis. (Highcharts also has a `flags` *series*
for Stock; plotLines are simpler and work on both axis types, so that's what we use.)

## Rendering target
`renderChartPage(finalData)` → a standalone `.html` (Highcharts from CDN). The same
`buildOptions(finalData)` object can instead be passed to `@highcharts/react`'s
`<Chart options={…} />` if embedding in a React app — but then drop the descriptor/`optionsToJs`
step and provide real `formatter` functions in React (you're no longer constrained to JSON).
