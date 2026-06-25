# Semiconductors / hardware playbook

## Reporting calendar & conventions

- Fiscal year ends are all over the map: **NVDA ends late January** (so "FY2026" is
  mostly calendar 2025 — the label runs one ahead), AMD and Intel are calendar,
  Micron ends ~August, Broadcom ~October/November, Apple ~September.
- NVDA fiscal quarters end ~end of April / July / October / January — one month
  after calendar quarters. Map NVDA fiscal Qn-1 month-blocks (Feb–Apr, May–Jul,
  Aug–Oct, Nov–Jan) when joining calendar-quarter data.
- **Taiwan-listed companies (TSMC, Delta, Hon Hai…) publish monthly revenue in TWD**
  by the 10th of the following month — a leading indicator one to two months ahead
  of any US customer's quarterly print. Fetch via finmind.

## KPIs that matter

- **Segment revenue** (Data Center, Gaming, Client, Embedded…) — the real story;
  totals hide it. From earnings releases / 10-Q segment notes (sec-filings).
- **Segment definitions move**: NVDA's Data Center includes networking (Mellanox);
  AMD folded Xilinx into segments in 2022; recasts make long histories splice-y.
  Note any definition change in the deliverable.
- **Inventory and purchase obligations** — the cycle's early-warning gauges.
- **Gross margin** — mix (data center vs consumer) shows up here.
- For foundries/equipment: utilization, wafer shipments, book-to-bill.

## Normalization rules

- Monthly TWD revenue → aggregate into the **comparison target's fiscal quarters**;
  across currencies compare **YoY growth only** (or convert at period-average FX and
  say so).
- Use lag 12 for monthly YoY, lag 4 for quarterly YoY (charting pipeline).
- When fiscal quarters end a month apart (NVDA vs AMD), align by *closest calendar
  quarter* and state the rule; never pretend the periods are identical.

## Seasonality

Consumer-exposed lines (gaming, phones) skew to the September/December quarters
(holiday builds start in Q3). Data-center demand is capex-driven and lumpy, not
seasonal. Taiwan monthly revenue dips around Lunar New Year (Jan/Feb) — a January
drop is calendar, not demand.

## Valuation norms

- Deeply cyclical names trade on **normalized** earnings: P/E looks cheapest at the
  peak and most expensive at the trough — the multiple inverts the cycle.
- Growth/AI names price on EV/S and forward EPS revisions; memory trades near P/B
  at troughs.

## Common traps

- NVDA's FY label being one year ahead of the calendar.
- Comparing "GPU sales" across companies that don't report a GPU line — use the
  segments each company actually reports and say they're not identical.
- Splicing across a segment recast without flagging it.
- Treating a Lunar-New-Year monthly dip as a demand signal.
- Double-counting the supply chain: a supplier's revenue growth already embeds the
  customer's unit growth plus content/ASP gains.

## Data-source quirks

- finmind: Taiwan monthly revenue (`data_id` = stock number, e.g. 2308 Delta).
- FMP: US GAAP statements + fiscal-period mapping (use it to confirm quarter end
  dates before aligning).
- Segment revenue: earnings release tables via sec-filings; FMP's segmentation
  endpoints are spotty for these names.
