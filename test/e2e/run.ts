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
// baked into the image. Model selection (Sonnet + Haiku) is baked into the image ENV.

import { spawn, spawnSync } from 'node:child_process';
import {
  existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync, appendFileSync,
  copyFileSync, createWriteStream, rmSync, symlinkSync, lstatSync,
} from 'node:fs';
import { createServer } from 'node:http';
import { join, basename, extname, resolve as pathResolve } from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';

// Secrets the harness forwards into the container (inline > .env file > unset).
const FORWARD_KEYS = ['ANTHROPIC_API_KEY', 'FMP_API_KEY', 'FINMIND_TOKEN', 'SEC_EDGAR_USER_AGENT'];
const DEFAULT_TIMEOUT_MS = 20 * 60 * 1000;

// run.ts lives at <repo>/test/e2e/run.ts → repo root is two levels up. `import.meta.dir`
// is set by Bun; fall back to deriving it from the URL for plain node.
const HERE = (import.meta as any).dir ?? new URL('.', import.meta.url).pathname;
const REPO_ROOT = pathResolve(HERE, '..', '..');

const argv = process.argv.slice(2);
const IN_CONTAINER = argv.includes('--in-container');
const taskFilter = flagValue(argv, '--task');
// After a host run finishes, auto-start a local server for the JSONL log viewer.
// Off in CI / when piping, or via --no-viewer / E2E_NO_VIEWER.
const NO_VIEWER = argv.includes('--no-viewer') || !!process.env.E2E_NO_VIEWER || !!process.env.CI;

if (IN_CONTAINER) {
  await runInContainer(taskFilter);
} else {
  hostMode(argv.filter((a) => a !== '--in-container' && a !== '--no-viewer'));
}

function flagValue(args: string[], name: string): string | null {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

// ── HOST MODE ──────────────────────────────────────────────────────────────────────────
function hostMode(passthrough: string[]) {
  loadDotEnv(join(REPO_ROOT, 'test', 'e2e', '.env')); // optional convenience; never overrides

  if (!process.env.ANTHROPIC_API_KEY) {
    fail('ANTHROPIC_API_KEY is required. Set it inline, e.g.\n'
      + '  ANTHROPIC_API_KEY=sk-… bun test/e2e/run.ts [--task <id>]');
  }
  if (!hasCmd('devcontainer')) {
    fail('the devcontainer CLI is not installed.\n  npm i -g @devcontainers/cli');
  }

  const present = FORWARD_KEYS.filter((k) => process.env[k]);

  console.error('▶ bringing the dev container up …');
  const up = spawnSync('devcontainer', ['up', '--workspace-folder', REPO_ROOT], { encoding: 'utf8' });
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

  const envArgs = present.flatMap((k) => ['-e', `${k}=${process.env[k]}`]);
  const cmd = [
    'exec', ...envArgs, '-u', user, '-w', remoteWs, info.containerId,
    'bun', `${remoteWs}/test/e2e/run.ts`, '--in-container', ...passthrough,
  ];
  console.error(`▶ running harness in ${info.containerId.slice(0, 12)} (forwarding: ${present.join(', ') || 'none'})`);
  const r = spawnSync('docker', cmd, { stdio: 'inherit' });
  const status = r.status ?? 1;

  // The container wrote logs to the mounted workspace, so they're on the host now.
  // Serve them through viewer.html and stay up until the user stops the process.
  if (NO_VIEWER) process.exit(status);
  startViewer(join(REPO_ROOT, 'test', 'e2e'), status);
}

// ── LOG VIEWER ─────────────────────────────────────────────────────────────────────────
// A zero-dependency static server scoped to test/e2e/, so viewer.html can fetch the run's
// `*.stream.jsonl` via ?file=. Stays alive (keeps the event loop busy) until Ctrl+C, then
// exits with the run's real status so scripted callers still see pass/fail.
function startViewer(e2eDir: string, status: number): void {
  const root = pathResolve(e2eDir);
  const latest = join(root, 'logs', 'latest');
  const streams = existsSync(latest)
    ? readdirSync(latest).filter((f) => f.endsWith('.stream.jsonl')).sort()
    : [];
  if (!streams.length) {
    console.error('▶ no stream logs to view; skipping viewer.');
    process.exit(status);
  }

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
      res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream' });
      res.end(readFileSync(file));
    } catch { res.writeHead(500); res.end('error'); }
  });

  const basePort = Number(process.env.E2E_VIEWER_PORT) || 8787;
  const listen = (port: number, tries: number) => {
    server.once('error', (e: any) => {
      if (e.code === 'EADDRINUSE' && tries > 0) listen(port + 1, tries - 1);
      else { console.error(`✗ could not start viewer: ${e.message}`); process.exit(status); }
    });
    server.listen(port, '127.0.0.1', () => {
      const base = `http://127.0.0.1:${port}`;
      const urls = streams.map((f) => `${base}/viewer.html?file=logs/latest/${f}`);
      const bar = '─'.repeat(64);
      console.log(`\n${bar}`);
      console.log(`▶ log viewer running at ${base}/viewer.html  (Ctrl+C to stop)`);
      streams.forEach((f, i) => console.log(`    ${f.replace(/\.stream\.jsonl$/, '').padEnd(24)} ${urls[i]}`));
      console.log(bar);
      openBrowser(urls[0]);
      const stop = () => { try { server.close(); } catch { /* ignore */ } process.exit(status); };
      process.on('SIGINT', stop);
      process.on('SIGTERM', stop);
    });
  };
  listen(basePort, 10);
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

function loadDotEnv(file: string) {
  if (!existsSync(file)) return;
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
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
async function runInContainer(filter: string | null) {
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
  const log = (m: string) => { console.log(m); appendFileSync(join(runDir, 'run.log'), m + '\n'); };

  const skills: any[] = getSkills();
  const folderByName = new Map(skills.map((s) => [s.name, s.folder]));
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

  // Phase 1b — install agent definitions (e.g. the Haiku-powered data-extractor), so
  // tasks can delegate data gathering to a cheap model instead of burning premium turns.
  const agentsSrc = join(e2e, 'agents');
  const agentsHome = join(homedir(), '.claude', 'agents');
  const agentFiles = existsSync(agentsSrc) ? readdirSync(agentsSrc).filter((f) => f.endsWith('.md')) : [];
  mkdirSync(agentsHome, { recursive: true });
  for (const f of agentFiles) copyFileSync(join(agentsSrc, f), join(agentsHome, f));
  report.phases.agents = { ok: true, installed: agentFiles };
  log(`Phase 1b · agents — ${agentFiles.length} agent definitions → ${agentsHome}`);

  // Phase 2 — verify each skill folder landed.
  const verify = skills.map((s) => ({ skill: s.folder, present: existsSync(join(skillsHome, s.folder, 'SKILL.md')) }));
  const verifyOk = verify.every((v) => v.present);
  report.phases.verifyInstall = { ok: verifyOk, skillsHome, results: verify };
  log(`Phase 2 · verify — ${verify.filter((v) => v.present).length}/${verify.length} skill folders present`);
  for (const v of verify) if (!v.present) log(`  ✗ missing: ${v.skill}`);

  // Discover tasks (skip TEMPLATE.md — it isn't *.task.md).
  const tasksDir = join(e2e, 'tasks');
  let taskFiles = readdirSync(tasksDir).filter((f) => f.endsWith('.task.md')).sort();

  for (const file of taskFiles) {
    const raw = readFileSync(join(tasksDir, file), 'utf8');
    const { data, body } = parseFrontmatter(raw);
    const id: string = (data && data.id) || file.replace(/\.task\.md$/, '');
    const stem = file.replace(/\.task\.md$/, '');
    if (filter && filter !== id && filter !== stem) continue;

    const rec: any = { id, file, ok: false };
    const timeoutMs = Number(data?.timeoutMs) || DEFAULT_TIMEOUT_MS;
    const requiresEnv: string[] = Array.isArray(data?.requiresEnv) ? data.requiresEnv : [];
    const requiresSkills: string[] = Array.isArray(data?.skills) ? data.skills : [];

    // Fail fast on declared-but-missing prerequisites (don't burn a Claude run).
    const missingEnv = requiresEnv.filter((k) => !process.env[k]);
    const missingSkills = requiresSkills.filter((s) => !existsSync(join(skillsHome, folderByName.get(s) || s, 'SKILL.md')));
    if (missingEnv.length || missingSkills.length) {
      rec.skipped = { missingEnv, missingSkills };
      log(`Phase 3 · task ${id} — SKIPPED (missing ${[...missingEnv, ...missingSkills.map((s) => `skill:${s}`)].join(', ')})`);
      report.tasks.push(rec);
      continue;
    }

    // Run the agent in an isolated cwd; deliverable lands in output/ (see the contract).
    const workdir = `/tmp/run/${id}`;
    const outdir = join(workdir, 'output');
    mkdirSync(outdir, { recursive: true });
    // Pre-inject environment facts + workflow guidance as project memory, so the agent
    // never spends turns probing the environment or doing work a script/cheap model should.
    writeFileSync(join(workdir, 'CLAUDE.md'), envBrief(id));
    const prompt = (body || '').trim() + outputContractFooter(id);

    log(`Phase 3 · task ${id} — claude -p (timeout ${Math.round(timeoutMs / 1000)}s, cwd ${workdir})`);
    const res = await runClaude(prompt, workdir, join(runDir, `${id}.stream.jsonl`), timeoutMs);
    writeFileSync(join(runDir, `${id}.log`),
      [`task: ${id}`, `cwd: ${workdir}`, `exit: ${res.code}`, `timedOut: ${res.timedOut}`,
        `durationMs: ${res.durationMs}`, `costUsd: ${res.costUsd}`, `result: ${res.resultSummary}`].join('\n') + '\n');
    copyNewestTranscript(runDir, id);

    // Phase 3b — platform post-processing: if the agent left an HTML deliverable but no
    // PDF, convert it here. HTML→PDF is the harness's job, not a turn the agent spends.
    const listBy = (dir: string, ext: string) =>
      existsSync(dir) ? readdirSync(dir).filter((f) => f.toLowerCase().endsWith(ext)) : [];
    if (listBy(outdir, '.pdf').length === 0) {
      const htmls = listBy(outdir, '.html').map((f) => join(outdir, f))
        .concat(listBy(workdir, '.html').map((f) => join(workdir, f)));
      // Prefer the contracted name, else the most recently written candidate.
      const pick = htmls.find((p) => basename(p) === `${id}.html`)
        ?? htmls.sort((a, b) => lstatSync(b).mtimeMs - lstatSync(a).mtimeMs)[0];
      if (pick) {
        const conv = spawnSync('html2pdf', [pick, join(outdir, `${id}.pdf`)], { encoding: 'utf8' });
        rec.autoPdf = { from: basename(pick), ok: conv.status === 0 };
        log(`  · auto-converted ${basename(pick)} → ${id}.pdf${conv.status === 0 ? '' : ` (FAILED: ${lastLine(conv.stderr || conv.stdout)})`}`);
      }
    }

    // Phase 4 — verify exactly one valid, non-empty PDF.
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
    }
    rec.claude = { code: res.code, timedOut: res.timedOut, durationMs: res.durationMs, costUsd: res.costUsd };
    report.tasks.push(rec);
    log(`  → ${rec.ok ? '✓ valid PDF' : '✗ no valid PDF'}${rec.pdf?.bytes ? ` (${rec.pdf.bytes} bytes)` : ''}`);
  }

  // Phase 5 — report + exit code.
  report.ok = installOk && verifyOk && report.tasks.length > 0 && report.tasks.every((t: any) => t.ok);
  writeFileSync(join(runDir, 'report.json'), JSON.stringify(report, null, 2));
  printSummary(report, ts);
  process.exit(report.ok ? 0 : 1);
}

function outputContractFooter(id: string): string {
  return `\n\n---\nOUTPUT CONTRACT (added by the test harness): Produce the final deliverable as a SINGLE `
    + `self-contained HTML file at the relative path \`output/${id}.html\` in your current working `
    + `directory (inline all scripts and data — it is rendered offline). The harness converts it to `
    + `\`output/${id}.pdf\` automatically after your run; do NOT run html2pdf yourself. Writing `
    + `\`output/${id}.pdf\` directly is also accepted. Create no other files in output/.`;
}

// Pre-verified environment brief, written to the task workdir as CLAUDE.md (auto-loaded
// project memory). Everything here is guaranteed by the image/harness, so the agent must
// not spend turns re-checking it — and the workflow section routes expensive work to
// scripts and to the cheap data-extractor agent.
function envBrief(id: string): string {
  const present = FORWARD_KEYS.filter((k) => process.env[k]);
  const absent = FORWARD_KEYS.filter((k) => !process.env[k]);
  return `# Environment (pre-verified by the harness — do NOT spend turns re-checking any of this)

- On PATH, preinstalled: \`python3\` (with polars, pandas, requests), \`bun\` (runs TypeScript
  directly — no npm install needed), \`node\`, \`git\`, \`curl\`, \`html2pdf\`.
- Skills are installed at \`~/.claude/skills/<name>/\` (read each skill's SKILL.md when you use it).
- API keys set in env: ${present.join(', ') || '(none)'}.${absent.length ? ` NOT set: ${absent.join(', ')}.` : ''}
- \`output/\` already exists in this directory.

# How to work (cost discipline)

1. **Data gathering → delegate.** Use the Task tool with the \`data-extractor\` agent (it runs
   on a cheap, fast model) for ALL external data: API calls, web search, IR pages. Ask it for
   raw JSON records (\`[{"date": "YYYY-MM-DD", "<metric>": <absolute USD value>, …}]\`) and tell
   it the company, metrics, period range, and granularity. Do not web-search or fetch yourself.
2. **Derived numbers → compute, never in your head.** YoY growth, margins, rebasing etc. come
   from the charting skill's Polars pipeline, e.g.
   \`cd ~/.claude/skills/charting && python3 -m pipeline.cli yoy /tmp/data.json --metrics revenue,bookings --lag 4 -o /tmp/contract.json\`
3. **Charts → render, never hand-write.** \`bun ~/.claude/skills/charting/scripts/render.ts /tmp/contract.json output/${id}.html\`
   emits a finished, self-contained Highcharts page (works offline; PDF-safe).
4. **PDF is automatic.** Write the final self-contained HTML to \`output/${id}.html\` and stop —
   the harness converts it to PDF after your run. Only call \`html2pdf\` if you must inspect the PDF.
`;
}

function runClaude(prompt: string, cwd: string, streamPath: string, timeoutMs: number): Promise<{
  code: number | null; timedOut: boolean; durationMs: number; costUsd: number | null; resultSummary: string;
}> {
  return new Promise((resolve) => {
    const args = ['-p', prompt, '--verbose', '--output-format', 'stream-json', '--dangerously-skip-permissions'];
    // stdin = /dev/null so `claude -p` doesn't wait 3s for piped input before starting.
    const child = spawn('claude', args, { cwd, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    const out = createWriteStream(streamPath);
    const start = Date.now();
    let buf = '';
    let lastResult: any = null;
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutMs);

    child.stdout.on('data', (d) => {
      out.write(d);
      buf += d.toString();
      let nl: number;
      while ((nl = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
        if (!line.trim()) continue;
        try { const ev = JSON.parse(line); if (ev?.type === 'result') lastResult = ev; } catch { /* partial/non-JSON */ }
      }
    });
    child.stderr.on('data', (d) => out.write(d));
    const done = (code: number | null, summary?: string) => {
      clearTimeout(timer); out.end();
      resolve({
        code, timedOut, durationMs: Date.now() - start,
        costUsd: lastResult?.total_cost_usd ?? null,
        resultSummary: summary ?? (lastResult ? (lastResult.subtype || 'result') : '(no result event)'),
      });
    };
    child.on('close', (code) => done(code));
    child.on('error', (err) => done(null, `spawn error: ${err.message}`));
  });
}

// Best-effort: copy the freshest Claude transcript for post-mortem (stream-json is primary).
function copyNewestTranscript(runDir: string, id: string) {
  try {
    const projects = join(homedir(), '.claude', 'projects');
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

function printSummary(report: any, ts: string) {
  const line = '─'.repeat(64);
  console.log(`\n${line}`);
  console.log(`e2e report · ${ts} · ${report.ok ? 'PASS ✓' : 'FAIL ✗'}`);
  console.log(line);
  console.log(`install: ${report.phases.install.ok ? 'ok' : 'FAILED'}   `
    + `verify: ${report.phases.verifyInstall.ok ? 'ok' : 'FAILED'}`);
  for (const t of report.tasks) {
    const status = t.skipped ? 'SKIP' : (t.ok ? 'PASS' : 'FAIL');
    const detail = t.skipped
      ? `missing ${[...(t.skipped.missingEnv || []), ...(t.skipped.missingSkills || [])].join(', ')}`
      : `${t.pdf?.bytes ? `${t.pdf.bytes}b` : (t.pdf?.count ?? 0) + ' pdfs'}`
        + `${t.claude?.timedOut ? ' (TIMED OUT)' : ''}`
        + `${t.claude?.durationMs ? ` ${Math.round(t.claude.durationMs / 1000)}s` : ''}`;
    console.log(`  ${status.padEnd(4)}  ${t.id.padEnd(24)} ${detail}`);
  }
  console.log(line);
  console.log(`PDFs:   test/e2e/pdfs/`);
  console.log(`logs:   test/e2e/logs/${ts}/  (also test/e2e/logs/latest)`);
  console.log(`${line}\n`);
}
