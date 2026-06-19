# Integration-test image for the analyst-kit skill installers across agent runtimes.
# Separate from ../Dockerfile (the skills e2e image) — this one installs the two
# CLIs we install INTO (Claude Code + Codex) so the installers and the integration
# tests (incl. the path.win32 "Windows simulator") run end-to-end on Linux.
# The repo is mounted at runtime, so editing the installer/skills needs no rebuild.
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# System runtimes a few skill scripts need, plus git/jq/curl for the harness.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git jq ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Global CLIs: Claude Code + Codex (the runtimes we install into) and Bun (skills).
# Pinned to current majors for reproducible builds.
RUN npm install -g @anthropic-ai/claude-code@2 @openai/codex@0 bun

# Python libs imported by some skill scripts (kept minimal).
RUN pip3 install --break-system-packages --no-cache-dir polars pandas pytest requests

# Quiet headless first-run noise for both CLIs.
ENV DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    CODEX_DISABLE_UPDATE_CHECK=1

# Non-root: Claude Code's --dangerously-skip-permissions refuses uid 0; `node` is
# the image's built-in uid-1000 user, synced to the host uid by the devcontainer.
USER node
WORKDIR /workspaces
