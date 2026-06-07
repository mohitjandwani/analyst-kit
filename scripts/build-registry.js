#!/usr/bin/env node
// Generate registry.json from skill frontmatter. With --check, verify the
// committed registry.json is in sync (for CI) instead of writing.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { buildRegistry } from '../src/registry.js';
import { REGISTRY_FILE } from '../src/paths.js';

const check = process.argv.includes('--check');
const registry = buildRegistry();
const json = JSON.stringify(registry, null, 2) + '\n';

if (check) {
  const current = existsSync(REGISTRY_FILE) ? readFileSync(REGISTRY_FILE, 'utf8') : '';
  if (current !== json) {
    console.error('✗ registry.json is out of date — run `npm run build:registry`');
    process.exit(1);
  }
  console.log('✓ registry.json is in sync');
} else {
  writeFileSync(REGISTRY_FILE, json);
  console.log(`✓ wrote registry.json (${registry.skills.length} skills, skipped: ${registry.skipped.join(', ') || 'none'})`);
}
