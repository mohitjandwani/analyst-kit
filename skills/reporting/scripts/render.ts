/**
 * Render a report contract to a branded PDF (or self-contained HTML).
 *
 *   bun scripts/render.ts report.json out/report.pdf
 *   bun scripts/render.ts report.json out/report.html --html-only
 *   bun scripts/render.ts report.json out/report.pdf --keep-html
 *   bun scripts/render.ts report.json out/report.pdf --brand my-brand.json
 *
 * Pipeline: contract → per-page template HTML → one paginated document
 * (vendored Highcharts from the sibling charting skill inlined once) →
 * Playwright prints it with CSS @page geometry (A4 portrait or 16:9 deck).
 * Paths inside the contract (chart contracts, brand, logo) resolve relative
 * to the file that mentions them.
 */
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, isAbsolute, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// The charting skill is a declared dependency (requires: [charting]) and is always
// installed side-by-side with this skill — same relative layout as in the repo.
import { buildOptions, optionsToJs, HELPERS_JS } from '../../charting/src/index.ts';
import type { FinalData } from '../../charting/src/types.ts';

const SKILL_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CHARTING = resolve(SKILL_ROOT, '..', 'charting');

// ── contract types ──────────────────────────────────────────────────────────

interface Brand {
  company?: string;
  logo?: string | null;
  logoPlacement?: 'top-left' | 'top-right';
  colors?: Partial<Record<'primary' | 'accent' | 'text' | 'muted' | 'background' | 'panel', string>>;
  fonts?: { body?: string; heading?: string };
  footerText?: string;
}

interface TextBlock { heading?: string; body: string }
type ChartSlot = string | { contract?: string; image?: string };
interface Page { template: string; slots: Record<string, any> }

interface ReportContract {
  meta: {
    mode: 'report' | 'presentation';
    title: string;
    subtitle?: string;
    date?: string;
    footer?: string;
  };
  brand?: string | Brand;
  pages: Page[];
}

function fail(msg: string): never {
  console.error(`reporting: ${msg}`);
  process.exit(1);
}

// ── small rendering helpers ─────────────────────────────────────────────────

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
}

/** Tiny markdown subset: **bold**, *italic*, lines starting "- " become bullets. */
function mdLite(s: string): string {
  const inline = (t: string) =>
    escapeHtml(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.+?)\*/g, '<em>$1</em>');
  const lines = String(s).split('\n');
  const out: string[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) out.push(`<ul>${bullets.map((b) => `<li>${b}</li>`).join('')}</ul>`);
    bullets = [];
  };
  for (const line of lines) {
    if (line.startsWith('- ')) bullets.push(inline(line.slice(2)));
    else { flush(); if (line.trim()) out.push(`<p>${inline(line)}</p>`); }
  }
  flush();
  return out.join('');
}

function textBlock(tb: TextBlock): string {
  return `<div class="tb">${tb.heading ? `<h3>${escapeHtml(tb.heading)}</h3>` : ''}${mdLite(tb.body)}</div>`;
}

const MIME: Record<string, string> = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp',
};
function dataUri(path: string): string {
  const mime = MIME[extname(path).toLowerCase()];
  if (!mime) fail(`unsupported image type: ${path}`);
  return `data:${mime};base64,${readFileSync(path).toString('base64')}`;
}

const resolveFrom = (base: string, p: string) => (isAbsolute(p) ? p : resolve(dirname(base), p));

// ── charts ──────────────────────────────────────────────────────────────────

interface ChartJob { id: string; js: string; stock: boolean }
const chartJobs: ChartJob[] = [];
let needsStock = false;
let needsMore = false;

/** Returns the HTML for a chart slot; queues Highcharts boot code when it's a contract. */
function chartHtml(slot: ChartSlot, contractPath: string, heightPx: number): string {
  const spec = typeof slot === 'string' ? { contract: slot } : slot;
  if (spec.image) {
    const p = resolveFrom(contractPath, spec.image);
    if (!existsSync(p)) fail(`chart image not found: ${p}`);
    return `<img src="${dataUri(p)}" style="height:${heightPx}px" alt="" />`;
  }
  if (!spec.contract) fail(`chart slot needs a "contract" path or an "image" path`);
  const p = resolveFrom(contractPath, spec.contract);
  if (!existsSync(p)) fail(`chart contract not found: ${p}`);
  const data = JSON.parse(readFileSync(p, 'utf8')) as FinalData;
  const stock = !!data.meta?.stock;
  needsStock ||= stock;
  needsMore ||= data.series.some((s) => s.kind === 'waterfall' || s.kind === 'arearange');
  // Print-tuned: no navigator/range-selector chrome (meaningless in a PDF), fixed height.
  const options = buildOptions(data, { navigator: false, rangeSelector: false });
  options.chart = { ...options.chart, height: heightPx, width: null };
  const id = `chart-${chartJobs.length}`;
  chartJobs.push({ id, js: optionsToJs(options), stock });
  return `<div id="${id}" class="chart-mount" style="height:${heightPx}px"></div>`;
}

// ── page templates ──────────────────────────────────────────────────────────

interface Ctx {
  meta: ReportContract['meta'];
  brand: Brand;
  logoUri: string | null;
  contractPath: string;
  deck: boolean; // presentation mode
}

function brandStrip(ctx: Ctx): string {
  const logo = ctx.logoUri ? `<img class="logo" src="${ctx.logoUri}" alt="" />` : '';
  const company = ctx.brand.company ? `<span class="company">${escapeHtml(ctx.brand.company)}</span>` : '';
  const [l, r] = ctx.brand.logoPlacement === 'top-right' ? [company, logo] : [logo, company];
  return l || r ? `<div class="brand-strip">${l || '<span></span>'}${r || ''}</div>` : '';
}

function titleBlock(slots: Record<string, any>): string {
  return `<div class="title-block"><h1>${escapeHtml(slots.title)}</h1>${
    slots.subtitle ? `<div class="subtitle">${escapeHtml(slots.subtitle)}</div>` : ''}</div>`;
}

function need(slots: Record<string, any>, tpl: string, keys: string[]): void {
  for (const k of keys) if (slots[k] === undefined) fail(`template "${tpl}" requires slot "${k}"`);
}

/** The point of the page — required on every data page. Rendered as a prominent
 *  banner under the title so a reader gets the conclusion before the evidence. */
function storyBanner(slots: Record<string, any>): string {
  return `<div class="story">${mdLite(slots.story)}</div>`;
}

/** Key-number chips (entry/exit price, latest YoY, …) — available on every template. */
function statsRow(slots: Record<string, any>): string {
  if (!slots.stats?.length) return '';
  return `<div class="stats-row">${slots.stats.map((s: any) =>
    `<span class="stat"><b>${escapeHtml(s.label)}</b> ${escapeHtml(s.value)}</span>`).join('')}</div>`;
}

/** Shared page top: brand strip, title, the page's story, key stats. */
function pageTop(slots: Record<string, any>, ctx: Ctx): string {
  return `${brandStrip(ctx)}${titleBlock(slots)}${storyBanner(slots)}${statsRow(slots)}`;
}

const RATING_KEYS = ['narrative', 'revenue', 'profit', 'purity'] as const;
const RATING_LABELS = ['Narrative', 'Revenue sens.', 'Profit sens.', 'Purity'];

const templates: Record<string, (slots: Record<string, any>, ctx: Ctx) => string> = {
  cover(slots, ctx) {
    need(slots, 'cover', ['title']);
    const logo = ctx.logoUri ? `<img class="logo-lg" src="${ctx.logoUri}" alt="" />` : '';
    const date = slots.date ?? ctx.meta.date;
    return `<div class="page-body">${logo}${
      slots.kicker ? `<div class="kicker">${escapeHtml(slots.kicker)}</div>` : ''
    }<h1>${escapeHtml(slots.title)}</h1>${
      slots.subtitle ? `<div class="subtitle">${escapeHtml(slots.subtitle)}</div>` : ''
    }${date ? `<div class="date">${escapeHtml(date)}${ctx.brand.company ? ` · ${escapeHtml(ctx.brand.company)}` : ''}</div>` : ''}</div>`;
  },

  comparison(slots, ctx) {
    need(slots, 'comparison', ['title', 'story', 'companies']);
    const rows: any[] = slots.companies;
    if (rows.length < 2 || rows.length > 7)
      fail(`comparison takes 2–7 companies (got ${rows.length}) — split across two pages`);
    const pill = (lvl: string) => `<span class="pill ${lvl}">${lvl}</span>`;
    const body = rows.map((c) => `<tr>
      <td class="co">${escapeHtml(c.name)}${c.ticker ? ` <span class="tk">${escapeHtml(c.ticker)}</span>` : ''}</td>
      <td>${escapeHtml(c.mechanism ?? '')}</td>
      ${RATING_KEYS.map((k) => `<td>${c.ratings?.[k] ? pill(c.ratings[k]) : '—'}</td>`).join('')}
    </tr>`).join('');
    return `${pageTop(slots, ctx)}<div class="page-body">
      <table class="matrix"><thead><tr><th>Company</th><th>Mechanism</th>${
        RATING_LABELS.map((l) => `<th>${l}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>
      ${slots.takeaway ? `<div class="takeaway">${textBlock(slots.takeaway)}</div>` : ''}</div>`;
  },

  'industry-breakdown'(slots, ctx) {
    need(slots, 'industry-breakdown', ['title', 'story', 'layers']);
    const layers: any[] = slots.layers;
    if (layers.length < 2 || layers.length > 9)
      fail(`industry-breakdown takes 2–9 layers (got ${layers.length})`);
    const cards = layers.map((l) => `<div class="layer-card ${escapeHtml(l.scarcity ?? 'commoditized')}">
      <span class="lname">${escapeHtml(l.name)}</span>
      <span class="lrole">${escapeHtml(l.role ?? '')}</span>
      <span class="chips">${(l.tickers ?? []).map((t: string) => `<span class="chip">${escapeHtml(t)}</span>`).join('')}</span>
    </div>`).join('');
    const legend = `<div class="scarcity-legend">
      <span><i style="background:#15803d"></i>scarce</span>
      <span><i style="background:#b45309"></i>contested</span>
      <span><i style="background:var(--muted)"></i>commoditized</span></div>`;
    return `${pageTop(slots, ctx)}<div class="page-body">${legend}
      <div class="layers">${cards}</div>
      ${slots.takeaway ? `<div class="takeaway">${textBlock(slots.takeaway)}</div>` : ''}</div>`;
  },

  'price-chart-technicals'(slots, ctx) {
    need(slots, 'price-chart-technicals', ['title', 'story', 'chart', 'commentary']);
    const blocks: TextBlock[] = slots.commentary;
    if (blocks.length < 1 || blocks.length > 4)
      fail(`price-chart-technicals takes 1–4 commentary blocks (got ${blocks.length})`);
    // Deck slide is 720px tall; A4 content ~990px. Story+stats live at the top now.
    const height = ctx.deck ? 330 : 520;
    return `${pageTop(slots, ctx)}<div class="page-body">
      <div class="chart-zone">${chartHtml(slots.chart, ctx.contractPath, height)}</div>
      <div class="commentary-cols">${blocks.map(textBlock).join('')}</div></div>`;
  },

  'table-commentary'(slots, ctx) {
    need(slots, 'table-commentary', ['title', 'story', 'table', 'commentary']);
    const { columns, rows } = slots.table as { columns: string[]; rows: string[][] };
    if (ctx.deck && rows.length > 10)
      fail(`table-commentary in presentation mode takes ≤10 rows (got ${rows.length}) — split across two slides`);
    const table = `<table class="data"><thead><tr>${columns.map((c) => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    return `${pageTop(slots, ctx)}<div class="page-body"><div class="tc-split">
      <div class="tc-table">${table}</div>
      <div class="tc-note">${textBlock(slots.commentary)}</div></div></div>`;
  },
};

// ── assembly ────────────────────────────────────────────────────────────────

const _vendor = new Map<string, string>();
function readVendor(rel: string): string {
  if (!_vendor.has(rel)) _vendor.set(rel, readFileSync(resolve(CHARTING, 'vendor', 'highcharts', rel), 'utf8'));
  return _vendor.get(rel)!;
}

function loadBrand(contract: ReportContract, contractPath: string, brandFlag?: string): { brand: Brand; logoUri: string | null } {
  const defaults = JSON.parse(readFileSync(resolve(SKILL_ROOT, 'assets', 'default-brand.json'), 'utf8')) as Brand;
  let brand: Brand = defaults;
  let base = contractPath;
  const fromFile = (p: string, origin: string) => {
    if (!existsSync(p)) fail(`brand file not found: ${p} (${origin})`);
    base = p;
    return JSON.parse(readFileSync(p, 'utf8')) as Brand;
  };
  if (brandFlag) brand = fromFile(resolve(brandFlag), '--brand flag');
  else if (typeof contract.brand === 'string') brand = fromFile(resolveFrom(contractPath, contract.brand), 'contract "brand"');
  else if (contract.brand) brand = contract.brand;
  else {
    const conventional = resolve(process.cwd(), 'report-brand', 'brand.json');
    if (existsSync(conventional)) brand = fromFile(conventional, 'working-dir convention');
  }
  const merged: Brand = {
    ...defaults, ...brand,
    colors: { ...defaults.colors, ...brand.colors },
    fonts: { ...defaults.fonts, ...brand.fonts },
  };
  let logoUri: string | null = null;
  if (merged.logo) {
    const p = resolveFrom(base, merged.logo);
    if (!existsSync(p)) fail(`logo not found: ${p}`);
    logoUri = dataUri(p);
  }
  return { brand: merged, logoUri };
}

function assemble(contract: ReportContract, contractPath: string, brandFlag?: string): string {
  const { meta, pages } = contract;
  if (!meta?.title || !Array.isArray(pages) || pages.length === 0) fail('contract needs meta.title and a non-empty pages array');
  const mode = meta.mode === 'presentation' ? 'presentation' : 'report';
  const deck = mode === 'presentation';
  const { brand, logoUri } = loadBrand(contract, contractPath, brandFlag);

  const sections = pages.map((page, i) => {
    const render = templates[page.template];
    if (!render) fail(`unknown template "${page.template}" (have: ${Object.keys(templates).join(', ')})`);
    const ctx: Ctx = { meta, brand, logoUri, contractPath, deck };
    const inner = render(page.slots ?? {}, ctx);
    const footerText = meta.footer ?? brand.footerText ?? '';
    const footer = page.template === 'cover' ? '' :
      `<footer class="pg"><span>${escapeHtml(footerText)}</span>${
        page.slots?.source ? `<span class="src">Source: ${escapeHtml(page.slots.source)}</span>` : ''
      }<span>${i + 1} / ${pages.length}</span></footer>`;
    return `<section class="page tpl-${page.template}">${inner}${footer}</section>`;
  });

  // Highcharts inlined once; highstock is a superset of highcharts.
  const hcTags = chartJobs.length
    ? [needsStock ? 'highstock.js' : 'highcharts.js', ...(needsMore ? ['highcharts-more.js'] : [])]
        .map((f) => `<script>${readVendor(f)}</script>`).join('\n')
    : '';
  const boot = chartJobs.length ? `<script>
${HELPERS_JS}
(function () {
  var pending = ${chartJobs.length};
  window.__REPORT_READY__ = false;
  function done() { if (--pending === 0) window.__REPORT_READY__ = true; }
  function mount(id, opts, stock) {
    opts.chart = opts.chart || {};
    opts.chart.events = Object.assign({}, opts.chart.events, { load: done });
    Highcharts[stock ? 'stockChart' : 'chart'](id, opts);
  }
${chartJobs.map((c) => `  mount(${JSON.stringify(c.id)}, ${c.js}, ${c.stock});`).join('\n')}
})();
</script>` : '<script>window.__REPORT_READY__ = true;</script>';

  const c = brand.colors!;
  const pageSize = deck ? '13.333in 7.5in' : 'A4 portrait';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(meta.title)}</title>
${hcTags}
<style>
:root {
  --primary: ${c.primary}; --accent: ${c.accent}; --text: ${c.text}; --muted: ${c.muted};
  --bg: ${c.background}; --panel: ${c.panel};
  --font-body: ${brand.fonts!.body}; --font-heading: ${brand.fonts!.heading};
}
@page { size: ${pageSize}; margin: 0; }
${readFileSync(resolve(SKILL_ROOT, 'assets', 'styles.css'), 'utf8')}
</style>
</head>
<body class="${mode}">
${sections.join('\n')}
${boot}
</body>
</html>
`;
}

// ── PDF (Playwright) ────────────────────────────────────────────────────────

async function printPdf(htmlPath: string, outPath: string): Promise<void> {
  let chromium;
  try {
    ({ chromium } = await import('playwright'));
  } catch {
    console.error(
      'reporting: playwright is not installed. One-time setup:\n' +
      `  cd ${SKILL_ROOT} && bun install && bunx playwright install chromium\n` +
      'Or render HTML only (--html-only) and convert with any HTML→PDF tool.');
    process.exit(3);
  }
  // --no-sandbox: Chromium's sandbox needs privileges containers don't grant.
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    let pageError: string | null = null;
    page.on('pageerror', (e: Error) => { pageError = e.message; });
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'load', timeout: 60_000 });
    await page.waitForFunction('window.__REPORT_READY__ === true', undefined, { timeout: 30_000 });
    await page.evaluate('document.fonts.ready');
    const empty = await page.evaluate(`[...document.querySelectorAll('.chart-mount')].filter(c => !c.querySelector('svg')).length`);
    if (pageError) fail(`page JS error: ${pageError}`);
    if (empty) fail(`${empty} chart container(s) have no SVG — chart failed to render`);
    await page.pdf({ path: outPath, printBackground: true, preferCSSPageSize: true });
  } finally {
    await browser.close();
  }
}

// ── CLI ─────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const flags = new Set(args.filter((a) => a.startsWith('--')));
const brandIdx = args.indexOf('--brand');
const brandFlag = brandIdx >= 0 ? args[brandIdx + 1] : undefined;
const positional = args.filter((a, i) => !a.startsWith('--') && (brandIdx < 0 || i !== brandIdx + 1));
const [input, output] = positional;

if (!input || !output) {
  console.error('usage: bun scripts/render.ts <report.json> <out.pdf|out.html> [--html-only] [--keep-html] [--brand brand.json]');
  process.exit(2);
}
const contractPath = resolve(input);
if (!existsSync(contractPath)) fail(`contract not found: ${contractPath}`);
const contract = JSON.parse(readFileSync(contractPath, 'utf8')) as ReportContract;

const outPath = resolve(output);
mkdirSync(dirname(outPath), { recursive: true });
const html = assemble(contract, contractPath, brandFlag);

const htmlOnly = flags.has('--html-only') || extname(outPath) === '.html';
const htmlPath = htmlOnly ? outPath : `${outPath.replace(/\.pdf$/, '')}.html`;
writeFileSync(htmlPath, html);

if (htmlOnly) {
  console.error(`reporting: wrote ${htmlPath} (${contract.pages.length} pages, ${Math.round(statSync(htmlPath).size / 1024)} KB)`);
} else {
  await printPdf(htmlPath, outPath);
  if (!flags.has('--keep-html')) { const { unlinkSync } = await import('node:fs'); unlinkSync(htmlPath); }
  console.error(`reporting: wrote ${outPath} (${contract.pages.length} pages, ${Math.round(statSync(outPath).size / 1024)} KB)`);
}
