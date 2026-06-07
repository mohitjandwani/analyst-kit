---
name: wiki-builder
type: capability
description: "Serve any directory of markdown files as a beautiful, navigable browser wiki — sidebar navigation, on-page table of contents, frontmatter metadata chips, and interactive ECharts charts. Use when the user wants to view, browse, preview, or serve markdown files (notes, research, a brain/knowledge base, a company wiki) as a local website. Triggers: 'serve wiki', 'start wiki server', 'render markdown as a website', 'open my notes in the browser', 'view brain as wiki', 'open wiki'. Self-contained Bun + markdown-it server; runs a local HTTP server, mutates nothing."
---

# Wiki Builder

Serve any directory of markdown files as a navigable browser wiki. The renderer
runs on the fly — no pre-building, no generated output written to disk.

## Requirements

- **Bun** must be installed (`bun --version`). If missing, install it with
  `curl -fsSL https://bun.sh/install | bash` (macOS/Linux) or see https://bun.sh.

## Run

Always run from the skill directory so the renderer's templates/assets resolve.

```bash
cd "$(dirname SKILL.md)"   # the directory containing this file

# First run only: install dependencies (node_modules is NOT bundled with the skill)
[ -d node_modules ] || bun install

# Serve a directory of markdown files
bun run serve.ts /path/to/notes
```

Then open `http://localhost:4000/wiki/`.

- Serve the current directory: `bun run serve.ts`
- Custom port + site name: `PORT=3000 WIKI_SITE_NAME="My Notes" bun run serve.ts /path/to/notes`

> Dependencies are installed on first use rather than shipped with the skill, so
> they stay current and the skill itself holds only source + instructions. The
> `[ -d node_modules ] || bun install` guard makes the first run self-installing.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `4000` | HTTP port |
| `WIKI_DIR` | cwd | Directory to serve (overridden by the first CLI arg) |
| `WIKI_SITE_NAME` | `Brain Wiki` | Site name in the topbar |
| `WIKI_NO_CHARTS` | unset | Set to `1` to disable the ECharts CDN |

## Page frontmatter

Each markdown file may declare frontmatter to control its sidebar placement and
metadata chips:

```yaml
---
title: My Page
navGroup: Reference   # sidebar section (default: Pages)
navOrder: 1           # sort order within group
ticker: NVDA          # rendered as a metadata chip
author: Mohit
updated: 2026-06-05
---
```

## Charts

Render interactive ECharts from a fenced `chart` block containing an ECharts
option object (optionally with `caption` and `height`):

````markdown
```chart
{ "type": "line", "xAxis": { "data": ["Q1","Q2","Q3"] }, "series": [{ "data": [10,14,11] }] }
```
````

## File structure

```
wiki-builder/
  SKILL.md              ← this file
  serve.ts              ← entry point (Bun HTTP server)
  package.json          ← dependency manifest
  bun.lock              ← pinned versions for reproducible `bun install`
  wiki/
    index.ts            ← markdown renderer (markdown-it + nunjucks)
    assets/
      theme.css         ← styles
      wiki.js           ← TOC + chart init
    templates/
      layouts/
        page.njk        ← HTML template
```
