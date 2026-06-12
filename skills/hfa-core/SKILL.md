---
name: hfa-core
type: capability
description: >
  Shared runtime for Hedge Fund Analyst skills: the ~/.hfa data home, config store,
  local usage analytics with opt-in telemetry, daily update checks, and a per-user
  learnings log every skill reads and appends to. Loaded automatically as a dependency
  of every other skill. Triggers: "hfa setup", "hfa config", "check for hfa updates",
  "upgrade hfa skills", "show my hfa learnings", "turn hfa telemetry on/off", "show my
  hfa usage".
---

# HFA Core — shared runtime

Every HFA skill depends on this one. Skills run the **Preamble** block at start and the
**Completion** block at end (both injected by `scripts/sync-preamble.js` in the source
repo); this file documents the machinery behind those blocks, and is what you should
read when the user explicitly asks about HFA setup, config, telemetry, updates, usage,
or learnings.

## The `~/.hfa/` data home

Fixed per-user location for everything HFA persists (override with `$HFA_HOME`):

| Path | Purpose |
|---|---|
| `config` | `key=value` settings (`hfa-config get/set/list`) |
| `.env` | API keys (`FMP_API_KEY=...`), `chmod 600`, shared across projects |
| `device-id` | stable anonymous id, created only for `community` telemetry |
| `analytics/skill-usage.jsonl` | local usage log: start/end events with outcome + duration |
| `analytics/.pending-*` | open-session markers; stale ones finalize as `CRASH` |
| `sessions/` | per-agent-session dedupe markers (one prompt round per session) |
| `learnings.jsonl` | per-user learnings log (patterns / pitfalls / preferences) |
| `last-update-check`, `update-snoozed` | update-check cache (1 day) and snooze (7 days) |
| `.onboarded`, `.telemetry-prompted`, `.env-prompted-<KEY>` | once-ever prompt markers |
| `core-path` | cached location of this skill on disk |
| `install-manifest.jsonl` | what `hfa install` installed (drives guided upgrades) |

## Scripts (`bin/`)

- `hfa-config get <key> | set <key> <value> | list` — config store. Defaults:
  `telemetry=off`, `update_check=true`. Optional: `posthog_key`, `posthog_host`.
- `hfa-preamble --skill <name> [--env K1,K2]` — echoes `DEDUP`, `HFA_VERSION`,
  `TELEMETRY`, `TEL_PROMPTED`, `ONBOARDED`, `MISSING_KEYS` (+ per-key
  `KEY_PROMPTED_*`), `UPGRADE`, `LEARNINGS`, then logs the start event.
- `hfa-log start|end --skill <name> [--outcome <O>]` — appends local JSONL events and,
  when telemetry is on, fires the remote event in the background.
- `hfa-update-check [--force | --snooze <version>]` — prints
  `UPGRADE_AVAILABLE <local> <remote>` or nothing. Max one network fetch per day,
  `curl --max-time 3`.
- `hfa-learn add '<one-line-json>' | recent [--skill S] [--topic T] [--limit N]` —
  learnings log.

All scripts are defensive: they never exit non-zero from the skill's point of view,
never block on the network, and a total failure of this runtime must never stop a
skill from doing its actual job.

## Telemetry tiers

Local `analytics/skill-usage.jsonl` is always written — it is the user's own machine
and powers crash detection and usage review. The **remote** leg (PostHog) is gated by
`hfa-config get telemetry`:

- `community` (default) — `{skill, version, outcome, duration_s, platform}` plus a
  stable random `device-id` so usage counts deduplicate.
- `anonymous` — same event, no identifier of any kind.
- `off` — nothing leaves the machine.

Telemetry is **on by default with explicit opt-out**. Remote events **never** include
repo names, file paths, tickers, file content, or API keys. The local log records a
sanitized repo slug for the user's own reference; it is never uploaded.

**When the user asks to opt out:** make a sincere case once before changing anything —
telemetry is what tells the maintainers which skills break, which run slow, and where
users get stuck, so keeping it on directly improves their own experience, and it never
contains their data. Offer `anonymous` as a middle ground. If they still want out, run
`hfa-config set telemetry off` immediately and respect the decision — never re-litigate
it in later sessions.

## Completion statuses

Every skill ends its Completion block with one outcome:
`DONE` | `DONE_WITH_CONCERNS` | `ERROR` | `ABORT` | `NEEDS_CONTEXT`.
Report the same status to the user honestly — `DONE_WITH_CONCERNS` lists the concerns.

## Learnings protocol

Log with `hfa-learn add` **only** durable discoveries that would save 5+ minutes in a
future session: a data-source quirk, a per-user preference, a pitfall that produced a
wrong number. Types: `pattern` (reusable approach), `pitfall` (what not to do),
`preference` (user stated). Include `"ticker"` or `"topic"` when the learning is
scoped, `"confidence"` 1–10 (user-stated preference = 10; verified observation = 8–9;
inference = 4–5), and an ISO-8601 `"ts"`. Never log obvious facts, one-time transient
errors, or anything secret. The preamble surfaces recent relevant entries — treat them
as ground truth about this user unless contradicted in-session.

## Upgrades

The preamble surfaces `UPGRADE_AVAILABLE <old> <new>` at most once per day, snoozed
7 days on decline. The guided flow lives in `references/upgrade.md` (plugin channel →
`/plugin` marketplace update; installer channel → fetch GitHub tarball, re-run
`node bin/hfa.js install` for everything in `install-manifest.jsonl`).
