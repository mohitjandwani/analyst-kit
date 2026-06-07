---
name: company-universe-manager
type: capability
description: >
  Manage a CSV-based company universe stored in GitHub: add companies with metadata,
  update company information, soft-delete companies, list active/inactive companies, and
  sync with the repository. Triggers: "add company to the universe", "update company
  info", "soft-delete company X", "list active companies", "sync the company universe".
---

# Company Universe Manager

Manage a CSV file containing company universe data stored in the `hedge-fund-analyst` GitHub repository. The skill handles adding, updating, and soft-deleting companies with metadata including financial metrics, competitors, and investment rationale.

## Repository Configuration

- **Repository**: `hedge-fund-analyst` (user's GitHub account)
- **Branch**: `main`
- **CSV Location**: `data/FULL_UNIVERSE.csv` 
- **Authentication**: Uses GitHub Connector

## Core Workflow

All operations follow this pattern:

1. **Sync with GitHub**: Pull latest changes before any operation
2. **Perform Operation**: Add, update, or soft-delete company data
3. **Commit and Push**: Save changes back to GitHub with descriptive message

### Git Synchronization

Always sync before reading or modifying the CSV to avoid conflicts:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/git_sync.py pull /path/to/hedge-fund-analyst
```

Check for conflicts in the output. If conflicts exist, abort the operation and notify the user to resolve manually.

After making changes, commit and push:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/git_sync.py commit /path/to/hedge-fund-analyst company_universe.csv "Add company: TICKER"
```

## Operations

### 1. Initialize Universe CSV

Create a new CSV file with proper headers if it doesn't exist:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py init /path/to/hedge-fund-analyst/company_universe.csv
```

Alternatively, copy the template:

```bash
cp /home/ubuntu/skills/company-universe-manager/templates/universe.csv /path/to/hedge-fund-analyst/company_universe.csv
```

### 2. Add Company

When adding a company, research it and populate all fields. Use web search (or any available market-data source) to find:

- Company name and ticker
- Exchange and currency
- Market cap and trading volume
- Competitor list
- A reference URL (e.g. the company's investor-relations page)

**Steps**:

1. Pull latest changes from GitHub
2. Research the company via web search (or an available market-data source)
3. Extract the company data and a reference URL
4. Determine market cap category based on avg_market_cap value
5. Add investment rationale (ask user to provide it)
6. Use csv_manager.py to add the company
7. Commit and push changes

**Example**:

```bash
# After researching the company
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py add \
  /path/to/hedge-fund-analyst/company_universe.csv \
  AAPL \
  "Apple Inc." \
  exchange=NASDAQ \
  currency=USD \
  market_cap_category="large cap" \
  avg_market_cap=2800 \
  avg_trading_volume=50000000 \
  competitors="MSFT,GOOGL,AMZN" \
  investment_rationale="Leading consumer tech; potential cloud partnership" \
  source_url="https://investor.apple.com/"
```

### 3. Update Company

Update existing company information (e.g., refresh financial data, update rationale):

**Steps**:

1. Pull latest changes from GitHub
2. Research updated data via web search if needed
3. Use csv_manager.py to update fields
4. Commit and push changes

**Example**:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py update \
  /path/to/hedge-fund-analyst/company_universe.csv \
  AAPL \
  avg_market_cap=2900 \
  avg_trading_volume=55000000 \
  investment_rationale="Updated: Expanding AI initiatives"
```

### 4. Remove Company (Soft Delete)

Set `active=false` instead of deleting the row. This preserves historical data:

**Steps**:

1. Pull latest changes from GitHub
2. Use csv_manager.py to soft-delete
3. Commit and push changes

**Example**:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py remove \
  /path/to/hedge-fund-analyst/company_universe.csv \
  AAPL
```

### 5. Reactivate Company

Set `active=true` for a previously removed company:

**Example**:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py reactivate \
  /path/to/hedge-fund-analyst/company_universe.csv \
  AAPL
```

### 6. List Companies

View all active companies or include inactive ones:

**Active companies only**:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py list \
  /path/to/hedge-fund-analyst/company_universe.csv
```

**All companies (including inactive)**:

```bash
python3.11 /home/ubuntu/skills/company-universe-manager/scripts/csv_manager.py list \
  /path/to/hedge-fund-analyst/company_universe.csv --all
```

## Data Sources

### Company research

Use web search (or any available market-data source) to gather each field:

- **Company Name**: Official company name
- **Exchange & Currency**: Primary listing exchange and trading currency
- **Market Cap**: Convert to billions (e.g., "$2.8T" → 2800)
- **Trading Volume**: Average daily volume
- **Competitors**: Closest peers (extract ticker symbols)

Store a reference URL (e.g. the company's investor-relations page) in the
`source_url` field for future reference.

### Market Cap Categories

Determine category based on `avg_market_cap` value:

- **Small cap**: < 2 (less than $2 billion)
- **Mid cap**: 2 to 10 ($2 billion to $10 billion)
- **Large cap**: > 10 (greater than $10 billion)

## Error Handling

### Git Conflicts

If `git pull` reports conflicts, abort the operation and instruct the user:

> "Git conflict detected in company_universe.csv. Please resolve manually by:
> 1. Navigate to the hedge-fund-analyst repository
> 2. Run `git status` to see conflicting files
> 3. Resolve conflicts and commit
> 4. Retry the operation"

### Company Already Exists

If adding a company that already exists (same ticker), report the error and suggest using the update operation instead.

### Missing Data

If company research is incomplete or data can't be found, notify the user and ask them to provide the missing fields, then retry.

## CSV Schema Reference

For detailed field definitions, formats, and requirements, read:

```
/home/ubuntu/skills/company-universe-manager/references/csv_schema.md
```

## Best Practices

1. **Always sync first**: Run `git pull` before any read or write operation
2. **Descriptive commit messages**: Use format "Add company: TICKER" or "Update TICKER: field changes"
3. **Verify data**: Cross-check researched data for accuracy
4. **Soft delete only**: Never hard-delete rows; always use soft delete (active=false)
5. **Update dates**: The `last_update_date` field is automatically set by csv_manager.py
6. **Handle quotes**: If investment_rationale contains commas, the CSV manager handles quoting automatically
