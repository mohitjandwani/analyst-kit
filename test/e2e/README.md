# e2e test harness

End-to-end smoke test for the skills in this repo: spin up a container with Claude Code
installed, install the skills with `bin/hfa.js`, run agent **tasks**, and assert that each
task produces a valid PDF (file exists, non-empty, starts with the `%PDF-` header). The
PDF's content, layout, and styling are reviewed **manually** — the harness does not inspect
them.

Prerequisites on the host: Docker, the devcontainer CLI (`npm i -g @devcontainers/cli`), and
Bun. The image (Claude Code + Python/Bun + headless Chromium) builds once on first run.

## Tasks

A task is a Markdown file `tasks/<NN>-<slug>.task.md` with YAML frontmatter plus a free-form
prompt body. Start from:

- **`tasks/TEMPLATE.md`** — the format and a field reference (copy it to a real
  `tasks/<NN>-<slug>.task.md`).
- **`tasks/00-smoke.task.md`** — a complete example that needs no external API; it proves the
  container → Claude Code → `html2pdf` → PDF pipeline before any skill or live-data complexity.

Key conventions:

- Tasks declare only two frontmatter fields: `id` (required) and `timeoutMs` (optional,
  default 20 min). There is no `skills:` or `requiresEnv:` field.
- The harness installs **every** skill in the repo into the container before running any
  task; the agent selects whichever skills it needs autonomously.
- The harness forwards whatever API keys are present in its environment; if a key a task
  needs is absent the task will fail with no PDF output — that failure is visible in the
  report. Each skill declares its own required env keys in its `SKILL.md` frontmatter (`env:`).
- The frontmatter `id` names the output (`pdfs/<id>.pdf`) and the log files.
- Every task's PDF lands in one flat folder, `pdfs/`, for easy manual review.
- Task bodies describe **intent only** — the harness automatically appends an output contract
  asking for a single self-contained `output/<id>.html` (writing `output/<id>.pdf` directly
  also counts).
- Frontmatter is parsed by the repo's minimal parser (`src/frontmatter.js`): scalars only,
  and **no inline `#` comments**.

## What the harness does around each task (cost discipline)

The premium agent should spend its turns on judgment, not plumbing, so the harness:

- **Injects an environment brief** — each task workdir gets a `CLAUDE.md` (auto-loaded
  project memory) stating what is pre-verified: tools on PATH (`html2pdf`, `python3`+polars,
  `bun`), where skills live, and which API keys are present. The agent must not burn turns
  probing any of this.
- **Installs `agents/*.md`** into `~/.claude/agents/` — notably `data-extractor`
  (`model: haiku`), which the brief tells the main agent to delegate **all** data gathering
  to (FMP for GAAP metrics, IR press releases for non-GAAP KPIs; returns raw JSON records).
- **Routes math and boilerplate to scripts** — the brief points at the charting skill's
  one-shot CLIs (`python3 -m pipeline.cli yoy …` for Polars-computed growth,
  `bun scripts/render.ts …` for contract → self-contained HTML), so the model never
  hand-computes YoY or hand-writes Highcharts pages.
- **Converts HTML → PDF itself** — after the run, if `output/` has an `.html` but no PDF,
  the harness runs `html2pdf` as a post-processing step (recorded as `autoPdf` in
  `report.json`).

## Running (available once the harness lands)

Put your keys in `test/e2e/.env` (copy `test/e2e/.env.example`); the launcher loads it and
forwards the allowlisted keys into the container. That file is **authoritative — it
overrides any matching vars already in your shell**, so a stray `ANTHROPIC_API_KEY` in your
environment can't shadow it. With the `.env` filled in, no inline env is needed:

```bash
bun test/e2e/run.ts --task 00-smoke          # one task
bun test/e2e/run.ts                          # whole suite (sequential)
bun test/e2e/run.ts --concurrency 4          # whole suite, 4 at a time
```

Inline `KEY=… bun test/e2e/run.ts` still works for keys you haven't put in the `.env`, but
anything present in the `.env` takes precedence over the ambient environment.

Outputs: `pdfs/<id>.pdf` (review surface) and `logs/<timestamp>/` (per-task stream logs,
transcripts, and `report.json`), with `logs/latest` pointing at the most recent run.

### Running tasks concurrently

`--concurrency N` (alias `--parallel N`, default `1`) runs up to N tasks at once **inside
the single dev container** — one container's memory, one skill install, N agents. Each task
gets full isolation so concurrent `claude -p` processes never step on each other:

- its own working directory (`/tmp/run/<id>/`) for the deliverable and any intermediate files;
- its own **Claude HOME** (`/tmp/run/<id>/home`, exported as `HOME` + `CLAUDE_CONFIG_DIR`),
  so sessions, the project transcript dir, todos, and the onboarding json never collide. The
  installed `skills/` and `agents/` are shared read-only via symlink, so isolation costs no
  extra install and no extra container.

The per-task transcript copied into `logs/<ts>/<id>.transcript.jsonl` is read from that
task's own HOME, so it's always the right one. Heartbeat and `--verbose` trace lines are
prefixed with `[<id>]` so interleaved output stays attributable. `report.json` tasks are
sorted by id regardless of completion order.

There is no separate-container mode — same-container concurrency is strictly better on
memory and avoids installing every skill N times. (Note: `devcontainer up` is keyed to the
workspace folder, so launching the harness twice would reuse the **same** container anyway;
use `--concurrency` instead of running the harness in parallel yourself.)

## Viewing the logs

When a host run finishes, the harness **auto-starts a local viewer** and opens your browser
to the run's `*.stream.jsonl`. The viewer (`viewer.html`) renders the run as a timeline:
assistant text and the final result are formatted as Markdown, every tool call is
colour-coded by family (Skill is the violet standout), each call is stitched to its result,
and thinking is collapsed by default (toggle it from the header).

```
────────────────────────────────────────────────────────────────
▶ log viewer running at http://127.0.0.1:8787/viewer.html  (Ctrl+C to stop)
    00-smoke                 http://127.0.0.1:8787/viewer.html?file=logs/latest/00-smoke.stream.jsonl
────────────────────────────────────────────────────────────────
```

The server stays up (scoped to `test/e2e/`) until you press Ctrl+C, which exits with the
run's pass/fail status. Knobs:

- `--no-viewer` flag, or `E2E_NO_VIEWER=1` — skip the viewer and exit immediately. Auto-off
  when `CI` is set, so it never hangs a pipeline.
- `E2E_VIEWER_PORT=9000` — override the port (default `8787`; auto-increments if taken).

You can also open `viewer.html` directly (no server) and drag any `*.stream.jsonl` onto it.
