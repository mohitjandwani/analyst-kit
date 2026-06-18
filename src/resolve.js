import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { PLUGINS_DIR } from './paths.js';
import { getSkills, skillByName } from './registry.js';

// Walk the `requires` graph from one or more roots and return the full set of
// skills to install (dependencies included), ordered dependencies-first.
// Throws on an unknown skill or a dependency cycle.
export function resolveClosure(rootNames, skills = getSkills()) {
  const ordered = [];
  const seen = new Set();
  const inStack = new Set();

  const visit = (name, trail) => {
    const skill = skillByName(name, skills);
    if (!skill) {
      throw new Error(`unknown skill "${name}"${trail.length ? ` (required by ${trail[trail.length - 1]})` : ''}`);
    }
    if (seen.has(skill.name)) return;
    if (inStack.has(skill.name)) {
      throw new Error(`dependency cycle: ${[...trail, skill.name].join(' → ')}`);
    }
    inStack.add(skill.name);
    for (const dep of skill.requires) visit(dep, [...trail, skill.name]);
    inStack.delete(skill.name);
    seen.add(skill.name);
    ordered.push(skill);
  };

  for (const name of rootNames) visit(name, []);
  return ordered;
}

// Personas are defined by the persona plugin manifests (single source of truth).
export function listPersonas() {
  if (!existsSync(PLUGINS_DIR)) return [];
  const out = [];
  for (const entry of readdirSync(PLUGINS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const manifest = join(PLUGINS_DIR, entry.name, '.claude-plugin', 'plugin.json');
    if (!existsSync(manifest)) continue;
    try {
      const data = JSON.parse(readFileSync(manifest, 'utf8'));
      out.push({
        name: data.name || entry.name,
        description: data.description || '',
        skills: (data.skills || []).map((p) => basename(p)),
      });
    } catch { /* skip malformed manifest */ }
  }
  return out;
}

export function personaByName(name) {
  return listPersonas().find((p) => p.name === name) || null;
}

// Resolve a target into a closure. `all` installs every shipped skill; otherwise
// the target may be a persona name or a single skill name.
export function resolveTarget(name, skills = getSkills()) {
  if (name === 'all') return resolveClosure(skills.map((s) => s.name), skills);
  const persona = personaByName(name);
  if (persona) return resolveClosure(persona.skills, skills);
  return resolveClosure([name], skills);
}
