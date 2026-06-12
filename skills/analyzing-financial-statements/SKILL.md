---
name: analyzing-financial-statements
type: capability
description: >
  Calculate and interpret key financial ratios from financial statement data
  (income statement, balance sheet, cash flow, market data) for investment
  analysis — profitability (ROE, ROA, margins), liquidity (current/quick/cash),
  leverage (debt-to-equity, interest coverage), efficiency (asset/inventory/
  receivables turnover), valuation (P/E, P/B, P/S, EV/EBITDA, PEG), and
  per-share metrics, with industry-standard interpretation and benchmarking.
  Pure-stdlib Python, fully offline — no API key. Triggers: "calculate financial ratios for X",
  "what's the P/E / ROE / debt-to-equity of Y", "analyze the liquidity /
  leverage / profitability of Z", "interpret these financial statements",
  "ratio analysis on this balance sheet", "is this company's margin / coverage
  healthy", "benchmark <company>'s ratios".
---

# Financial Ratio Calculator Skill

This skill provides comprehensive financial ratio analysis for evaluating company performance, profitability, liquidity, and valuation.

## Capabilities

Calculate and interpret:
- **Profitability Ratios**: ROE, ROA, Gross Margin, Operating Margin, Net Margin
- **Liquidity Ratios**: Current Ratio, Quick Ratio, Cash Ratio
- **Leverage Ratios**: Debt-to-Equity, Interest Coverage, Debt Service Coverage
- **Efficiency Ratios**: Asset Turnover, Inventory Turnover, Receivables Turnover
- **Valuation Ratios**: P/E, P/B, P/S, EV/EBITDA, PEG
- **Per-Share Metrics**: EPS, Book Value per Share, Dividend per Share

## How to Use

1. **Input Data**: Provide financial statement data (income statement, balance sheet, cash flow)
2. **Select Ratios**: Specify which ratios to calculate or use "all" for comprehensive analysis
3. **Interpretation**: The skill will calculate ratios and provide industry-standard interpretations

## Input Format

Financial data can be provided as:
- CSV with financial line items
- JSON with structured financial statements
- Text description of key financial figures
- Excel files with financial statements (convert to JSON/dict first with your
  own tooling — the bundled scripts read structured Python dicts, not .xlsx)

## Output Format

The scripts return calculated ratios and interpretations as Python dicts /
JSON. Results include:
- Calculated ratios with values
- Industry benchmark comparisons (when available)
- Trend analysis (if multiple periods provided)
- Interpretation and insights

If the user wants a formatted Excel or chart deliverable, assemble it from the
JSON output with other tools — the scripts themselves don't write Excel.

## Example Usage

"Calculate key financial ratios for this company based on the attached financial statements"

"What's the P/E ratio if the stock price is $50 and annual earnings are $2.50 per share?"

"Analyze the liquidity position using the balance sheet data"

## Scripts

- `scripts/calculate_ratios.py`: Main calculation engine for all financial ratios
- `scripts/interpret_ratios.py`: Provides interpretation and benchmarking

Both scripts are pure standard-library Python (no third-party dependencies).
Import the classes (`FinancialRatioCalculator`, the interpreter) into a small
driver script, or run them directly to see the built-in example.

## Best Practices

1. Always validate data completeness before calculations
2. Handle missing values appropriately (use industry averages or exclude)
3. Consider industry context when interpreting ratios
4. Include period comparisons for trend analysis
5. Flag unusual or concerning ratios

## Limitations

- Requires accurate financial data
- Industry benchmarks are general guidelines
- Some ratios may not apply to all industries
- Historical data doesn't guarantee future performance
