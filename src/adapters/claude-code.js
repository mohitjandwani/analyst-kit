import { homedir } from 'node:os';
import nodePath from 'node:path';
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
      : path.join(home, '.hfa', '.env');
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
};
