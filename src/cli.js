import { existsSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { getSkills } from './registry.js';
import { listPersonas, resolveTarget } from './resolve.js';
import { getAdapter, PLATFORMS } from './adapters/index.js';
import { install } from './install.js';
import { buildRoutingTable } from './routing-table.js';
import { requiredEnv, resolveEnv, parseEnvFile } from './env.js';

// `analyst-kit <target>` / `analyst-kit setup <target>` installs ALL skills for a runtime. Cowork
// is marketplace/GUI-based, so it prints the in-app steps + writes its global-
// instructions table instead of copying files.
const SETUP_TARGETS = [...PLATFORMS, 'cowork'];

const HELP = `
analyst-kit — Analyst Kit skills installer

Usage:
  analyst-kit <claude-code|codex|openclaw|cowork> [--scope user|project]    # install ALL skills (cowork: print steps)
  analyst-kit setup <claude-code|codex|openclaw|cowork> [--scope user|project]
  analyst-kit list [--type capability|composite] [--persona <name>]
  analyst-kit install <skill|persona> --platform <${PLATFORMS.join('|')}> [--scope user|project] [--dry-run] [-y]
  analyst-kit update <skill|persona> --platform <p> [--scope user|project]
  analyst-kit uninstall <skill|persona> --platform <p> [--scope user|project]
  analyst-kit env --platform <p> [--scope user|project]
  analyst-kit doctor --platform <p> [--scope user|project]

Options:
  --platform   target agent runtime (${PLATFORMS.join(', ')})
  --scope      user (default) or project
  --type       filter list by skill type
  --persona    filter list to a persona's skills
  --dry-run    resolve & print, write nothing
  -y, --yes    non-interactive (don't prompt for keys)
  -h, --help   show this help
`;

function parseArgs(argv) {
  const out = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-h' || a === '--help') out.flags.help = true;
    else if (a === '-y' || a === '--yes') out.flags.yes = true;
    else if (a === '--dry-run') out.flags.dryRun = true;
    else if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith('-')) { out.flags[key] = next; i++; }
      else out.flags[key] = true;
    } else out._.push(a);
  }
  return out;
}

function cmdList(flags) {
  const skills = getSkills();
  if (flags.persona) {
    const closure = resolveTarget(flags.persona);
    console.log(`\n  persona ${flags.persona} → ${closure.length} skills:`);
    for (const s of closure) console.log(`    • ${s.name} [${s.type}]`);
    console.log('');
    return;
  }
  const filtered = flags.type ? skills.filter((s) => s.type === flags.type) : skills;
  console.log(`\n  Skills (${filtered.length}):`);
  for (const s of filtered.sort((a, b) => a.type.localeCompare(b.type) || a.name.localeCompare(b.name))) {
    const req = s.requires.length ? `  ← ${s.requires.join(', ')}` : '';
    const env = s.env.length ? `  [keys: ${s.env.join(', ')}]` : '';
    console.log(`    ${s.type === 'composite' ? '◆' : '○'} ${s.name.padEnd(26)} ${s.type}${req}${env}`);
  }
  const personas = listPersonas();
  if (personas.length) {
    console.log(`\n  Personas (${personas.length}):`);
    for (const p of personas) console.log(`    ▣ ${p.name.padEnd(26)} ${p.skills.length} skills`);
  }
  console.log('');
}

function cmdUninstall(target, flags) {
  const platform = flags.platform;
  const scope = flags.scope || 'user';
  const adapter = getAdapter(platform);
  const closure = resolveTarget(target);
  const base = adapter.installDir(scope);
  let removed = 0;
  for (const s of closure) {
    const dest = join(base, s.folder);
    if (existsSync(dest)) { rmSync(dest, { recursive: true, force: true }); removed++; console.log(`    ✗ removed ${s.name}`); }
  }
  console.log(`\n  uninstalled ${removed} skill(s) from ${base}\n`);
}

async function cmdEnv(flags) {
  const adapter = getAdapter(flags.platform);
  const scope = flags.scope || 'user';
  const vars = requiredEnv(getSkills());
  console.log(`\n  Resolving ${vars.length} known key(s) into ${adapter.envFile(scope)}`);
  const res = await resolveEnv(vars, { envFile: adapter.envFile(scope), interactive: !flags.yes });
  console.log(`  resolved: ${Object.keys(res.resolved).join(', ') || '(none)'}`);
  if (res.missing.length) console.log(`  missing:  ${res.missing.join(', ')}`);
  console.log('');
}

function cmdDoctor(flags) {
  const adapter = getAdapter(flags.platform);
  const scope = flags.scope || 'user';
  const skills = getSkills();
  console.log(`\n  analyst-kit doctor — platform ${flags.platform} (${scope})`);
  console.log(`  install dir: ${adapter.installDir(scope)}`);
  console.log(`  env file:    ${adapter.envFile(scope)}`);

  // The skill runtime is POSIX/bash, so Windows is supported only via WSL2 (which
  // is also the only place the agents' own sandbox runs). Node reports 'win32' for
  // native Windows even under Git Bash, but 'linux' inside WSL2 — so this is precise.
  if (process.platform === 'win32') {
    console.log('\n  ⚠ Native Windows detected — UNSUPPORTED.');
    console.log('    Analyst Kit skills run a POSIX/bash runtime; on Windows, run Claude Code (or Codex)');
    console.log('    and this installer inside a WSL2 distribution. See the README "Windows" note.');
  }

  const runtimes = new Set(skills.map((s) => s.runtime).filter((r) => r !== 'none'));
  console.log(`\n  Runtimes used by skills: ${[...runtimes].join(', ') || '(none)'}`);
  for (const rt of runtimes) {
    console.log(`    ${rt}: documented as a per-skill prerequisite (analyst-kit does not install runtimes)`);
  }

  const vars = requiredEnv(skills);
  const have = { ...parseEnvFile(adapter.envFile(scope)), ...process.env };
  console.log(`\n  API keys:`);
  for (const v of vars) console.log(`    ${have[v] ? '✓' : '✗'} ${v}`);
  console.log('');
}

async function cmdSetup(platform, flags) {
  if (!platform || !SETUP_TARGETS.includes(platform)) {
    throw new Error(`setup requires a platform: ${SETUP_TARGETS.join(' | ')}`);
  }
  if (platform === 'cowork') { cmdSetupCowork(); return; }
  await install('all', {
    platform, scope: flags.scope || 'user', dryRun: !!flags.dryRun, yes: true,
  });
}

// Cowork has no CLI install — it's a desktop app whose skills come from the plugin
// marketplace. Generate the paste-ready Global Instructions table + print the steps.
function cmdSetupCowork() {
  const out = join(process.cwd(), 'cowork-global-instructions.md');
  writeFileSync(out, buildRoutingTable(getSkills(), { includeLoad: false }) + '\n');
  console.log(`
  Claude Cowork installs inside the Claude desktop app (no terminal). One-time setup:
    1. Customize → Plugins → Personal plugins → +  → Add marketplace:  MohitKumar1991/analyst-kit
    2. Add a plugin:  us-stock-analyst   (or international-analyst / taiwan-stock-analyst)
    3. Settings → Capabilities → enable Code execution
    4. Settings → Cowork → Global instructions → paste the contents of:
         ${out}
`);
}

export async function main(argv) {
  const { _, flags } = parseArgs(argv);
  const cmd = _[0];
  if (!cmd || flags.help) { console.log(HELP); return; }

  try {
    // Simple cross-platform entrypoint: `analyst-kit <platform>` or `analyst-kit setup <platform>`.
    if (cmd === 'setup' || SETUP_TARGETS.includes(cmd)) {
      await cmdSetup(cmd === 'setup' ? _[1] : cmd, flags);
      return;
    }
    switch (cmd) {
      case 'list':
        cmdList(flags); break;
      case 'install': {
        if (!_[1]) throw new Error('install requires a <skill|persona> argument');
        if (!flags.platform) throw new Error('install requires --platform');
        await install(_[1], {
          platform: flags.platform, scope: flags.scope || 'user',
          dryRun: !!flags.dryRun, yes: !!flags.yes,
        });
        break;
      }
      case 'update': {
        if (!_[1]) throw new Error('update requires a <skill|persona> argument');
        if (!flags.platform) throw new Error('update requires --platform');
        // update == reinstall at the current bundled version
        await install(_[1], { platform: flags.platform, scope: flags.scope || 'user', yes: true });
        break;
      }
      case 'uninstall':
        if (!_[1]) throw new Error('uninstall requires a <skill|persona> argument');
        if (!flags.platform) throw new Error('uninstall requires --platform');
        cmdUninstall(_[1], flags); break;
      case 'env':
        if (!flags.platform) throw new Error('env requires --platform');
        await cmdEnv(flags); break;
      case 'doctor':
        if (!flags.platform) throw new Error('doctor requires --platform');
        cmdDoctor(flags); break;
      default:
        console.error(`unknown command: ${cmd}`);
        console.log(HELP);
        process.exitCode = 1;
    }
  } catch (e) {
    console.error(`\n  error: ${e.message}\n`);
    process.exitCode = 1;
  }
}
