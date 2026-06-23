/**
 * Render a final-data payload to a self-contained HTML page.
 *
 * `optionsToJs` serializes the options object to a JS source string, hydrating the
 * `{__fn__:'fmt'}` formatter descriptors into real `function(){…}` that call the
 * embedded `AK.fmt`. By default the page inlines the vendored Highcharts scripts so
 * it renders in any headless/sandboxed environment with no outbound network access.
 * Pass `opts.cdnScripts = true` to emit lightweight `<script src>` tags instead
 * (good for browser preview; uses jsDelivr, never code.highcharts.com).
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildOptions } from './charts/build.js';
import { HELPERS_JS } from './format.js';
import type { BuildOpts, FinalData } from './types.js';

// jsDelivr (not code.highcharts.com, which returns 403 for headless requests).
const CDN = 'https://cdn.jsdelivr.net/npm/highcharts@12';

// Vendored scripts live at ../vendor/highcharts/ relative to this source file.
// That path survives skill installation (vendor/ is not in the installer's SKIP_DIRS).
const VENDOR = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'vendor', 'highcharts');
const _cache = new Map<string, string>();
function readVendor(rel: string): string {
  if (!_cache.has(rel)) _cache.set(rel, readFileSync(resolve(VENDOR, rel), 'utf8'));
  return _cache.get(rel)!;
}

/** Serialize options to JS, turning formatter descriptors into functions. */
export function optionsToJs(node: unknown): string {
  if (node === null || node === undefined) return 'null';
  if (Array.isArray(node)) return '[' + node.map(optionsToJs).join(',') + ']';
  if (typeof node === 'object') {
    const obj = node as Record<string, unknown>;
    if (obj.__fn__ === 'fmt') {
      return `function(){var v=(this.value!=null?this.value:this.y);return AK.fmt(v,${JSON.stringify(obj.opts)});}`;
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

/** Inline the vendored Highcharts scripts as `<script>…</script>` blocks.
 *  Makes the page self-contained — no network access required at render time. */
function inlineTagsFor(useStock: boolean, needsMore: boolean): string {
  const files = [useStock ? 'highstock.js' : 'highcharts.js'];
  if (needsMore) files.push('highcharts-more.js');
  files.push('modules/exporting.js', 'modules/accessibility.js');
  return files.map((f) => `<script>${readVendor(f)}</script>`).join('\n  ');
}

export function renderChartPage(d: FinalData, opts: BuildOpts = {}): string {
  const options = buildOptions(d, opts);
  const useStock = opts.stock ?? !!d.meta?.stock;
  const needsMore = d.series.some((s) => s.kind === 'waterfall' || s.kind === 'arearange');
  const ctor = useStock ? 'stockChart' : 'chart';
  const tags = opts.cdnScripts
    ? scriptsFor(useStock, needsMore).map((s) => `<script src="${s}"></script>`).join('\n  ')
    : inlineTagsFor(useStock, needsMore);
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
