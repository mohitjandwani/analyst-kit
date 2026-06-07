# Regional Data Sources Reference

## Table of Contents
1. [Data Retrieval by Geography](#data-retrieval-by-geography)
2. [Earnings Transcripts & Presentations by Region](#earnings-transcripts--presentations-by-region)
3. [Financial Data by Region](#financial-data-by-region)
4. [Competitor Identification by Region](#competitor-identification-by-region)
5. [FMP API Ticker Formats](#fmp-api-ticker-formats)
6. [stockanalysis.com Exchange Prefixes](#stockanalysiscom-exchange-prefixes)

---

## Data Retrieval by Geography

| Geography | Competitors | Earnings Transcripts | Investor Presentations |
|---|---|---|---|
| **US** (e.g., AMD) | FMP API `peers`; SEC 10-K; Seeking Alpha | FMP API `latest-transcripts` or `transcript`; Seeking Alpha | FMP API `latest-8k`; Company IR; SEC EDGAR |
| **Europe** (e.g., IQE.L, SOI.PA, SIVE.ST) | FMP API `peers`; Company Annual Reports | FMP API (partial); Company IR webcasts; Seeking Alpha | Company IR; Exchange filings (LSE RNS, AMF, Nasdaq Nordic) |
| **Japan** (e.g., 4063.T) | FMP API `peers`; JPX; EDINET | Company IR **"Q&A Summary" PDFs**; Seeking Alpha (ADR) | Company IR; JPX TDnet; EDINET |
| **Taiwan** (e.g., 2308.TW) | FMP API `peers`; TWSE MOPS | **AlphaSpread** (full English text); Company IR webcasts | MOPS (`mops.twse.com.tw`); Company IR |
| **India** (e.g., OLAELEC.NS) | FMP API `peers`; Screener.in; Trendlyne | Company IR (full transcript PDFs — SEBI LODR mandated); Trendlyne; BSE/NSE filings | BSE/NSE filings; Trendlyne; Company IR |

---

## Earnings Transcripts & Presentations by Region

### United States
- **Best source**: FMP API — `GET /v3/earning_call_transcript/{ticker}?quarter={Q}&year={YYYY}`
- **Fallback**: Seeking Alpha earnings page; SEC EDGAR 8-K filings
- Full text transcripts are universally available for US-listed companies

### Europe
- **Large-caps**: FMP API often has partial transcripts; supplement with company IR
- **Small-caps**: Text transcripts are frequently unavailable. Use the **video/audio webcast** from the company IR site or platforms like Inderes (Nordic companies)
- Exchange filing portals: LSE RNS (UK), AMF (France), Nasdaq Nordic (Scandinavia)

### Japan
- **Critical rule**: Do NOT search for "earnings call transcripts" — this format does not exist for Japanese companies
- The standard format is **"Q&A Summary" PDFs** published on the company IR website after each earnings briefing
- Also check JPX TDnet (`https://www.jpx.co.jp/english/listing/disclosure/`) for timely disclosure documents
- EDINET (`https://disclosure2.edinet-fsa.go.jp/`) for statutory filings (Annual Securities Reports)
- Seeking Alpha may have transcripts for companies with US ADRs

### Taiwan
- **Best source**: **AlphaSpread** (`https://alphaspread.com/`) — has full English text transcripts for major TWSE-listed companies; far superior to trying to extract from video webcasts
- Company IR page: look for `/en/investor/events` — download the earnings presentation PDF (often the primary disclosure format)
- MOPS (`https://mops.twse.com.tw/`): official TWSE filing portal for annual reports, quarterly filings, and monthly revenue disclosures
- Monthly revenue reports: `https://tw.stock.yahoo.com/quote/{ticker}.TW/revenue`

### India
- **Best source**: Company IR website — SEBI LODR regulations legally require listed companies to publish full earnings call transcript PDFs
- BSE filings: `https://www.bseindia.com/stock-share-price/{company}/{ticker}/` → Corporate Announcements
- NSE filings: `https://www.nseindia.com/get-quotes/equity?symbol={ticker}` → Corporate Actions
- Trendlyne (`https://trendlyne.com/`): aggregates transcripts, analyst reports, and quarterly data for Indian companies
- Screener.in (`https://www.screener.in/`): clean financial data and peer comparison for Indian companies

---

## Financial Data by Region

### Primary Source (All Regions)
stockanalysis.com is the most consistent cross-regional source for annual and quarterly financials:
- Annual: `https://stockanalysis.com/stocks/{ticker}/financials/` (US)
- Annual (non-US): `https://stockanalysis.com/quote/{prefix}/{ticker}/financials/`
- Quarterly: append `?p=quarterly`
- Balance sheet: append `/balance-sheet/`
- Statistics / multiples: append `/statistics/` (or `/financials/ratios/`)

### Periodic Revenue Sources
| Region | Frequency | Source |
|---|---|---|
| Taiwan | Monthly | `https://tw.stock.yahoo.com/quote/{ticker}.TW/revenue` |
| US | Quarterly | stockanalysis.com or company earnings releases |
| Europe | Quarterly | stockanalysis.com or company IR quarterly reports |
| Japan | Quarterly | Company IR page; JPX TDnet |
| India | Quarterly | BSE/NSE filings; Trendlyne; Screener.in |

### Fallback Sources
- Macrotrends (`https://www.macrotrends.net/`) — USD-denominated historical data for most global companies
- Company annual reports (IR page) — authoritative but requires manual extraction

---

## Competitor Identification by Region

**Fastest method (all regions):** FMP API `peers` endpoint
```
GET https://financialmodelingprep.com/api/v4/stock_peers?symbol={ticker}&apikey={key}
```

**By region if FMP peers are incomplete:**

| Region | Source |
|---|---|
| US | SEC 10-K "Competition" section; Seeking Alpha sector pages |
| Europe | Company Annual Report "Competition" section; exchange sector indices |
| Japan | JPX sector classification; company IR "Industry Position" section |
| Taiwan | TWSE industry classification; MOPS peer search |
| India | NSE sector index constituents; Screener.in peer comparison |

---

## FMP API Ticker Formats

| Exchange | Country | FMP Suffix | Example |
|---|---|---|---|
| NASDAQ / NYSE | US | (none) | `AMD` |
| London Stock Exchange | UK | `.L` | `IQE.L` |
| Euronext Paris | France | `.PA` | `SOI.PA` |
| Euronext Amsterdam | Netherlands | `.AS` | `ASML.AS` |
| Xetra / Frankfurt | Germany | `.DE` | `SAP.DE` |
| Nasdaq Stockholm | Sweden | `.ST` | `SIVE.ST` |
| Tokyo Stock Exchange | Japan | `.T` | `4063.T` |
| Taiwan Stock Exchange | Taiwan | `.TW` | `2308.TW` |
| NSE India | India | `.NS` | `OLAELEC.NS` |
| BSE India | India | `.BO` | `OLAELEC.BO` |

---

## stockanalysis.com Exchange Prefixes

| Exchange | Prefix | Example URL |
|---|---|---|
| Taiwan Stock Exchange (TWSE) | `tpe` | `/quote/tpe/4958/financials/` |
| Taipei Exchange (OTC) | `tpex` | `/quote/tpex/6488/financials/` |
| Tokyo Stock Exchange | `tse` | `/quote/tse/4063/financials/` |
| London Stock Exchange | `lse` | `/quote/lse/IQE/financials/` |
| Xetra / Frankfurt | `xetra` | `/quote/xetra/SAP/financials/` |
| Euronext (Paris/Amsterdam) | `euronext` | `/quote/euronext/ASML/financials/` |
| NSE India | `nse` | `/quote/nse/OLAELEC/financials/` |
| BSE India | `bse` | `/quote/bse/OLAELEC/financials/` |
