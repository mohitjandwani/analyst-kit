import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { parseFrontmatter } from './frontmatter.js';
import {
  SKILLS_DIR, REGISTRY_FILE, EXCLUDED_SKILLS, NON_SKILL_ENTRIES,
} from './paths.js';

function detectRuntime(dir) {
  if (existsSync(join(dir, 'package.json'))) return 'bun';
  const scripts = join(dir, 'scripts');
  if (existsSync(scripts)) {
    try {
      if (readdirSync(scripts).some((f) => f.endsWith('.py'))) return 'python';
    } catch { /* ignore */ }
  }
  return 'none';
}

// Scan skills/ and build skill records straight from frontmatter.
// Returns { skills: [...], issues: [...] } so callers (CLI vs validator) decide
// how strict to be. EXCLUDED_SKILLS are reported in `skipped`, not `skills`.
export function scanSkills() {
  const skills = [];
  const issues = [];
  const skipped = [];

  let entries = [];
  try {
    entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
  } catch (e) {
    return { skills, issues: [`cannot read skills dir: ${e.message}`], skipped };
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (NON_SKILL_ENTRIES.has(entry.name)) continue;
    const dir = join(SKILLS_DIR, entry.name);
    const skillMd = join(dir, 'SKILL.md');

    if (EXCLUDED_SKILLS.has(entry.name)) {
      skipped.push({ name: entry.name, reason: 'excluded (work-in-progress)' });
      continue;
    }
    if (!existsSync(skillMd)) {
      issues.push({ skill: entry.name, error: 'missing SKILL.md' });
      continue;
    }

    const raw = readFileSync(skillMd, 'utf8');
    const { data, body } = parseFrontmatter(raw);
    if (!data) {
      issues.push({ skill: entry.name, error: 'missing or malformed frontmatter' });
      continue;
    }
    skills.push({
      name: data.name,
      folder: entry.name,
      type: data.type,
      description: data.description || '',
      requires: Array.isArray(data.requires) ? data.requires : [],
      env: Array.isArray(data.env) ? data.env : [],
      runtime: detectRuntime(dir),
      bodyLength: (body || '').trim().length,
      dir,
    });
  }
  return { skills, issues, skipped };
}

// Build the serializable registry object (the artifact written to registry.json).
export function buildRegistry() {
  const { skills, skipped } = scanSkills();
  return {
    generated: 'run `npm run build:registry` to refresh',
    skills: skills
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(({ dir, bodyLength, ...rest }) => rest),
    skipped: skipped.map((s) => s.name).sort(),
  };
}

// Load skills for the CLI. Scan the live skills/ tree FIRST so the CLI always
// reflects what's actually on disk (registry.json is a generated artifact that
// can lag behind edits/deletions). Fall back to registry.json only if a live
// scan isn't possible (e.g. skills/ missing from a stripped install).
export function getSkills() {
  const scanned = scanSkills();
  if (scanned.skills.length) return scanned.skills;
  if (existsSync(REGISTRY_FILE)) {
    try {
      const reg = JSON.parse(readFileSync(REGISTRY_FILE, 'utf8'));
      if (Array.isArray(reg.skills) && reg.skills.length) {
        return reg.skills.map((s) => ({ ...s, dir: join(SKILLS_DIR, s.folder) }));
      }
    } catch { /* ignore */ }
  }
  return scanned.skills;
}

export function skillByName(name, skills = getSkills()) {
  return skills.find((s) => s.name === name || s.folder === name) || null;
}
