# Software / internet playbook

## Reporting calendar & conventions

- Fiscal year ends vary: Salesforce/Workday end **January**, Microsoft **June**,
  Adobe **November/December**, Oracle **May**; most internet names are calendar.
  Check before aligning anything.
- The metrics that matter are **non-GAAP and live only in the earnings release /
  shareholder letter** (8-K exhibit EX-99.1/99.2), not in fundamentals APIs.

## KPIs that matter

Know the ladder — these are *different numbers* and must never be mixed in one series:

- **Bookings** — contracts signed in the period (Roblox's headline metric).
- **Billings** — invoiced; revenue + change in deferred revenue.
- **Revenue (GAAP)** — recognized ratably; lags bookings for upfront-paid products.
- **ARR / RPO** — annualized run-rate vs contracted backlog (cRPO = next 12m).
- **NDR/NRR** — expansion within existing customers; the durability metric.
- **Engagement** (DAU/MAU, hours) — for consumer; the leading indicator of bookings.
- **FCF margin and Rule of 40** (growth % + FCF margin %) — the efficiency frame.
- **SBC as % of revenue** — the gap between non-GAAP and real economics.

## Normalization rules

- Bookings/ARR histories: pull every quarter's 8-K exhibit (sec-filings batch
  listing) — companies restate definitions; use the metric as defined *at the time*
  and flag definition changes.
- Index-like series (search interest, app downloads) vs dollars → YoY only.
- Compare growth on a like basis: cc (constant-currency) growth if disclosed and FX
  swung.

## Seasonality

- Enterprise: Q4 budget-flush — the January/December-ending Q4 is the bookings
  quarter; Q1 is seasonally weak (don't read a sequential Q1 drop as deceleration).
- Consumer: December quarter peaks (holiday engagement + ad spend); summer lull.

## Valuation norms

- EV/Revenue (or EV/ARR) adjusted for growth — the market's line moves with rates;
  state the regime, don't quote a multiple as cheap/expensive in a vacuum.
- At scale the frame shifts to FCF multiples and Rule of 40.

## Common traps

- Mixing bookings and revenue in one growth series (they can diverge for quarters).
- Treating ARR as revenue run-rate (definitions differ by company).
- Quoting non-GAAP margins without noting SBC.
- Comparing a January-FY company's "Q4" with a calendar company's Q4.
- COVID-era base effects: 2020–2021 pull-forward makes 2021–2022 YoY look broken;
  use 3-year CAGRs across that window.

## Data-source quirks

- GAAP revenue/income: FMP. Bookings, DAU, ARR, NDR: **only** sec-filings 8-K
  exhibits (the data-extractor pattern: list exhibits for N quarters in one call,
  then BM25-narrow each).
- Earnings-call transcripts (FMP) carry guidance language the releases omit.
