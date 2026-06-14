---
id: 50-tsla-entry-exit
timeoutMs: 1200000
---

Using daily price AND volume for Tesla (TSLA) over the last 2 years, identify good
entry and exit points and present them on a chart.

This must be rule-based, not hindsight storytelling:

1. Fetch 2 years of daily OHLCV from FMP.
2. Define 2-3 explicit, mechanical signal rules up front that combine price and volume —
   for example: a close above the 50-day moving average on volume at least 1.5x its
   20-day average (entry), a volume-climax reversal day (exit), or a close below a prior
   swing low on elevated volume (exit). State each rule precisely (thresholds and
   lookback windows) before showing any results.
3. Compute the signals with a script over the full series — never by eyeballing the
   chart — and keep only the signal dates the rules actually fire on.

Deliver a single report with: a candlestick chart of the full 2 years with volume
visible and every entry/exit signal annotated on the chart at its date; a table listing
each signal (date, closing price, which rule fired, and the price change to the next
opposite signal); a simple honesty check stating what a buy-and-hold position returned
over the same window versus naively following the signals; and a short paragraph on
which rule looked most and least useful. Make clear this is a methodology demonstration,
not investment advice.

Assemble the final deliverable with the reporting skill: a branded PDF report written to `output/50-tsla-entry-exit.pdf`.
