import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { FinalData } from '../src/types.js';

const here = dirname(fileURLToPath(import.meta.url));
const FX = join(here, 'contracts');

/** Load a committed chart contract (the data layer's output). */
export function fixture(name: string): FinalData {
  return JSON.parse(readFileSync(join(FX, `${name}.json`), 'utf8'));
}

export const FIXTURE_NAMES = [
  'revenue_margins', 'revenue_trend', 'revenue_yoy', 'compare_rebased',
  'segments_stacked', 'segments_percent', 'segments_grouped', 'waterfall',
  'dividend_yield', 'surprise_eps', 'estimate_vs_reported_revenue',
  'estimate_vs_reported_eps', 'price_candlestick', 'price_with_revenue',
  'price_revenue_reaction', 'price_revenue_growth', 'compare_price_rebased',
];
