import { claudeCode } from './claude-code.js';
import { codex } from './codex.js';
import { openclaw } from './openclaw.js';

const ADAPTERS = {
  'claude-code': claudeCode,
  codex,
  openclaw,
};

export const PLATFORMS = Object.keys(ADAPTERS);

export function getAdapter(platform) {
  const a = ADAPTERS[platform];
  if (!a) {
    throw new Error(`unknown platform "${platform}". Supported: ${PLATFORMS.join(', ')}`);
  }
  return a;
}
