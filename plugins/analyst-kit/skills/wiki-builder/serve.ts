#!/usr/bin/env bun
/**
 * Wiki Builder — serve any directory of markdown files as a browser wiki.
 *
 *   bun run serve.ts [dir]
 *   PORT=3000 WIKI_SITE_NAME="My Wiki" bun run serve.ts /path/to/notes
 */

import { existsSync, readFileSync } from 'fs';
import { join, resolve } from 'path';
import { renderPage, getAssetDir } from './wiki/index.ts';

const PORT      = parseInt(process.env.PORT ?? '4000');
const BRAIN_DIR = resolve(process.argv[2] ?? process.env.WIKI_DIR ?? process.cwd());
const SITE_NAME = process.env.WIKI_SITE_NAME ?? 'Brain Wiki';
const CHARTS    = process.env.WIKI_NO_CHARTS !== '1';
const ASSETS    = getAssetDir();

if (!existsSync(BRAIN_DIR)) {
  console.error(`[wiki] directory not found: ${BRAIN_DIR}`);
  process.exit(1);
}

const MIME: Record<string, string> = {
  css: 'text/css', js: 'application/javascript',
  png: 'image/png', svg: 'image/svg+xml',
};

function serve(req: Request): Response {
  const { pathname: p } = new URL(req.url);

  if (p === '/' || p === '') {
    return new Response(null, { status: 302, headers: { Location: '/wiki/' } });
  }

  if (p.startsWith('/wiki-assets/')) {
    const name = p.slice('/wiki-assets/'.length);
    const file = join(ASSETS, name);
    if (!file.startsWith(ASSETS) || !existsSync(file))
      return new Response('Not found', { status: 404 });
    return new Response(readFileSync(file), {
      headers: { 'Content-Type': MIME[name.split('.').pop() ?? ''] ?? 'application/octet-stream' },
    });
  }

  if (p.startsWith('/wiki')) {
    const html = renderPage(BRAIN_DIR, p, { siteName: SITE_NAME, charts: CHARTS });
    if (!html) return new Response('Not found', { status: 404 });
    return new Response(html, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }

  return new Response('Not found', { status: 404 });
}

console.log(`\n  Wiki  ·  http://localhost:${PORT}/wiki/`);
console.log(`  Dir   ·  ${BRAIN_DIR}\n`);

Bun.serve({ port: PORT, fetch: serve, error: (e) => new Response(String(e), { status: 500 }) });
