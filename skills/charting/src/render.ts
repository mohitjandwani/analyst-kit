/**
 * Render a final-data payload to a self-contained HTML page.
 *
 * `optionsToJs` serializes the options object to a JS source string, hydrating the
 * `{__fn__:'fmt'}` formatter descriptors into real `function(){…}` that call the
 * embedded `HFA.fmt`. The page loads Highcharts (Stock for time-series) from CDN,
 * so it opens in a browser with no build step.
 */
import { buildOptions } from './charts/build.js';
import { HELPERS_JS } from './format.js';
import type { BuildOpts, FinalData } from './types.js';

// jsDelivr (not code.highcharts.com, which is blocked on some networks). Pinned major version.
const CDN = 'https://cdn.jsdelivr.net/npm/highcharts@12';

/** Serialize options to JS, turning formatter descriptors into functions. */
export function optionsToJs(node: unknown): string {
  if (node === null || node === undefined) return 'null';
  if (Array.isArray(node)) return '[' + node.map(optionsToJs).join(',') + ']';
  if (typeof node === 'object') {
    const obj = node as Record<string, unknown>;
    if (obj.__fn__ === 'fmt') {
      return `function(){var v=(this.value!=null?this.value:this.y);return HFA.fmt(v,${JSON.stringify(obj.opts)});}`;
    }
    const parts = Object.entries(obj)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${JSON.stringify(k)}:${optionsToJs(v)}`);
    return '{' + parts.join(',') + '}';
  }
  return JSON.stringify(node);
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
}

/** Highcharts CDN scripts a chart needs. Highstock = time-series bundle (has candlestick);
 *  highcharts-more carries the waterfall series type (not in core). */
export function scriptsFor(useStock: boolean, needsMore = false): string[] {
  const out = [useStock ? `${CDN}/highstock.js` : `${CDN}/highcharts.js`];
  if (needsMore) out.push(`${CDN}/highcharts-more.js`);
  out.push(`${CDN}/modules/exporting.js`, `${CDN}/modules/accessibility.js`);
  return out;
}

export function renderChartPage(d: FinalData, opts: BuildOpts = {}): string {
  const options = buildOptions(d, opts);
  const useStock = opts.stock ?? !!d.meta?.stock;
  const needsMore = d.series.some((s) => s.kind === 'waterfall');
  const ctor = useStock ? 'stockChart' : 'chart';
  const tags = scriptsFor(useStock, needsMore).map((s) => `<script src="${s}"></script>`).join('\n  ');
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(d.title)}</title>
  ${tags}
  <style>html,body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}#c{width:100%;height:520px}</style>
</head>
<body>
  <div id="c"></div>
  <script>
${HELPERS_JS}
Highcharts.${ctor}('c', ${optionsToJs(options)});
  </script>
</body>
</html>
`;
}
