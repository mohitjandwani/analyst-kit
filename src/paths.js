import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// Repo/package root is the parent of src/.
export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const SKILLS_DIR = join(ROOT, 'skills');
export const PLUGINS_DIR = join(ROOT, 'plugins');
export const REGISTRY_FILE = join(ROOT, 'registry.json');
export const ENV_EXAMPLE = join(ROOT, '.env.example');

// Skills intentionally excluded from the shippable registry/plugins
// (e.g. work-in-progress with an empty SKILL.md). The validator reports these
// as skipped rather than failing the build.
export const EXCLUDED_SKILLS = new Set();

// Non-skill entries that live under skills/ but are not skill folders.
export const NON_SKILL_ENTRIES = new Set([
  'README.md',
  '.skill-schema.json',
]);
