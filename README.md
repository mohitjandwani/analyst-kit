# Hedge Fund Analyst

Installable, hedge-fund-grade **equity-research skills** for AI coding agents.
Each skill is a self-contained folder of instructions (and, where useful, runnable
scripts) that an agent loads on demand. Install them into Claude Code as a plugin,
or copy them into any agent runtime with the bundled installer.

The skill frontmatter is the single source of truth — the registry, the plugin
manifests, and the installer all derive from it.

## What's inside

Ten skills today, split into **capabilities** (one atomic job) and **composites**
(a workflow that orchestrates capabilities, declared in `requires:`).

| Skill | Type | What it does | Needs |
|-------|------|--------------|-------|
| **13f-analysis** | capability | Fetch & read U.S. institutional **13F-HR** holdings from SEC EDGAR — resolve a fund to its CIK, pull a quarter's holdings as a normalized, ranked CSV, and read it without the common traps | Python (stdlib) |
| **finmind** | capability | Pull Taiwan (TWSE/TPEx) market data — prices, monthly revenue, financials, dividends, shareholding — via the FinMind API | Python · `FINMIND_TOKEN` |
| **company-universe-manager** | capability | Maintain a CSV "company universe" (add / update / soft-delete / list), synced to a GitHub repo | Python |
| **wiki-builder** | capability | Serve any folder of markdown as a navigable browser wiki (sidebar, table of contents, ECharts) | Bun |
| **infographics** | capability | Turn source material into a clean one-page infographic | — |
| **charting** | capability | Financially-correct charts: a thin Python/Polars layer normalizes already-available data → a TypeScript layer emits Highcharts options + a self-contained HTML page (trends, segments, margins, dividends, surprise, waterfalls, price) | Node · Python |
| **single-stock-deep-dive** | composite | Forensic, decision-useful deep dive on one stock: thesis, valuation, catalysts, variant perception, value-chain adjacencies | — |
| **thematic-investing** | composite | Map a theme or trend into an investable value chain — who benefits, where value accrues, what's mispriced | — |
| **company-wiki** | composite | Build a multi-page company-research wiki (overview, products, 5-year financials, model, competitors, citations) | `FMP_API_KEY` |
| **data-analysis** | composite | End-to-end analysis of a structured dataset — profile, clean, visualize, model, and report with reproducible code | — |

## Install

### Option A — Claude Code plugin (recommended)

Install a persona plugin (a bundle of skills) straight from this GitHub repo:

```
/plugin marketplace add MohitKumar1991/hedge-fund-analyst
/plugin install us-stock-analyst@hedge-fund-analyst
```

- The `@hedge-fund-analyst` suffix is the **marketplace name**, not the repo name.
- Swap `us-stock-analyst` for `international-analyst` or `taiwan-stock-analyst`.
- Prefer a menu? Run `/plugin` to browse and install interactively.
- Update later with `/plugin marketplace update hedge-fund-analyst`.

Once installed, the skills activate automatically from their triggers (run
`/reload-plugins` if they don't appear immediately in a running session).

### Option B — Clone and use the bundled installer

The repo ships a small installer (`bin/hfa.js`) that copies skills — and their
dependency closure — into a target runtime. It targets **Claude Code** and
**Codex**, runs on Node ≥ 18, and needs no global install:

```bash
git clone https://github.com/MohitKumar1991/hedge-fund-analyst
cd hedge-fund-analyst

node bin/hfa.js list                                              # browse skills + personas
node bin/hfa.js install single-stock-deep-dive --platform claude-code
node bin/hfa.js install us-stock-analyst --platform claude-code   # installs the whole persona
node bin/hfa.js doctor  --platform claude-code                    # check runtimes + keys
```

Installing a composite (or a persona) automatically pulls its capability
dependencies. Use `--scope project` to install into `./.claude/skills` instead of
`~/.claude/skills`, `--dry-run` to preview, and `--platform codex` to target Codex.
Other commands: `update`, `uninstall`, `env`.

## Personas (plugins)

Three persona plugins bundle the research workflows for different markets. All
three include the four research composites plus their supporting capabilities
(`wiki-builder`, `company-universe-manager`); the market difference is whether
FinMind (Taiwan data) is included.

| Plugin | Includes | Skills |
|--------|----------|:-----:|
| `us-stock-analyst` | the four research composites + supporting capabilities (incl. charting) | 7 |
| `international-analyst` | the above **+ FinMind** (Taiwan/TWSE market data) | 8 |
| `taiwan-stock-analyst` | Taiwan-focused: the above **+ FinMind** | 8 |

Run `node bin/hfa.js list --persona <name>` to see a plugin's exact contents.

## API keys

Keys are read from the environment or a git-ignored `.env`. The installer
(`hfa env` / `hfa install`) prompts for anything missing when run interactively.
See [`.env.example`](.env.example).

| Variable | Used by | Get it |
|----------|---------|--------|
| `FINMIND_TOKEN` | finmind | <https://finmindtrade.com/> (free) |
| `FMP_API_KEY` | company-wiki | <https://site.financialmodelingprep.com/developer/docs> |

`13f-analysis` needs no key — it reads SEC EDGAR directly (set the optional
`SEC_EDGAR_UA` contact string as an SEC fair-access courtesy).

Skills that run code bootstrap their own dependencies on first use. Runtimes are a
per-skill prerequisite the installer does not install for you: **Python** (finmind,
company-universe-manager; 13f-analysis is standard-library only) and **Bun**
(wiki-builder).

## Skill format

Each skill is `skills/<name>/SKILL.md` with YAML frontmatter:

```yaml
---
name: 13f-analysis          # kebab-case; must equal the folder name
type: capability            # capability | composite
description: >              # what it does + a "Triggers:" clause of trigger phrases
  ... Triggers: "get the 13F for X", "what does <fund> own", ...
requires: [ ... ]           # composite only — capability skills it builds on
env: [ FMP_API_KEY ]        # API keys the skill needs
---
```

Agents read only `name` + `description`, so trigger phrases live inside the
description. `type`, `requires`, and `env` drive the installer and validator.

## Development

```bash
npm run validate         # lint skills + plugin manifests
npm run build:registry   # regenerate registry.json from frontmatter
npm run check:registry   # verify registry.json is in sync
```

`registry.json` is generated — edit skill frontmatter, then rebuild it. The same
checks run in CI (`.github/workflows/validate.yml`) on every push and pull request.

## Roadmap

Planned skills, not yet available: a calendar manager, accounting /
financial-statement analysis, and PDF report analysis.

## License

MIT © Mohit Kumar
