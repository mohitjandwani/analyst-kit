// Real end-to-end installs on the host OS (Linux in the devcontainer): run the
// actual `bin/hfa.js install` into throwaway project dirs and assert (a) the skill
// + its closure land where the adapter says, (b) the codex slash-prompt bridge is
// generated, and (c) the routing table is injected into the common-prompt file.
// HFA_HOME is redirected to the temp dir so the manifest never touches ~/.hfa.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, existsSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const HFA = join(ROOT, 'bin', 'hfa.js');

function run(cwd, ...args) {
  execFileSync('node', [HFA, ...args], {
    cwd, env: { ...process.env, HFA_HOME: join(cwd, '.hfa') }, stdio: 'pipe',
  });
}
const tmp = (p) => mkdtempSync(join(tmpdir(), `hfa-${p}-`));

// Per-platform project-scope layout: skills dir, common-prompt file, codex slash dir.
const LAYOUT = {
  'claude-code': { dir: '.claude/skills', prompt: 'CLAUDE.md' },
  codex: { dir: '.codex/skills', prompt: 'AGENTS.md', slash: '.codex/prompts' },
  openclaw: { dir: '.openclaw/skills', prompt: 'AGENTS.md' },
};

for (const [platform, l] of Object.entries(LAYOUT)) {
  test(`${platform} · installs skill + dep and injects the routing table`, () => {
    const dir = tmp(platform);
    try {
      run(dir, 'install', 'single-stock-deep-dive', '--platform', platform, '--scope', 'project', '-y');
      assert.ok(existsSync(join(dir, l.dir, 'single-stock-deep-dive', 'SKILL.md')), 'skill copied');
      assert.ok(existsSync(join(dir, l.dir, 'hfa-core', 'SKILL.md')), 'closure dep hfa-core copied');
      if (l.slash) {
        assert.ok(existsSync(join(dir, l.slash, 'single-stock-deep-dive.md')), 'codex slash-prompt generated');
      }
      const prompt = readFileSync(join(dir, l.prompt), 'utf8');
      assert.match(prompt, /hfa:skills:start/, 'routing markers present');
      assert.match(prompt, /\| single-stock-deep-dive \|/, 'skill row present');
      assert.match(prompt, /\| hfa-core \|/, 'dep row present');
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
}

test('routing table accumulates across installs (merge, not overwrite)', () => {
  const dir = tmp('merge');
  try {
    run(dir, 'install', 'sec-filings', '--platform', 'claude-code', '--scope', 'project', '-y');
    run(dir, 'install', 'charting', '--platform', 'claude-code', '--scope', 'project', '-y');
    const prompt = readFileSync(join(dir, 'CLAUDE.md'), 'utf8');
    assert.match(prompt, /\| sec-filings \|/, 'first install still listed');
    assert.match(prompt, /\| charting \|/, 'second install added');
    assert.equal(prompt.match(/hfa:skills:start/g).length, 1, 'exactly one routing block');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('routing Load paths point at the platform skills dir', () => {
  const dir = tmp('paths');
  try {
    run(dir, 'install', 'wiki-builder', '--platform', 'codex', '--scope', 'project', '-y');
    const prompt = readFileSync(join(dir, 'AGENTS.md'), 'utf8');
    assert.match(prompt, /\.codex\/skills\/wiki-builder\/SKILL\.md/, 'load path uses the codex skills dir');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('install all · installs every skill and lists them all in one routing table', () => {
  const dir = tmp('all');
  try {
    run(dir, 'install', 'all', '--platform', 'claude-code', '--scope', 'project', '-y');
    for (const s of ['single-stock-deep-dive', 'charting', 'sec-filings', 'hfa-core']) {
      assert.ok(existsSync(join(dir, '.claude', 'skills', s, 'SKILL.md')), `${s} installed`);
    }
    const prompt = readFileSync(join(dir, 'CLAUDE.md'), 'utf8');
    assert.equal(prompt.match(/hfa:skills:start/g).length, 1, 'exactly one routing block');
    const rows = (prompt.match(/^\| [a-z0-9-]+ \|/gm) || []).length;
    assert.ok(rows >= 17, `routing table lists all skills (got ${rows})`);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('entrypoint · bare `hfa claude-code` installs all + injects routing', () => {
  const dir = tmp('setup');
  try {
    run(dir, 'claude-code', '--scope', 'project'); // == `hfa setup claude-code`
    assert.ok(existsSync(join(dir, '.claude', 'skills', 'single-stock-deep-dive', 'SKILL.md')), 'skill installed');
    assert.match(readFileSync(join(dir, 'CLAUDE.md'), 'utf8'), /hfa:skills:start/, 'routing table injected');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('entrypoint · `hfa cowork` writes the global-instructions table (no Load column)', () => {
  const dir = tmp('cowork');
  try {
    run(dir, 'cowork');
    const f = join(dir, 'cowork-global-instructions.md');
    assert.ok(existsSync(f), 'global-instructions file written');
    const md = readFileSync(f, 'utf8');
    assert.match(md, /hfa:skills:start/, 'routing markers present');
    assert.doesNotMatch(md, /SKILL\.md/, 'no Load column (app-managed skills)');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
