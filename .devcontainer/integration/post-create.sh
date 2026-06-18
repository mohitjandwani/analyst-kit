#!/usr/bin/env bash
# Runs once after the integration container is created (non-root `node`, in the workspace).
set -euo pipefail

# Seed Claude Code state so headless runs never block on onboarding/folder-trust.
mkdir -p "$HOME/.claude"
if [ ! -f "$HOME/.claude.json" ]; then
  printf '{"hasCompletedOnboarding": true, "bypassPermissionsModeAccepted": true}\n' \
    > "$HOME/.claude.json"
fi

echo "== runtimes under test =="
printf 'node   %s\n' "$(node --version)"
printf 'claude %s\n' "$(claude --version 2>/dev/null || echo 'NOT FOUND')"
printf 'codex  %s\n' "$(codex --version 2>/dev/null || echo 'NOT FOUND')"
printf 'bun    %s\n' "$(bun --version 2>/dev/null || echo 'NOT FOUND')"
printf 'python %s\n' "$(python3 --version 2>/dev/null || echo 'NOT FOUND')"

echo "== integration tests (real installs on Linux + path.win32 'Windows simulator') =="
# Non-fatal so the container still comes up for debugging if a test fails.
node --test test/integration/*.test.mjs || echo "!! integration tests reported failures (see above)"

echo "post-create(integration): CLIs present; integration tests ran."
