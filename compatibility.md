# Compatibility — what each runtime does with the skills

> **Installation instructions live in the [README](README.md).** This document is the *under-the-hood*
> reference: where files land, how each agent discovers the skills, the routing table that advertises them,
> the `hfa-core` runtime layer, Windows behavior, and the per-runtime caveats — for **Claude Code**,
> **Codex**, **OpenClaw**, and **Claude Cowork**, on Linux/macOS and Windows.

Two things happen on every install:

1. **Placement** — the skill folders are copied where the runtime *discovers* them (so the agent can load a
   skill's body on demand).
2. **Advertisement** — a **routing table** (skill → trigger phrases → load path) is injected into the
   runtime's always-loaded common-prompt file (`CLAUDE.md` / `AGENTS.md`), so the agent is aware of the whole
   toolbox up-front. See [The routing table](#the-routing-table).

---

## At a glance

| Runtime | Native skills? | Skills land in — Linux/macOS | Skills land in — Windows | Common-prompt file | Auto-injected into system prompt? |
|---|---|---|---|---|---|
| **Claude Code** | ✅ yes (`SKILL.md`) | `~/.claude/skills/<name>/` | `%USERPROFILE%\.claude\skills\<name>\` | `~/.claude/CLAUDE.md` (user) / `./CLAUDE.md` (project) | Discovered from name+`description`; loaded on trigger |
| **Codex** | ❌ no | `~/.codex/skills/<name>/` **+** `~/.codex/prompts/<name>.md` | `%USERPROFILE%\.codex\skills\<name>\` **+** `…\prompts\<name>.md` | `~/.codex/AGENTS.md` (global) / `./AGENTS.md` (project) | No — reachable as `/<name>`; advertised via the AGENTS.md table |
| **OpenClaw** | ✅ yes (`SKILL.md`) | `~/.openclaw/skills/<name>/` | `%USERPROFILE%\.openclaw\skills\<name>\` | `~/.openclaw/workspace/AGENTS.md` | ✅ yes — compiled into an XML block in the system prompt |
| **Claude Cowork** | ✅ yes (plugins / `SKILL.md`) | account-managed (desktop app; no local skills dir) | account-managed | **Settings → Cowork → Global instructions** | ✅ yes — installed skills surface in Chat + Cowork |

`~` resolves to `%USERPROFILE%` on Windows (e.g. `C:\Users\<you>`).

---

## Concepts

### A skill, from the agent's point of view
An agent only ever sees a skill's **`name` + `description`**. Discoverability therefore lives in the
`Triggers:` clause inside each `description`. The body (instructions, scripts) is loaded only when the skill
is invoked. There are two kinds:

- **capability** — an atomic, requirable unit (a data source, an engine, a deliverable, or knowledge). May
  `require:` other capabilities.
- **workflow** — an engagement entry point that orchestrates capabilities via `requires:`. Nothing may
  require a workflow.

### Dependency closure
Each skill declares `requires:`. The bundled installer (`src/resolve.js`) walks that graph depth-first and
installs the full closure automatically (e.g. installing `reporting` also pulls `charting` and `hfa-core`).
**OpenClaw and Cowork don't resolve `requires:`** — there you install the whole set (the README's
`--platform openclaw` command and the Cowork plugin each bring everything along).

### The `hfa-core` runtime layer
Every shipped `SKILL.md` carries a generated **preamble** and **epilogue** block (between
`<!-- hfa:preamble -->` / `<!-- hfa:epilogue -->` markers). On skill invocation the preamble runs a small
**bash** program (`skills/hfa-core/bin/hfa-preamble`) that manages onboarding, anonymous telemetry, missing
API-key prompts, daily update checks, and a per-user learnings log — all under `~/.hfa/`. `hfa-core` is
installed automatically as a dependency of every other skill.

This runtime layer is **bash + Unix coreutils** and is **optional**: if no POSIX shell is reachable it prints
`HFA_CORE: not found` and the skill proceeds without it. The skill's *instructions* always work; only the
runtime niceties go dormant. This matters on Windows — see [Runtime layer on Windows](#runtime-layer-on-windows).

---

## Claude Code

Claude Code has **first-class skill support**: it scans its skills directories for `SKILL.md` files and
surfaces each skill's name + description to the model, which invokes the skill when a request matches its
triggers.

### What happens underneath
Driven by `src/adapters/claude-code.js` + `src/install.js`:
1. **Resolve closure** — `requires:` walked depth-first (dependencies first).
2. **Copy** — `copyTree` recursively copies each skill folder into `~/.claude/skills/<name>/` (user) or
   `./.claude/skills/<name>/` (project), **skipping** `node_modules`, `.venv`, `__pycache__`, `.git`,
   `tests` (vendored first-party assets like `charting/vendor/highcharts/` are kept).
3. **Env** — the union of `env:` keys across the closure is resolved from `process.env` → env file →
   interactive prompt, then written to `~/.hfa/.env` (user) or `./.env` (project), `chmod 600`.
4. **Manifest** — an install record is appended to `~/.hfa/install-manifest.jsonl` (powers guided upgrades).
5. **Runtime warning** — if any skill needs `python` or `bun`, you're told to have it installed.

**Discovery:** Claude Code reads each `SKILL.md`'s frontmatter; the model matches your request against the
`Triggers:` in the description and loads the body on demand. The `hfa-core` preamble runs first on invocation.

### Surfacing skills in the common prompt
After copying, the installer injects the [routing table](#the-routing-table) into Claude Code's memory file
(`~/.claude/CLAUDE.md` for user scope, `./CLAUDE.md` for project) and merges with anything already there, so
repeated installs accumulate. CLAUDE.md is loaded into context every session, so every installed skill is
advertised even before lazy discovery kicks in.

### Caveats
- The runtime layer needs a POSIX shell (native on Linux/macOS; **Git Bash** on Windows).
- `python` / `bun` are per-skill prerequisites the installer does not install for you.

---

## Codex

Codex has **no native skills concept**. The installer bridges this two ways: it copies the skill source
*and* generates a **custom slash-prompt** for each skill, which Codex exposes as `/<name>`.

### What happens underneath
Driven by `src/adapters/codex.js`:
1. **Copy** — `copyTree` into `~/.codex/skills/<name>/` (user) or `./.codex/skills/<name>/` (project).
2. **Slash-prompt** — a file `~/.codex/prompts/<name>.md` is generated: a small header
   (`Skill: <name>`, `Source: <path>`) followed by the skill's `SKILL.md` body (frontmatter stripped).
   Codex surfaces this as the `/<name>` command.
3. **Env** — written to `~/.codex/.env` (user) or `./.env` (project), `chmod 600`.

**Invocation:** type `/single-stock-deep-dive` (etc.) to load that skill's instructions into the turn.

### Surfacing skills in the common prompt
Codex reads **`AGENTS.md`** into the first turn of a session, and the installer injects the routing table
there (`~/.codex/AGENTS.md` user / `./AGENTS.md` project), merging across installs — this is what makes the
model *aware* of the skills (the slash-prompts alone are not auto-listed). Codex resolves instruction files
in this precedence: `AGENTS.override.md` → `AGENTS.md` → `TEAM_GUIDE.md` → `.agents.md`. **Size cap:** Codex
truncates each instruction file at `project_doc_max_bytes` (set in `~/.codex/config.toml`) — for the full
18-skill table, raise that limit or keep trigger lists terse.

Codex can be driven headlessly with an OpenAI API key (`codex exec`) to confirm the skills load — the README
shows the command.

### Caveats
- No native skills — the slash-prompt is the only bridge; skills are not auto-injected, so the AGENTS.md
  table is what makes the model *aware* of them.
- AGENTS.md is size-capped (`project_doc_max_bytes`).
- Runtime layer needs a POSIX shell; on Windows Codex may default to PowerShell — see
  [Runtime layer on Windows](#runtime-layer-on-windows).

---

## OpenClaw

[OpenClaw](https://openclaw.ai) is an open-source, locally-run personal AI assistant (controlled through chat
apps; backends Anthropic / OpenAI / local models). It has **first-class skill support** following the
`SKILL.md` convention, an agent **workspace**, and a JSON config at `~/.openclaw/openclaw.json`.

### What happens underneath
OpenClaw discovers any `SKILL.md` under a configured root and compiles the discovered skills into a **compact
XML block injected directly into the system prompt** (model-invoked unless a skill sets
`disable-model-invocation: true`; user-invocable skills also appear as slash commands). When it uses its
bundled Claude CLI backend, it passes the skills via `--plugin-dir`. Skill roots, highest → lowest
precedence: `<workspace>/skills` → `<workspace>/.agents/skills` → `~/.agents/skills` → `~/.openclaw/skills`
(the managed root the installer writes to) → bundled → `skills.load.extraDirs`. So on OpenClaw **placement
alone already advertises every skill in the system prompt** — the routing table the installer writes to
`~/.openclaw/workspace/AGENTS.md` (loaded every session) is belt-and-suspenders dispatch discipline.
(`SOUL.md`, the persona/tone file, is loaded too but is not the place for a skills table.)

### Caveats
- **No `requires:` closure resolution** — the README's `--platform openclaw` install brings the whole set.
- **Tool-name skew** — skill bodies reference Claude Code tools ("the Bash tool", "the Read/Edit tool",
  "the Agent tool"); OpenClaw's surface is `exec` / `read` / `write` / `edit` / `sessions_spawn`. The
  instructions still read sensibly, but the literal tool names differ.
- **`~/.hfa/.env` is not read natively** — set API keys (`FMP_API_KEY`, `FINMIND_TOKEN`, `SERPAPI_API_KEY`)
  in OpenClaw's environment; the `hfa-core` runtime path reads `~/.hfa/.env` only when its bash preamble runs.
- **Frontmatter** — OpenClaw expects any `metadata` to be a single-line JSON object; it ignores fields it
  doesn't use (`requires:`, `env:` are inert there).

> Facts in this section come solely from OpenClaw's own documentation
> ([openclaw.ai](https://openclaw.ai), [docs.openclaw.ai](https://docs.openclaw.ai)).

---

## Claude Cowork

[Claude Cowork](https://claude.com/product/cowork) is Anthropic's agentic **desktop app** (announced Jan
2026; Pro/Max/Team/Enterprise; macOS + Windows). It runs the **same agentic engine as Claude Code** inside
the Claude app — no terminal — executing multi-step work against your local files in an isolated VM.

### What happens underneath
Cowork reads the **same Agent-Skills + plugin format** this repo already ships. Skills are managed by your
Claude **account** (synced) rather than a local folder, and are added through the app UI; once added they
work in **both Cowork and Chat**, and any code they run executes in an isolated VM. Adding our marketplace as
a plugin pulls a persona's whole skill set in one step (no `requires:` resolution needed).

### Surfacing skills in the common prompt
Cowork's common prompt is **Settings → Cowork → Global instructions** — standing instructions applied to
every session. That's where the routing table goes; because Cowork skills are app-managed, the README
generates a Cowork-flavoured table with no filesystem **Load** column.

### Caveats
- **No CLI / no local skills dir** — Cowork skills are account-managed and added in the app UI, not by
  copying into a folder. (The bundled installer has no `--platform cowork`; it only generates the
  global-instructions table — see the README.)
- **Per-skill `description` ≤ 200 chars** on the *ZIP-upload* path — our descriptions are longer (built for
  Claude Code). Via the **plugin** path they ingest as-is (same as Claude Code); if a direct ZIP upload
  rejects a long description, trim the frontmatter `description` (the `Triggers:` already live in the routing
  table).
- **`SKILL.md` casing** — the skill spec is `SKILL.md`; if a ZIP upload insists on lowercase `skill.md`,
  rename it inside the ZIP.
- **hfa-core runtime layer** runs in Cowork's VM sandbox; if it can't locate `hfa-core` it prints
  `HFA_CORE: not found` and the skill proceeds (instructions work; telemetry/keys/learnings dormant).

> Source: Anthropic / Claude docs — [claude.com/product/cowork](https://claude.com/product/cowork) and
> [support.claude.com](https://support.claude.com) ("Get started with Cowork", "Use plugins in Claude",
> "How to create custom skills").

---

## The routing table

A **routing table** is a consolidated, always-loaded list that names every skill, its trigger phrases, and
where its `SKILL.md` lives — so the agent is aware of the full toolbox without waiting for lazy discovery.
**The installer generates and injects it automatically** on every install (merging across installs); the
[README](README.md) shows how to (re)generate it by hand. It is written into each runtime's common-prompt
file:

| Runtime | Injected into |
|---|---|
| Claude Code | `~/.claude/CLAUDE.md` (user) or `./CLAUDE.md` (project) |
| Codex | `~/.codex/AGENTS.md` (global) or `./AGENTS.md` (project) |
| OpenClaw | `~/.openclaw/workspace/AGENTS.md` |
| Claude Cowork | **Settings → Cowork → Global instructions** (pasted; no Load column) |

It is built from each skill's `Triggers:` (in `registry.json`), one row per skill. Example (token
`<skills-dir>` stands in for the runtime's skills path):

```markdown
## Hedge Fund Analyst skills (routing table)

When a request matches a skill's triggers, load that skill's SKILL.md and follow it.

| Skill | Use when the user… | Load |
|-------|--------------------|------|
| single-stock-deep-dive | "analyze X", "deep dive on Y", "is Z a buy", "bull/bear case", "thesis on Y" | `<skills-dir>/single-stock-deep-dive/SKILL.md` |
| thematic-investing | "value chain for X", "who benefits from X", "picks and shovels for X", "is X theme real" | `<skills-dir>/thematic-investing/SKILL.md` |
| technical-analysis | "technical analysis of X", "entry/exit for Y", "where's my stop", "is X overbought", "support/resistance" | `<skills-dir>/technical-analysis/SKILL.md` |
| company-wiki | "build a company wiki for X", "research wiki on Y", "company research site for Z" | `<skills-dir>/company-wiki/SKILL.md` |
| analyst-playbook | "how should I structure this analysis", "compare X and Y", "what matters for this sector" | `<skills-dir>/analyst-playbook/SKILL.md` |
| 13f-analysis | "get the 13F for X", "what does <fund> own", "13F holdings of Y", "CIK for <fund>" | `<skills-dir>/13f-analysis/SKILL.md` |
| sec-filings | "get the 10-K/10-Q/8-K for X", "risk factors / MD&A", "insider transactions", "EX-99.1 for Y" | `<skills-dir>/sec-filings/SKILL.md` |
| financialmodellingprep | "historical prices for X", "stock news", "income statement for Y", "earnings transcript" | `<skills-dir>/financialmodellingprep/SKILL.md` |
| finmind | "Taiwan stock data for X", "TSMC monthly revenue", "TWSE financials / dividends for Y" | `<skills-dir>/finmind/SKILL.md` |
| market-intelligence | "google trends for X", "nowcast <company> sales", "trends-based revenue model" | `<skills-dir>/market-intelligence/SKILL.md` |
| company-universe-manager | "add to my watchlist", "when does X report earnings", "run the daily monitor", "daily brief" | `<skills-dir>/company-universe-manager/SKILL.md` |
| analyzing-financial-statements | "calculate financial ratios for X", "P/E / ROE / debt-to-equity of Y", "ratio analysis" | `<skills-dir>/analyzing-financial-statements/SKILL.md` |
| creating-financial-models | "build a DCF for X", "intrinsic value of Y", "accretion/dilution", "sensitivity / scenarios" | `<skills-dir>/creating-financial-models/SKILL.md` |
| charting | "chart revenue over time", "plot YoY", "segment breakdown", "candlestick chart", "margins over time" | `<skills-dir>/charting/SKILL.md` |
| reporting | "generate a PDF report", "turn this into a deck", "client-ready report", "investment memo PDF" | `<skills-dir>/reporting/SKILL.md` |
| wiki-builder | "serve wiki", "render markdown as a website", "open my notes in the browser" | `<skills-dir>/wiki-builder/SKILL.md` |
| data-analysis | "analyze this CSV", "explore this dataset", "build a dashboard", "EDA on X", "data quality of X" | `<skills-dir>/data-analysis/SKILL.md` |
| hfa-core | runtime (auto-installed): "hfa setup/config", "check for hfa updates", "show my hfa learnings" | `<skills-dir>/hfa-core/SKILL.md` |
```

---

## Windows specifics

### The install layer is genuinely cross-platform
All adapters build paths only from Node's `os.homedir()` + `path.join()` — no hardcoded `~`, no `%APPDATA%`,
no POSIX-only assumptions — and `test/integration/windows-paths.test.mjs` asserts the Windows layout by
driving the real adapters with `path.win32`. On Windows, `os.homedir()` is `%USERPROFILE%` and `path.join`
uses `\`. The exact Windows paths the installer produces (reproduced with Node's `path.win32`):

```
Claude Code   user skills      C:\Users\me\.claude\skills\single-stock-deep-dive
              project skills   C:\proj\.claude\skills\single-stock-deep-dive
              user env         C:\Users\me\.hfa\.env
Codex         user skills      C:\Users\me\.codex\skills\single-stock-deep-dive
              user slash-prompt C:\Users\me\.codex\prompts\single-stock-deep-dive.md
              user env         C:\Users\me\.codex\.env
OpenClaw      managed skills   C:\Users\me\.openclaw\skills\single-stock-deep-dive
              config           C:\Users\me\.openclaw\openclaw.json
```

Relocate config roots with environment variables: `CLAUDE_CONFIG_DIR` (Claude Code), `CODEX_HOME` (Codex),
`OPENCLAW_PROFILE` (OpenClaw → `~/.openclaw/workspace-<profile>`).

### Runtime layer on Windows
The **install** works on native Windows. The **`hfa-core` runtime layer** (the bash preamble/epilogue in
every `SKILL.md`, plus `skills/hfa-core/bin/*`) is a different matter: `hfa-preamble` is
`#!/usr/bin/env bash` and uses Unix coreutils — `find -mmin`, `wc`, `tr`, `grep -E`, `printenv`, `touch`,
`mkdir`, `dirname`. PowerShell/cmd cannot run it, and even a bare `bash.exe` is not enough — it needs the
coreutils too. To make it work:

1. **Git Bash (Git for Windows) — recommended.** It bundles bash **and** the MSYS2 coreutils the scripts
   call. As of the **2.1.139** release (May 2026) Claude Code on Windows defaults to a **native PowerShell
   tool** and no longer *requires* Git for Windows — but the `hfa-core` preamble is bash, so you still need
   **Git for Windows** (it enables Claude Code's Bash tool via Git Bash; without it Claude Code falls back to
   PowerShell, which can't run the preamble). Ensure `bash` is on `PATH`.
2. **WSL.** A full Linux userland — everything works — but installs and state land *inside* the WSL
   filesystem (`~/.claude/skills`, `~/.hfa`). Keep the agent and the install on the same side of the WSL
   boundary, or paths won't line up.
3. **Codex / OpenClaw on Windows.** These may default to PowerShell for shell execution. Put **Git Bash** on
   `PATH` so the bash-fenced preamble runs (or arrange for it to be invoked via `bash -c`).
4. **If no POSIX shell is reachable** the preamble prints `HFA_CORE: not found` and the skill proceeds —
   **skill instructions still work; only telemetry, key prompts, learnings, and update checks go dormant.**

> **Durable fix (proposed, not yet built):** reimplement the five `bin/` scripts in **Node** — already a hard
> dependency of the installer — and have the generated preamble call `node "$_HFA/bin/hfa-core.mjs" preamble …`
> instead of executing a bash script. That removes the bash + coreutils dependency and makes the runtime
> layer OS-agnostic. Tracked in [Known gaps](#known-gaps--follow-ups).

---

## How this was built & verified

- **`--platform openclaw`** — `src/adapters/openclaw.js` installs SKILL.md folders into `~/.openclaw/skills`
  (or `./.openclaw/skills` for project scope), registered in `src/adapters/index.js`.
- **Automatic routing-table injection** — `src/routing-table.js` + `scripts/build-routing-table.js` generate
  the table from frontmatter; `install()` injects and merges it into each runtime's `CLAUDE.md` / `AGENTS.md`.
- **Integration harness + devcontainer** — `test/integration/` (real installs for all three CLI platforms +
  the `path.win32` Windows simulator) and `.devcontainer/integration/` (Claude Code + Codex baked in; built
  and run green inside the Linux container).

## Known gaps / follow-ups

1. **Preamble discovery list omits `~/.openclaw/...`.** The bash preamble scans `~/.claude/...` and
   `~/.codex/...` but not OpenClaw paths; until added, point `~/.hfa/core-path` at the installed `hfa-core`.
2. **Runtime layer is bash + coreutils.** Reimplementing the `bin/` scripts in Node is the durable
   cross-platform fix so the `hfa-core` runtime works in native Windows PowerShell (see
   [Runtime layer on Windows](#runtime-layer-on-windows)).
3. **OpenClaw tool-name skew.** Skill bodies say "the Bash/Read/Edit/Agent tool"; the OpenClaw adapter copies
   them verbatim (no rewrite to `exec`/`read`/`write`/`sessions_spawn`) — a future content transform could map them.
4. **Live Windows / CI verification deferred.** No `windows-latest` CI leg yet; the install/path layer is
   proven via the `path.win32` harness + the Linux integration container, not a real Windows runtime.

---

## Sources

**OpenClaw** — [openclaw.ai](https://openclaw.ai),
[docs.openclaw.ai/tools/skills](https://docs.openclaw.ai/tools/skills),
[docs.openclaw.ai/concepts/agent-workspace](https://docs.openclaw.ai/concepts/agent-workspace),
[docs.openclaw.ai/tools/skills-config](https://docs.openclaw.ai/tools/skills-config).
**Codex** — [developers.openai.com/codex/guides/agents-md](https://developers.openai.com/codex/guides/agents-md),
[Codex config](https://github.com/openai/codex/blob/main/docs/config.md),
[Codex non-interactive mode](https://developers.openai.com/codex/noninteractive),
[Codex auth](https://developers.openai.com/codex/auth.md).
**Claude Code** — [code.claude.com/docs](https://code.claude.com/docs) (skills, plugins, settings, memory).
**Claude Cowork** — [claude.com/product/cowork](https://claude.com/product/cowork);
[support.claude.com](https://support.claude.com) ("Get started with Cowork", "Use plugins in Claude",
"How to create custom skills").
**This repo** — `src/adapters/claude-code.js`, `src/adapters/codex.js`, `src/adapters/openclaw.js`,
`src/adapters/copy.js`, `src/install.js`, `src/resolve.js`, `src/routing-table.js`,
`skills/hfa-core/bin/hfa-preamble`, `skills/hfa-core/templates/{preamble,epilogue}.md.tmpl`, `registry.json`.
