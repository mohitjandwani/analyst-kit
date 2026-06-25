# Storage backend & sync

The universe and its key dates live behind one `UniverseStore` contract
(`scripts/storage.py`). The **source of truth** is selected by
`config.json` and can be a local folder or a connected server (e.g. a Google
Sheet over MCP).

## Store root & layout

Root resolution order: explicit path argument → `$COMPANY_UNIVERSE_HOME` →
default `~/company-universe`.

```
config.json                   backend selection + remote descriptor
universe.csv                  roster (csv_manager.py — existing 12-col schema)
events/<TICKER>.json          per-ticker dated events (events_schema.md)
snapshots/<YYYY-MM-DD>.json   point-in-time capture of all events (diff basis)
changes/<YYYY-MM-DD>.json     date changes detected that day (monitor output)
reports/daily-<YYYY-MM-DD>.md report skeleton (markdown)
reports/daily-<YYYY-MM-DD>.contract.json   reporting-skill contract for the PDF
```

Initialize with `python3 scripts/storage.py init [root]`.

## config.json

```json
{
  "backend": "local",
  "remote": null
}
```

For a connected server, set `backend: "remote"` and describe it (free-form, read
by the *agent*, not the Python scripts):

```json
{
  "backend": "remote",
  "remote": {
    "type": "google-sheets",
    "spreadsheet": "Company Universe",
    "tab_universe": "roster",
    "tab_events": "events"
  }
}
```

## Why the remote backend is agent-mediated

MCP tools (Google Sheets, Notion, etc.) live in the **agent's** tool namespace.
A Python subprocess cannot call them. So the Python layer (`storage.py`,
`monitor_dates.py`, `build_report.py`) **always** reads and writes the **local
folder** as the working copy, and the agent performs any remote sync around
script runs using whatever MCP tools the user has connected (surface them with
ToolSearch).

The `UniverseStore` base class documents the full method contract, so a future
*native* remote backend (one that talks to a server API directly from Python,
not via MCP) can subclass it and the monitor/report scripts work unchanged.

## Remote sync procedure (agent)

When `config.backend == "remote"`:

1. **Before reading/modifying** — pull the remote into the local store: read the
   remote roster/events via the connected MCP tools and write them through
   `csv_manager.py` / `events_manager.py` so local matches remote.
2. **Run the Python operation** (add company, monitor, build report) against the
   local store as usual.
3. **After writing** — push the changed local files back to the remote via the
   same MCP tools.
4. If the MCP connection is unavailable, fall back to local-only and tell the
   user the remote is stale until the next successful sync.

The local folder is always authoritative for the scripts; the remote is a
shared, human-viewable mirror.

## Optional git versioning

`scripts/git_sync.py` can version the **store root** if you want history /
backup (it is no longer tied to any specific GitHub repo): run `git init` in the
store root, then `git_sync.py commit <root> <file> "<msg>"`. This is independent
of the `remote` backend above.
