#!/usr/bin/env node
// Generate the skills routing table from frontmatter, then print it, write it
// to a file, or inject it idempotently into a common-prompt file (CLAUDE.md /
// AGENTS.md) between <!-- analyst-kit:skills:start/end --> markers.
//
//   node scripts/build-routing-table.js                                   # print (token <skills-dir>)
//   node scripts/build-routing-table.js --skills-dir ~/.claude/skills     # print with real load paths
//   node scripts/build-routing-table.js --inject ~/.claude/CLAUDE.md --skills-dir ~/.claude/skills
//   node scripts/build-routing-table.js --inject ./AGENTS.md --skills-dir ~/.codex/skills --check
//
// The installers call buildRoutingTable()/injectRoutingTable() directly with the
// adapter's resolved skills dir; this CLI is for manual use and CI checks.

import { writeFileSync } from 'node:fs';
import { getSkills } from '../src/registry.js';
import {
  buildRoutingTable, injectRoutingTable, routingTableInSync,
} from '../src/routing-table.js';

function arg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const skillsDir = arg('--skills-dir', '<skills-dir>');
const out = arg('--out');
const inject = arg('--inject');
const check = process.argv.includes('--check');
const includeLoad = !process.argv.includes('--no-path'); // --no-path: drop the Load column (e.g. Claude Cowork)

const block = buildRoutingTable(getSkills(), { skillsDir, includeLoad });

if (inject) {
  if (check) {
    if (routingTableInSync(inject, block)) {
      console.log(`✓ routing table in ${inject} is in sync`);
    } else {
      console.error(`✗ routing table in ${inject} is out of date — re-run --inject ${inject}`);
      process.exit(1);
    }
  } else {
    const changed = injectRoutingTable(inject, block);
    console.log(`${changed ? '✓ injected' : '= unchanged'} routing table → ${inject}`);
  }
} else if (out) {
  writeFileSync(out, block + '\n');
  console.log(`✓ wrote routing table → ${out}`);
} else {
  process.stdout.write(block + '\n');
}
