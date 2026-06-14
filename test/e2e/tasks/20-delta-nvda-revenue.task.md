---
id: 20-delta-nvda-revenue
timeoutMs: 1200000
---

Delta Electronics (TWSE 2308) supplies power components into the AI-server build-out
that drives NVIDIA's (NVDA) results, but the two companies report on incompatible
calendars: Delta publishes monthly revenue in TWD on the Taiwan calendar, while NVIDIA
reports quarterly in USD on a fiscal year ending late January (fiscal quarters ending
roughly end of April, July, October, and January).

Build a revenue-growth comparison for the last 3 years that handles this correctly:

1. Fetch Delta's monthly revenue (FinMind) and NVIDIA's quarterly revenue (FMP).
2. Aggregate Delta's months into NVIDIA's fiscal quarters (Feb-Apr, May-Jul, Aug-Oct,
   Nov-Jan) so the two series cover identical periods. State the mapping you used.
3. Because one series is TWD and the other USD, compare year-over-year growth rates
   only — never absolute revenue across the two companies.

The deliverable is a single report with: one chart of both YoY growth series on the
aligned fiscal-quarter axis, a supporting chart or table of Delta's raw monthly YoY
growth (lag 12) so the intra-quarter shape is visible, and a short written analysis of
whether Delta's growth tracks, leads, or lags NVIDIA's — calling out the quarters with
the largest gap between the two.

Assemble the final deliverable with the reporting skill: a branded PDF report written to `output/20-delta-nvda-revenue.pdf`.
