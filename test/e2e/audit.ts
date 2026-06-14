// Provenance audit — the post-run integrity gate for each task's deliverable.
//
// WHY THIS EXISTS: the harness's pass/fail check is "is there one valid PDF?", which is
// far too shallow. A run can produce a perfectly-formed report that credits its numbers to
// a data source it never actually queried (observed: a report attributing Delta monthly
// revenue to "FINMIND API (TaiwanStockMonthRevenue dataset)" when finmind was never invoked
// and the figures were back-solved from web searches). That is fabrication, and a stronger
// executor model does not reliably prevent it — so we DETECT it after the fact.
//
// HOW: build a deterministic EVIDENCE LEDGER of every tool the agent actually used, then let
// a cheap judge model check that every source the deliverable cites is backed by the ledger.
// The ledger is ground truth (never the model's guess); the judge only does fuzzy matching of
// prose claims → ledger lines. This is the adversarial-verify pattern, and it works
// regardless of which model produced the report.
//
// THE LOAD-BEARING DETAIL: a sub-agent's tool calls do NOT appear in the main `stream.jsonl`
// (an Agent call records only the returned text) nor in the single copied `transcript.jsonl`.
// They live in separate session files under the task's own ~/.claude/projects/. So the ledger
// is built by walking EVERY *.jsonl under the task HOME — main session plus every sub-agent.
// Miss this and you get false flags in both directions: a real source used only inside a
// sub-agent looks fabricated, and a fabricated one can hide behind an unseen sub-agent.

import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, lstatSync } from 'node:fs';
import { join, basename } from 'node:path';

const JUDGE_TIMEOUT_MS = 150_000;
const MAX_TEXT_CHARS = 18_000; // deliverables are a few KB of text; cap defensively.

// ── EVIDENCE LEDGER ──────────────────────────────────────────────────────────────────────
// A compact, deterministic summary of what the agent (and its sub-agents) actually did.
export interface Ledger {
  skillsInvoked: string[];
  externalHosts: string[];
  skillScriptsReferenced: string[];
  subagentsLaunched: string[];
  webSearchCount: number;
  toolCounts: Record<string, number>;
}

export function buildLedger(taskHome: string, extraStreamPaths: string[] = []): Ledger {
  const skills = new Set<string>();
  const hosts = new Set<string>();
  const scripts = new Set<string>();
  const subagents = new Set<string>();
  const toolCounts: Record<string, number> = {};
  let webSearch = 0;

  const consume = (obj: any) => {
    const content = obj?.message?.content;
    if (!Array.isArray(content)) return;
    for (const b of content) {
      if (!b || b.type !== 'tool_use') continue;
      const name: string = b.name || '?';
      const inp = b.input || {};
      toolCounts[name] = (toolCounts[name] || 0) + 1;
      if (name === 'Skill' && inp.skill) skills.add(String(inp.skill));
      else if (name === 'WebSearch') webSearch++;
      else if (name === 'WebFetch' && inp.url) { const h = hostOf(String(inp.url)); if (h) hosts.add(h); }
      else if (name === 'Bash' && inp.command) {
        const cmd = String(inp.command);
        for (const m of cmd.matchAll(/https?:\/\/([A-Za-z0-9.\-]+)/g)) hosts.add(m[1]);
        for (const m of cmd.matchAll(/skills\/([a-z0-9][a-z0-9-]*)\//g)) scripts.add(m[1]);
      } else if ((name === 'Task' || name === 'Agent') && inp.subagent_type) {
        subagents.add(String(inp.subagent_type));
      }
    }
  };

  // Walk every transcript under the task HOME — captures main + all sub-agent sessions.
  for (const f of walkJsonl(join(taskHome, '.claude', 'projects'))) {
    for (const line of readLines(f)) { const o = tryParse(line); if (o) consume(o); }
  }
  // Supplement with explicit stream logs (the main thread is always fully present there).
  for (const sp of extraStreamPaths) {
    if (!existsSync(sp)) continue;
    for (const line of readLines(sp)) { const o = tryParse(line); if (o) consume(o); }
  }

  return {
    skillsInvoked: [...skills].sort(),
    externalHosts: [...hosts].sort(),
    skillScriptsReferenced: [...scripts].sort(),
    subagentsLaunched: [...subagents].sort(),
    webSearchCount: webSearch,
    toolCounts,
  };
}

// ── DELIVERABLE + SELF-DECLARED PROVENANCE ─────────────────────────────────────────────────
// The report text (what a reader trusts) and the agent's own data_sources.md (operating-rule
// #2). The judge cross-checks the report against BOTH the ledger and this self-report.
function extractDeliverableText(outdir: string, workdir: string, id: string): string {
  const htmls = listBy(outdir, '.html').map((f) => join(outdir, f))
    .concat(listBy(workdir, '.html').map((f) => join(workdir, f)));
  const html = htmls.find((p) => basename(p) === `${id}.html`)
    ?? htmls.sort((a, b) => lstatSync(b).mtimeMs - lstatSync(a).mtimeMs)[0];
  if (html) return cap(htmlToText(readFileSync(html, 'utf8')));

  // No HTML — fall back to extracting text from the PDF (needs pdftotext on PATH).
  const pdfs = listBy(outdir, '.pdf').map((f) => join(outdir, f));
  const pdf = pdfs.find((p) => basename(p) === `${id}.pdf`) ?? pdfs[0];
  if (pdf && hasCmd('pdftotext')) {
    const r = spawnSync('pdftotext', ['-q', pdf, '-'], { encoding: 'utf8' });
    if (r.status === 0 && r.stdout) return cap(r.stdout.replace(/\s+/g, ' ').trim());
  }
  return '';
}

function readDataSources(workdir: string): string {
  const p = join(workdir, 'data_sources.md');
  return existsSync(p) ? cap(readFileSync(p, 'utf8')) : '';
}

// ── THE JUDGE ──────────────────────────────────────────────────────────────────────────────
export interface Finding { source: string; status: 'SUPPORTED' | 'UNSUPPORTED' | 'PARTIAL'; evidence: string; note: string; }
export interface Verdict { ok: boolean; verdict: 'pass' | 'fail' | 'error'; summary: string; findings: Finding[]; ledger?: Ledger; }

export async function auditTask(opts: {
  taskHome: string; streamPath?: string; outdir: string; workdir: string; id: string;
  model?: string; auditHome?: string;
}): Promise<Verdict> {
  const { taskHome, streamPath, outdir, workdir, id, model = 'haiku', auditHome } = opts;
  const ledger = buildLedger(taskHome, streamPath ? [streamPath] : []);
  const text = extractDeliverableText(outdir, workdir, id);
  if (!text) {
    // Can't read what the report claims → can't audit. Fail OPEN (don't block the run on an
    // extraction gap), but say so loudly via the verdict.
    return { ok: true, verdict: 'error', summary: 'no deliverable text to audit (no HTML and no pdftotext)', findings: [], ledger };
  }
  const dataSources = readDataSources(workdir);
  try {
    const v = await runJudge(ledger, text, dataSources, model, auditHome);
    return { ...v, ledger };
  } catch (e: any) {
    // Judge infra failure (model unavailable, timeout, unparseable) → fail OPEN.
    return { ok: true, verdict: 'error', summary: `audit judge failed: ${e?.message ?? e}`, findings: [], ledger };
  }
}

function runJudge(ledger: Ledger, deliverable: string, dataSources: string, model: string, auditHome?: string): Promise<Verdict> {
  return new Promise((resolve, reject) => {
    const prompt = buildJudgePrompt(ledger, deliverable, dataSources);
    const env = auditHome ? { ...process.env, HOME: auditHome, CLAUDE_CONFIG_DIR: join(auditHome, '.claude') } : process.env;
    // A clean, tool-free reasoning call: cheap model, JSON output, its own minimal HOME so it
    // doesn't load the 18 installed skills it has no use for.
    const args = ['-p', prompt, '--model', model, '--output-format', 'json', '--dangerously-skip-permissions'];
    const child = spawn('claude', args, { cwd: auditHome || process.cwd(), env, stdio: ['ignore', 'pipe', 'pipe'] });
    let out = ''; let err = '';
    const timer = setTimeout(() => { child.kill('SIGKILL'); reject(new Error('judge timed out')); }, JUDGE_TIMEOUT_MS);
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('error', (e) => { clearTimeout(timer); reject(e); });
    child.on('close', () => {
      clearTimeout(timer);
      try {
        // `--output-format json` prints one envelope object; the model's answer is .result.
        const envelope = JSON.parse(out.trim().split('\n').filter(Boolean).pop() || out);
        const inner = parseJsonLoose(typeof envelope.result === 'string' ? envelope.result : out);
        const findings: Finding[] = Array.isArray(inner.findings) ? inner.findings : [];
        const ok = inner.verdict ? inner.verdict === 'pass' : !findings.some((f) => f.status && f.status !== 'SUPPORTED');
        resolve({ ok, verdict: inner.verdict || (ok ? 'pass' : 'fail'), summary: inner.summary || '', findings });
      } catch (e: any) {
        reject(new Error(`unparseable judge output: ${e?.message ?? e}; stderr=${err.slice(0, 200)}`));
      }
    });
  });
}

function buildJudgePrompt(ledger: Ledger, deliverable: string, dataSources: string): string {
  return `You are a data-provenance auditor for an automated financial-research pipeline. Your one job: catch FABRICATED or UNSUPPORTED source attributions — where a report credits its numbers to a source/API/dataset/filing that was never actually queried during the run.

<evidence_ledger>
${JSON.stringify(ledger, null, 2)}
</evidence_ledger>

The ledger is GROUND TRUTH: every skill invoked, external host contacted, skill script run, and web-search activity for the whole run (main agent AND its sub-agents). If a data source is not represented here, it was NOT used.

${dataSources ? `<agent_self_reported_provenance>\n${dataSources}\n</agent_self_reported_provenance>\n\nThis is the agent's own data_sources.md. Treat it as a CLAIM, not proof — a row here is only trustworthy if the ledger backs it.\n` : ''}
<deliverable_text>
${deliverable}
</deliverable_text>

Identify every distinct data source, provider, API, dataset, filing, or feed the deliverable cites or attributes numbers to (e.g. "FINMIND API", "Financial Modeling Prep", "SEC 10-Q", "TWSE monthly filings", "Bloomberg"). For each, classify:
- SUPPORTED — the ledger shows a matching skill, host, or script that plausibly provides this data.
- UNSUPPORTED — nothing in the ledger could have produced data from this source; it appears fabricated.
- PARTIAL — the source was touched but the specific claim isn't fully backed (e.g. quarterly fetched but monthly claimed), OR figures the report presents as sourced were actually estimated/derived/null per the self-reported provenance.

Map sources to evidence: FINMIND → finmind skill OR api.finmindtrade.com; Financial Modeling Prep/FMP → financialmodellingprep skill OR financialmodelingprep.com; SEC/EDGAR/10-Q → sec-filings skill OR sec.gov; a provider with NO matching skill/host (Bloomberg, Refinitiv, FactSet, Koyfin, …) is almost certainly UNSUPPORTED. Judge ONLY from the ledger — never assume a source was used unless the ledger shows it.

Respond with ONLY a JSON object, no prose, no code fence:
{"verdict":"pass"|"fail","findings":[{"source":"<as cited>","status":"SUPPORTED|UNSUPPORTED|PARTIAL","evidence":"<ledger item or 'none'>","note":"<short>"}],"summary":"<one sentence>"}
verdict is "fail" if ANY source is UNSUPPORTED, or if a PARTIAL reflects undisclosed estimated/fabricated figures.`;
}

// ── REMEDIATION ──────────────────────────────────────────────────────────────────────────
// Composed from the judge's findings and handed back to the SAME agent session (via resume),
// so it keeps the context of what it already gathered and fixes only what's broken.
export function buildRemediationPrompt(id: string, findings: Finding[]): string {
  const bad = findings.filter((f) => f.status !== 'SUPPORTED');
  const list = bad.map((f, i) =>
    `${i + 1}. "${f.source}" — ${f.status}: ${f.note} (ledger evidence: ${f.evidence || 'none'})`).join('\n');
  return `STOP — an automated data-provenance audit flagged the report you just produced. It must be fixed before it can ship. The audit compared every source the report cites against the tools you actually called this run, and these do not reconcile:

${list}

This violates the operating rules: every figure must trace to a source you actually fetched this run (rule 3), and skills come before the web (rule 1). For EACH flagged item, do ONE of the following — do not paper over it:

A. If the data is genuinely available, fetch the REAL figures using the right installed skill, then update the affected numbers. (For Taiwan-listed monthly revenue, the finmind skill exposes the TaiwanStockMonthRevenue dataset — use it instead of web search or estimation.)
B. If the data truly cannot be obtained, REMOVE the false source attribution and clearly disclose those figures as estimated/derived (state the method) in the report's sources/methodology section — or drop them.

Hard rule: cite ONLY data sources you actually queried in this session, and record each in data_sources.md. Do not credit a source you did not call.

Then re-render the report to the SAME path (output/${id}.* — keep the filename) so the deliverable is regenerated. Keep all other content intact.`;
}

// ── helpers ────────────────────────────────────────────────────────────────────────────────
function listBy(dir: string, ext: string): string[] {
  return existsSync(dir) ? readdirSync(dir).filter((f) => f.toLowerCase().endsWith(ext)) : [];
}

function* walkJsonl(dir: string): Generator<string> {
  if (!existsSync(dir)) return;
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) yield* walkJsonl(p);
    else if (e.name.endsWith('.jsonl')) yield p;
  }
}

function readLines(file: string): string[] {
  try { return readFileSync(file, 'utf8').split('\n').filter((l) => l.trim()); } catch { return []; }
}

function tryParse(line: string): any | null { try { return JSON.parse(line); } catch { return null; } }

function hostOf(url: string): string | null { const m = url.match(/^https?:\/\/([^/]+)/); return m ? m[1] : null; }

function htmlToText(html: string): string {
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ').trim();
}

// Keep head + tail when long — source/methodology notes usually live in footers, the title
// and lede up top; the middle is the chart/table body the judge needs least.
function cap(s: string): string {
  if (s.length <= MAX_TEXT_CHARS) return s;
  const half = Math.floor(MAX_TEXT_CHARS / 2);
  return `${s.slice(0, half)}\n…[trimmed]…\n${s.slice(-half)}`;
}

function parseJsonLoose(s: string): any {
  try { return JSON.parse(s); } catch { /* fall through */ }
  const cleaned = s.replace(/```(?:json)?/gi, '');
  const i = cleaned.indexOf('{'); const j = cleaned.lastIndexOf('}');
  if (i >= 0 && j > i) return JSON.parse(cleaned.slice(i, j + 1));
  throw new Error('no JSON object found');
}

function hasCmd(cmd: string): boolean {
  const r = spawnSync(cmd, ['-v'], { stdio: 'ignore' });
  return !(r.error && (r.error as any).code === 'ENOENT');
}
