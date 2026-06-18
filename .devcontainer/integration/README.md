# Integration test devcontainer

A **separate** devcontainer from [`../`](../) (the `hfa-skills-e2e` image). This one
exists to test the **installers** — it bakes in the two runtimes we install *into*,
**Claude Code** and **Codex**, plus the runtimes skills need, so the full
`node bin/hfa.js install … --platform <p>` flow and the integration tests run
end-to-end on Linux.

## What's inside

| Component | Why |
|-----------|-----|
| `@anthropic-ai/claude-code` (npm, pinned `@2`) | target runtime — `--platform claude-code` |
| `@openai/codex` (npm, pinned `@0`) | target runtime — `--platform codex` |
| Node 22, Bun, Python 3 (+ polars/pandas/pytest/requests) | the per-skill runtimes |
| `git`, `jq`, `curl` | harness plumbing |

The **"Windows simulator"** is not a VM — it's the `test/integration/windows-paths.test.mjs`
harness, which drives the **real adapters** with an injected Windows `homedir`/`cwd`
and `path.win32`, asserting the exact `%USERPROFILE%\.claude\skills\…` /
`…\.codex\…` layout from Linux. (A real Windows runtime is only needed to exercise the
bash `hfa-core` *runtime layer* — see `compatibility.md`.)

## Open it

- **VS Code / Cursor:** “Dev Containers: Reopen in Container” → pick **hfa-integration**.
- **CLI:** `devcontainer up --config .devcontainer/integration/devcontainer.json`

`postCreateCommand` prints the CLI versions and runs the integration tests once.

## Use it

```bash
# the integration tests (real installs on Linux + the path.win32 Windows simulator)
npm run test:integration

# install all skills into Claude Code (project scope, inside the container workspace)
for s in $(jq -r '.skills[].name' registry.json); do
  node bin/hfa.js install "$s" --platform claude-code --scope project -y
done

# same for Codex (also generates ~/.codex/prompts/<name>.md slash-prompts)
node bin/hfa.js install single-stock-deep-dive --platform codex --scope project -y

# confirm the CLIs see them
claude --version && codex --version
```

> The image build installs the CLIs but does **not** authenticate them — set
> `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (or sign in) before driving the agents.
> The installer + path tests need no auth.
