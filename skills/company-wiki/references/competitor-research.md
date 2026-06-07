# Competitor Research Framework

## Table of Contents
1. [General Competitive Positioning Framework](#general-competitive-positioning-framework)
2. [Identifying the Peer Set](#identifying-the-peer-set)
3. [Data Collection per Competitor](#data-collection-per-competitor)
4. [Moat Assessment Dimensions](#moat-assessment-dimensions)
5. [Appendix: Taiwanese PCB Sector Peers](#appendix-taiwanese-pcb-sector-peers)

---

## General Competitive Positioning Framework

When building the Competitors page, assess each company on these universal dimensions:

1. **Revenue scale** — absolute revenue and 3–5 year CAGR
2. **Profitability** — gross margin %, operating margin %, net margin %
3. **Valuation** — P/E (TTM), forward P/E, P/S, P/B, EV/EBITDA
4. **Customer concentration** — single large customer dependency is both a moat and a risk
5. **Technology differentiation** — proprietary processes, certifications, or capability thresholds that competitors cannot easily replicate
6. **Qualification cycles** — longer customer qualification = higher switching cost
7. **Capacity scale** — larger scale = better cost position and ability to win large orders
8. **Exposure to secular growth themes** — AI, EVs, 5G, defence, etc.

---

## Identifying the Peer Set

**Step 1 — FMP API (fastest, all regions):**
```
GET https://financialmodelingprep.com/api/v4/stock_peers?symbol={ticker}&apikey={key}
```
Returns a list of peer tickers. Verify each is genuinely comparable (same product category, not just same SIC code).

**Step 2 — Company's own disclosures:**
- US: 10-K "Competition" section names direct competitors explicitly
- Japan: IR presentations often include market share charts naming peers
- Taiwan: TWSE industry classification groups; company IR "Industry Position" slides
- India: Annual report "Industry Overview" section; SEBI filings
- Europe: Annual report "Competitive Landscape" section

**Step 3 — Sector index constituents:**
Use the relevant sector index (e.g., PHLX Semiconductor Index for US semis, TWSE Electronics sub-index for Taiwan) to identify the full peer universe, then filter to the most directly comparable companies.

---

## Data Collection per Competitor

For each peer, collect from `stockanalysis.com` (see `regional-data-sources.md` for exchange prefixes):
- Revenue (5 years) and YoY growth %
- Gross margin %, operating margin %, net margin %
- P/E (TTM), P/S, P/B, market cap
- EV/EBITDA if available

**Fallback if stockanalysis.com is incomplete:**
- Macrotrends (`https://www.macrotrends.net/`) for USD-denominated historical data
- Company annual reports for segment-level breakdown
- Screener.in (India), Trendlyne (India), MOPS (Taiwan) for local-market data

---

## Moat Assessment Dimensions

For the **Product Moat Matrix** on the Competitors page, define rows as the key product types or capability dimensions in the industry. Rate each company on a four-level scale:

| Level | Badge Colour | Meaning |
|---|---|---|
| **Leader** | Green | Best-in-class; sets the industry benchmark |
| **Capable** | Blue | Competitive offering; can win business |
| **Limited** | Amber | Present but not a primary strength |
| **None** | Grey | Does not offer this product/capability |

For the **Moat Narrative Cards**, write one card per company describing:
- Their single most defensible competitive advantage
- The specific mechanism that makes it hard to replicate (e.g., qualification cycles, proprietary IP, scale economics, regulatory approval)
- Any structural risk to that moat (e.g., customer diversification, technology disruption, new entrant)

---

## Appendix: Taiwanese PCB Sector Peers

### Standard Peer Set

| Company | Ticker | Specialisation |
|---|---|---|
| Unimicron Technology | 3037.TW | ABF IC substrates, HDI, SLP |
| Compeq Manufacturing | 2313.TW | HDI, rigid PCB, server boards |
| Tripod Technology | 3044.TW | Automotive PCB, HDI, rigid |
| Nan Ya PCB | 8046.TW | ABF IC substrates, HDI |
| Kinsus Interconnect | 3189.TW | IC substrates (BT, ABF), SiP |

### Key Product Moat Concepts

**ABF (Ajinomoto Build-up Film) Substrates**
- Used in high-end CPUs, GPUs, AI accelerators (NVIDIA, AMD, Intel)
- Extremely high barriers: 3–5 year qualification cycles, proprietary process know-how
- Key players: Unimicron, Nan Ya PCB, Kinsus, Ibiden (Japan), Shinko (Japan)
- Demand driver: AI server build-out — each H100/H200/B200 GPU uses 2–4 ABF substrates

**SLP (Substrate-Like PCB)**
- Used in iPhone main logic boards (Apple is the dominant customer)
- Requires sub-30μm line/space capability — very few manufacturers qualify
- Key players: Zhen Ding (~60–70% Apple SLP share), Ibiden, AT&S

**FPC (Flexible PCB)**
- Zhen Ding is the world's largest FPC manufacturer by volume
- High volume, moderate margin — competitive with Chinese manufacturers

**HDI (High Density Interconnect)**
- Widely manufactured — lower moat than SLP or ABF substrates
- Compeq and Tripod are strong in server/networking HDI

### Data Collection for Taiwan PCB Peers

```
https://stockanalysis.com/quote/tpe/{ticker}/financials/
https://stockanalysis.com/quote/tpe/{ticker}/statistics/
```

Exchange prefix: `tpe` (TWSE), `tpex` (Taipei OTC/emerging board)
