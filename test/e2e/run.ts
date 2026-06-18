// e2e harness — single Bun entrypoint with two modes.
//
//   HOST mode (default):  KEY=k … bun test/e2e/run.ts [--task <id>]
//     Brings the dev container up, forwards an allowlist of API keys it finds in its own
//     environment into the container, then re-invokes itself INSIDE the container.
//
//   IN-CONTAINER mode (--in-container):
//     Installs every skill via bin/hfa.js, verifies they landed, runs each task through
//     `claude -p`, checks that each produced exactly one valid PDF, writes a report.
//
// Keys are passed inline on the host command (or via an optional test/e2e/.env) and never
// baked into the image. Models are baked into the image ENV: the main agent runs on Opus,
// and it delegates to Sonnet/Haiku subagents per-task (see the Dockerfile + system prompt).

import { spawn, spawnSync } from 'node:child_process';
import {
  existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, appendFileSync,
  copyFileSync, createWriteStream, rmSync, symlinkSync, lstatSync,
} from 'node:fs';
import { createServer } from 'node:http';
import { join, basename, extname, resolve as pathResolve } from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { auditTask, buildRemediationPrompt } from './audit.ts';

// Secrets the harness forwards into the container (inline > .env file > unset).
// SEC_EDGAR_UA is what skills/sec-filings/scripts/edgar.py reads; SEC_EDGAR_USER_AGENT is
// the MCP-based path. Forward both so whichever the agent uses gets the contact string.
const FORWARD_KEYS = ['ANTHROPIC_API_KEY', 'FMP_API_KEY', 'FINMIND_TOKEN', 'SEC_EDGAR_UA', 'SEC_EDGAR_USER_AGENT', 'SERPAPI_API_KEY'];
const DEFAULT_TIMEOUT_MS = 20 * 60 * 1000;

// run.ts lives at <repo>/test/e2e/run.ts → repo root is two levels up. `import.meta.dir`
// is set by Bun; fall back to deriving it from the URL for plain node.
const HERE = (import.meta as any).dir ?? new URL('.', import.meta.url).pathname;
const REPO_ROOT = pathResolve(HERE, '..', '..');

// Behavioral system prompt, APPENDED to Claude Code's default (which already lists the
// installed skills + tools). Edit test/e2e/system-prompt.md to change the rules. Read once
// here — before the top-level dispatch below — so the const is initialized when runClaude
// (called during runInContainer's top-level await) reads it.
const SYSTEM_PROMPT_FILE = join(REPO_ROOT, 'test', 'e2e', 'system-prompt.md');
const SYSTEM_PROMPT = existsSync(SYSTEM_PROMPT_FILE) ? readFileSync(SYSTEM_PROMPT_FILE, 'utf8').trim() : '';

const argv = process.argv.slice(2);
const IN_CONTAINER = argv.includes('--in-container');
const taskFilter = flagValue(argv, '--task');
// How many tasks to run at once inside the one container. Default 1 (sequential — the
// proven path). `--concurrency N` / `--parallel N` runs N tasks side-by-side, each in its
// own cwd + isolated Claude HOME so they never race on shared state. Rides through to the
// container via `passthrough`.
const CONCURRENCY = Math.max(1, Number(flagValue(argv, '--concurrency') ?? flagValue(argv, '--parallel')) || 1);
// After a host run finishes, auto-start a local server for the JSONL log viewer.
// Off in CI / when piping, or via --no-viewer / E2E_NO_VIEWER.
const NO_VIEWER = argv.includes('--no-viewer') || !!process.env.E2E_NO_VIEWER || !!process.env.CI;
// --verbose streams `devcontainer up` build output live and traces every Claude stream
// event (tool calls, text, result) as a one-liner. The flag rides through to the
// container via `passthrough`; E2E_VERBOSE only affects the side it's set on.
const VERBOSE = argv.includes('--verbose') || !!process.env.E2E_VERBOSE;

// Colored live trace. The trace runs IN-CONTAINER, whose stderr is a non-TTY pipe (via
// `docker exec`), so host mode forwards E2E_TTY=1 when its own stdout is a TTY; a manual
// in-container interactive shell has stderr.isTTY itself. Emit ANSI only then — so piped /
// tee'd / backgrounded runs stay clean plain text. Declared before the dispatch (no TDZ).
const COLOR = !!process.env.E2E_TTY || !!process.stderr.isTTY;
const paint = (code: string, s: string) => (COLOR ? `\x1b[${code}m${s}\x1b[0m` : s);
// Secondary-text grays tuned for a dark terminal — ANSI `dim` (code 2) renders nearly
// invisible, so use explicit readable greys instead.
const DIM = '38;5;246'; // tool detail, init/result lines, heartbeat
const SAY = '38;5;252'; // assistant narration — brighter, so it's actually readable
// Tool → { 256-color, icon }, mirroring viewer.html's TOOL_THEME (Skill is the violet
// standout). Bright variants chosen for contrast on a dark background.
const TOOL_COLOR: Record<string, { code: string; icon: string }> = {
  Skill:     { code: '38;5;177', icon: '✦' },
  Task:      { code: '38;5;86',  icon: '⟁' },
  Agent:     { code: '38;5;86',  icon: '⟁' },
  Bash:      { code: '38;5;114', icon: '❯' },
  Read:      { code: '38;5;81',  icon: '▤' },
  Write:     { code: '38;5;221', icon: '✎' },
  Edit:      { code: '38;5;215', icon: '✎' },
  WebSearch: { code: '38;5;117', icon: '⌕' },
  WebFetch:  { code: '38;5;117', icon: '⌕' },
  Grep:      { code: '38;5;249', icon: '⌕' },
  Glob:      { code: '38;5;249', icon: '⌕' },
};
const DEFAULT_TOOL = { code: '38;5;249', icon: '⚒' };

// ── Provenance audit (see audit.ts) ──────────────────────────────────────────────────────
// ADVISORY data-provenance self-repair. A judge checks that every source the report's DATA
// cites (the contract's references + data_sources.md) was actually queried (ground truth = a
// ledger of real tool calls, incl. sub-agents). On a flagged source it RESUMES the same agent
// session to fetch the real data or DROP the unsupported data, then re-audits — up to
// --audit-retries times. It NEVER fails the task (pass/fail stays "valid PDF"); it only
// improves the deliverable. Flags ride through to the container via `passthrough`.
const AUDIT_ENABLED = !argv.includes('--no-audit');
const AUDIT_MODEL = flagValue(argv, '--audit-model') || 'sonnet';
const MAX_AUDIT_RETRIES = Math.max(0, Number(flagValue(argv, '--audit-retries')) || 1);

if (IN_CONTAINER) {
  await runInContainer(taskFilter, CONCURRENCY);
} else {
  await hostMode(argv.filter((a) => a !== '--in-container' && a !== '--no-viewer'));
}

function flagValue(args: string[], name: string): string | null {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

// ── HOST MODE ──────────────────────────────────────────────────────────────────────────
async function hostMode(passthrough: string[]) {
  loadDotEnv(join(REPO_ROOT, 'test', 'e2e', '.env'), true); // authoritative: overrides host env

  if (!process.env.ANTHROPIC_API_KEY) {
    fail('ANTHROPIC_API_KEY is required. Set it inline, e.g.\n'
      + '  ANTHROPIC_API_KEY=sk-… bun test/e2e/run.ts [--task <id>]');
  }
  if (!hasCmd('devcontainer')) {
    fail('the devcontainer CLI is not installed.\n  npm i -g @devcontainers/cli');
  }

  const present = FORWARD_KEYS.filter((k) => process.env[k]);

  console.error(`▶ bringing the dev container up …${VERBOSE ? '' : ' (silent; can take minutes on a rebuild — pass --verbose to stream build output)'}`);
  // stdout must stay piped (we parse its JSON result); stderr carries the build log, so
  // under --verbose inherit it and let it stream to the terminal in real time.
  const up = spawnSync('devcontainer', ['up', '--workspace-folder', REPO_ROOT], {
    encoding: 'utf8', stdio: ['ignore', 'pipe', VERBOSE ? 'inherit' : 'pipe'],
  });
  if (up.status !== 0) {
    process.stderr.write(up.stdout || '');
    process.stderr.write(up.stderr || '');
    fail('`devcontainer up` failed (see output above).');
  }
  const info = parseUpJson(up.stdout || '');
  if (!info?.containerId) {
    process.stderr.write(up.stdout || '');
    fail('could not read containerId from `devcontainer up` output.');
  }
  const remoteWs = info.remoteWorkspaceFolder || `/workspaces/${basename(REPO_ROOT)}`;
  const user = info.remoteUser || 'node';

  // Forward E2E_TTY when the host terminal is a TTY, so the in-container trace colorizes (its
  // stderr is a non-TTY pipe via docker exec, so it can't detect this itself).
  const ttyArgs = process.stdout.isTTY ? ['-e', 'E2E_TTY=1'] : [];
  const envArgs = [...present.flatMap((k) => ['-e', `${k}=${process.env[k]}`]), ...ttyArgs];
  const cmd = [
    'exec', ...envArgs, '-u', user, '-w', remoteWs, info.containerId,
    'bun', `${remoteWs}/test/e2e/run.ts`, '--in-container', ...passthrough,
  ];
  console.error(`▶ running harness in ${info.containerId.slice(0, 12)} (forwarding: ${present.join(', ') || 'none'})`);

  // --no-viewer (CI, piping, scripted/background runs): the proven BLOCKING path, unchanged.
  if (NO_VIEWER) {
    const r = spawnSync('docker', cmd, { stdio: 'inherit' });
    process.exit(r.status ?? 1);
  }

  // Viewer path: start the static server FIRST (so the event loop is free to serve while the
  // run streams to the terminal), run the harness async, open the browser as soon as the run
  // writes its first stream log, then keep the viewer up for review until Ctrl+C. viewer.html
  // live-tails, so the timeline grows as the agent works.
  const e2eDir = join(REPO_ROOT, 'test', 'e2e');
  let srv: { server: ReturnType<typeof createServer>; base: string };
  try {
    srv = await serveE2E(e2eDir);
  } catch (e: any) {
    console.error(`✗ could not start viewer (${e?.message}); running without it.`);
    const r = spawnSync('docker', cmd, { stdio: 'inherit' });
    process.exit(r.status ?? 1);
  }
  watchAndOpen(e2eDir, srv.base); // non-blocking: polls logs/latest, opens the browser when ready

  const child = spawn('docker', cmd, { stdio: 'inherit' });
  const status: number = await new Promise((res) => {
    child.on('close', (code) => res(code ?? 1));
    child.on('error', (err) => { console.error(`✗ run failed to spawn: ${err.message}`); res(1); });
  });

  // Run finished — keep the viewer alive for review (it stays tailing the now-complete log).
  const latest = join(e2eDir, 'logs', 'latest');
  const streams = existsSync(latest)
    ? readdirSync(latest).filter((f) => f.endsWith('.stream.jsonl')).sort() : [];
  if (!streams.length) { try { srv.server.close(); } catch { /* ignore */ } process.exit(status); }
  const bar = '─'.repeat(64);
  console.log(`\n${bar}`);
  console.log(`▶ log viewer running at ${srv.base}/viewer.html  (Ctrl+C to stop)`);
  streams.forEach((f) => console.log(`    ${f.replace(/\.stream\.jsonl$/, '').padEnd(24)} ${srv.base}/viewer.html?file=logs/latest/${f}`));
  console.log(bar);
  const stop = () => { try { srv.server.close(); } catch { /* ignore */ } process.exit(status); };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
}

// ── LOG VIEWER ─────────────────────────────────────────────────────────────────────────
// A zero-dependency static server scoped to test/e2e/, so viewer.html can fetch a run's
// `*.stream.jsonl` via ?file=. Returns the server + base URL; the caller opens the browser and
// owns the lifecycle. viewer.html live-tails the stream, so it can be opened mid-run.
function serveE2E(e2eDir: string): Promise<{ server: ReturnType<typeof createServer>; base: string }> {
  const root = pathResolve(e2eDir);
  const MIME: Record<string, string> = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css', '.json': 'application/json', '.jsonl': 'application/json',
    '.png': 'image/png', '.pdf': 'application/pdf', '.md': 'text/plain; charset=utf-8',
  };
  const server = createServer((req, res) => {
    try {
      const rel = decodeURIComponent((req.url || '/').split('?')[0]).replace(/^\/+/, '') || 'viewer.html';
      const file = pathResolve(root, rel);
      // Confine every request to test/e2e/ — no path traversal, no directory listings.
      if (file !== root && !file.startsWith(root + '/')) { res.writeHead(403); return res.end('forbidden'); }
      if (!existsSync(file) || lstatSync(file).isDirectory()) { res.writeHead(404); return res.end('not found'); }
      // no-store so viewer.html's live polling always reads the growing file, never a cached copy.
      res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      res.end(readFileSync(file));
    } catch { res.writeHead(500); res.end('error'); }
  });
  return new Promise((resolve, reject) => {
    const basePort = Number(process.env.E2E_VIEWER_PORT) || 8787;
    const listen = (port: number, tries: number) => {
      server.once('error', (e: any) => {
        if (e.code === 'EADDRINUSE' && tries > 0) listen(port + 1, tries - 1);
        else reject(e);
      });
      server.listen(port, '127.0.0.1', () => resolve({ server, base: `http://127.0.0.1:${port}` }));
    };
    listen(basePort, 10);
  });
}

// Poll logs/latest until the run's first stream log exists, then open the browser to it (and
// print URLs for any others, e.g. under --concurrency). Non-blocking; gives up after ~90s.
function watchAndOpen(e2eDir: string, base: string): void {
  const latest = join(e2eDir, 'logs', 'latest');
  let tries = 0;
  const tick = () => {
    let streams: string[] = [];
    try { streams = existsSync(latest) ? readdirSync(latest).filter((f) => f.endsWith('.stream.jsonl')).sort() : []; } catch { /* not yet */ }
    if (streams.length) {
      const urls = streams.map((f) => `${base}/viewer.html?file=logs/latest/${f}`);
      console.error(`▶ live log viewer: ${urls[0]}${urls.length > 1 ? `  (+${urls.length - 1} more below)` : ''}`);
      urls.slice(1).forEach((u) => console.error(`    also: ${u}`));
      openBrowser(urls[0]);
      return;
    }
    if (tries++ < 90) setTimeout(tick, 1000);
    else console.error(`▶ viewer up at ${base}/viewer.html (no stream logs yet — open manually).`);
  };
  setTimeout(tick, 500);
}

function openBrowser(url: string): void {
  const [cmd, args] = process.platform === 'darwin' ? ['open', [url]]
    : process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]]
    : ['xdg-open', [url]];
  try { spawn(cmd, args as string[], { stdio: 'ignore', detached: true }).unref(); } catch { /* best-effort */ }
}

function parseUpJson(stdout: string): any | null {
  // `devcontainer up` prints a JSON result object (usually the last line).
  const lines = stdout.split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    if (!lines[i].startsWith('{')) continue;
    try {
      const obj = JSON.parse(lines[i]);
      if (obj && obj.containerId) return obj;
    } catch { /* keep scanning */ }
  }
  return null;
}

// test/e2e/.env is the harness's authoritative key source, so it OVERRIDES ambient host
// env (override=true). Without this, a key leaked into the parent shell — e.g. an
// ANTHROPIC_API_KEY meant for the host's own Claude Code — would shadow the .env value and
// get forwarded into the container, where it may auth-fail (401). The file wins; to use a
// different key for one run, edit the file.
function loadDotEnv(file: string, override = false) {
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
    if (m && (override || !process.env[m[1]])) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

function hasCmd(cmd: string): boolean {
  const r = spawnSync(cmd, ['--version'], { stdio: 'ignore' });
  return !(r.error && (r.error as any).code === 'ENOENT');
}

function fail(msg: string): never {
  console.error(`\n✗ ${msg}\n`);
  process.exit(2);
}

// ── IN-CONTAINER MODE ──────────────────────────────────────────────────────────────────
async function runInContainer(filter: string | null, concurrency: number) {
  // Keys normally arrive via `docker exec -e` (host mode forwards them). Load test/e2e/.env
  // here too so a single task can be launched directly from inside the container —
  // `bun test/e2e/run.ts --in-container --task <id>` — with no manual sourcing. Non-override,
  // so an explicitly-exported shell var still wins; harmless in the normal flow (keys already set).
  loadDotEnv(join(REPO_ROOT, 'test', 'e2e', '.env'));

  const { getSkills } = await import(pathToFileURL(join(REPO_ROOT, 'src', 'registry.js')).href);
  const { parseFrontmatter } = await import(pathToFileURL(join(REPO_ROOT, 'src', 'frontmatter.js')).href);

  const e2e = join(REPO_ROOT, 'test', 'e2e');
  const logsRoot = join(e2e, 'logs');
  const pdfsDir = join(e2e, 'pdfs');
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const runDir = join(logsRoot, ts);
  mkdirSync(runDir, { recursive: true });
  mkdirSync(pdfsDir, { recursive: true });
  pointLatest(logsRoot, ts);

  const report: any = { startedAt: ts, ok: false, phases: {}, tasks: [] };
  const stamp = () => new Date().toISOString().slice(11, 19);
  const log = (m: string) => { const l = `[${stamp()}] ${m}`; console.log(l); appendFileSync(join(runDir, 'run.log'), l + '\n'); };

  const skills: any[] = getSkills();
  const skillsHome = join(homedir(), '.claude', 'skills');

  // Phase 1 — install every skill (so any task can autonomously pick what it needs).
  log(`Phase 1 · install — ${skills.length} skills via bin/hfa.js → ${skillsHome}`);
  const installResults = skills.map((s) => {
    const r = spawnSync('node', [
      join(REPO_ROOT, 'bin', 'hfa.js'), 'install', s.name,
      '--platform', 'claude-code', '--scope', 'user', '-y',
    ], { cwd: REPO_ROOT, encoding: 'utf8' });
    if (r.status !== 0) log(`  ✗ ${s.name}: ${lastLine(r.stderr || r.stdout)}`);
    return { skill: s.name, ok: r.status === 0 };
  });
  const installOk = installResults.every((r) => r.ok);
  report.phases.install = { ok: installOk, results: installResults };
  log(`  → ${installResults.filter((r) => r.ok).length}/${installResults.length} installed`);

  // The harness installs SKILLS only — no agent definitions. Any sub-agent a task needs for
  // data gathering is launched via the Task tool per the relevant skill's own instructions
  // (e.g. sec-filings documents the extraction sub-agent recipe).

  // Phase 2 — verify each skill folder landed.
  const verify = skills.map((s) => ({ skill: s.folder, present: existsSync(join(skillsHome, s.folder, 'SKILL.md')) }));
  const verifyOk = verify.every((v) => v.present);
  report.phases.verifyInstall = { ok: verifyOk, skillsHome, results: verify };
  log(`Phase 2 · verify — ${verify.filter((v) => v.present).length}/${verify.length} skill folders present`);
  for (const v of verify) if (!v.present) log(`  ✗ missing: ${v.skill}`);

  // Discover tasks (skip TEMPLATE.md — it isn't *.task.md). Apply the --task filter up
  // front so the worker pool only schedules tasks we actually intend to run.
  const tasksDir = join(e2e, 'tasks');
  const sharedClaude = join(homedir(), '.claude'); // skills + agents were installed here above
  // --task accepts a comma-separated list, e.g. --task 10-rblx-trends-bookings,20-delta-nvda-revenue
  const wanted = filter ? new Set(filter.split(',').map((s) => s.trim()).filter(Boolean)) : null;
  const taskFiles = readdirSync(tasksDir)
    .filter((f) => f.endsWith('.task.md')).sort()
    .filter((file) => {
      const { data } = parseFrontmatter(readFileSync(join(tasksDir, file), 'utf8'));
      const id: string = (data && data.id) || file.replace(/\.task\.md$/, '');
      const stem = file.replace(/\.task\.md$/, '');
      return !wanted || wanted.has(id) || wanted.has(stem);
    });
  log(`Phase 3 · ${taskFiles.length} task(s) — concurrency ${concurrency}`);

  // One task end-to-end. Runs in its own cwd AND its own Claude HOME, so concurrent
  // `claude -p` processes never race on shared ~/.claude state (sessions, projects, todos,
  // the onboarding json). Skills + agents — installed once above — are shared read-only via
  // symlink, so N tasks cost one install and one container's memory, not N.
  const runTask = async (file: string): Promise<any> => {
    const raw = readFileSync(join(tasksDir, file), 'utf8');
    const { data, body } = parseFrontmatter(raw);
    const id: string = (data && data.id) || file.replace(/\.task\.md$/, '');
    const rec: any = { id, file, ok: false };
    const timeoutMs = Number(data?.timeoutMs) || DEFAULT_TIMEOUT_MS;

    // Isolated cwd; deliverable lands in output/ (see the contract). The dev container is
    // reused across runs, so /tmp/run/<id> may still hold a PRIOR run's deliverable. Clear
    // it first — otherwise a failed/timed-out run's auto-PDF step (3b) picks up stale HTML
    // and reports a false PASS.
    const workdir = `/tmp/run/${id}`;
    const outdir = join(workdir, 'output');
    rmSync(workdir, { recursive: true, force: true });
    mkdirSync(outdir, { recursive: true });
    // The user prompt is the bare task body — it states its own deliverable. All behavioral
    // guidance (skills-first, provenance, no-made-up-data, plan/verify, clarify) lives in the
    // appended system prompt; tools/skills the agent discovers from its native skill listing.
    const prompt = (body || '').trim();

    // Per-task Claude HOME. skills/ is symlinked to the shared install (read-only at run
    // time, so safe to share); everything Claude WRITES stays under this home.
    const taskHome = join(workdir, 'home');
    const taskClaude = join(taskHome, '.claude');
    mkdirSync(taskClaude, { recursive: true });
    const skillsSrc = join(sharedClaude, 'skills');
    if (existsSync(skillsSrc)) { try { symlinkSync(skillsSrc, join(taskClaude, 'skills')); } catch { /* ignore */ } }
    // Seed onboarding flags so headless `claude -p` never blocks on first-run (mirrors
    // post-create.sh, which only seeds the real HOME, not these per-task ones).
    writeFileSync(join(taskHome, '.claude.json'),
      '{"hasCompletedOnboarding": true, "bypassPermissionsModeAccepted": true}\n');

    log(`Phase 3 · task ${id} — claude -p (timeout ${Math.round(timeoutMs / 1000)}s, cwd ${workdir})`);
    const res = await runClaude(prompt, workdir, join(runDir, `${id}.stream.jsonl`), timeoutMs, taskHome, id);
    writeFileSync(join(runDir, `${id}.log`),
      [`task: ${id}`, `cwd: ${workdir}`, `home: ${taskHome}`, `exit: ${res.code}`, `timedOut: ${res.timedOut}`,
        `durationMs: ${res.durationMs}`, `costUsd: ${res.costUsd}`, `result: ${res.resultSummary}`].join('\n') + '\n');
    copyNewestTranscript(runDir, id, taskHome);

    // Phase 3b/4 — platform post-processing + verification, wrapped so the audit loop can
    // re-run it after a repair turn. 3b: if the agent left an HTML deliverable but no PDF,
    // convert it here (HTML→PDF is the harness's job, not a turn the agent spends). 4: verify
    // exactly one valid, non-empty PDF. `forceReconvert` drops stale PDFs first so a repaired
    // HTML re-renders rather than the prior pass's PDF passing again.
    const listBy = (dir: string, ext: string) =>
      existsSync(dir) ? readdirSync(dir).filter((f) => f.toLowerCase().endsWith(ext)) : [];
    const convertAndVerify = (forceReconvert = false): void => {
      // Snapshot before a forced drop so a repair that re-renders straight to PDF (no HTML to
      // reconvert from) can never LOSE a valid deliverable — restore it below if we end empty.
      let snapshot: { name: string; buf: Buffer } | null = null;
      if (forceReconvert) {
        const existing = listBy(outdir, '.pdf');
        if (existing.length) snapshot = { name: existing[0], buf: readFileSync(join(outdir, existing[0])) };
        for (const f of existing) rmSync(join(outdir, f), { force: true });
      }
      if (listBy(outdir, '.pdf').length === 0) {
        const htmls = listBy(outdir, '.html').map((f) => join(outdir, f))
          .concat(listBy(workdir, '.html').map((f) => join(workdir, f)));
        // Prefer the contracted name, else the most recently written candidate.
        const pick = htmls.find((p) => basename(p) === `${id}.html`)
          ?? htmls.sort((a, b) => lstatSync(b).mtimeMs - lstatSync(a).mtimeMs)[0];
        if (pick) {
          const conv = spawnSync('html2pdf', [pick, join(outdir, `${id}.pdf`)], { encoding: 'utf8' });
          rec.autoPdf = { from: basename(pick), ok: conv.status === 0 };
          log(`  · [${id}] auto-converted ${basename(pick)} → ${id}.pdf${conv.status === 0 ? '' : ` (FAILED: ${lastLine(conv.stderr || conv.stdout)})`}`);
        }
      }
      // A forced reconvert that produced nothing → restore the snapshot, so a repair turn that
      // didn't re-render never downgrades a valid deliverable to "no PDF".
      if (forceReconvert && snapshot && listBy(outdir, '.pdf').length === 0) {
        writeFileSync(join(outdir, snapshot.name), snapshot.buf);
        log(`  · [${id}] repair produced no new PDF — restored prior deliverable`);
      }
      const pdfs = listBy(outdir, '.pdf');
      if (pdfs.length === 1) {
        const p = join(outdir, pdfs[0]);
        const buf = readFileSync(p);
        const valid = buf.length > 0 && buf.subarray(0, 5).toString('latin1') === '%PDF-';
        rec.pdf = { file: pdfs[0], bytes: buf.length, validHeader: valid };
        rec.ok = valid;
        if (valid) {
          copyFileSync(p, join(pdfsDir, `${id}.pdf`)); // flat review folder
          copyFileSync(p, join(runDir, `${id}.pdf`));  // archived with the run
        }
      } else {
        rec.pdf = { count: pdfs.length, files: pdfs };
        rec.ok = false;
      }
    };

    rec.claude = { code: res.code, timedOut: res.timedOut, durationMs: res.durationMs, costUsd: res.costUsd };
    convertAndVerify();
    log(`  → [${id}] ${rec.ok ? '✓ valid PDF' : '✗ no valid PDF'}${rec.pdf?.bytes ? ` (${rec.pdf.bytes} bytes)` : ''}`);

    // Phase 5 — data-provenance audit + self-repair (ADVISORY: never fails the task; it audits
    // the DATA handed to reporting — the contract's references + data_sources.md — against the
    // tool-call ledger, and on a flagged source resumes the agent to fetch it or DROP it).
    // Runs whenever the agent ran (not gated on a valid PDF); a timed-out run is skipped.
    if (AUDIT_ENABLED && !res.timedOut) {
      // The judge runs as its own `claude -p` call; give it a minimal HOME so it doesn't load
      // the 18 installed skills it has no use for.
      const auditHome = join(workdir, '.audit-home');
      mkdirSync(join(auditHome, '.claude'), { recursive: true });
      writeFileSync(join(auditHome, '.claude.json'),
        '{"hasCompletedOnboarding": true, "bypassPermissionsModeAccepted": true}\n');
      const streamPath = join(runDir, `${id}.stream.jsonl`);
      const doAudit = () => auditTask({ taskHome, streamPath, outdir, workdir, id, model: AUDIT_MODEL, auditHome });
      const badCount = (a: any) => (a.findings || []).filter((f: any) => f.status !== 'SUPPORTED').length;
      const label = (a: any) => a.verdict === 'error' ? `inconclusive — ${a.summary}`
        : a.ok ? '✓ provenance clean' : `✗ ${badCount(a)} unsupported source(s)`;

      let audit = await doAudit();
      rec.audit = { model: AUDIT_MODEL, ok: audit.ok, verdict: audit.verdict, ledger: audit.ledger,
        attempts: [{ verdict: audit.verdict, summary: audit.summary, findings: audit.findings }] };
      log(`Phase 5 · [${id}] audit ${label(audit)}`);

      let attempt = 0;
      let sid = res.sessionId;
      while (!audit.ok && audit.verdict !== 'error' && attempt < MAX_AUDIT_RETRIES && sid) {
        attempt++;
        log(`Phase 5 · [${id}] self-repair ${attempt}/${MAX_AUDIT_RETRIES} — resuming ${sid.slice(0, 8)} to fix or drop flagged data`);
        const remediation = buildRemediationPrompt(id, audit.findings);
        const r2 = await runClaude(remediation, workdir, join(runDir, `${id}.audit-retry${attempt}.stream.jsonl`),
          timeoutMs, taskHome, `${id}:fix${attempt}`, sid);
        sid = r2.sessionId ?? sid;
        rec.claude.repairs = (rec.claude.repairs ?? []).concat([{ attempt, durationMs: r2.durationMs, costUsd: r2.costUsd, timedOut: r2.timedOut }]);
        convertAndVerify(true); // re-render the repaired report, re-verify the PDF (snapshot-safe)
        audit = await doAudit();
        rec.audit.attempts.push({ verdict: audit.verdict, summary: audit.summary, findings: audit.findings });
        log(`Phase 5 · [${id}] re-audit ${label(audit)}`);
      }
      rec.audit.ok = audit.ok;
      rec.audit.verdict = audit.verdict;
      // Advisory only — the audit NEVER sets rec.ok. Task pass/fail stays "valid PDF" (Phase 4).
    }
    return rec;
  };

  // Run tasks through a bounded pool (concurrency=1 ⇒ strictly sequential). runPool keeps
  // input order; sort by id anyway so the report is stable however the files were ordered.
  const recs = await runPool(taskFiles, concurrency, runTask);
  report.tasks = recs.filter(Boolean).sort((a: any, b: any) => a.id.localeCompare(b.id));

  // Phase 5 — report + exit code.
  report.ok = installOk && verifyOk && report.tasks.length > 0 && report.tasks.every((t: any) => t.ok);
  writeFileSync(join(runDir, 'report.json'), JSON.stringify(report, null, 2));
  printSummary(report, ts);
  process.exit(report.ok ? 0 : 1);
}


function runClaude(prompt: string, cwd: string, streamPath: string, timeoutMs: number,
  homeDir?: string, label?: string, resumeSessionId?: string): Promise<{
  code: number | null; timedOut: boolean; durationMs: number; costUsd: number | null;
  resultSummary: string; sessionId: string | null;
}> {
  return new Promise((resolve) => {
    const args = ['-p', prompt, '--verbose', '--output-format', 'stream-json', '--dangerously-skip-permissions'];
    // --resume continues an existing session as a new turn (used by the audit self-repair
    // loop): the agent keeps the context of what it already gathered and fixes only what's
    // broken. Same HOME below, so the session file is found.
    if (resumeSessionId) args.push('--resume', resumeSessionId);
    // Append our behavioral rules to Claude Code's default system prompt (keeps the native
    // skill listing). Inline because this CLI has no --append-system-prompt-file variant.
    if (SYSTEM_PROMPT) args.push('--append-system-prompt', SYSTEM_PROMPT);
    // Per-task HOME (+ CLAUDE_CONFIG_DIR) isolates Claude's writable state so concurrent
    // runs in the same container never clobber each other's sessions/projects/config.
    const env = homeDir
      ? { ...process.env, HOME: homeDir, CLAUDE_CONFIG_DIR: join(homeDir, '.claude') }
      : process.env;
    const tag = label ? `[${label}] ` : '';
    // stdin = /dev/null so `claude -p` doesn't wait 3s for piped input before starting.
    const child = spawn('claude', args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });
    const out = createWriteStream(streamPath);
    const start = Date.now();
    let buf = '';
    let lastResult: any = null;
    let timedOut = false;
    let lastActivity = '(no events yet)';
    let sessionId: string | null = null;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutMs);
    // Heartbeat: a silent `claude -p` and a hung one look identical from outside. Every
    // 30s, say how long we've been running and the last stream event we saw. The tag keeps
    // pulses attributable when several tasks run concurrently.
    const pulse = setInterval(() => {
      console.error(paint(DIM, `  · ${tag}still running (${Math.round((Date.now() - start) / 1000)}s) — last: ${lastActivity}`));
    }, 30_000);

    child.stdout.on('data', (d) => {
      out.write(d);
      buf += d.toString();
      let nl: number;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        if (!line.trim()) continue;
        try {
          const ev = JSON.parse(line);
          if (ev?.type === 'result') lastResult = ev;
          if (ev?.session_id) sessionId = ev.session_id; // last wins; needed to --resume for repair
          lastActivity = describeEvent(ev) ?? lastActivity;
          traceEvent(ev, tag, VERBOSE); // always on; --verbose appends full tool-input JSON
        } catch { /* partial/non-JSON */ }
      }
    });
    child.stderr.on('data', (d) => out.write(d));
    const done = (code: number | null, summary?: string) => {
      clearTimeout(timer); clearInterval(pulse); out.end();
      resolve({
        code, timedOut, durationMs: Date.now() - start,
        costUsd: lastResult?.total_cost_usd ?? null,
        resultSummary: summary ?? (lastResult ? (lastResult.subtype || 'result') : '(no result event)'),
        sessionId: lastResult?.session_id ?? sessionId,
      });
    };
    child.on('close', (code) => done(code));
    child.on('error', (err) => done(null, `spawn error: ${err.message}`));
  });
}

// One-line description of a stream-json event — used for the heartbeat's "last:" field.
function describeEvent(ev: any): string | null {
  if (ev?.type === 'system' && ev.subtype === 'init') return `session start (model ${ev.model})`;
  if (ev?.type === 'assistant') {
    const tool = (ev.message?.content ?? []).find((c: any) => c.type === 'tool_use');
    if (tool) return `${tool.name}${tool.name === 'Agent' || tool.name === 'Task' ? ` → ${tool.input?.subagent_type ?? '?'}` : ''}`;
    const text = (ev.message?.content ?? []).find((c: any) => c.type === 'text' && c.text?.trim());
    if (text) return 'assistant text';
  }
  if (ev?.type === 'result') return `result (${ev.subtype})`;
  return null;
}

// Live trace: one colored line per interesting stream event, prefixed so it reads distinctly
// from phase logs. Always on (so you see the current skill/tool without --verbose); `verbose`
// appends the full tool-input JSON. Color is gated by COLOR (see top); the full record is
// always in the .stream.jsonl.
function traceEvent(ev: any, tag = '', verbose = false) {
  if (ev?.type === 'system' && ev.subtype === 'init') {
    console.error(`    ${paint('38;5;177', '∙')} ${tag}${paint(DIM, `init model=${ev.model}`)}`);
  } else if (ev?.type === 'assistant') {
    for (const c of ev.message?.content ?? []) {
      if (c.type === 'tool_use') {
        const th = TOOL_COLOR[c.name] ?? DEFAULT_TOOL;
        const detail = toolDetail(c.name, c.input);
        const extra = verbose ? ' ' + JSON.stringify(c.input ?? {}).slice(0, 140) : '';
        console.error(`    ${paint(th.code, `${th.icon} ${tag}${c.name}`)} ${paint(DIM, detail + extra)}`);
      } else if (c.type === 'text' && c.text?.trim()) {
        console.error(`    ${paint(SAY, `✎ ${tag}${c.text.trim().replace(/\s+/g, ' ').slice(0, 160)}`)}`);
      }
    }
  } else if (ev?.type === 'result') {
    const cost = typeof ev.total_cost_usd === 'number' ? `$${ev.total_cost_usd.toFixed(4)}` : '?';
    console.error(`    ${paint('38;5;177', '∙')} ${tag}${paint(DIM, `result ${ev.subtype} cost=${cost} turns=${ev.num_turns ?? '?'}`)}`);
  }
}

// A short, human-readable summary of a tool call's input for the live trace — the meaningful
// field per family (skill name, subagent + model, the command/path/query), not raw JSON.
function toolDetail(name: string, input: any): string {
  const s = (v: any) => String(v ?? '').replace(/\s+/g, ' ').trim();
  if (name === 'Skill') return `→ ${s(input?.skill ?? input?.command) || '?'}`;
  if (name === 'Task' || name === 'Agent') {
    return `→ ${s(input?.subagent_type) || '?'}${input?.model ? ` [${s(input.model)}]` : ''}`;
  }
  if (name === 'Bash') return s(input?.command).slice(0, 100);
  if (name === 'Read' || name === 'Write' || name === 'Edit' || name === 'NotebookEdit') return s(input?.file_path).slice(0, 100);
  if (name === 'WebSearch') return s(input?.query).slice(0, 100);
  if (name === 'WebFetch') return s(input?.url).slice(0, 100);
  if (name === 'Grep' || name === 'Glob') return s(input?.pattern).slice(0, 100);
  return JSON.stringify(input ?? {}).slice(0, 100);
}

// Best-effort: copy the freshest Claude transcript for post-mortem (stream-json is primary).
// Scoped to this task's own HOME (when given), so concurrent tasks never grab each other's
// transcript — "newest jsonl" is unambiguous within a per-task projects dir.
function copyNewestTranscript(runDir: string, id: string, homeDir?: string) {
  try {
    const projects = join(homeDir ?? homedir(), '.claude', 'projects');
    if (!existsSync(projects)) return;
    const found: { path: string; mtime: number }[] = [];
    const walk = (dir: string) => {
      for (const e of readdirSync(dir, { withFileTypes: true })) {
        const p = join(dir, e.name);
        if (e.isDirectory()) walk(p);
        else if (e.name.endsWith('.jsonl')) found.push({ path: p, mtime: lstatSync(p).mtimeMs });
      }
    };
    walk(projects);
    if (!found.length) return;
    const newest = found.reduce((a, b) => (b.mtime > a.mtime ? b : a));
    copyFileSync(newest.path, join(runDir, `${id}.transcript.jsonl`));
  } catch { /* non-fatal */ }
}

function pointLatest(logsRoot: string, ts: string) {
  const latest = join(logsRoot, 'latest');
  try { rmSync(latest, { force: true }); } catch { /* ignore */ }
  try { symlinkSync(ts, latest); } catch { /* symlink optional */ }
}

function lastLine(s: string): string {
  return (s || '').trim().split('\n').filter(Boolean).pop() || '';
}

// Bounded worker pool: run `worker` over `items` with at most `limit` in flight at once.
// Results are returned in ORIGINAL item order regardless of completion order. limit=1 makes
// this a plain sequential loop. Items are leased off a shared cursor, so a slow task never
// blocks a free worker from picking up the next one.
async function runPool<T, R>(items: T[], limit: number, worker: (item: T, i: number) => Promise<R>): Promise<R[]> {
  const results = new Array(items.length) as R[];
  let next = 0;
  const workers = Math.max(1, Math.min(limit, items.length));
  await Promise.all(Array.from({ length: workers }, async () => {
    while (true) {
      const i = next++;
      if (i >= items.length) return;
      results[i] = await worker(items[i], i);
    }
  }));
  return results;
}

function printSummary(report: any, ts: string) {
  const line = '─'.repeat(64);
  console.log(`\n${line}`);
  console.log(`e2e report · ${ts} · ${report.ok ? 'PASS ✓' : 'FAIL ✗'}`);
  console.log(line);
  console.log(`install: ${report.phases.install.ok ? 'ok' : 'FAILED'}   `
    + `verify: ${report.phases.verifyInstall.ok ? 'ok' : 'FAILED'}`);
  for (const t of report.tasks) {
    const status = t.ok ? 'PASS' : 'FAIL';
    const detail = `${t.pdf?.bytes ? `${t.pdf.bytes}b` : (t.pdf?.count ?? 0) + ' pdfs'}`
      + `${t.claude?.timedOut ? ' (TIMED OUT)' : ''}`
      + `${t.claude?.durationMs ? ` ${Math.round(t.claude.durationMs / 1000)}s` : ''}`
      + `${t.audit ? (t.audit.ok ? ' audit✓' : ' audit✗') : ''}`
      + `${t.claude?.repairs?.length ? ` +${t.claude.repairs.length} repair` : ''}`;
    console.log(`  ${status.padEnd(4)}  ${t.id.padEnd(24)} ${detail}`);
  }
  console.log(line);
  console.log(`PDFs:   test/e2e/pdfs/`);
  console.log(`logs:   test/e2e/logs/${ts}/  (also test/e2e/logs/latest)`);
  console.log(`${line}\n`);
}
