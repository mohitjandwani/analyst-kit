# Company Universe CSV Schema

## Column Definitions

### company_name
- **Type**: String
- **Description**: Full legal or common name of the company
- **Example**: "Apple Inc.", "Microsoft Corporation"
- **Required**: Yes

### ticker_symbol
- **Type**: String (uppercase)
- **Description**: Stock ticker symbol used for trading
- **Example**: "AAPL", "MSFT", "GOOGL"
- **Required**: Yes
- **Unique**: Yes

### exchange
- **Type**: String
- **Description**: Primary stock exchange where the company trades
- **Example**: "NASDAQ", "NYSE", "LSE", "TSX"
- **Required**: Yes

### currency
- **Type**: String (ISO 4217 currency code)
- **Description**: Currency in which the stock trades
- **Example**: "USD", "EUR", "GBP", "CAD"
- **Required**: Yes

### market_cap_category
- **Type**: Enum
- **Description**: Market capitalization category
- **Values**: "small cap", "mid cap", "large cap"
- **Definitions**:
  - Small cap: < $2 billion
  - Mid cap: $2 billion - $10 billion
  - Large cap: > $10 billion
- **Required**: Yes

### avg_market_cap
- **Type**: Number (in billions)
- **Description**: Average market capitalization in billions of USD
- **Example**: "2500.5" (for $2.5 trillion)
- **Format**: Decimal number, no currency symbols
- **Required**: Yes

### avg_trading_volume
- **Type**: Number
- **Description**: Average daily trading volume (number of shares)
- **Example**: "50000000" (50 million shares)
- **Format**: Integer, no commas
- **Required**: Yes

### competitors
- **Type**: String (comma-separated list)
- **Description**: List of main competitor ticker symbols
- **Example**: "MSFT,GOOGL,AMZN"
- **Format**: Comma-separated ticker symbols, no spaces
- **Required**: No

### last_update_date
- **Type**: Date (ISO 8601)
- **Description**: Date when company information was last updated
- **Example**: "2026-02-12"
- **Format**: YYYY-MM-DD
- **Required**: Yes (auto-generated)

### investment_rationale
- **Type**: String (free text)
- **Description**: Notes on why this company might invest in your business
- **Example**: "Looking to expand cloud infrastructure; recent M&A activity in AI space"
- **Format**: Free text, use quotes if contains commas
- **Required**: No

### source_url
- **Type**: String (URL)
- **Description**: Reference URL for the company (e.g. its investor-relations page or a financial-data profile)
- **Example**: "https://investor.apple.com/"
- **Format**: Full URL
- **Required**: No

### active
- **Type**: Boolean
- **Description**: Whether the company is currently in the active universe
- **Values**: "true", "false"
- **Default**: "true"
- **Required**: Yes

## CSV Format Notes

- **Encoding**: UTF-8
- **Delimiter**: Comma (,)
- **Quote Character**: Double quote (")
- **Header Row**: Always present as first row
- **Empty Values**: Use empty string for optional fields
- **Text with Commas**: Must be enclosed in double quotes
