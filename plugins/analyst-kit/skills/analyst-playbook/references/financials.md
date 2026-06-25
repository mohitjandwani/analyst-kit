# Financials (banks, insurers, exchanges) playbook

## Reporting calendar & conventions

- Almost all calendar-year reporters; the alignment problems of other sectors
  mostly don't apply.
- The income statement is structurally different: **there is no "revenue" line** for
  a bank — top-line = net interest income (NII) + noninterest (fee) income. Any
  generic "revenue growth" number from a fundamentals API needs checking against
  what it actually summed.

## KPIs that matter

- **NII and NIM** (net interest margin) — the core engine; driven by asset yields
  vs deposit costs (deposit beta through a rate cycle).
- **Provisions / net charge-offs (NCOs)** — the credit cycle; under CECL,
  provisions front-load expected losses and swing earnings hard.
- **Efficiency ratio** — expenses / revenue (lower is better).
- **CET1 ratio** — the regulatory capital constraint on buybacks/dividends.
- **TBV per share and ROTE** — the valuation pair (see below).
- Insurers: combined ratio, float growth, investment income. Exchanges/brokers:
  volumes (ADV), net interest on client cash.

## Normalization rules

- Use **tangible** book and **ROTE**, not stated book/ROE (goodwill distorts).
- Strip identifiable one-offs before trending: FDIC special assessments, securities
  sale losses, legal reserves — listed in the earnings release.
- AOCI marks on AFS securities hit TBV through rates; a TBV drop in a rate spike is
  a mark, not a loss event — but it is real for capital. Say which lens you're using.

## Seasonality

Mild. Trading/markets revenue skews Q1; provisions follow the credit cycle, not the
calendar. Sequential comparisons are acceptable here, unlike retail/software.

## Valuation norms

- **P/TBV against ROTE** is the sector's pricing line (a ~10% ROTE bank at ~1.0x
  TBV; premium scales with sustainable ROTE above the cost of equity).
- P/E works as a cross-check; DDM/capital-return yield for mature franchises.
- Banks are macro instruments: the rate path and credit cycle move the group more
  than idiosyncratic execution.

## Common traps

- Reading a fundamentals API's "revenue"/"cost of revenue" fields literally for a
  bank (interest expense often lands in odd places).
- Trending EPS through provision swings without separating PPNR (pre-provision
  net revenue) from credit costs.
- Ignoring AOCI when comparing TBV across the 2022–2023 rate shock.
- Comparing efficiency ratios across banks with different business mixes
  (markets-heavy vs retail-heavy).

## Data-source quirks

- sec-filings: the 10-Q/10-K and the earnings release supplement carry NIM, NCOs,
  CET1, and the PPNR bridge — none of which fundamentals APIs model well.
- FMP: fine for prices, EPS history, and shares; treat its bank income-statement
  line mapping with suspicion and reconcile against the release.
