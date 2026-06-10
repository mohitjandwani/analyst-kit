# e2e harness image: Claude Code + the runtimes skills need + a headless-Chromium
# HTML->PDF tool. Built once; the repo is mounted at runtime (not COPY'd) so editing
# skills/tasks never requires a rebuild.
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# System runtimes: python (charting/finmind/13f/universe scripts), git, curl, certs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Python libs used by skill scripts + common agent reach-fors (data fetching/analysis).
RUN pip3 install --break-system-packages --no-cache-dir \
        polars pandas pytest requests

# Global CLIs: Claude Code (the agent under test) and Bun (skills + the harness runner).
RUN npm install -g @anthropic-ai/claude-code bun

# html2pdf: a self-contained Playwright install in its own dir, exposed as a CLI on PATH.
# Browsers live in a world-readable shared path so the non-root runtime user can use them.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY html2pdf.mjs /opt/html2pdf/index.mjs
RUN cd /opt/html2pdf \
    && npm init -y >/dev/null 2>&1 \
    && npm install playwright \
    && npx playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright /opt/html2pdf
RUN printf '#!/bin/sh\nexec node /opt/html2pdf/index.mjs "$@"\n' > /usr/local/bin/html2pdf \
    && chmod +x /usr/local/bin/html2pdf

# Force Sonnet (main) + Haiku (small/fast/background) for EVERYTHING, and quiet the
# headless first-run noise. These are image-level ENV so they're present in every exec.
ENV ANTHROPIC_MODEL=claude-sonnet-4-6 \
    ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5-20251001 \
    ANTHROPIC_SMALL_FAST_MODEL=claude-haiku-4-5-20251001 \
    DISABLE_AUTOUPDATER=1 \
    DISABLE_TELEMETRY=1 \
    DISABLE_ERROR_REPORTING=1 \
    DISABLE_NON_ESSENTIAL_MODEL_CALLS=1

# Run as the image's built-in non-root user `node` (uid 1000). Required: Claude Code's
# --dangerously-skip-permissions refuses to run as root. The devcontainer syncs this
# user's uid to the host user's uid (updateRemoteUserUID) so mounted writes Just Work.
USER node
WORKDIR /workspaces
