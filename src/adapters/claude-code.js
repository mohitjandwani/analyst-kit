import { homedir } from 'node:os';
import { join } from 'node:path';
import { copyTree } from './copy.js';

// Claude Code: skills are folders under ~/.claude/skills (user) or
// .claude/skills (project). SKILL.md is the native format — copy source as-is.
export const claudeCode = {
  id: 'claude-code',

  installDir(scope) {
    return scope === 'project'
      ? join(process.cwd(), '.claude', 'skills')
      : join(homedir(), '.claude', 'skills');
  },

  envFile(scope) {
    return scope === 'project'
      ? join(process.cwd(), '.env')
      : join(homedir(), '.hfa', '.env');
  },

  write(skill, scope) {
    const dest = join(this.installDir(scope), skill.folder);
    copyTree(skill.dir, dest);
    return dest;
  },
};
