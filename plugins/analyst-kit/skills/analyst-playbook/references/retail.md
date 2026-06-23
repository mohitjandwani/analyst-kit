# Retail / consumer playbook

## Reporting calendar & conventions

- Most US retailers report on the **NRF 4-5-4 calendar**: fiscal year ends the
  Saturday nearest **January 31**, quarters are fixed 13-week blocks
  (Q1 Feb–Apr, Q2 May–Jul, Q3 Aug–Oct, Q4 Nov–Jan).
- Label convention: "fiscal 2024" is the year that *mostly falls in calendar 2024*
  but **ends in early calendar 2025**. Always print the period end date next to the
  label.
- Every 5–6 years the fiscal year has a **53rd week** (e.g. many retailers' FY2023).
  The extra week lands in Q4 and inflates that year's Q4 and FY growth by ~7–8% and
  ~2% respectively; the *following* year's YoY is correspondingly depressed.

## KPIs that matter

- **Comparable sales ("comps"/SSS)** — the headline. Definitions vary by company
  (some include e-commerce, some exclude; the definition is in the earnings release
  footnotes via sec-filings). Never compare comps across companies without checking.
- **Net sales by channel/brand/segment** — stores vs direct/digital vs international;
  in the earnings release (8-K EX-99.x), not in fundamentals APIs.
- **Gross margin** — the markdown cycle shows up here before it shows up in sales.
- **Inventory vs sales growth** — inventory growing faster than sales for 2+ quarters
  precedes markdowns.
- **Store count / square footage** — separates comp growth from expansion growth.

## Normalization rules

- Re-bin anything calendar-based (search interest, foot traffic, macro series) into
  the **retail fiscal quarters** (Feb–Apr, …, Nov–Jan), not calendar quarters.
- In 53-week years, either exclude the extra week (companies usually disclose
  comps on a 52-vs-52 basis) or flag the comparison as distorted.
- Compare YoY of the **same fiscal quarter**; sequential quarters are meaningless
  (see seasonality).

## Seasonality

Q4 (Nov–Jan) contains holiday and is the year for most retailers — often 30%+ of
sales and most of the profit. Q1 is the trough. Any analysis comparing Q4 to Q3
levels, or aligning a retailer's Q4 with a calendar company's Q4, is wrong by
construction.

## Valuation norms

- EV/EBITDA and P/E on *next* fiscal year; the market pays for comp acceleration,
  not absolute growth.
- Margin structure matters more than sales growth at maturity: a 100bp gross-margin
  move dominates a 3% comp.

## Common traps

- Treating "FY2024" as calendar 2024 (it ends Feb 2025).
- YoY across a 53-week year without adjustment.
- Comparing comps with different definitions (with/without digital).
- Aligning retail quarters to calendar quarters when joining external data.
- Ignoring that January (clearance month) sits inside Q4.

## Data-source quirks

- FMP carries GAAP statements with the company's fiscal labels — verify the actual
  period end dates via its fiscal-period data before mapping.
- Comps, channel splits, and store counts live **only** in earnings releases /
  10-K/10-Q — use sec-filings (8-K exhibits, items 2.02).
