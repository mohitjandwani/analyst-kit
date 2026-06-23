// Render every contract with the REAL Highcharts (no CDN) under jsdom, reproducing the page
// exactly (hydrated formatters + correct modules), and report svg/errors. Catches the class of
// bug where the options object is valid but the chart never draws (missing module, etc.).
import { createRequire } from 'node:module';
import { readdirSync, readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
// @ts-ignore - diagnostic only
import { JSDOM } from 'jsdom';

import { buildOptions } from '../src/charts/build.js';
import { optionsToJs } from '../src/render.js';
import { HELPERS_JS } from '../src/format.js';

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const FX = join(here, '..', 'tests', 'contracts');

const dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true });
(globalThis as any).window = dom.window;
(globalThis as any).document = dom.window.document;
(dom.window as any).requestAnimationFrame = (cb: any) => setTimeout(cb, 0);

const HC = require('highcharts/highstock');   // superset: chart + stockChart + candlestick
require('highcharts/highcharts-more');         // adds waterfall

const hydrate = (opts: any) => new Function(`${HELPERS_JS}\nreturn (${optionsToJs(opts)});`)();

let fail = 0;
for (const f of readdirSync(FX).filter((x) => x.endsWith('.json'))) {
  const name = basename(f, '.json');
  const data = JSON.parse(readFileSync(join(FX, f), 'utf8'));
  const useStock = !!data.meta?.stock;
  const opts = hydrate(buildOptions(data));
  const div = dom.window.document.createElement('div');
  dom.window.document.body.appendChild(div);
  const errs: string[] = [];
  const oErr = dom.window.console.error;
  dom.window.console.error = (...a: any[]) => errs.push('ERR:' + a.join(' '));
  try {
    (useStock ? HC.stockChart : HC.chart)(div, opts);
    const ok = !!div.querySelector('svg') && errs.length === 0;
    if (!ok) fail++;
    console.log(`${ok ? '✓' : '✗'} ${name.padEnd(30)} ${useStock ? 'stock' : 'core '} ${errs.join(' ') || ''}`);
  } catch (e: any) {
    fail++;
    console.log(`✗ ${name.padEnd(30)} THREW: ${e?.message ?? e}`);
  } finally {
    dom.window.console.error = oErr;
  }
}
console.log(fail ? `\n${fail} chart(s) FAILED to render` : '\nall charts render');
process.exit(fail ? 1 : 0);
