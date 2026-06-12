#!/usr/bin/env node
// Inject the hfa-core preamble/epilogue blocks into every shipped SKILL.md and
// stamp the root VERSION into everything that carries it (hfa-core/VERSION,
// plugin manifests, package.json). With --check, verify instead of writing (CI).
//
// The blocks live between <!-- hfa:preamble:start/end --> and
// <!-- hfa:epilogue:start/end --> markers; the source of truth is
// skills/hfa-core/templates/*.md.tmpl — never edit between markers by hand.

import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { scanSkills } from '../src/registry.js';
import { resolveClosure } from '../src/resolve.js';
import { ROOT, SKILLS_DIR, PLUGINS_DIR, VERSION_FILE } from '../src/paths.js';

const check = process.argv.includes('--check');
const stale = [];
let touched = 0;

const version = readFileSync(VERSION_FILE, 'utf8').trim();
const CORE = join(SKILLS_DIR, 'hfa-core');
const preTpl = readFileSync(join(CORE, 'templates', 'preamble.md.tmpl'), 'utf8').trim();
const epiTpl = readFileSync(join(CORE, 'templates', 'epilogue.md.tmpl'), 'utf8').trim();

const PRE = /<!-- hfa:preamble:start[\s\S]*?hfa:preamble:end -->/;
const EPI = /<!-- hfa:epilogue:start[\s\S]*?hfa:epilogue:end -->/;
const FM_CLOSE = /^---\n[\s\S]*?\n---[ \t]*\n/; // frontmatter open through closing ---

function emit(path, next, raw) {
  if (next === raw) return;
  if (check) stale.push(path.replace(ROOT + '/', ''));
  else { writeFileSync(path, next); touched += 1; }
}

// --- SKILL.md blocks -------------------------------------------------------
const { skills } = scanSkills(); // shipped skills only (EXCLUDED_SKILLS skipped)
for (const s of skills) {
  if (s.name === 'hfa-core') continue; // the runtime doesn't instrument itself
  // Union of env keys across the skill's full closure, so the preamble can
  // flag missing API keys even when the key belongs to a dependency.
  const envUnion = [...new Set(resolveClosure([s.name], skills).flatMap((d) => d.env))].sort();
  const envArg = envUnion.length ? ` --env ${envUnion.join(',')}` : '';
  const pre = preTpl.replaceAll('{{SKILL}}', s.name).replaceAll('{{ENV_ARG}}', envArg);
  const epi = epiTpl.replaceAll('{{SKILL}}', s.name);

  const path = join(s.dir, 'SKILL.md');
  const raw = readFileSync(path, 'utf8');
  let next = raw;

  if (PRE.test(next)) {
    next = next.replace(PRE, pre);
  } else {
    const m = next.match(FM_CLOSE);
    if (!m) {
      console.error(`✗ ${s.name}: cannot find frontmatter close — preamble not injected`);
      process.exitCode = 1;
      continue;
    }
    next = next.slice(0, m[0].length) + '\n' + pre + '\n' + next.slice(m[0].length);
  }
  next = EPI.test(next) ? next.replace(EPI, epi) : next.trimEnd() + '\n\n' + epi + '\n';
  emit(path, next, raw);
}

// --- VERSION propagation ---------------------------------------------------
const coreVer = join(CORE, 'VERSION');
emit(coreVer, version + '\n', existsSync(coreVer) ? readFileSync(coreVer, 'utf8') : '');

// Regex-replace the version field so the manifests keep their formatting.
function stampJson(path) {
  if (!existsSync(path)) return;
  const raw = readFileSync(path, 'utf8');
  emit(path, raw.replace(/"version":\s*"[^"]*"/, `"version": "${version}"`), raw);
}
for (const entry of readdirSync(PLUGINS_DIR, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  stampJson(join(PLUGINS_DIR, entry.name, '.claude-plugin', 'plugin.json'));
}
stampJson(join(ROOT, 'package.json'));

// --- report ----------------------------------------------------------------
if (check) {
  if (stale.length) {
    console.error(`✗ out of sync with templates/VERSION — run \`npm run sync:preamble\`:\n  ${stale.join('\n  ')}`);
    process.exit(1);
  }
  console.log('✓ preamble blocks and version stamps are in sync');
} else {
  console.log(`✓ synced preamble/epilogue + version ${version} (${touched} file${touched === 1 ? '' : 's'} updated)`);
}
