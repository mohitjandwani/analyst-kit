import { homedir } from 'node:os';
import nodePath from 'node:path';
import { copyTree } from './copy.js';

// OpenClaw (openclaw.ai) consumes SKILL.md folders natively — it discovers any
// SKILL.md under a configured root and compiles them into the system prompt — so
// installing is a tree copy, like Claude Code. Targets:
//   user    → ~/.openclaw/skills        (managed/global, like `openclaw skills install --global`)
//   project → ./.openclaw/skills
// The common-prompt file is the workspace AGENTS.md, loaded every session.
//
// installDir/envFile/commonPromptFile take an optional { home, cwd, path } so tests
// can assert the Windows layout from any OS; real callers get the live values.
export const openclaw = {
  id: 'openclaw',

  installDir(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, '.openclaw', 'skills')
      : path.join(home, '.openclaw', 'skills');
  },

  envFile(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    // OpenClaw doesn't read ~/.hfa/.env natively; this is just where hfa records keys.
    return scope === 'project'
      ? path.join(cwd, '.env')
      : path.join(home, '.openclaw', '.env');
  },

  commonPromptFile(scope, { home = homedir(), cwd = process.cwd(), path = nodePath } = {}) {
    return scope === 'project'
      ? path.join(cwd, 'AGENTS.md')
      : path.join(home, '.openclaw', 'workspace', 'AGENTS.md');
  },

  write(skill, scope) {
    const dest = nodePath.join(this.installDir(scope), skill.folder);
    copyTree(skill.dir, dest);
    return dest;
  },
};
