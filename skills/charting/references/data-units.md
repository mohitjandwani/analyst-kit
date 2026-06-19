# Data units & number formatting

How every number is formatted on axes, data labels, and tooltips. Implemented by
`AK.fmt` (`src/format.ts`), driven by each axis's `currency` / `unit` / `percent` / `decimals`.
The Polars layer ships numbers **already scaled**; the TS layer only formats.

## Conventions table

| Data type | `yAxes` hint | Example (pos / neg) | Decimals | Negatives | Prefix / suffix |
|---|---|---|---|---|---|
| Currency, scaled | `unit:"B"｜"M"｜"K"`, `currency` | `$1.2B` / `($2.5M)` | 1 | `( )` | currency + B/M/K |
| Per-share ($/share: EPS, DPS) | `currency`, `decimals:2` | `$1.00` / `($0.45)` | **2 (fixed)** | `( )` | currency |
| Ratio / multiple | `unit:"x"`, `decimals:2` | `1.00x` / `(0.80x)` | **2 (fixed)** | `( )` | `x` suffix |
| Percent (margin, growth, yield, surprise) | `percent:true` | `26.9%` / `-3.2%` | 1 | leading `−` | `%` suffix |
| Index (rebased) | *(no unit/currency)* | `120.0` | 1 | `( )` | none (base = 100) |
| Count / shares | `unit:"B"｜"M"｜"K"` | `1.2B` | 0–1 | `( )` | B/M/K |

Rules in this table:
- **EPS / per-share / ratios are always 2 dp**, even whole values (`1` → `1.00`). Set
  `decimals: 2` on the axis.
- **Negatives use accounting parentheses** for money / per-share / ratio / index. **Percent**
  uses a leading minus (finance convention for growth/margin/surprise). To make percent use
  parentheses too, change the percent branch in `src/format.ts`.
- **Compact only** — labels never show a raw `12312135`; always the scaled value + unit.
- Add a new data type by adding a row here and setting the matching axis hints; `AK.fmt`
  needs no change unless a new negative/suffix rule is required.

## One unit per axis
Scale the whole series group together by its largest absolute value (`process.pick_scale`):
≥1e12 → `T`, ≥1e9 → `B`, ≥1e6 → `M`, ≥1e3 → `K`, else none. Write the unit into the axis
**name** (`Revenue ($B)`) and the tick **formatter**. Two different units (`$` and `%`) → **two
axes** (`opposite: true`), tinted to their series. Two series sharing a unit stay on one axis.

## Transforms (`pipeline/process.py`)
| Need | Call |
|---|---|
| Scale a series group | `pick_scale` + `scale` |
| Year-over-year % | `yoy(values, lag=1｜4)` — leading `null` gaps; zero/None-safe |
| Compare unequal sizes | `rebase(values, 100)` |
| Whole-period growth | `cagr(first, last, years)` |
| Margin % | `margin(numerator, denominator)` |
| Axis type | `resolve_axis([x_kind(x) …])` → `category` / `datetime` |

## Other rules
- **Percent is a percent**, not a ratio: pass `26.9`, not `0.269`.
- **Missing = gap** (`null`, line breaks); a never-reported segment is a real `0`.
- **Growth uses YoY**, not raw levels; **comparisons across companies use `rebase`**, not a raw
  overlay.
- **Currency**: one per axis; for cross-currency comparison use `rebase` to an index.

## Axis resolution (data-driven)
`process.resolve_axis` picks the x-axis from the data: all-category → **category**; all-datetime
→ **datetime** (Stock features); mixed-but-mappable → map categories to period-end dates and use
**datetime** so the series align.
