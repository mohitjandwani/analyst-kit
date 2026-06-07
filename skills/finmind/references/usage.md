# FinMind API — usage reference

Mechanics for ad-hoc queries. For the common operations (download / update a company,
resolve a name to a data_id) use the scripts in `scripts/` instead — you do **not** need
to read this file for those.

## Authentication

All requests need a bearer token in the header:

```
Authorization: Bearer {token}
```

The scripts read it from `$FINMIND_TOKEN`. Register at https://finmindtrade.com/ for a free
token. Never hardcode the token in a file.

## Endpoints

Base URL: `https://api.finmindtrade.com/api/v4`

| Endpoint | Purpose | Key params |
|----------|---------|------------|
| `GET /data` | Fetch a dataset (almost everything) | `dataset`, `data_id`, `start_date`, `end_date` |
| `GET /datalist` | List available `data_id` values for a dataset | `dataset` |
| `GET /translation` | Chinese→English column-name mapping | `dataset` |

Check quota: `GET https://api.web.finmindtrade.com/v2/user_info` (bearer token) → returns
`level_title` and `api_request_limit`.

## Standard query pattern

```python
import os, requests, pandas as pd

resp = requests.get(
    "https://api.finmindtrade.com/api/v4/data",
    params={"dataset": "TaiwanStockPrice", "data_id": "2330",
            "start_date": "2024-01-01", "end_date": "2024-06-30"},
    headers={"Authorization": f"Bearer {os.environ['FINMIND_TOKEN']}"},
    timeout=60,
)
payload = resp.json()
df = pd.DataFrame(payload["data"]) if payload.get("status") == 200 else None
```

`scripts/finmind_client.py` already wraps this with retry, quota handling, and the
per-company dataset list — import it (`import finmind_client as fm; fm.fetch_df(...)`)
rather than re-implementing.

## Rate limits

| Tier | Limit | Access |
|------|-------|--------|
| Free | 600 req/hr | Basic datasets (everything this skill's scripts use) |
| Backer | 1,600 req/hr | + week/month K, market value, holding levels, ticks |
| Sponsor | 6,000 req/hr | + real-time, branch trading, block trades |

## Error handling

- **HTTP 402** — quota/rate limit exceeded. Wait an hour or upgrade.
- **`status != 200`** — read `msg`. Common causes: invalid token, wrong dataset name,
  missing required param, or a paid-tier dataset on a free token
  (e.g. `"Your level is register. Please update your level"`).
- **Empty `data` (`[]`)** — usually a wrong `data_id`, a date range with no trading days,
  or (for financial statements) a window with no reporting period. Not necessarily an error.

## Notes specific to company data

- **Free tier needs a `data_id`** for per-stock datasets. Omitting `data_id` to pull all
  stocks at once requires Backer/Sponsor.
- **Financial statements are long format**: `date, stock_id, type, value, origin_name`
  (one row per line-item per quarter). Pivot on `type` for a conventional statement;
  `origin_name` is the Chinese label. Applies to `TaiwanStockFinancialStatements`,
  `TaiwanStockBalanceSheet`, `TaiwanStockCashFlowsStatement`.
- **Market cap**: `TaiwanStockMarketValue` is Backer-only. On free tier compute
  `market_cap = close × NumberOfSharesIssued`, where `NumberOfSharesIssued` comes from
  `TaiwanStockShareholding` (this is what `compute_market_cap` in `finmind_client.py` does).
- **Names are Chinese only**: `TaiwanStockInfo` has no English names — match by Chinese
  name or stock id.

For the full dataset catalog (all datasets, columns, and tier requirements) see
[`datasets.md`](./datasets.md).
