# Guided upgrade

Followed by the agent when the user accepts an `UPGRADE_AVAILABLE <old> <new>` offer.
Never start this flow without explicit user consent in this session.

## 1. Detect the install channel

```bash
[ -f ~/.hfa/install-manifest.jsonl ] && echo "CHANNEL: installer" || true
grep -q "/plugins/" ~/.hfa/core-path 2>/dev/null && echo "CHANNEL: plugin" || true
```

If both (or neither) print, ask the user which way they installed: the `hfa` CLI
(`node bin/hfa.js install ...`) or the Claude Code plugin marketplace.

## 2a. Plugin channel (Claude Code marketplace)

Do **not** attempt file surgery on the plugin cache. Tell the user to update through
Claude Code itself:

> Run `/plugin`, open **Manage marketplaces → hedge-fund-analyst → Update**, then
> reinstall/update the installed persona plugin. Restart the session afterwards.

## 2b. Installer channel

Fetch the latest release and re-run the installer for every target the user previously
installed (recorded in `~/.hfa/install-manifest.jsonl`):

```bash
T=$(mktemp -d)
curl -sfL --max-time 60 https://github.com/MohitKumar1991/hedge-fund-analyst/archive/refs/heads/main.tar.gz \
  | tar xz -C "$T" --strip-components=1
```

Then for each **unique** `{target, platform, scope}` line in
`~/.hfa/install-manifest.jsonl`:

```bash
node "$T/bin/hfa.js" install <target> --platform <platform> --scope <scope> -y
```

Finally clean up:

```bash
rm -rf "$T"
```

## 3. Confirm and reset

```bash
rm -f ~/.hfa/last-update-check ~/.hfa/update-snoozed
cat "$(cat ~/.hfa/core-path)/VERSION"
```

Report the new version to the user. If the printed version is still the old one
(plugin channel before a session restart, or a failed copy), say so plainly — do not
claim the upgrade succeeded.
