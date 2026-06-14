# Task template

Copy this file to `tasks/<NN>-<slug>.task.md` (for example `tasks/10-nvda-deep-dive.task.md`)
and fill it in. The harness runs every file matching `tasks/*.task.md` in **filename order**;
this `TEMPLATE.md` is intentionally *not* named `*.task.md`, so the harness skips it.

## Copy this frontmatter block

Keep it clean — the frontmatter parser is minimal and does **not** support inline `#`
comments (anything after `key:` becomes part of the value). Document nothing inside it.

```markdown
---
id: 10-my-task
timeoutMs: 1200000
---
Write the task intent here as a normal prompt to the agent: what to research and what the
final deliverable should contain. Do NOT mention "PDF" or "html2pdf" — the harness appends a
fixed instruction telling the agent to render the single deliverable to `output/<id>.pdf`.
```

## Field reference

- **id** (required) — a slug. Names the output PDF (`pdfs/<id>.pdf`) and the per-task log
  files. Prefix the *filename* with a number (e.g. `10-`, `20-`) to control run order.
- **timeoutMs** (optional) — per-task wall-clock cap in milliseconds. Default is 20 minutes.

Tasks no longer declare skills or required env keys. The harness installs every skill in the
repo into the container, and the agent selects whichever it needs autonomously. The harness
forwards whatever API keys are present in its own environment; each skill declares its own
required env keys in its `SKILL.md` frontmatter (`env:`).

## Notes

- The body (everything after the closing `---`) is a free-form prompt to the agent.
- Each task is expected to produce exactly **one** PDF. The harness checks only that a valid,
  non-empty PDF was created (`%PDF-` header) — never its content, layout, or styling.
