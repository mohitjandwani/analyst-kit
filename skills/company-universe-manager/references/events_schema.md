# Key-date (event) schema

Each company's dated events live in `events/<TICKER>.json` under the store root:

```json
{
  "ticker": "AAPL",
  "events": [
    {
      "type": "earnings",
      "date": "2026-07-31",
      "status": "confirmed",
      "source": "FMP",
      "source_url": "https://...",
      "ref": "2026-06-30",
      "fetched_at": "2026-06-12",
      "note": "AMC"
    }
  ]
}
```

Events are stored date-sorted (undated last). A company has **many** events; the
roster (`universe.csv`) stays one-row-per-company.

## Fields

| Field | Required | Description |
|---|---|---|
| `type` | yes | One of the event types below. |
| `date` | yes | `YYYY-MM-DD`. The date the event occurs / is announced. |
| `status` | yes | `confirmed`, `estimated`, or `tentative`. Defaults to `estimated`. |
| `source` | no | Short label of where the date came from: `FMP`, `SEC-8K`, `IR-page`, `finmind`, `manual`. |
| `source_url` | no | Reference URL. |
| `ref` | no | **Slot identifier** that survives a date change. For earnings, the fiscal period end (e.g. `2026-06-30`). The monitor matches events across fetches by `(type, ref)` when present, so a moved announcement date for the *same* quarter reads as a *move*, not a new+dropped pair. |
| `fetched_at` | no | `YYYY-MM-DD` the value was recorded. |
| `note` | no | Free text (e.g. `AMC`/`BMO`, "preliminary"). |

## Event types

| Type | Meaning | Typical source |
|---|---|---|
| `earnings` | Quarterly/annual results announcement | FMP earnings calendar; SEC 8-K item 2.02 (last reported) |
| `investor_day` | Investor / analyst / capital-markets day | IR page, web search |
| `ex_dividend` | Ex-dividend trading date | FMP; finmind (`TaiwanStockDividend`) for TWSE |
| `agm` | Annual general meeting | IR page, proxy filing |
| `conference` | Conference / fireside appearance | IR page, web search |
| `guidance` | Guidance update / pre-announcement | 8-K, IR page |
| `lockup_expiry` | IPO/secondary lockup expiration | prospectus, IR page |
| `index_rebalance` | Index add/delete or rebalance effective date | index provider |
| `other` | Anything else worth tracking | — |

## Identity & upsert

The pair `(type, date)` identifies an event for CRUD upsert in
`events_manager.py` (re-adding the same type+date updates in place). The monitor
uses the richer `(type, ref)` slot when a `ref` is present so it can recognize a
date that *moved*. Keep `ref` stable across fetches for the same underlying
event (the fiscal period for earnings is ideal).
