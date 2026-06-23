# Our goal is to build a charting library which understands financial data better than regular claude charting

Charting skill should have
1. Matching intent to right type of charts
2. Guidelines on data units in charts and how to normalise them
3. Chart Aesthetics
4. Examples & References
5. Tests


A line chart which shows year-over-year numbers with flags to indicate major events. With shift, the ability to shift one chart to see lead and lag.


Break down bar chart over time with different sections showing different revenue segments. 

Earnings surprise over time


Breakdown waterfall chart of Revenue into net profits
- waterfall chart

Dividend history + Dividend yield in the same chart
- dividend history bar charts
- dividend yield line chart


Company’s recent performance and margins
Revenue
Net Income
Margin %


Revenue breakdown over time
grouped bar chart

Estimate vs Reported


Things to keep in mind:
1. Colors of each data
2. X-axis
3. Y-axis
4. labels
5. Data Units 
6. Placeholder hints

Dividend history %
Lead, Lags


# Charting test cases

YoY for multiple data

Shift of 3, 6, 9 months for multiple data

Flags for earnings and calls



# Data

The financial data is assumed to be already available (produced by an upstream step in
the workflow). This skill does not fetch data — its thin Polars layer only loads,
validates, and normalises records into the chart contract.

> Note: this file is the original design brief. The implemented skill lives in
> `SKILL.md` + `pipeline/` + `src/` + `references/` + `tests/`.