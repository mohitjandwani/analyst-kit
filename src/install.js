import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';
import { getAdapter } from './adapters/index.js';
import { resolveTarget, personaByName } from './resolve.js';
import { requiredEnv, resolveEnv } from './env.js';
import { fileCount } from './adapters/copy.js';
import { upsertRoutingTable } from './routing-table.js';
import { VERSION_FILE } from './paths.js';

// Record what was installed in ~/.analyst-kit/install-manifest.jsonl so the guided
// upgrade flow (skills/analyst-kit-core/references/upgrade.md) can re-run the same
// installs against a newer release. Best-effort: never fails an install.
function recordInstall(target, platform, scope) {
  try {
    const home = process.env.AK_HOME || join(homedir(), '.analyst-kit');
    mkdirSync(home, { recursive: true });
    const version = readFileSync(VERSION_FILE, 'utf8').trim();
    const line = JSON.stringify({
      target, platform, scope, version, ts: new Date().toISOString(),
    });
    appendFileSync(join(home, 'install-manifest.jsonl'), line + '\n');
  } catch { /* analytics must never break an install */ }
}

// Install a skill or persona (+ its dependency closure) into a platform.
export async function install(target, opts = {}) {
  const {
    platform, scope = 'user', dryRun = false, interactive = true, yes = false,
  } = opts;

  const adapter = getAdapter(platform);
  const closure = resolveTarget(target);
  const isPersona = !!personaByName(target);

  const log = (...a) => console.log(...a);
  if (process.platform === 'win32') {
    log('\n  ⚠ Native Windows is unsupported — run inside WSL2 (the skill runtime is POSIX/bash).');
  }
  log(`\n  analyst-kit install ${target} → ${platform} (${scope} scope)`);
  log(`  ${isPersona ? 'persona' : 'skill'}: resolves to ${closure.length} skill(s):`);
  for (const s of closure) {
    const deps = s.requires.length ? `  ← ${s.requires.join(', ')}` : '';
    log(`    • ${s.name} [${s.type}]${deps}`);
  }

  if (dryRun) {
    log(`\n  dry run — nothing written. Target dir: ${adapter.installDir(scope)}\n`);
    return { closure, written: [], missing: [] };
  }

  const written = [];
  for (const s of closure) {
    const dest = adapter.write(s, scope);
    written.push({ name: s.name, dest, files: fileCount(s.dir) });
  }
  recordInstall(target, platform, scope);

  // Advertise the installed skills in the runtime's common prompt (routing table),
  // merging with anything already listed so repeated installs accumulate.
  if (typeof adapter.commonPromptFile === 'function') {
    const promptFile = adapter.commonPromptFile(scope);
    const changed = upsertRoutingTable(promptFile, closure, { skillsDir: adapter.installDir(scope) });
    log(`  ${changed ? '✓ updated' : '= unchanged'} routing table → ${promptFile}`);
  }

  // Resolve API keys across the whole closure.
  const vars = requiredEnv(closure);
  let missing = [];
  if (vars.length) {
    log(`\n  API keys needed: ${vars.join(', ')}`);
    const res = await resolveEnv(vars, {
      envFile: adapter.envFile(scope),
      interactive: interactive && !yes,
    });
    missing = res.missing;
    if (res.wrote) log(`  wrote keys to ${adapter.envFile(scope)}`);
  }

  // Report runtimes still required on this machine.
  const runtimes = new Set(closure.map((s) => s.runtime).filter((r) => r !== 'none'));

  log(`\n  installed ${written.length} skill(s) to ${adapter.installDir(scope)}`);
  for (const w of written) log(`    ✓ ${w.name} (${w.files} files)`);
  if (runtimes.size) log(`  runtimes required: ${[...runtimes].join(', ')} (skills bootstrap deps on first use)`);
  if (missing.length) log(`  ⚠ still missing keys: ${missing.join(', ')} — run \`analyst-kit env --platform ${platform}\``);
  log('');

  return { closure, written, missing };
}
