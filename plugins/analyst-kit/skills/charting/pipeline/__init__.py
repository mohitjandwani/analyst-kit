"""Charting data layer — Python + Polars.

Loads, validates, and normalizes already-available financial records into the chart
contract the TypeScript Highcharts builders consume (see SKILL.md). All the dataframe
work — scaling, YoY, rebasing, segment pivots, waterfall reconciliation, axis
resolution, lookback windowing — lives here. The TS side only formats and draws.
"""
