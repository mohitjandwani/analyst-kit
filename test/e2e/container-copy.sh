#!/usr/bin/env bash
# Copy a file or folder OUT of the running e2e devcontainer to the host, print the host path,
# and reveal it in Finder (macOS). Invoked via `npm run container:copy` from the worktree root.
#
#   npm run container:copy -- /tmp/run/60-stm-deep-dive
#   npm run container:copy -- /tmp/run/60-stm-deep-dive/output/60-stm-deep-dive.pdf
#
# The container path is always /tmp/run/<id>/… (the task's working dir inside the container).
set -uo pipefail

src="${1:-}"
if [ -z "$src" ]; then
  echo "usage: npm run container:copy -- <container path>" >&2
  echo "   e.g. npm run container:copy -- /tmp/run/60-stm-deep-dive/output/60-stm-deep-dive.pdf" >&2
  exit 2
fi

# Resolve the running devcontainer for this workspace folder (same label as container:terminal).
cid=$(docker ps -q --filter label=devcontainer.local_folder="$PWD" | head -1)
if [ -z "$cid" ]; then
  echo "No running devcontainer for this folder — run: devcontainer up --workspace-folder ." >&2
  exit 1
fi

dest_dir="/tmp/e2e-copies"
base=$(basename "$src")
dest="$dest_dir/$base"
mkdir -p "$dest_dir"
rm -rf "$dest"

if ! docker cp "$cid:$src" "$dest_dir/"; then
  echo "✗ docker cp failed — does '$src' exist in the container? (check: npm run container:terminal, then ls $src)" >&2
  exit 1
fi

echo "→ copied to host: $dest"

# Open Finder to it: a folder opens; a file is revealed (selected) in its containing folder.
if [ -d "$dest" ]; then open "$dest"; else open -R "$dest"; fi
