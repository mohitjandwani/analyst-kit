import { getAdapter } from './adapters/index.js';
import { resolveTarget, personaByName } from './resolve.js';
import { requiredEnv, resolveEnv } from './env.js';
import { fileCount } from './adapters/copy.js';

// Install a skill or persona (+ its dependency closure) into a platform.
export async function install(target, opts = {}) {
  const {
    platform, scope = 'user', dryRun = false, interactive = true, yes = false,
  } = opts;

  const adapter = getAdapter(platform);
  const closure = resolveTarget(target);
  const isPersona = !!personaByName(target);

  const log = (...a) => console.log(...a);
  log(`\n  hfa install ${target} → ${platform} (${scope} scope)`);
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
  if (missing.length) log(`  ⚠ still missing keys: ${missing.join(', ')} — run \`hfa env --platform ${platform}\``);
  log('');

  return { closure, written, missing };
}
