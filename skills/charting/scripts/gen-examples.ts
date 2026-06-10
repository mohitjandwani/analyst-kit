/** Render every processed fixture to a self-contained HTML page in examples/. */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { renderChartPage } from '../src/render.js';
import type { FinalData } from '../src/types.js';

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = join(here, '..');
const FX = join(ROOT, 'tests', 'contracts');
const OUT = join(ROOT, 'examples');

mkdirSync(OUT, { recursive: true });
for (const f of readdirSync(FX).filter((x) => x.endsWith('.json'))) {
  const data = JSON.parse(readFileSync(join(FX, f), 'utf8')) as FinalData;
  const name = basename(f, '.json') + '.html';
  writeFileSync(join(OUT, name), renderChartPage(data, { cdnScripts: true }));
  console.log('wrote examples/' + name);
}
