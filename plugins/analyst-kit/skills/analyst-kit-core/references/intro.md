# Analyst Kit — full setup (intro)

Follow this end to end when the user asks to set up Analyst Kit — e.g.
"set up analyst-kit", "help me set up Analyst Kit", "configure all skills". Unlike a
single skill's lazy key prompt, this configures **every** installed skill in one pass.

It is interactive: **you** ask the questions; the `analyst-kit-setup` subcommands only persist
the answers. Drive it top to bottom and never block on a single key.

## 0. Locate the runtime + read state

```bash
_AK="$(cat ~/.analyst-kit/core-path 2>/dev/null)"
[ -x "$_AK/bin/analyst-kit-setup" ] || for d in ~/.claude/skills/analyst-kit-core .claude/skills/analyst-kit-core ~/.codex/skills/analyst-kit-core .codex/skills/analyst-kit-core; do
  [ -x "$d/bin/analyst-kit-setup" ] && _AK="$d" && break
done
"$_AK/bin/analyst-kit-setup" status
```

Read the `status` output:
- `HOME:` — the data home; `TELEMETRY:` — the current tier.
- one `KEY <NAME> present=… prompted=… needed_by=… url=… desc=…` line per API key the
  installed skills need.
- one `SKILL <name> disabled=… keys=… missing=…` line per key-needing skill.

## 1. Data home

Tell the user Analyst Kit stores config, API keys, local usage analytics, and a learnings log
in one folder on this machine (the `HOME:` value, default `~/.analyst-kit`). Ask if they want it
somewhere else; if so, run `"$_AK/bin/analyst-kit-setup" home <dir>` (it creates the folder and
migrates anything already written). Otherwise move on.

## 2. Telemetry notice

State it once (a notice, not a question): usage telemetry is **on by default** — it sends
only skill name, duration, outcome, and version, tagged with a random per-machine device
id, and **never** repo names, file paths, tickers, or content. They can opt out anytime.
If they want out now, run `"$_AK/bin/analyst-kit-config" set telemetry off` (offer `anonymous`,
which drops the device id, as a middle ground). Then `"$_AK/bin/analyst-kit-setup" ack-telemetry`.

## 3. API keys — walk every key

For each `KEY <NAME> present=no` line, explain what the key unlocks (`desc=`) and where to
get it (`url=`), then ask the user for the value:

- **Provided** → `"$_AK/bin/analyst-kit-setup" set-key <NAME> <value>` (this also re-enables any
  skill that now has all of its keys).
- **Declined / not available** → `"$_AK/bin/analyst-kit-setup" skip-key <NAME>` (this **disables**
  the skills that need it — they stay off until the key is added). Never block on it.

Keys already `present=yes` need no action.

## 4. Reconcile + summarize

```bash
"$_AK/bin/analyst-kit-setup" reconcile
"$_AK/bin/analyst-kit-setup" status
```

From the refreshed `SKILL …` lines, tell the user plainly which skills are now **enabled**
and which are **disabled**, and name the key that would re-enable each disabled one. A
disabled skill is one whose API key the user didn't provide — it will refuse to run until
the key is set (the user can give it to you anytime, or re-run "set up analyst-kit").

## 5. Finish

```bash
"$_AK/bin/analyst-kit-setup" finish
```

Confirm setup is complete and summarize the enabled/disabled skills once more.
