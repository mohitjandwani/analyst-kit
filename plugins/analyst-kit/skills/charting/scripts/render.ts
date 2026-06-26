#!/usr/bin/env bun
/**
 * Contract → finished chart page (bun/tsx entry) — so an agent never hand-writes
 * Highcharts HTML/CSS/JS boilerplate:
 *
 *   bun scripts/render.ts contract.json chart.html         # vendored Highcharts inlined (offline/PDF-safe)
 *   bun scripts/render.ts contract.json chart.html --cdn   # lightweight CDN page for browser preview
 *
 * Prefer `node scripts/render.mjs <contract.json> <out.html> [--cdn]` — the universal
 * launcher that runs on plain node (no bun/tsx install needed) and falls back to this
 * file when bun/tsx is present. No npm install needed: src/ uses only node builtins and
 * the vendored Highcharts files, both of which survive skill installation.
 */
import { readFileSync, writeFileSync } from 'node:fs';

import { renderChartPage } from '../src/index.js';

const args = process.argv.slice(2);
const [inPath, outPath] = args.filter((a) => !a.startsWith('--'));
if (!inPath || !outPath) {
  console.error('usage: bun scripts/render.ts <contract.json> <out.html> [--cdn]');
  process.exit(2);
}
const contract = JSON.parse(readFileSync(inPath, 'utf8'));
const html = renderChartPage(contract, { cdnScripts: args.includes('--cdn') });
writeFileSync(outPath, html);
console.log(`wrote ${outPath} (${Math.round(html.length / 1024)} KB)`);
