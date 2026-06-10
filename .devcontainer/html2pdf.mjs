// html2pdf <input.html|url> <output.pdf>
// Renders HTML to a PDF with headless Chromium (Playwright). Installed in the image as the
// `html2pdf` CLI on PATH so the agent has a dead-simple, reliable HTML->PDF path.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: html2pdf <input.html|url> <output.pdf>');
  process.exit(2);
}

const url = /^https?:\/\//.test(input) ? input : pathToFileURL(resolve(input)).href;

// --no-sandbox: Chromium's sandbox needs privileges we don't grant a non-root container user.
const browser = await chromium.launch({ args: ['--no-sandbox'] });
let exitCode = 0;
try {
  const page = await browser.newPage();

  // Surface network failures, JS errors, and non-2xx responses so a blank chart
  // is a loud error rather than a silent valid-looking PDF.
  page.on('requestfailed', (r) => {
    console.error(`[html2pdf] network fail: ${r.url()} :: ${r.failure()?.errorText}`);
    exitCode = 1;
  });
  page.on('response', (r) => {
    if (!r.ok() && r.status() !== 0)
      console.error(`[html2pdf] HTTP ${r.status()}: ${r.url()}`);
  });
  page.on('pageerror', (e) => {
    console.error(`[html2pdf] page error: ${e.message}`);
    exitCode = 1;
  });

  await page.goto(url, { waitUntil: 'networkidle', timeout: 60_000 });

  // Warn when a #c div (Highcharts mount) has no SVG — chart failed to draw.
  const emptySvg = await page.evaluate(() => {
    const c = document.getElementById('c');
    return c && c.querySelectorAll('svg').length === 0;
  });
  if (emptySvg) {
    console.error('[html2pdf] warning: #c has no SVG — chart did not render');
    exitCode = 1;
  }

  await page.pdf({
    path: output,
    printBackground: true,
    format: 'A4',
    margin: { top: '12mm', bottom: '12mm', left: '12mm', right: '12mm' },
  });
  console.error(`html2pdf: wrote ${output}`);
} finally {
  await browser.close();
}
process.exit(exitCode);
