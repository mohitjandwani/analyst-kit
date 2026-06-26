#!/usr/bin/env node
/**
 * Universal render launcher: contract.json -> self-contained chart HTML, with ZERO
 * setup on any machine that has `node` (which every Claude Code / Cowork / Desktop
 * runtime does — the agent harness itself is node). This is THE command to run:
 *
 *   node scripts/render.mjs <contract.json> <out.html> [--cdn]
 *
 * It picks the best available TypeScript runtime, in order:
 *   1. bun  (if installed)  -> bun scripts/render.ts ...     (fastest, the tested path)
 *   2. tsx  (if installed)  -> tsx scripts/render.ts ...
 *   3. node (>= 22.18)      -> strip types in-process via ts-resolve.mjs   (no install)
 *   4. else                 -> install bun once, then run under it
 *
 * Default output INLINES the vendored Highcharts, so the page is self-contained and
 * renders from file:// or in a headless PDF with no network. `--cdn` emits <script src>
 * tags instead and ONLY works when the page is served over http(s) — opening a --cdn
 * page from file:// yields a blank chart ("Highcharts is not defined").
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url)); // .../charting/scripts
const skillRoot = dirname(here); // .../charting
const renderTs = join(here, 'render.ts'); // bun/tsx entry point
const loader = join(here, 'ts-resolve.mjs');

const argv = process.argv.slice(2);
const [inPath, outPath] = argv.filter((a) => !a.startsWith('--'));
const cdn = argv.includes('--cdn');
if (!inPath || !outPath) {
  console.error('usage: node scripts/render.mjs <contract.json> <out.html> [--cdn]');
  process.exit(2);
}
// Resolve I/O against the caller's cwd so the paths survive being handed to a subprocess
// (which may run with a different cwd) and the node-native branch alike.
const inAbs = resolvePath(process.cwd(), inPath);
const outAbs = resolvePath(process.cwd(), outPath);
const tsArgs = [renderTs, inAbs, outAbs, ...(cdn ? ['--cdn'] : [])];

/** True if `bin --version` runs (ENOENT -> not on PATH). */
function have(bin) {
  return !spawnSync(bin, ['--version'], { stdio: 'ignore' }).error;
}
function runWith(bin, args) {
  const r = spawnSync(bin, args, { stdio: 'inherit' });
  return r.status ?? (r.error ? 1 : 0);
}

// 1. bun — the documented, fastest path.
if (have('bun')) process.exit(runWith('bun', tsArgs));

// 2. tsx — global on PATH, or the skill's local node_modules/.bin (dev checkout).
const localTsx = join(skillRoot, 'node_modules', '.bin', 'tsx');
if (have('tsx')) process.exit(runWith('tsx', tsArgs));
if (existsSync(localTsx)) process.exit(runWith(localTsx, tsArgs));

// 3. node in-process — no install. Needs type stripping (Node >= 22.18, or 22.6 w/ flag).
if (process.features.typescript) {
  const { register } = await import('node:module');
  register(pathToFileURL(loader).href); // map nested `.js` imports -> `.ts`
  const { renderChartPage } = await import(pathToFileURL(join(skillRoot, 'src', 'index.ts')).href);
  const contract = JSON.parse(readFileSync(inAbs, 'utf8'));
  const html = renderChartPage(contract, { cdnScripts: cdn });
  writeFileSync(outAbs, html);
  console.log(`wrote ${outAbs} (${Math.round(html.length / 1024)} KB)`);
  process.exit(0);
}

// 4. Last resort — no bun/tsx and this node can't strip types. Install bun, then run.
console.error('charting: no bun/tsx found and this Node cannot strip TypeScript — installing bun…');
const installed = spawnSync('bash', ['-lc', 'curl -fsSL https://bun.sh/install | bash'], {
  stdio: 'inherit',
});
const bunBin = join(homedir(), '.bun', 'bin', 'bun');
if (installed.status === 0 && existsSync(bunBin)) {
  process.exit(runWith(bunBin, tsArgs));
}
console.error(
  'charting: could not obtain a TypeScript runtime.\n' +
    '  Install bun (https://bun.sh) or upgrade Node to >= 22.18, then re-run.',
);
process.exit(1);
