# Chart aesthetics — color, axes, labels, hints

Color, axis, label, and tooltip settings the TS layer applies (`src/theme.ts`,
`src/charts/build.ts`).

## Color carries meaning
In finance, color is semantic — decorative or wrong color actively misleads.

| Color | `theme.ts` | Means |
|---|---|---|
| Green `#1A9850` | `POSITIVE` | beat, gain, up bar, accretive delta |
| Red `#D73027` | `NEGATIVE` | miss, loss, down bar, dilutive delta |
| Blue `#0072B2` | `PRIMARY` | main level series (revenue, reported) |
| Orange `#E69F00` | `SECONDARY` | paired level series (net income, dividend) |
| Purple `#6A3D9A` | `NEUTRAL` | overlaid line (margin, yield) — stands out over bars |
| Grey `#9E9E9E` | `ESTIMATE` | consensus / forecast — **dashed** line |
| Slate `#37474F` | `TOTAL` | waterfall totals / subtotals |

**Rules:**
- Never color a miss green or a beat red — sign drives color in `surprise` and `waterfall`.
- Estimates muted + **dashed**; actuals solid + bold. The eye lands on what happened.
- **Categorical palette** for segments / multiple companies: `PALETTE` is Okabe–Ito,
  colorblind-safe (deuteranopia/protanopia), cycled by `colorForIndex`. Same segment keeps its
  color across periods.
- Candlestick: `upColor` green, down `color` red.

## Axes
- **Y-axis** named with unit — `Revenue ($B)`, `Net margin (%)`, `Dividend / share ($)`, or
  `Indexed (base 100)`. Label formatter matches (`src/format.ts`).
- **Secondary y-axis** only when units differ; `opposite: true`, tinted, split-lines tied to
  the primary axis.
- **X-axis**: fiscal labels (`FY2025`, `Q2'26`) on a category axis; real dates on a datetime
  axis (Stock). Sorted oldest → newest.
- Bars baseline at **0** (length encodes magnitude); let `%`/price axes auto-range.

## Labels & chrome
- **Title** = subject + metric; **subtitle** = period/currency qualifier.
- **Legend** when >1 series; suppressed for single-series and waterfall (x-labels name each bar).
- **Data labels**: compact (`AK.fmt`), small (9px), **per-need** — on for ≤3-series category
  charts (margins, surprise, dividends, waterfall, estimate-vs-reported); off for dense
  segment stacks, datetime/price, and 100%-stacked. Override with `buildOptions(d,{dataLabels})`.
- **Event flags** (`flags`) annotate *why* a line moved — labelled dashed plotLines.
- **Tooltip**: shared on category charts (all series at a period together), units via
  `valuePrefix`/`valueSuffix`.

## Placeholder hints (missing data)
- Missing points are **gaps** (`null`, line breaks) — see `data-units.md` §8.
- A not-yet-reported quarter in `surprise`/`estimate_vs_reported` is a gap, not a zero bar.
- If a whole series is empty, **don't render an empty chart** — tell the user the data wasn't
  available (e.g. no segmentation reported for this issuer) and offer the nearest chart you can.
- A segment absent only in some years → real `0` (it didn't exist), distinct from a gap.

## Anti-patterns (don't ship these)
- Raw dollars on an axis (`400000000000`) — scale + label.
- `$` and `%` on one axis — split to two axes.
- Pie charts for time series or >5 slices — use a (100%) stacked bar.
- Dual axes for two same-unit series — implies a false scale difference.
- A waterfall that doesn't reconcile to its final total.
- Overlaid raw levels to compare unequal companies — rebase to 100.
- Green/red as category identity rather than gain/loss.
- More than ~6 competing colors — group, facet, or pick the few that matter.
