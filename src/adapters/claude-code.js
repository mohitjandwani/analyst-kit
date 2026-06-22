import { homedir } from 'node:os';
import nodePath from 'node:path';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { copyTree } from './copy.js';

// Claude Code consumes SKILL.md folders natively, so installing is just a tree
// copy into its skills dir (~/.claude/skills, or ./.claude/skills for a project).
//
// installDir/envFile take an optional { home, cwd, path } so tests can assert the
// Windows layout from any OS (pass path: require('node:path').win32). Real callers
// pass nothing and get the live homedir()/cwd()/platform path module.
export const claudeCode = {
  id: 'claude-code',

  installDir(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, '.claude', 'skills')
      : path.join(home, '.claude', 'skills');
  },

  envFile(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, '.env')
      : path.join(home, '.analyst-kit', '.env');
  },

  commonPromptFile(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, 'CLAUDE.md')
      : path.join(home, '.claude', 'CLAUDE.md');
  },

  write(skill, scope) {
    const dest = nodePath.join(this.installDir(scope), skill.folder);
    copyTree(skill.dir, dest);
    return dest;
  },

  settingsFile(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, '.claude', 'settings.json')
      : path.join(home, '.claude', 'settings.json');
  },

  // Merge WebSearch + WebFetch into permissions.allow so agents never prompt for
  // these during skill execution. Safe to call repeatedly — deduplicates the list.
  upsertPermissions(scope) {
    const file = this.settingsFile(scope);
    let settings = {};
    try { settings = JSON.parse(readFileSync(file, 'utf8')); } catch {}
    const existing = Array.isArray(settings?.permissions?.allow) ? settings.permissions.allow : [];
    const toAdd = ['WebSearch', 'WebFetch'];
    const merged = [...new Set([...existing, ...toAdd])];
    if (merged.length === existing.length) return { file, changed: false };
    settings.permissions = { ...settings.permissions, allow: merged };
    mkdirSync(nodePath.dirname(file), { recursive: true });
    writeFileSync(file, JSON.stringify(settings, null, 2) + '\n');
    return { file, changed: true };
  },
};
