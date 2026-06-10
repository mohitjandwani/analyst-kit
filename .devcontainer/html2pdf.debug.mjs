// html2pdf.debug.mjs — Phase-1 diagnostic wrapper.
// Usage: node html2pdf.debug.mjs <input.html> [output.pdf]
// Emits every network failure, JS error, and console message from the page,
// then probes whether Highcharts loaded and whether the chart rendered.
// Does NOT write a PDF unless an output path is given (useful for pure diagnostics).
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [input, output] = process.argv.slice(2);
if (!input) { console.error('usage: node html2pdf.debug.mjs <input.html> [output.pdf]'); process.exit(2); }

const url = /^https?:\/\//.test(input) ? input : pathToFileURL(resolve(input)).href;
console.error('[debug] loading:', url);

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const page = await browser.newPage();

const requestsFailed = [];
const errors = [];

// Network failures — the single most informative signal for CDN-blocking.
// The errorText contains the exact Chromium net error (ERR_CERT_AUTHORITY_INVALID,
// ERR_BLOCKED_BY_CLIENT, ERR_NAME_NOT_RESOLVED, ERR_CONNECTION_REFUSED, etc.).
page.on('requestfailed', r => {
  const entry = `${r.url().slice(0, 120)} :: ${r.failure()?.errorText}`;
  requestsFailed.push(entry);
  console.error('[requestfailed]', entry);
});

// Non-2xx HTTP responses (e.g. 403 from a proxy, 407 Proxy Auth Required).
page.on('response', r => {
  if (!r.ok() && r.status() !== 0) {
    console.error(`[http ${r.status()}] ${r.url().slice(0, 120)}`);
  }
});

// JS errors thrown in the page — catches "Highcharts is not defined" etc.
page.on('pageerror', e => {
  errors.push(e.message);
  console.error('[pageerror]', e.message);
});

// console.log/warn/error from the page itself.
page.on('console', m => console.error(`[console.${m.type()}] ${m.text()}`));

await page.goto(url, { waitUntil: 'networkidle', timeout: 60_000 }).catch(e => {
  console.error('[goto error]', e.message);
});

// Active probes — the two questions we actually need answered.
const hcType  = await page.evaluate(() => typeof window.Highcharts).catch(() => 'eval-error');
const svgCount = await page.evaluate(() => document.querySelectorAll('#c svg').length).catch(() => -1);
const hcVer   = await page.evaluate(() => window.Highcharts?.version ?? null).catch(() => null);

console.error('[probe] typeof Highcharts =', hcType, hcVer ? `(v${hcVer})` : '');
console.error('[probe] #c svg count      =', svgCount);

if (output) {
  await page.pdf({
    path: output, printBackground: true, format: 'A4',
    margin: { top: '12mm', bottom: '12mm', left: '12mm', right: '12mm' },
  });
  console.error('[debug] wrote', output);
}

await browser.close();

// Exit non-zero if we know the chart is broken.
const broken = requestsFailed.length > 0 || errors.length > 0 || svgCount === 0;
process.exit(broken ? 1 : 0);
