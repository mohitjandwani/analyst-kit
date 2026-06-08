/**
 * Public API for the charting layer.
 *
 *   import { renderChartPage, buildOptions } from "@hfa/charting";
 *   const html = renderChartPage(finalData);     // self-contained HTML page
 *   const opts = buildOptions(finalData);         // Highcharts options object
 *
 * `finalData` is produced by the Python + Polars layer (pipeline/charts.py).
 * One generic builder serves every chart; the contract carries the per-chart
 * decisions. The named aliases below exist for readable call sites.
 */
export * from './types.js';
export { buildOptions } from './charts/build.js';
export { renderChartPage, optionsToJs, scriptsFor } from './render.js';
export { HELPERS_JS, fmtRef } from './format.js';
export * as theme from './theme.js';

import { buildOptions } from './charts/build.js';
import { renderChartPage } from './render.js';
import type { BuildOpts, FinalData } from './types.js';

/** Build options for a chart whose type is carried in the data. */
export const buildChart = (d: FinalData, o?: BuildOpts) => buildOptions(d, o);
/** Render a chart straight to an HTML page. */
export const renderChart = (d: FinalData, o?: BuildOpts) => renderChartPage(d, o);
