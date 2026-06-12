---
name: company-universe-manager
type: capability
requires:
  - financialmodellingprep
  - reporting
description: >
  Own a watchlist ("universe") of companies and everything time-based about
  them. Maintain the roster (add / update / soft-delete / reactivate / list with
  metadata, competitors, rationale) and track each company's key dates —
  earnings, investor days, ex-dividend, AGMs, conferences, guidance, lockups.
  Run a daily monitor that re-fetches dates and detects what changed (earnings
  moved, newly announced, confirmed-from-estimated, dropped), and produce a
  daily brief (key-date changes, upcoming calendar, news + 8-K material events)
  as markdown or a branded PDF. Storage is pluggable behind one contract: a
  local folder (~/company-universe) or a connected server (e.g. Google Sheets
  over MCP). Triggers: "add company to my universe / watchlist", "list my
  companies", "when does X report earnings", "track earnings / ex-dividend dates
  for Y", "what changed in earnings dates", "any investor days coming up", "run
  the daily universe monitor", "daily brief / report for my watchlist",
  "schedule the daily check", "upcoming key dates for my companies".
---

# Company Universe Manager

Owns a watchlist of companies and the **time dimension** over it. Three jobs:

1. **Roster** — the list of companies and their metadata.
2. **Key dates** — earnings, investor days, ex-dividend, AGMs, etc., per company.
3. **Daily intelligence** — detect date changes and produce a daily brief.

All scripts are run from this skill's directory: `python3 scripts/<name>.py`.

## Storage (pluggable)

Everything lives behind one `UniverseStore` contract (`scripts/storage.py`). The
source of truth is selected by `config.json` and is either a **local folder** or
a **connected server**. The store root resolves as: explicit path →
`$COMPANY_UNIVERSE_HOME` → default `~/company-universe`.

Initialize once:

```bash
python3 scripts/storage.py init        # creates ~/company-universe + config.json
python3 scripts/storage.py info        # show root, backend, counts
```

Layout and the full backend/config/remote-sync details are in
`references/storage.md`. Key rule: the **Python scripts always read/write the
local folder** (the working copy). A remote backend (Google Sheets, etc.) is
**agent-mediated** — MCP tools can't be called from a subprocess — so when
`config.backend == "remote"` you (the agent) sync local ↔ remote around script
runs using the connected MCP tools. See "Remote sync" below.

## Roster operations

The roster is `<root>/universe.csv` (12-column schema in
`references/csv_schema.md`), managed by `scripts/csv_manager.py`. Always pass the
store's CSV path.

```bash
ROOT=~/company-universe                         # or $COMPANY_UNIVERSE_HOME

# Add (research metadata via the FMP skill or web search first)
python3 scripts/csv_manager.py add "$ROOT/universe.csv" AAPL "Apple Inc." \
  exchange=NASDAQ currency=USD market_cap_category="large cap" \
  avg_market_cap=2800 competitors="MSFT,GOOGL" \
  investment_rationale="..." source_url="https://investor.apple.com/"

python3 scripts/csv_manager.py update "$ROOT/universe.csv" AAPL avg_market_cap=2900
python3 scripts/csv_manager.py remove "$ROOT/universe.csv" AAPL      # soft delete (active=false)
python3 scripts/csv_manager.py reactivate "$ROOT/universe.csv" AAPL
python3 scripts/csv_manager.py list "$ROOT/universe.csv" [--all]
```

Research company metadata via the **financialmodellingprep** skill (fundamentals,
profile) or web search; market-cap categories: small `<2`, mid `2–10`, large
`>10` ($bn).

## Key dates (events)

Each company has many dated events in `<root>/events/<TICKER>.json` (schema and
event types in `references/events_schema.md`). Manage them with
`scripts/events_manager.py`:

```bash
python3 scripts/events_manager.py add AAPL type=earnings date=2026-07-31 \
  status=confirmed source=FMP ref=2026-06-30
python3 scripts/events_manager.py add AAPL type=investor_day date=2026-09-15 \
  status=tentative source=IR-page
python3 scripts/events_manager.py list AAPL [--upcoming]
python3 scripts/events_manager.py remove AAPL earnings 2026-07-31
```

`ref` is the slot identifier that survives a date change (for earnings, the
fiscal period end). The monitor matches on `(type, ref)` so a moved date for the
same quarter reads as a *move*, not a new+dropped pair.

## Daily monitor (deterministic, cheap)

`scripts/monitor_dates.py` re-fetches current dates for every **active** roster
ticker, diffs them against the stored events, refreshes the store, and records
what changed — all without the LLM, so it is cheap to run on a schedule.

```bash
FMP_API_KEY=... python3 scripts/monitor_dates.py
```

It sources:
- **Earnings dates** — FMP earnings calendar (needs `FMP_API_KEY`, provided by
  the required `financialmodellingprep` skill).
- **Last-reported earnings** — SEC 8-K **item 2.02** via the `sec-filings` skill
  **if installed** (free), for US filers (opportunistic; not a hard dependency).
- **Taiwan ex-dividend dates** — the `finmind` skill **if installed** and
  `FINMIND_TOKEN` is set (opportunistic; not a hard dependency).

It writes `snapshots/<date>.json` (all events that day) and `changes/<date>.json`
(the diff), and prints a JSON change summary. Change kinds: `new`, `moved`,
`status_changed`, `dropped`. A fetch is only authoritative over the event
**types it returns**, so an earnings fetch never spuriously drops an investor
day. For investor days / conferences / guidance not in any API, discover and add
them with web search + the IR page (`source_url`) and `events_manager.py`.

## Daily brief (report)

```bash
FMP_API_KEY=... python3 scripts/fetch_news.py > /tmp/news.json   # FMP news + recent 8-Ks
python3 scripts/build_report.py --news /tmp/news.json            # writes md + reporting contract
```

`build_report.py` writes a markdown brief and a `reporting`-skill JSON contract
to `<root>/reports/`. The contract uses chart-free `cover` + `table-commentary`
pages (what-changed table, upcoming-calendar table). For the **branded PDF**,
enrich the commentary (summarize the news, call out what matters), then hand the
contract to the required `reporting` skill:

```bash
cd ../reporting && bun scripts/render.ts \
  ~/company-universe/reports/daily-<date>.contract.json out/daily-<date>.pdf
```

Markdown is the zero-dependency default; the PDF is the full-featured output.

## Scheduling the daily routine

Register a recurring in-session job with **CronCreate** (full caveats and a
launchd alternative in `references/scheduling.md`):

```
CronCreate({
  cron: "13 7 * * *", durable: true, recurring: true,
  prompt: "Run the company-universe-manager daily routine: monitor key dates, gather news, build and render the daily report, then summarize what changed."
})
```

**Tell the user the caveats:** harness cron only fires while a Claude session is
open and idle, and recurring jobs auto-expire after 7 days. For truly unattended
overnight runs, use the macOS launchd recipe in `references/scheduling.md`.

When the job fires, run: `monitor_dates.py` → `fetch_news.py` → `build_report.py`
→ render via `reporting` → summarize `changes/<today>.json` for the user → mirror
to the remote backend if configured.

## Remote sync (when `config.backend == "remote"`)

The Python scripts only touch the local folder. To keep a connected server
(e.g. Google Sheets) in sync, you (the agent) do this around script runs
(details in `references/storage.md`):

1. **Before** any read/modify — pull the remote into local via the connected MCP
   tools (write through `csv_manager.py` / `events_manager.py`).
2. Run the Python operation against the local store.
3. **After** writes — push the changed local files back to the remote.
4. If the MCP connection is unavailable, stay local-only and tell the user the
   remote is stale.

Surface the available MCP tools with ToolSearch; do not hardcode a connector.

## Error handling

- **No `FMP_API_KEY`** — the monitor and news fetch report the gap and skip the
  FMP-sourced data rather than failing; SEC 8-K (free) and manually-entered
  events still work.
- **Non-US ticker** — SEC lookups return nothing; rely on FMP / finmind / IR.
- **Adding a duplicate ticker** — `csv_manager.py` reports it; use `update`.
- **`dropped` changes** — surfaced for human review, never auto-deleted from the
  store. Confirm before removing the event.

## Best practices

1. Always `storage.py init` before first use; check `config.json` backend.
2. Keep `ref` stable across fetches for earnings (use the fiscal period end).
3. Sync the remote (if configured) before and after every roster/event change.
4. Soft-delete companies (`active=false`); never hard-delete rows.
5. Re-arm the cron job weekly (7-day expiry) or move to launchd.
