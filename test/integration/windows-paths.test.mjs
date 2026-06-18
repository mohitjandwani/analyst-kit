// Path-layer portability: assert the REAL adapters build correct paths under
// path.win32 from any OS (injecting a Windows homedir/cwd). This is what lets
// WSL2 (Linux) Just Work; Windows itself is supported via WSL2, not natively.
// Exercises the actual adapter code (not a copy of its logic) — see src/adapters/*.js.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import nodePath from 'node:path';
import { claudeCode } from '../../src/adapters/claude-code.js';
import { codex } from '../../src/adapters/codex.js';
import { openclaw } from '../../src/adapters/openclaw.js';

// Simulated Windows environment: %USERPROFILE% + project cwd + win32 separators.
const win = { home: 'C:\\Users\\analyst', cwd: 'C:\\proj', path: nodePath.win32 };

// --- skills directories -------------------------------------------------------
test('claude-code · user skills → %USERPROFILE%\\.claude\\skills', () => {
  assert.equal(claudeCode.installDir('user', win), 'C:\\Users\\analyst\\.claude\\skills');
});
test('claude-code · project skills → <cwd>\\.claude\\skills', () => {
  assert.equal(claudeCode.installDir('project', win), 'C:\\proj\\.claude\\skills');
});
test('codex · user skills → %USERPROFILE%\\.codex\\skills', () => {
  assert.equal(codex.installDir('user', win), 'C:\\Users\\analyst\\.codex\\skills');
});
test('codex · project skills → <cwd>\\.codex\\skills', () => {
  assert.equal(codex.installDir('project', win), 'C:\\proj\\.codex\\skills');
});
test('openclaw · user skills → %USERPROFILE%\\.openclaw\\skills', () => {
  assert.equal(openclaw.installDir('user', win), 'C:\\Users\\analyst\\.openclaw\\skills');
});
test('openclaw · project skills → <cwd>\\.openclaw\\skills', () => {
  assert.equal(openclaw.installDir('project', win), 'C:\\proj\\.openclaw\\skills');
});

// --- env files ----------------------------------------------------------------
test('claude-code · user env → %USERPROFILE%\\.hfa\\.env', () => {
  assert.equal(claudeCode.envFile('user', win), 'C:\\Users\\analyst\\.hfa\\.env');
});
test('codex · user env → %USERPROFILE%\\.codex\\.env', () => {
  assert.equal(codex.envFile('user', win), 'C:\\Users\\analyst\\.codex\\.env');
});
test('openclaw · user env → %USERPROFILE%\\.openclaw\\.env', () => {
  assert.equal(openclaw.envFile('user', win), 'C:\\Users\\analyst\\.openclaw\\.env');
});

// --- common-prompt file (where the routing table is injected) -----------------
test('claude-code · common prompt = %USERPROFILE%\\.claude\\CLAUDE.md', () => {
  assert.equal(claudeCode.commonPromptFile('user', win), 'C:\\Users\\analyst\\.claude\\CLAUDE.md');
});
test('codex · common prompt = %USERPROFILE%\\.codex\\AGENTS.md', () => {
  assert.equal(codex.commonPromptFile('user', win), 'C:\\Users\\analyst\\.codex\\AGENTS.md');
});
test('codex · project common prompt = <cwd>\\AGENTS.md', () => {
  assert.equal(codex.commonPromptFile('project', win), 'C:\\proj\\AGENTS.md');
});
test('openclaw · common prompt = %USERPROFILE%\\.openclaw\\workspace\\AGENTS.md', () => {
  assert.equal(openclaw.commonPromptFile('user', win), 'C:\\Users\\analyst\\.openclaw\\workspace\\AGENTS.md');
});

// --- backward-compat: defaults still resolve on the host OS -------------------
test('defaults still resolve on the host OS', () => {
  const d = claudeCode.installDir('user');
  assert.ok(d.includes('.claude') && d.includes('skills') && nodePath.isAbsolute(d));
});
