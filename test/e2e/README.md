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
- Task bodies are **self-describing prompts** — each states its own deliverable (e.g. "a
  branded PDF report written to `output/<id>.pdf`"). The harness adds **no** preamble to the
  user prompt; cross-cutting behavior (skills-first, source-tracking, no made-up data, plan
  & verify, clarify) lives in a **system prompt** (`system-prompt.md`) appended to Claude
  Code's default. The PDF check keys off `output/<id>`; an `.html` left in the workdir is
  auto-converted (see below), so an `output/<id>.pdf` or any `.html` deliverable counts.
- Frontmatter is parsed by the repo's minimal parser (`src/frontmatter.js`): scalars only,
  and **no inline `#` comments**.

## What the harness does around each task

The harness keeps the user prompt realistic — it does **not** inject an environment brief, a
cost-discipline playbook, or an output contract into it. The agent works from its
natively-listed installed skills and the task body. The harness only:

- **Appends a system prompt** — `test/e2e/system-prompt.md` is passed via
  `--append-system-prompt` (it augments Claude Code's default, which already lists installed
  skills). It carries the cross-cutting rules: search skills before the web, record every
  source in `data_sources.md`, never state data from memory, plan-with-skills then verify,
  and clarify-then-record-in-learnings. Edit that file to change agent behavior; the user
  prompt stays the bare task. The harness installs **skills only** — no agent definitions;
  any data-gathering sub-agent is launched via the Task tool per a skill's own recipe (e.g.
  `sec-filings`).
- **Converts HTML → PDF itself** — after the run, if `output/` has no PDF, the harness runs
  `html2pdf` on the agent's `.html` deliverable (in `output/` or the workdir) as a
  post-processing step (recorded as `autoPdf` in `report.json`).
- **Verifies exactly one valid PDF** — file exists, non-empty, `%PDF-` header. Content is
  reviewed manually.

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

## Viewing the logs (live)

The harness **auto-opens a local viewer at run start** and it **live-tails** while the agent
works — the browser opens within a few seconds of the run beginning, and the timeline grows in
real time. The viewer (`viewer.html`) renders the run as a timeline: assistant text and the
final result are Markdown, every tool call is colour-coded by family (Skill is the violet
standout), each call is stitched to its result, and thinking is collapsed by default. A status
pill in the header shows `● live` while tailing and `✓ done` once the run's `result` lands.

```
▶ live log viewer: http://127.0.0.1:8787/viewer.html?file=logs/latest/00-smoke.stream.jsonl
```

Under the hood it polls the served `*.stream.jsonl` every ~2s and re-renders on growth,
preserving your expanded panels and scroll position. The server stays up (scoped to
`test/e2e/`) until you press Ctrl+C, which exits with the run's pass/fail status. Knobs:

- `--no-viewer` flag, or `E2E_NO_VIEWER=1` — skip the viewer entirely; the harness then uses
  the simple blocking run path. Auto-off when `CI` is set, so it never hangs a pipeline.
- `E2E_VIEWER_PORT=9000` — override the port (default `8787`; auto-increments if taken).

You can also open `viewer.html` directly (no server) and drag any `*.stream.jsonl` onto it
(a manual open cancels live mode).

## Watching the run in the terminal

Independently of the browser viewer, every run prints a **colorized live trace** to the
terminal — one line per tool call, coloured by family and showing the active skill/subagent:

```
  ✦ Skill → single-stock-deep-dive
  ❯ Bash  python edgar.py exhibits STM --items 2.02
  ⟁ Task → general-purpose [haiku]
  ▤ Read  research/STM-deep-dive/09-valuation.md
```

Colour is emitted only when your terminal is a TTY (the harness forwards `E2E_TTY=1` into the
container for this), so piped / `tee`'d / backgrounded output stays clean plain text. Pass
`--verbose` to also append each tool call's full input JSON.

## Running a single task from inside the container

After `npm run container:terminal` (opens a shell in the running devcontainer), launch one
task directly — the harness loads `test/e2e/.env` in `--in-container` mode, so the API keys are
already present, no manual sourcing:

```bash
bun test/e2e/run.ts --in-container --task 60-stm-deep-dive   # from inside the container
```

There is also an in-container convenience script: `npm run e2e:task -- 60-stm-deep-dive`
(**run it from inside the container only** — unlike the host-side `container:terminal`).
