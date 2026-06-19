# Integration test devcontainer

A **separate** devcontainer from [`../`](../) (the `analyst-kit-skills-e2e` image). This one
exists to test the **installers** — it bakes in the two runtimes we install *into*,
**Claude Code** and **Codex**, plus the runtimes skills need, so the full
`node bin/analyst-kit.js install … --platform <p>` flow and the integration tests run
end-to-end on Linux.

## What's inside

| Component | Why |
|-----------|-----|
| `@anthropic-ai/claude-code` (npm, pinned `@2`) | target runtime — `--platform claude-code` |
| `@openai/codex` (npm, pinned `@0`) | target runtime — `--platform codex` |
| Node 22, Bun, Python 3 (+ polars/pandas/pytest/requests) | the per-skill runtimes |
| `git`, `jq`, `curl` | harness plumbing |

The **path-layer check** (`test/integration/windows-paths.test.mjs`) drives the **real adapters** with an
injected Windows `homedir`/`cwd` and `path.win32` from Linux — proving the install paths are OS-portable,
which is what lets **WSL2 (Linux) Just Work**. Windows itself is supported **via WSL2**, not natively (the
bash `analyst-kit-core` runtime can't run under PowerShell/cmd — see `compatibility.md`).

## Open it

- **VS Code / Cursor:** “Dev Containers: Reopen in Container” → pick **analyst-kit-integration**.
- **CLI:** `devcontainer up --config .devcontainer/integration/devcontainer.json`

`postCreateCommand` prints the CLI versions and runs the integration tests once.

## Use it

```bash
# the integration tests (real installs on Linux + the path.win32 path-layer check)
npm run test:integration

# install ALL skills into a runtime — one command (--scope project keeps it in the workspace)
node bin/analyst-kit.js claude-code --scope project       # or: codex · openclaw
node bin/analyst-kit.js codex --scope project             # Codex also writes ~/.codex/prompts/<name>.md

# confirm the CLIs see them
claude --version && codex --version
```

> The image build installs the CLIs but does **not** authenticate them — set
> `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (or sign in) before driving the agents.
> The installer + path tests need no auth.
