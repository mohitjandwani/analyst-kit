#!/usr/bin/env node
// Materialize the self-contained `analyst-kit` plugin bundle.
//
// WHY THIS EXISTS: Claude Code / Cowork install a marketplace plugin into an
// ISOLATED per-plugin cache — only files UNDER the plugin directory are copied,
// and `../..` references out of the plugin root break after install. So the
// plugin cannot point at the top-level skills/ tree; it must carry its own copy.
//
// Top-level skills/ stays the single source of truth (the Node installer and the
// registry scan it). This script regenerates plugins/analyst-kit/skills/ from the
// shipped closure so the two never drift — exactly like registry.json. The
// plugin's agents/, hooks/, and .claude-plugin/ are hand-authored and left alone.
//
//   node scripts/build-plugin.js            # rebuild the bundled skills/
//   node scripts/build-plugin.js --check    # CI: fail if the bundle is stale

import {
  mkdtempSync, rmSync, mkdirSync, readdirSync, readFileSync, statSync,
} from 'node:fs';
import { join, relative } from 'node:path';
import { tmpdir } from 'node:os';
import { scanSkills } from '../src/registry.js';
import { copyTree } from '../src/adapters/copy.js';
import { PLUGINS_DIR, EXCLUDED_SKILLS } from '../src/paths.js';

const check = process.argv.includes('--check');
const BUNDLE_DIR = join(PLUGINS_DIR, 'analyst-kit');
const BUNDLE_SKILLS = join(BUNDLE_DIR, 'skills');

// The bundle ships every shipped skill (EXCLUDED_SKILLS are already dropped by
// scanSkills). Since the plugin is the whole kit, the closure is the full set.
const { skills, skipped } = scanSkills();
const shippable = skills.filter((s) => !EXCLUDED_SKILLS.has(s.folder));

function buildInto(skillsDir) {
  rmSync(skillsDir, { recursive: true, force: true });
  mkdirSync(skillsDir, { recursive: true });
  for (const s of shippable) copyTree(s.dir, join(skillsDir, s.folder));
}

// Flatten a tree into a sorted [relpath, contents] map for order-independent diff.
function snapshot(root) {
  const out = new Map();
  const walk = (dir) => {
    if (!safeExists(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const p = join(dir, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.isFile()) out.set(relative(root, p), readFileSync(p));
    }
  };
  walk(root);
  return out;
}

function safeExists(p) {
  try { statSync(p); return true; } catch { return false; }
}

if (check) {
  const tmp = mkdtempSync(join(tmpdir(), 'ak-plugin-'));
  try {
    buildInto(tmp);
    const want = snapshot(tmp);
    const have = snapshot(BUNDLE_SKILLS);
    const diffs = [];
    for (const [rel, buf] of want) {
      if (!have.has(rel)) diffs.push(`missing:  ${rel}`);
      else if (!have.get(rel).equals(buf)) diffs.push(`changed:  ${rel}`);
    }
    for (const rel of have.keys()) if (!want.has(rel)) diffs.push(`stale:    ${rel}`);
    if (diffs.length) {
      console.error(`✗ plugins/analyst-kit/skills is out of date — run \`npm run build:plugin\`:`);
      for (const d of diffs.slice(0, 40)) console.error(`  • ${d}`);
      if (diffs.length > 40) console.error(`  • …and ${diffs.length - 40} more`);
      process.exit(1);
    }
    console.log(`✓ plugins/analyst-kit/skills is in sync (${shippable.length} skills)`);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
} else {
  buildInto(BUNDLE_SKILLS);
  console.log(
    `✓ built plugins/analyst-kit/skills — ${shippable.length} skills`
    + (skipped.length ? ` (excluded: ${skipped.map((s) => s.name).join(', ')})` : ''),
  );
}
