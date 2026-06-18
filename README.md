# Hedge Fund Analyst

Installable, hedge-fund-grade **equity-research skills** for AI coding agents.
Each skill is a self-contained folder of instructions (and, where useful, runnable
scripts) that an agent loads on demand. Install them into Claude Code as a plugin,
or copy them into any agent runtime with the bundled installer.

The skill frontmatter is the single source of truth — the registry, the plugin
manifests, and the installer all derive from it.

## What's inside

The skills split into **capabilities** (one atomic job — a data source, an engine,
a deliverable, or reusable knowledge) and **workflows** (an engagement entry point
that orchestrates capabilities via `requires:`). The "Needs" column lists runtimes,
API keys, and required skills.

| Skill | Type | What it does | Needs |
|-------|------|--------------|-------|
| **analyst-playbook** | capability | How to structure any analysis before fetching a number: pick the deliverable, align fiscal calendars and frequencies, normalize units, route series to the right skill, and apply per-sector conventions | — |
| **13f-analysis** | capability | Fetch & read U.S. institutional **13F-HR** holdings from SEC EDGAR — resolve a fund to its CIK, pull a quarter's holdings as a normalized, ranked CSV, and read it without the common traps | Python (stdlib) |
| **sec-filings** | capability | Fetch & read U.S. SEC filings (10-K, 10-Q, 8-K, any EDGAR form) — risk factors, MD&A, material events, segment data, insider trades, earnings 8-K exhibits — with ticker→CIK resolution and BM25 search for large filings | Python (stdlib) |
| **financialmodellingprep** | capability | Call the Financial Modeling Prep REST API — daily prices, news, profiles, screener, quarterly income statements, fiscal-period info, earnings-call transcripts — with exact endpoints, params, and field schemas | Python · `FMP_API_KEY` |
| **finmind** | capability | Pull Taiwan (TWSE/TPEx) market data — prices, monthly revenue, financials, dividends, shareholding, institutional flows — via the FinMind API | Python · `FINMIND_TOKEN` |
| **market-intelligence** | capability | Nowcast a company's quarter and predict a revenue segment from Google Trends search-interest (via SerpAPI) — keyword selection, normalization to a quarterly index, and a quarter-to-date nowcast | Python · `SERPAPI_API_KEY` |
| **company-universe-manager** | capability | Own a watchlist of companies **and their key dates** (earnings, investor days, ex-dividend, AGMs…): roster CRUD, a daily monitor that detects date changes, and a daily brief (markdown or branded PDF). Pluggable local-folder or connected-server storage | Python · financialmodellingprep, reporting |
| **analyzing-financial-statements** | capability | Calculate & interpret financial ratios (profitability, liquidity, leverage, efficiency, valuation, per-share) from statement data, with industry benchmarking | Python (stdlib) |
| **creating-financial-models** | capability | DCF valuation, M&A accretion/dilution, sensitivity analysis (data tables, tornado charts), and probability-weighted best/base/worst scenario planning | Python · numpy/pandas |
| **charting** | capability | Financially-correct charts: a thin Python/Polars layer normalizes data → a TypeScript layer emits Highcharts options + a self-contained HTML page (trends, segments, margins, dividends, surprise, waterfalls, price) | Node · Python |
| **reporting** | capability | Assemble charts, tables, and analyst text into a branded PDF — A4 portrait report or 16:9 deck — from ready-made page templates; remembers your logo and brand colors | Node · charting |
| **wiki-builder** | capability | Serve any folder of markdown as a navigable browser wiki (sidebar, table of contents, frontmatter chips, ECharts) | Bun |
| **data-analysis** | capability | End-to-end analysis of a structured dataset (CSV/JSON/Excel/SQL) — profile, clean, visualize, model, and report with reproducible code | — |
| **single-stock-deep-dive** | workflow | Forensic, decision-useful deep dive on one stock: thesis, valuation, catalysts, variant perception, value-chain adjacencies | — |
| **thematic-investing** | workflow | Map a theme or trend into an investable value chain — who benefits, where value accrues, what's mispriced | company-universe-manager |
| **technical-analysis** | workflow | Disciplined technical analysis with concrete entry/exit levels: regime classification, a three-layer confluence stack, and ATR-based stops/sizing/targets from a zero-dependency indicator engine | Python · charting |
| **company-wiki** | workflow | Build a multi-page company-research wiki (overview, products, 5-year financials, model, competitors, citations) as a deployed web app | `FMP_API_KEY` · wiki-builder, company-universe-manager |

## Install

**One command — same on macOS, Linux, and Windows.** It installs *all* the skills into your chosen runtime
and wires them into the agent's system/common prompt. Needs only **Node ≥ 18** (which detects your OS and
installs to the right paths):

```bash
npx github:MohitKumar1991/hedge-fund-analyst claude-code      # or: codex · openclaw · cowork
```

Swap `claude-code` for `codex`, `openclaw`, or `cowork`; add `--scope project` to install into the current
project (`./.claude/skills`, …) instead of your home directory. Already cloned the repo? `node bin/hfa.js
claude-code` does the same (plus `list`, `doctor`, `uninstall`, or `install <skill|persona>` for just one).

For **Claude Cowork**, the command prints the in-app steps and writes `cowork-global-instructions.md` to paste
into **Settings → Cowork → Global instructions** — Cowork installs the skills themselves through its plugin
marketplace (below).

> **On Windows:** skills install fine; their `hfa-core` runtime helpers are bash, so install **Git for
> Windows** (or use WSL) for the telemetry/onboarding/update niceties — skills work without it
> ([details](compatibility.md#runtime-layer-on-windows)).

### Marketplace plugin — no clone, no Node (Claude Code & Cowork)

Both **Claude Code** and **[Claude Cowork](https://claude.com/product/cowork)** (Anthropic's desktop app)
install from the same plugin marketplace:

- **Claude Code:**
  ```
  /plugin marketplace add MohitKumar1991/hedge-fund-analyst
  /plugin install us-stock-analyst@hedge-fund-analyst    # or international-analyst / taiwan-stock-analyst
  ```
- **Claude Cowork** (desktop app): **Customize → Plugins → Personal plugins → + → Add marketplace** →
  `MohitKumar1991/hedge-fund-analyst`, add the **us-stock-analyst** plugin, then enable **Settings →
  Capabilities → Code execution**.

### Check it worked

After installing, ask a trigger phrase (e.g. "deep dive on NVDA") and the matching skill loads. From a clone
you can also self-test the installers across every platform:

```bash
npm run test:integration     # real installs per platform + the path.win32 Windows check
```

Codex (any OS, no ChatGPT login needed) — confirm a skill is reachable with an API key:

```bash
CODEX_API_KEY=sk-... codex exec --json "use the sec-filings skill to list NVDA's latest 8-K"
```

See **[compatibility.md](compatibility.md)** for what each runtime does underneath — where skills land, the
routing table, and Windows specifics.

## Personas (plugins)

Three persona plugins bundle the research workflows for different markets. All
three include the research workflows (deep dive, thematic, technical analysis,
company wiki) plus their supporting capabilities (charting, reporting,
wiki-builder, company-universe-manager, financialmodellingprep, market-intelligence,
analyzing-financial-statements, creating-financial-models, data-analysis); the
market difference is whether FinMind (Taiwan data) and SEC filings are included.

| Plugin | Includes | Skills |
|--------|----------|:-----:|
| `us-stock-analyst` | the research workflows + supporting capabilities, **incl. `sec-filings`** (US filings) | 15 |
| `international-analyst` | the above **+ FinMind** (Taiwan/TWSE market data) | 16 |
| `taiwan-stock-analyst` | Taiwan-focused: workflows + capabilities **+ FinMind**, minus `sec-filings` | 14 |

Run `node bin/hfa.js list --persona <name>` to see a plugin's exact contents.

## API keys

Keys are read from the environment or a git-ignored `.env`. The installer
(`hfa env` / `hfa install`) prompts for anything missing when run interactively.
See [`.env.example`](.env.example).

| Variable | Used by | Get it |
|----------|---------|--------|
| `FINMIND_TOKEN` | finmind | <https://finmindtrade.com/> (free) |
| `FMP_API_KEY` | financialmodellingprep, company-wiki | <https://site.financialmodelingprep.com/developer/docs> |
| `SERPAPI_API_KEY` | market-intelligence | <https://serpapi.com/> (free tier = 100 searches/month) |

`13f-analysis` needs no key — it reads SEC EDGAR directly (set the optional
`SEC_EDGAR_UA` contact string as an SEC fair-access courtesy).

Skills that run code bootstrap their own dependencies on first use. Runtimes are a
per-skill prerequisite the installer does not install for you: **Python** (finmind,
company-universe-manager; 13f-analysis is standard-library only) and **Bun**
(wiki-builder).

## The `~/.hfa` data home, analytics & updates

Every skill runs on a shared runtime (`hfa-core`, installed automatically as a
dependency) that keeps all per-user state in one fixed place, `~/.hfa/`:

- `.env` — your API keys (chmod 600, shared across projects)
- `config` — settings (`hfa-core/bin/hfa-config get|set|list`)
- `analytics/skill-usage.jsonl` — **local** usage log: which skill ran, when,
  outcome, duration
- `learnings.jsonl` — things the skills learned about your setup and preferences,
  so mistakes aren't repeated

**Telemetry is on by default (anonymous, opt-out).** It sends only skill name,
version, outcome, and duration — never repo names, file paths, tickers, or content —
and is what tells us which skills break or run slow, so keeping it on directly
improves your experience. You're told about it once on first run. Tiers: `community`
(default, stable anonymous id), `anonymous` (no id), `off`. Opt out any time:

```bash
~/.claude/skills/hfa-core/bin/hfa-config set telemetry off
```

**Updates:** skills check the published version at most once a day and offer a
guided upgrade when a new release is out (declining snoozes it for a week; disable
with `hfa-config set update_check false`).

## Skill format

Each skill is `skills/<name>/SKILL.md` with YAML frontmatter:

```yaml
---
name: 13f-analysis          # kebab-case; must equal the folder name
type: capability            # capability | workflow
description: >              # what it does + a "Triggers:" clause of trigger phrases
  ... Triggers: "get the 13F for X", "what does <fund> own", ...
requires: [ ... ]           # capability skills this one builds on (nothing may require a workflow)
env: [ FMP_API_KEY ]        # API keys the skill needs
---
```

Agents read only `name` + `description`, so trigger phrases live inside the
description. `type`, `requires`, and `env` drive the installer and validator.

## Development

```bash
npm run validate         # lint skills + plugin manifests (+ preamble sync check)
npm run build:registry   # regenerate registry.json from frontmatter
npm run check:registry   # verify registry.json is in sync
npm run sync:preamble    # regenerate the hfa-core blocks in every SKILL.md
```

`registry.json` is generated — edit skill frontmatter, then rebuild it. The
`<!-- hfa:preamble/epilogue -->` blocks in each SKILL.md are also generated — edit
`skills/hfa-core/templates/` and re-sync; never edit between the markers. The same
checks run in CI (`.github/workflows/validate.yml`) on every push and pull request.

## Roadmap

Planned skills, not yet available: an LBO model (debt schedule, cash sweep,
IRR/MOIC) and PDF report analysis.

## Acknowledgments

- **`analyzing-financial-statements`** and the DCF + sensitivity tooling in
  **`creating-financial-models`** were inspired by the custom financial skills
  in [Anthropic's claude-cookbooks](https://github.com/anthropics/claude-cookbooks/tree/main/skills/custom_skills),
  then reworked to this repo's skill contract (frontmatter, `scripts/` layout)
  and hardened with input guards and a test suite.
- The M&A accretion/dilution model in **`creating-financial-models`** was
  inspired by [joe-neary/MergerDealSimulator](https://github.com/joe-neary/MergerDealSimulator).
  The financial formulas were reimplemented from scratch (no code was copied);
  that project's worked example serves as an independent cross-check in the
  skill's test suite.

## License

MIT © Mohit Kumar
