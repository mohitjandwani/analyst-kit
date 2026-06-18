#!/usr/bin/env node
// Skill + packaging linter. Enforces the house contract (CLAUDE.md "Skill contract")
// so the repo stays installable. Exits non-zero on any error.

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { join, basename } from 'node:path';
import { execSync } from 'node:child_process';
import { scanSkills } from '../src/registry.js';
import { listPersonas } from '../src/resolve.js';
import { parseEnvFile } from '../src/env.js';
import {
  SKILLS_DIR, PLUGINS_DIR, ENV_EXAMPLE, EXCLUDED_SKILLS,
} from '../src/paths.js';

const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

const { skills, issues, skipped } = scanSkills();
for (const i of issues) err(`[${i.skill}] ${i.error}`);

const byName = new Map(skills.map((s) => [s.name, s]));
const declaredEnv = new Set(Object.keys(parseEnvFile(ENV_EXAMPLE)));

// Per-skill checks
for (const s of skills) {
  if (s.name !== s.folder) err(`[${s.folder}] name "${s.name}" must equal folder name`);
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(s.name)) err(`[${s.name}] name must be kebab-case`);
  if (s.type !== 'capability' && s.type !== 'workflow') err(`[${s.name}] type must be capability|workflow (got "${s.type}")`);
  if (!s.description || s.description.length < 40) err(`[${s.name}] description too short`);
  if (!/Triggers:/.test(s.description)) err(`[${s.name}] description must contain a "Triggers:" clause`);
  if (s.bodyLength === 0) err(`[${s.name}] SKILL.md has an empty body`);

  for (const dep of s.requires) {
    const d = byName.get(dep);
    if (!d) err(`[${s.name}] requires "${dep}" which does not exist`);
    else if (d.type !== 'capability') err(`[${s.name}] requires "${dep}" but it is a ${d.type} (nothing may require a workflow)`);
  }
  for (const v of s.env) {
    if (!declaredEnv.has(v)) err(`[${s.name}] env var ${v} not declared in .env.example`);
  }
}

// hfa-core's onboarding wizard prompts for keys at runtime using a SHIPPED
// catalog (references/api-keys.tsv) — the root .env.example does not travel with
// an installed skill. Enforce that every key any skill declares in env: has a
// catalog row, so the wizard can always describe what it asks for (this is what
// keeps the two key sources from drifting).
const KEYS_TSV = join(SKILLS_DIR, 'hfa-core', 'references', 'api-keys.tsv');
if (!existsSync(KEYS_TSV)) {
  err('[hfa-core] references/api-keys.tsv missing — the setup wizard has no key catalog');
} else {
  const catalog = new Set(
    readFileSync(KEYS_TSV, 'utf8')
      .split('\n')
      .filter((l) => l.trim() && !l.startsWith('#'))
      .map((l) => l.split('\t')[0].trim())
      .filter(Boolean),
  );
  const usedEnv = new Set(skills.flatMap((s) => s.env));
  for (const k of usedEnv) {
    if (!catalog.has(k)) err(`[hfa-core] api-keys.tsv has no row for "${k}" (a skill declares it in env:) — the setup wizard can't describe it`);
  }
}

// Cycle check — load-bearing: capabilities may require capabilities, so a
// requires chain (e.g. reporting → charting) could loop without this.
function hasCycle() {
  const state = new Map();
  const visit = (name, trail) => {
    if (state.get(name) === 'done') return false;
    if (state.get(name) === 'open') { err(`dependency cycle: ${[...trail, name].join(' → ')}`); return true; }
    const s = byName.get(name); if (!s) return false;
    state.set(name, 'open');
    for (const dep of s.requires) if (visit(dep, [...trail, name])) return true;
    state.set(name, 'done');
    return false;
  };
  for (const s of skills) visit(s.name, []);
}
hasCycle();

// No stray SKILL.md directly under skills/
if (existsSync(join(SKILLS_DIR, 'SKILL.md'))) err('stray skills/SKILL.md must be removed');

// No vendored dirs tracked by git
try {
  const tracked = execSync('git ls-files', { cwd: join(SKILLS_DIR, '..'), encoding: 'utf8' });
  for (const line of tracked.split('\n')) {
    if (/(^|\/)(node_modules|__pycache__|\.venv)\//.test(line)) err(`vendored path tracked by git: ${line}`);
  }
} catch { warn('git not available — skipped vendored-path check'); }

// Plugin manifests reference existing, valid skills
for (const entry of (existsSync(PLUGINS_DIR) ? readdirSync(PLUGINS_DIR, { withFileTypes: true }) : [])) {
  if (!entry.isDirectory()) continue;
  const manifest = join(PLUGINS_DIR, entry.name, '.claude-plugin', 'plugin.json');
  if (!existsSync(manifest)) { err(`[plugin ${entry.name}] missing .claude-plugin/plugin.json`); continue; }
  let data;
  try { data = JSON.parse(readFileSync(manifest, 'utf8')); }
  catch (e) { err(`[plugin ${entry.name}] invalid JSON: ${e.message}`); continue; }
  for (const p of data.skills || []) {
    const name = basename(p);
    if (EXCLUDED_SKILLS.has(name)) err(`[plugin ${entry.name}] references excluded skill "${name}"`);
    else if (!byName.has(name)) err(`[plugin ${entry.name}] references unknown skill "${name}"`);
  }
  // closure completeness: every required capability must be present in the plugin
  const present = new Set((data.skills || []).map((p) => basename(p)));
  for (const sn of present) {
    const s = byName.get(sn);
    if (!s) continue;
    for (const dep of s.requires) {
      if (!present.has(dep)) err(`[plugin ${entry.name}] includes "${sn}" but is missing its dependency "${dep}"`);
    }
  }
}

// Personas sanity (uses the same manifests)
if (!listPersonas().length) warn('no personas found under plugins/');

// Report
console.log(`\nValidated ${skills.length} skill(s); skipped ${skipped.length} (${skipped.map((s) => s.name).join(', ') || 'none'}).`);
for (const w of warnings) console.log(`  ⚠ ${w}`);
if (errors.length) {
  console.error(`\n✗ ${errors.length} error(s):`);
  for (const e of errors) console.error(`  • ${e}`);
  process.exit(1);
}
console.log('✓ all checks passed\n');
