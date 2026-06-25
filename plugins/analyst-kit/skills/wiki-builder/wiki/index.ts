import path from 'path';
import { readFileSync, readdirSync, existsSync } from 'fs';
import matter from 'gray-matter';

const WIKI_DIR = path.join(import.meta.dirname);
const TEMPLATES_DIR = path.join(WIKI_DIR, 'templates');
const ASSETS_DIR = path.join(WIKI_DIR, 'assets');

export interface WikiOptions {
  /** Site name shown in the topbar and page titles. Default: 'Brain Wiki' */
  siteName?: string;
  /** Enable ECharts chart rendering. Default: true */
  charts?: boolean;
}

// ── Markdown renderer (initialized once) ──────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-require-imports
const markdownIt = require('markdown-it');
// eslint-disable-next-line @typescript-eslint/no-require-imports
const markdownItAnchor = require('markdown-it-anchor');

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const md: any = (() => {
  const instance = markdownIt({ html: true, linkify: true, typographer: true });

  const defaultFence: Function =
    instance.renderer.rules.fence ||
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ((tokens: any, idx: any, opts: any, _env: any, self: any) => self.renderToken(tokens, idx, opts));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  instance.renderer.rules.fence = function (tokens: any, idx: number, opts: any, env: any, self: any) {
    const token = tokens[idx];
    if (token.info.trim() !== 'chart') return defaultFence(tokens, idx, opts, env, self);
    let raw: object;
    try { raw = JSON.parse(token.content); }
    catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      return `<div class="chart-error"><strong>Chart error:</strong> ${msg}</div>\n`;
    }
    const { caption = '', height = 250, ...config } = raw as Record<string, unknown>;
    const json = JSON.stringify(config).replace(/<\/script>/gi, '<\\/script>');
    const fig = caption ? `\n  <figcaption>${caption}</figcaption>` : '';
    return `<figure class="chart-figure">\n  <div class="chart-container" style="height:${height}px"><script type="application/json">${json}</script></div>${fig}\n</figure>\n`;
  };

  instance.use(markdownItAnchor, {
    permalink: markdownItAnchor.permalink.headerLink({ safariReaderFix: true }),
  });

  return instance;
})();

// ── Nunjucks environment (initialized once) ────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-require-imports
const nunjucks = require('nunjucks');

function firstSegment(url: string): string {
  return (url || '/').split('/').filter(Boolean)[0] || 'general';
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const njkEnv: any = (() => {
  const env = nunjucks.configure(TEMPLATES_DIR, { autoescape: true });

  // Assets served at /wiki-assets/ by the dashboard server
  env.addFilter('assetPath', (_pageUrl: string, asset: string) => {
    return '/wiki-assets/' + asset;
  });

  env.addFilter('getCompany', (url: string) => firstSegment(url).toUpperCase());
  env.addFilter('getCompanyKey', firstSegment);

  return env;
})();

// ── Nav tree (5-second TTL cache) ─────────────────────────────────────────────

interface NavPage { title: string; url: string; order: number; }
interface NavSection { label: string; pages: NavPage[]; }
type NavTree = Record<string, NavSection[]>;

let _navCache: { dir: string; ts: number; tree: NavTree } | null = null;
const NAV_TTL_MS = 5000;

function buildNavTree(brainDir: string): NavTree {
  const now = Date.now();
  if (_navCache && _navCache.dir === brainDir && now - _navCache.ts < NAV_TTL_MS) {
    return _navCache.tree;
  }

  const byNs: Record<string, Record<string, NavPage[]>> = {};

  function walk(dir: string) {
    try {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else if (entry.name.endsWith('.md')) {
          const rel = path.relative(brainDir, fullPath);
          const url = '/' + rel.replace(/\.md$/, '/').replace(/\\/g, '/');
          const ns = firstSegment(url);
          try {
            const raw = readFileSync(fullPath, 'utf-8');
            const { data } = matter(raw);
            const group: string = data.navGroup ?? 'Pages';
            (byNs[ns] ??= {})[group] ??= [];
            byNs[ns][group].push({
              title: data.title || path.basename(entry.name, '.md'),
              url,
              order: data.navOrder ?? 99,
            });
          } catch { /* skip unreadable files */ }
        }
      }
    } catch { /* skip unreadable directories */ }
  }

  walk(brainDir);

  const tree: NavTree = {};
  for (const [ns, groups] of Object.entries(byNs)) {
    tree[ns] = Object.entries(groups).map(([label, pages]) => ({
      label,
      pages: pages.sort((a, b) => a.order - b.order),
    }));
  }

  _navCache = { dir: brainDir, ts: now, tree };
  return tree;
}

// ── URL → markdown file path ───────────────────────────────────────────────────

/**
 * Maps a /wiki/... URL to the absolute path of the matching markdown file.
 * Returns null if no file exists or path traversal is detected.
 */
export function resolveFilePath(brainDir: string, urlPath: string): string | null {
  const rel = urlPath
    .replace(/^\/wiki\//, '')
    .replace(/^\//, '')
    .replace(/\/$/, '')
    .replace(/\.html$/, '')
    // Markdown inter-page links keep their `.md` extension (e.g. href="06-drivers.md"),
    // so the URL can arrive with `.md`. Strip it — `rel + '.md'` is re-appended below.
    .replace(/\.md$/, '');

  const brainAbs = path.resolve(brainDir);
  const sep = path.sep;

  if (!rel) {
    const idx = path.join(brainAbs, 'index.md');
    return existsSync(idx) ? idx : null;
  }

  const direct = path.resolve(brainAbs, rel + '.md');
  if (!direct.startsWith(brainAbs + sep) && direct !== brainAbs) return null;
  if (existsSync(direct)) return direct;

  const index = path.resolve(brainAbs, rel, 'index.md');
  if (!index.startsWith(brainAbs + sep)) return null;
  if (existsSync(index)) return index;

  return null;
}

// ── Per-request page rendering ─────────────────────────────────────────────────

/**
 * Render a single brain markdown file to a full HTML page on the fly.
 * No pre-building, no disk output — called fresh on every request.
 * Returns null when the requested path has no matching markdown file.
 */
export function renderPage(
  brainDir: string,
  urlPath: string,
  options: WikiOptions = {}
): string | null {
  const filePath = resolveFilePath(brainDir, urlPath);
  if (!filePath) return null;

  let raw: string;
  try { raw = readFileSync(filePath, 'utf-8'); }
  catch { return null; }

  const { content, data } = matter(raw);
  const bodyHtml: string = md.render(content);

  const rel = path.relative(brainDir, filePath);
  const pageUrl = '/' + rel.replace(/\.md$/, '/').replace(/\\/g, '/');

  const navTree = buildNavTree(brainDir);

  return njkEnv.render('layouts/page.njk', {
    content: bodyHtml,
    title: data.title || path.basename(filePath, '.md'),
    siteName: options.siteName ?? 'Brain Wiki',
    chartsEnabled: options.charts ?? true,
    collections: { navTree },
    page: { url: pageUrl },
    // Forward all frontmatter fields (ticker, sector, mktcap, etc.) to the template
    ...data,
  });
}

/** Absolute path to the CSS/JS assets directory for static serving. */
export function getAssetDir(): string {
  return ASSETS_DIR;
}
