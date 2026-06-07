# Wiki Page Component Patterns

## Table of Contents
1. [Home / Company Overview](#home--company-overview)
2. [Financials Page](#financials-page)
3. [Analyst Reports Page](#analyst-reports-page)
4. [Stock & Technical Analysis Page](#stock--technical-analysis-page)
5. [Financial Modelling Page](#financial-modelling-page)
6. [Competitors Page](#competitors-page)
7. [Sources Page](#sources-page)

---

## Home / Company Overview

Sections (top to bottom):
1. **Hero** — full-width image with company name, one-line description, ticker badge
2. **Key Stats Row** — 4 cards: Founded, Revenue (latest year), Employees, Global Rank
3. **About** — 3–4 paragraph narrative with inline `<Cite>` markers
4. **History Timeline** — vertical timeline component, one entry per major milestone
5. **Business Segments** — grid of segment cards linking to product pages
6. **Subsidiaries & Locations** — table of subsidiaries with country and specialisation

History timeline entry shape:
```tsx
interface TimelineEvent {
  year: string;
  title: string;
  description: string;
  cite?: number[];
}
```

---

## Financials Page

Sections:
1. **Revenue & Growth** — `BarChart` (Recharts) with revenue bars + YoY growth line overlay
2. **Margin Trends** — `LineChart` with gross margin %, operating margin %, net margin % lines
3. **Revenue Mix** — `PieChart` or `BarChart` (stacked) by product segment for latest year
4. **5-Year Summary Table** — columns: Year | Revenue | Gross Profit | GP Margin | Op Income | Net Income | EPS
5. **Monthly Revenue** — `AreaChart` of monthly revenue with YoY comparison toggle
6. **Balance Sheet Highlights** — key ratios: current ratio, debt/equity, cash position

All chart data should be hardcoded from research (no API calls). Use `recharts` which is pre-installed.

Tooltip formatter pattern (avoids TypeScript errors):
```tsx
formatter={(value: number) => [`NT$${(value / 1e9).toFixed(1)}B`, "Revenue"]}
```

---

## Analyst Reports Page

Each analyst report as a card:
```tsx
interface AnalystReport {
  bank: string;
  analyst: string;
  date: string;          // "March 2025"
  rating: "Buy" | "Hold" | "Sell" | "Outperform" | "Neutral" | "Underperform";
  priceTarget: string;   // "NT$420"
  priorTarget?: string;
  thesis: string[];      // Array of bullet-point strings
  risks: string[];
  cite: number;
}
```

Rating badge colours:
- Buy / Outperform → green (`bg-green-100 text-green-800`)
- Hold / Neutral → amber (`bg-amber-100 text-amber-800`)
- Sell / Underperform → red (`bg-red-100 text-red-800`)

Include a consensus summary bar at the top showing Buy/Hold/Sell count and average price target.

---

## Stock & Technical Analysis Page

Sections:
1. **Current Snapshot** — price, change, market cap, 52-week range bar
2. **Valuation Multiples Table** — P/E TTM, Fwd P/E, P/S, P/B, EV/EBITDA vs. sector average
3. **Price Performance Chart** — `AreaChart` with 1Y monthly closes (hardcode from Yahoo Finance data)
4. **Technical Levels** — support/resistance table with commentary
5. **Moving Averages** — 50d vs 200d status (above/below), golden/death cross notes
6. **RSI & MACD** — text summary with current reading and interpretation

For the price chart, hardcode monthly OHLC data collected in Phase 5. Do not call live APIs.

---

## Financial Modelling Page

State management:
```tsx
const [scenario, setScenario] = useState<"bear" | "base" | "bull">("base");
```

Scenario definitions (compute from actual CAGR):
```tsx
const scenarios = {
  bear:  { revenueGrowth: [cagr * 0.6, cagr * 0.5], label: "Bear", color: "#ef4444" },
  base:  { revenueGrowth: [cagr * 1.0, cagr * 0.9], label: "Base", color: "#3b82f6" },
  bull:  { revenueGrowth: [cagr * 1.4, cagr * 1.3], label: "Bull", color: "#22c55e" },
};
```

Sections:
1. **Monthly Revenue Chart** — `AreaChart` of all collected monthly data with YoY % overlay
2. **Scenario Selector** — three tab buttons (Bear / Base / Bull)
3. **Projection Summary Cards** — Revenue FY+1, Revenue FY+2, EPS FY+1, EPS FY+2
4. **Valuation Cards** — Fwd P/E FY+1, Fwd P/E FY+2, Fwd P/S FY+1, Fwd P/S FY+2
5. **Cross-Scenario Comparison Table** — all three scenarios side by side for FY+1 and FY+2

Assumptions footnote: state gross margin %, net margin %, share count, current price used.

---

## Competitors Page

State:
```tsx
const [selectedCompanies, setSelectedCompanies] = useState<string[]>(["all"]);
const [activeChart, setActiveChart] = useState<"revenue" | "growth" | "margin" | "netIncome">("revenue");
```

Sections:
1. **Chart Controls** — company filter checkboxes + chart type selector
2. **Main Chart** — `BarChart` or `LineChart` depending on `activeChart` selection
3. **Valuation Table** — columns: Company | Ticker | Mkt Cap | P/E | P/S | P/B | Gross Margin | Net Margin | Rev Growth
4. **Competitive Radar** — `RadarChart` (Recharts) with axes: Revenue Scale, Gross Margin, Net Margin, Revenue Growth, Valuation (inverse P/E)
5. **Product Moat Matrix** — HTML table, rows = product types, columns = companies
6. **Moat Narrative Cards** — one card per company with unique differentiator description

Capability level badges for moat matrix:
- Leader → `bg-green-100 text-green-800 font-semibold`
- Capable → `bg-blue-100 text-blue-800`
- Limited → `bg-amber-100 text-amber-800`
- None → `bg-gray-100 text-gray-500`

---

## Sources Page

Source entry shape:
```tsx
interface Source {
  id: number;
  type: "Earnings Presentation" | "Annual Report" | "Analyst Report" | "News Article" | "Company Website" | "Financial Data";
  publisher: string;
  title: string;
  date: string;       // "March 12, 2026"
  url: string;
  description: string; // What information this source provides
}
```

Render each source as a card with `id={`source-${source.id}`}` for scroll-to-anchor from `<Cite>` clicks.

Include a filter bar at the top to filter by source type.
