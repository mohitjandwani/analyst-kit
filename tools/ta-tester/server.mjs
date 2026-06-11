/**
 * Manual test UI for the technical-analysis skill, fed by live FMP data.
 *
 *   node tools/ta-tester/server.mjs        # → http://127.0.0.1:8787
 *
 * Pipeline per run (exactly what an agent would do, see the skill's SKILL.md):
 *   FMP /historical-price-full → runs/<id>/prices.json
 *   → python3 skills/technical-analysis/scripts/indicators.py
 *   → bun skills/charting/scripts/render.ts   (dashboard + levels HTML)
 *   → optional: bun skills/reporting/scripts/render.ts (branded PDF)
 *
 * Reads FMP_API_KEY from the repo .env (never sent to the browser).
 */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..', '..');
const SKILL = join(ROOT, 'skills', 'technical-analysis');
const CHARTING = join(ROOT, 'skills', 'charting');
const REPORTING = join(ROOT, 'skills', 'reporting');
const RUNS = join(HERE, 'runs');
const PORT = Number(process.env.PORT || 8787);

function apiKey() {
  if (process.env.FMP_API_KEY) return process.env.FMP_API_KEY;
  const envFile = join(ROOT, '.env');
  if (existsSync(envFile)) {
    const m = readFileSync(envFile, 'utf8').match(/^FMP_API_KEY=(.+)$/m);
    if (m) return m[1].trim();
  }
  throw new Error('FMP_API_KEY not found — set it in the repo .env');
}

// ── pipeline steps ──────────────────────────────────────────────────────────

async function fetchPrices(ticker, timeframe) {
  const years = timeframe === 'weekly' ? 5.5 : 2.5; // engine resamples; always daily in
  const from = new Date(Date.now() - years * 365.25 * 86400e3).toISOString().slice(0, 10);
  const url = `https://financialmodelingprep.com/api/v3/historical-price-full/${
    encodeURIComponent(ticker)}?from=${from}&apikey=${apiKey()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`FMP returned HTTP ${res.status} — ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  if (!data?.historical?.length) throw new Error(`FMP has no daily history for "${ticker}" — check the ticker`);
  return data;
}

function run(cmd, args, cwd) {
  const r = spawnSync(cmd, args, { cwd, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(`${cmd} ${args[0]} failed:\n${r.stderr || r.stdout}`);
  return r.stdout;
}

async function analyze({ ticker, timeframe, risk, capital }) {
  const id = `${ticker}-${timeframe}`;
  const dir = join(RUNS, id);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'prices.json'), JSON.stringify(await fetchPrices(ticker, timeframe)));

  const args = [join(SKILL, 'scripts', 'indicators.py'), join(dir, 'prices.json'),
    '--out-dir', dir, '--timeframe', timeframe, '--symbol', ticker, '--risk-pct', String(risk)];
  if (capital) args.push('--capital', String(capital));
  run('python3', args);

  run('bun', ['scripts/render.ts', join(dir, 'dashboard-contract.json'), join(dir, 'dashboard.html')], CHARTING);
  run('bun', ['scripts/render.ts', join(dir, 'levels-contract.json'), join(dir, 'levels.html')], CHARTING);

  const analysis = JSON.parse(readFileSync(join(dir, 'analysis.json'), 'utf8'));
  return { id, analysis };
}

const money = (cur, v) => (v == null ? '—' : `${cur}${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

function buildReport(id) {
  const dir = join(RUNS, id);
  const a = JSON.parse(readFileSync(join(dir, 'analysis.json'), 'utf8'));
  const plan = a.levels[a.bias];
  const cur = a.meta.currency;
  const sc = a.tables.scorecard.rows.map((r) => `- ${r[0]}: ${r[1]}`).join('\n');
  const higher = a.regime_higher_tf;
  const report = {
    meta: { mode: 'report', title: `${a.meta.symbol} — Technical Analysis`,
      footer: 'Educational analysis, not financial advice' },
    pages: [
      { template: 'cover', slots: { title: a.meta.symbol, kicker: 'Technical Analysis',
        subtitle: `${a.meta.timeframe} timeframe · regime: ${a.regime.label} · as of ${a.meta.as_of}` } },
      { template: 'price-chart-technicals', slots: {
        title: 'Dashboard — price, volume, MACD, RSI',
        story: `${higher ? higher.timeframe + ' and ' : ''}${a.meta.timeframe} read: **${a.regime.label}** with confluence score ${a.scorecard.score >= 0 ? '+' : ''}${a.scorecard.score} — ${a.scorecard.verdict}.`,
        chart: './dashboard-contract.json',
        levels: plan ? [
          { value: plan.entry_ref, label: `Entry ${money(cur, plan.entry_ref)}`, kind: 'entry' },
          { value: plan.suggested_stop, label: `Stop ${money(cur, plan.suggested_stop)}`, kind: 'exit' },
        ] : [],
        commentary: [
          { heading: `Regime (${higher ? higher.timeframe + ' → ' : ''}${a.meta.timeframe})`,
            body: `${higher ? `${higher.timeframe[0].toUpperCase() + higher.timeframe.slice(1)}: ${higher.label} (ADX ${higher.adx14}). ` : ''}${a.meta.timeframe[0].toUpperCase() + a.meta.timeframe.slice(1)}: ${a.regime.label} (ADX ${a.regime.adx14}, ${a.regime.close_vs_long_ma ?? 'long MA n/a'}).` },
          { heading: 'Signals', body: a.signals.length
            ? a.signals.slice(0, 4).map((s) => `- ${s.signal} (${s.direction}, ${s.bars_ago} bars ago)`).join('\n')
            : 'No fresh triggers in the last 3 bars.' },
        ],
        stats: [
          { label: 'Score', value: `${a.scorecard.score >= 0 ? '+' : ''}${a.scorecard.score}` },
          { label: 'ADX(14)', value: String(a.regime.adx14 ?? '—') },
          { label: 'ATR(14)', value: money(cur, a.levels.atr14) },
        ],
        sources: [1, 2] } },
      { template: 'price-chart-technicals', slots: {
        title: 'Entry & exit levels',
        story: plan
          ? `Enter near ${money(cur, plan.entry_ref)} with the stop at ${money(cur, plan.suggested_stop)} (${plan.stop_distance_atr?.toFixed(1)}× ATR) — first target ${money(cur, plan.targets.r2)} (2R).`
          : 'Not enough history to compute a trade plan.',
        chart: './levels-contract.json',
        commentary: [
          { heading: 'The plan', body: plan?.sizing
            ? `Risk ${money(cur, plan.sizing.risk_amount)} on ${plan.sizing.shares} shares (${plan.sizing.pct_of_capital}% of capital). Trail with the chandelier at ${money(cur, plan.trail.chandelier_3atr)} or exit on a supertrend flip.`
            : 'Set --capital to size the position; stop and targets above are price-only.' },
        ],
        stats: plan ? [
          { label: 'Entry', value: money(cur, plan.entry_ref) },
          { label: 'Stop', value: money(cur, plan.suggested_stop) },
          { label: 'Target 2R', value: money(cur, plan.targets.r2) },
        ] : [],
        sources: [1, 2] } },
      { template: 'table-commentary', slots: {
        title: 'Trade plan & confluence scorecard',
        story: 'The trade is invalid when the entry condition reverses — exit on the signal, don\'t wait for the stop.',
        table: a.tables.levels,
        commentary: { heading: 'Confluence scorecard',
          body: `${sc}\nMean-reversion entries go stale after 5-10 bars without progress; breakout entries die on a close back inside the channel.` },
        sources: [2] } },
    ],
    references: [
      { label: `Daily OHLCV, ${a.meta.symbol}`, detail: 'Financial Modeling Prep /historical-price-full, adjusted close' },
      { label: 'Indicator & level computation', detail: 'technical-analysis engine (ATR-based stops, fractal swing structure)' },
    ],
  };
  writeFileSync(join(dir, 'report.json'), JSON.stringify(report, null, 1));
  run('bun', ['scripts/render.ts', join(dir, 'report.json'), join(dir, 'report.pdf')], REPORTING);
  return `/runs/${id}/report.pdf`;
}

// ── http ────────────────────────────────────────────────────────────────────

const MIME = { '.html': 'text/html', '.json': 'application/json', '.pdf': 'application/pdf' };

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>technical-analysis tester</title>
<style>
  body{font:14px/1.5 system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#1f2937}
  header{background:#1a3c6e;color:#fff;padding:14px 24px;font-size:17px;font-weight:600}
  header small{font-weight:400;opacity:.75;margin-left:10px}
  main{max-width:1080px;margin:0 auto;padding:20px 24px}
  form{display:flex;gap:10px;align-items:end;flex-wrap:wrap;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px}
  label{display:flex;flex-direction:column;font-size:12px;color:#64748b;gap:4px;font-weight:600}
  input,select{font:inherit;padding:7px 9px;border:1px solid #cbd5e1;border-radius:7px;width:110px}
  button{font:inherit;font-weight:600;padding:8px 18px;border:0;border-radius:7px;background:#1a3c6e;color:#fff;cursor:pointer}
  button:disabled{opacity:.5}
  button.alt{background:#e8a33d;color:#1f2937}
  #status{margin:14px 2px;color:#64748b}
  .err{color:#b91c1c;white-space:pre-wrap}
  .banner{border-radius:10px;padding:12px 16px;margin:14px 0;font-weight:600;border:1px solid}
  .long{background:#ecfdf5;border-color:#a7f3d0;color:#065f46}
  .short{background:#fef2f2;border-color:#fecaca;color:#991b1b}
  .flat{background:#f8fafc;border-color:#e2e8f0;color:#475569}
  .chips{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
  .chip{background:#fff;border:1px solid #e2e8f0;border-radius:7px;padding:5px 10px;font-size:12.5px}
  .chip b{color:#1a3c6e;margin-right:5px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
  .card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px}
  .card h3{margin:2px 0 8px;font-size:13px;color:#1a3c6e}
  table{border-collapse:collapse;width:100%;font-size:13px}
  td,th{padding:5px 8px;border-bottom:1px solid #f1f5f9;text-align:left}
  td:last-child{text-align:right;font-variant-numeric:tabular-nums}
  iframe{width:100%;border:1px solid #e2e8f0;border-radius:10px;background:#fff}
  .warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:8px;padding:8px 12px;margin:10px 0;font-size:13px}
  ul{margin:4px 0;padding-left:18px}
</style></head><body>
<header>technical-analysis · manual tester <small>live data via financialmodellingprep</small></header>
<main>
  <form id="f">
    <label>Ticker <input name="ticker" value="AAPL" required style="text-transform:uppercase"></label>
    <label>Timeframe <select name="timeframe"><option>daily</option><option>weekly</option></select></label>
    <label>Risk % <input name="risk" type="number" value="1.0" step="0.25" min="0.25" max="5"></label>
    <label>Capital <input name="capital" type="number" value="100000" step="1000"></label>
    <button id="go">Analyze</button>
    <button id="pdf" class="alt" type="button" hidden>Generate PDF report</button>
  </form>
  <div id="status"></div>
  <div id="out"></div>
</main>
<script>
const f = document.getElementById('f'), st = document.getElementById('status'),
      out = document.getElementById('out'), pdfBtn = document.getElementById('pdf');
let runId = null;
f.onsubmit = async (e) => {
  e.preventDefault();
  const q = new URLSearchParams(new FormData(f)); q.set('ticker', q.get('ticker').toUpperCase());
  st.textContent = 'Fetching FMP prices, computing indicators, rendering charts…';
  out.innerHTML = ''; pdfBtn.hidden = true; document.getElementById('go').disabled = true;
  try {
    const res = await fetch('/analyze?' + q);
    const j = await res.json();
    if (!res.ok) throw new Error(j.error || res.statusText);
    runId = j.id; render(j); st.textContent = '';
    pdfBtn.hidden = false;
  } catch (err) { st.innerHTML = '<div class="err">' + err.message.replace(/</g,'&lt;') + '</div>'; }
  document.getElementById('go').disabled = false;
};
pdfBtn.onclick = async () => {
  pdfBtn.disabled = true; st.textContent = 'Rendering PDF (Playwright)…';
  try {
    const res = await fetch('/report?id=' + encodeURIComponent(runId));
    const j = await res.json();
    if (!res.ok) throw new Error(j.error || res.statusText);
    st.textContent = ''; window.open(j.pdf, '_blank');
  } catch (err) { st.innerHTML = '<div class="err">' + err.message.replace(/</g,'&lt;') + '</div>'; }
  pdfBtn.disabled = false;
};
function tbl(t){ return '<table><thead><tr>' + t.columns.map(c=>'<th>'+c+'</th>').join('') +
  '</tr></thead><tbody>' + t.rows.map(r=>'<tr>'+r.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('') + '</tbody></table>'; }
function render({ id, analysis: a }) {
  const plan = a.levels[a.bias], cur = a.meta.currency, h = a.regime_higher_tf;
  const cls = a.scorecard.score >= 2 ? 'long' : a.scorecard.score <= -2 ? 'short' : 'flat';
  out.innerHTML =
    (a.meta.warnings.length ? '<div class="warn">⚠ ' + a.meta.warnings.join('<br>⚠ ') + '</div>' : '') +
    '<div class="banner ' + cls + '">' + a.meta.symbol + ' (' + a.meta.timeframe + ', as of ' + a.meta.as_of + '): ' +
      a.regime.label + ' · score ' + (a.scorecard.score >= 0 ? '+' : '') + a.scorecard.score + ' — ' + a.scorecard.verdict + '</div>' +
    '<div class="chips">' +
      (h ? '<span class="chip"><b>' + h.timeframe + ' regime</b>' + h.label + ' (ADX ' + h.adx14 + ')</span>' : '') +
      '<span class="chip"><b>' + a.meta.timeframe + ' regime</b>' + a.regime.label + ' (ADX ' + a.regime.adx14 + ')</span>' +
      '<span class="chip"><b>vs long MA</b>' + (a.regime.close_vs_long_ma ?? '—') + '</span>' +
      '<span class="chip"><b>BB squeeze</b>' + (a.regime.bb_squeeze ? 'yes' : 'no') + '</span>' +
      (plan ? '<span class="chip"><b>Entry</b>' + cur + plan.entry_ref + '</span>' +
              '<span class="chip"><b>Stop</b>' + cur + plan.suggested_stop + '</span>' +
              '<span class="chip"><b>2R</b>' + cur + plan.targets.r2 + '</span>' : '') +
    '</div>' +
    '<div class="cols">' +
      '<div class="card"><h3>Confluence scorecard</h3>' + tbl(a.tables.scorecard) + '</div>' +
      '<div class="card"><h3>Trade plan (' + a.bias + ')</h3>' + tbl(a.tables.levels) + '</div>' +
      '<div class="card"><h3>Recent signals</h3>' + (a.signals.length
        ? '<ul>' + a.signals.map(s=>'<li>' + s.signal + ' — <b>' + s.direction + '</b> (' + s.bars_ago + ' bars ago, ' + (s.date ?? '') + ')</li>').join('') + '</ul>'
        : '<p>No triggers in the last 3 bars.</p>') + '</div>' +
      '<div class="card"><h3>Last bars</h3><div style="max-height:180px;overflow:auto">' +
        tbl({ columns: ['date','close','rsi14','adx14','macd_hist','supertrend'],
              rows: a.recent.map(r=>[r.date, r.close, r.rsi14, r.adx14, r.macd_hist, r.supertrend]) }) + '</div></div>' +
    '</div>' +
    '<iframe src="/runs/' + id + '/dashboard.html" height="620"></iframe>' +
    '<iframe src="/runs/' + id + '/levels.html" height="480" style="margin-top:14px"></iframe>';
}
</script></body></html>`;

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const send = (code, type, body) => { res.writeHead(code, { 'content-type': type }); res.end(body); };
  const sendJson = (code, obj) => send(code, 'application/json', JSON.stringify(obj));
  try {
    if (url.pathname === '/') return send(200, 'text/html', PAGE);
    if (url.pathname === '/analyze') {
      const ticker = (url.searchParams.get('ticker') || '').toUpperCase().trim();
      if (!/^[A-Z0-9.^-]{1,12}$/.test(ticker)) return sendJson(400, { error: 'invalid ticker' });
      const timeframe = url.searchParams.get('timeframe') === 'weekly' ? 'weekly' : 'daily';
      const risk = Math.min(5, Math.max(0.25, Number(url.searchParams.get('risk')) || 1));
      const capital = Number(url.searchParams.get('capital')) || null;
      return sendJson(200, await analyze({ ticker, timeframe, risk, capital }));
    }
    if (url.pathname === '/report') {
      const id = url.searchParams.get('id') || '';
      if (!existsSync(join(RUNS, id, 'analysis.json'))) return sendJson(404, { error: 'run not found — analyze first' });
      return sendJson(200, { pdf: buildReport(id) });
    }
    if (url.pathname.startsWith('/runs/')) {
      const file = normalize(join(HERE, url.pathname));
      if (!file.startsWith(RUNS) || !existsSync(file)) return send(404, 'text/plain', 'not found');
      return send(200, MIME[extname(file)] || 'application/octet-stream', readFileSync(file));
    }
    send(404, 'text/plain', 'not found');
  } catch (err) {
    sendJson(500, { error: String(err.message || err) });
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`technical-analysis tester → http://127.0.0.1:${PORT}`);
});
