# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **not an application** — it's a packager and distributor of *skills* for AI
coding agents (Claude Code, Codex). A "skill" is a self-contained folder under
`skills/<name>/` whose `SKILL.md` holds agent instructions, optionally alongside
runnable `scripts/`, `references/`, `templates/`, and `assets/`. The repo ships two
ways to consume them: the **primary** path is a single **Claude Code / Cowork plugin**
(`plugins/analyst-kit/`, advertised by `.claude-plugin/marketplace.json`) that bundles
every skill plus a `research-auditor` subagent (`agents/`) and a SessionStart runtime
hook (`hooks/`); the secondary path is a **Node installer** (`bin/analyst-kit.js` → `src/`)
that copies skills into a target runtime (Claude Code, Codex, OpenClaw, Cowork).

The skills themselves are the product; `src/` is just plumbing that catalogs, resolves,
and installs them. End-user docs (install paths, skill list, API keys) live in
`README.md` and are not repeated here.

## Commands

```bash
npm run validate         # lint skills + plugin manifests against the contract (src/registry + scripts/validate.js)
npm run build:registry   # regenerate registry.json from skill frontmatter
npm run check:registry   # CI check: fail if registry.json is stale (does not write)

node bin/analyst-kit.js list                                              # browse skills + personas
node bin/analyst-kit.js install <skill|persona> --platform claude-code   # copy a skill + its deps into a runtime
node bin/analyst-kit.js install <skill> --platform codex --scope project --dry-run
node bin/analyst-kit.js doctor --platform claude-code                    # check runtimes + API keys
```

`npm run validate` + `npm run check:registry` are exactly what CI runs
(`.github/workflows/validate.yml`) on every push/PR. There is no build step and no
JS test suite — individual skills may ship their own tests (e.g. `skills/finmind/tests/`
runs under `pytest`), run inside the skill folder.

Note: the package isn't published to npm yet (the name `analyst-kit` is *available* —
`npm view analyst-kit` 404s as of 2026-06-19), so invoke the binary as `node bin/analyst-kit.js`
from a clone. Public installs use `npx github:mohitjandwani/analyst-kit` or the plugin path.

## Architecture

**Skill frontmatter is the single source of truth.** The YAML block at the top of each
`SKILL.md` drives everything downstream — `registry.json`, the installer's dependency
resolution, and the validator. Never hand-edit `registry.json`; edit frontmatter and run
`npm run build:registry`.

### The pipeline (`src/`)

- `frontmatter.js` — a **minimal, purpose-built** YAML parser, *not* a general one. It
  handles only the shapes the skill contract allows (scalar/block `description`, inline
  or block `requires`/`env` lists). Frontmatter that strays outside those shapes will
  silently misparse — keep it within the contract.
- `registry.js` — `scanSkills()` walks `skills/`, parses frontmatter, and infers
  `runtime` from disk (`package.json` → `bun`; a `scripts/*.py` → `python`; else `none`).
  `getSkills()` scans **live disk first** and only falls back to `registry.json` if the
  tree is unavailable, so the CLI always reflects reality even when the committed
  registry lags.
- `resolve.js` — `resolveClosure()` walks the `requires` graph depth-first
  (dependencies-first, cycle-detecting). Personas are read from the plugins under
  `plugins/` — `listPersonas()` takes each plugin's skills from its manifest `skills`
  array if present, else from the folders bundled under `<plugin>/skills/` (the
  self-contained layout). Today that's the single `analyst-kit` plugin, so
  `install analyst-kit` ≈ `install all`.
- `install.js` + `adapters/` — `install()` resolves the closure, then each platform
  adapter (`claude-code.js`, `codex.js`) decides install dir, env-file location, and
  `write()` behavior. `copy.js#copyTree` does the recursive copy, skipping
  `node_modules`, `.venv`, `__pycache__`, `.git`, `tests`. Codex has no native skill
  format, so its adapter additionally emits a slash-prompt under `prompts/`.
- `env.js` — unions the `env:` keys across a closure, resolves them from
  `process.env` + an `.env` file, prompts interactively for the rest, and persists with
  `chmod 600`. Any `env:` key a skill declares **must** also appear in `.env.example`
  (the validator enforces this).
- `paths.js` — repo-root-relative paths and `EXCLUDED_SKILLS` (skills present on disk but
  withheld from the shippable registry/plugin, e.g. an in-progress skill with an empty
  body — reported as "skipped", not a failure).

### The plugin bundle (`plugins/analyst-kit/`)

The marketplace plugin is the **primary** install and must be **self-contained** —
Claude Code / Cowork copy a plugin into an isolated per-plugin cache, so anything it
references via `../..` (e.g. the top-level `skills/`) **breaks after install**. Layout:

- `skills/` — a **generated, committed artifact** (like `registry.json`). `scripts/build-plugin.js`
  copies every shipped skill from the top-level `skills/` source of truth into it; `--check`
  fails CI if it drifts. **Never hand-edit `plugins/analyst-kit/skills/`** — edit the source
  skill and run `npm run build:plugin`.
- `agents/research-auditor.md` — hand-authored subagent, invoked after every research
  deliverable (wired via the epilogue template) to fact-check it for hallucinations/data errors.
- `hooks/hooks.json` — a `SessionStart` hook running `skills/analyst-kit-core/bin/analyst-kit-session-hook`
  (the runtime: onboarding, daily update check, telemetry). The markdown preamble still runs
  the same bins for non-plugin runtimes; the two coordinate through state files in `~/.analyst-kit/`.
- `.claude-plugin/plugin.json` — hand-authored manifest (version stamped by `sync-preamble.js`).

### Skill contract (enforced by `scripts/validate.js`)

- `name` must equal the folder name and be kebab-case.
- `type` is `capability` (a requirable unit — data source, engine, deliverable, or
  knowledge like `analyst-playbook` — which may itself `require:` other capabilities,
  e.g. `reporting` → `charting`) or `workflow` (an engagement entry point that
  orchestrates capabilities via `requires:`). The one dependency rule: **nothing may
  require a workflow**; the validator also rejects dependency cycles.
- `description` ≥ 40 chars and **must contain a `Triggers:` clause** of natural-language
  phrases — agents only see `name` + `description`, so discoverability lives there.
- `SKILL.md` body must be non-empty; no dependency cycles; no **dependency-manager**
  dirs tracked by git (`node_modules`, `.venv`, `__pycache__` — this is what
  `validate.js` enforces). Deliberately-vendored *first-party runtime assets* a skill
  must ship to function (e.g. `skills/charting/vendor/highcharts/`, inlined for offline
  PDF-safe rendering) are allowed and **should** be committed — they are not "vendored
  dirs" in the dependency sense and `copyTree` ships them on install.
- A plugin must be self-contained: its skills live under `<plugin>/skills/` (no `../..`
  paths — they break after install), the bundle must be **closure-complete** (every
  required capability present), and it must not bundle an `EXCLUDED_SKILLS` entry. Shipped
  `agents/*.md` need `name` + `description` frontmatter; `hooks/hooks.json` must be valid
  JSON. All enforced by `validate.js`.

## Making changes

- **Editing a skill's frontmatter or adding/removing a skill** → run
  `npm run build:registry` **and `npm run build:plugin`**, then `npm run validate`. The
  single `analyst-kit` plugin bundles every shipped skill automatically, so there's no
  plugin manifest to hand-edit — just rebuild the bundle.
- **Promoting a work-in-progress skill** → remove it from `EXCLUDED_SKILLS` in
  `src/paths.js`, then rebuild the registry **and the plugin bundle**.
- **Adding a new API key** → declare it in `.env.example` *and* in the consuming skill's
  `env:` list, or validation fails.
- **Adding a platform** → add an adapter in `src/adapters/` and register it in
  `adapters/index.js`; the adapter interface is `installDir(scope)`, `envFile(scope)`,
  `write(skill, scope)`.
- **The analyst-kit-core runtime blocks** → every shipped SKILL.md carries generated
  `<!-- analyst-kit:preamble -->` / `<!-- analyst-kit:epilogue -->` blocks (analytics, onboarding,
  update check, learnings — state lives in `~/.analyst-kit/`). Never edit between the markers
  by hand: edit `skills/analyst-kit-core/templates/*.md.tmpl` and run `npm run sync:preamble`
  (CI runs `--check`). New skills must `require: [analyst-kit-core]`; the same script stamps
  the root `VERSION` into `skills/analyst-kit-core/VERSION`, plugin manifests, and
  `package.json` — bump only the root `VERSION` file.


## Git commit rules
- Use Conventional Commits: type(scope): subject (imperative, ≤50 chars).
- One logical change per commit; it must build and pass tests alone.
- Body explains WHY. Reference issues in footer (Fixes #123).
- Separate refactors from behavior changes into distinct commits.
- Stage files explicitly; never `git add -A`. Never commit secrets.
- Commit at completed checkpoints, not partial/broken states.