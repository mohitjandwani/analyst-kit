#!/usr/bin/env bash
# Runs once after the container is created (as the non-root `node` user, in the workspace).
set -euo pipefail

# Seed Claude Code state so headless `claude -p` never blocks on a first-run onboarding
# or folder-trust prompt. Harmless if the schema drifts; --dangerously-skip-permissions
# also covers trust at run time.
mkdir -p "$HOME/.claude"
if [ ! -f "$HOME/.claude.json" ]; then
  printf '{"hasCompletedOnboarding": true, "bypassPermissionsModeAccepted": true}\n' \
    > "$HOME/.claude.json"
fi

# Artifact dirs (inside the mounted workspace, so host-visible).
mkdir -p test/e2e/logs test/e2e/pdfs

echo "post-create: seeded ~/.claude.json; ensured test/e2e/{logs,pdfs}."
