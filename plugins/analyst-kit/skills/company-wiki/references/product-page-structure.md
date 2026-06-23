# Product Page Data Schema

## Table of Contents
1. [ProductPageTemplate Props](#productpagetemplate-props)
2. [Earnings Insights Schema](#earnings-insights-schema)
3. [Example: FPC Page Data](#example-fpc-page-data)

---

## ProductPageTemplate Props

Create a shared `ProductPageTemplate.tsx` component that accepts this data shape:

```tsx
interface ProductPageProps {
  name: string;               // Short name, e.g. "FPC"
  fullName: string;           // Full name, e.g. "Flexible Printed Circuit"
  tagline: string;            // One-line description
  heroImage?: string;         // URL from manus-upload-file --webdev
  description: string;        // 2–3 paragraph overview (JSX or string)
  citationDesc?: number[];    // Citation numbers for the description
  specs: Spec[];              // Technical specifications
  features: Feature[];        // Key product features / capabilities
  revenueShare?: string;      // e.g. "~45% of total revenue (2025)"
  citationRevenue?: number[]; // Citation numbers for revenue share
  customers: string[];        // Key customer segments or named customers
  earningsInsights: EarningsInsight[];
  outlook?: string;           // Management forward-looking commentary
  citationOutlook?: number[];
}

interface Spec {
  label: string;   // e.g. "Layer Count"
  value: string;   // e.g. "Up to 12 layers"
  cite?: number[];
}

interface Feature {
  title: string;
  description: string;
  cite?: number[];
}

interface EarningsInsight {
  quarter: string;    // e.g. "Q4 2025" or "FY 2025"
  insight: string;    // Verbatim or paraphrased management quote
  cite: number[];
}
```

## Earnings Insights Schema

Populate `earningsInsights` from the earnings presentation PDFs. For each product, extract:
- Revenue growth commentary ("FPC revenue grew 18% YoY driven by…")
- Capacity utilisation statements
- Customer concentration changes
- New product introductions or qualifications
- Margin commentary specific to the product

Always cite the exact presentation (source number) for each insight.

## Example: FPC Page Data

```tsx
const fpcData: ProductPageProps = {
  name: "FPC",
  fullName: "Flexible Printed Circuit",
  tagline: "The world's largest FPC manufacturer by volume",
  revenueShare: "~45% of total revenue (FY 2025)",
  citationRevenue: [1, 2],
  specs: [
    { label: "Layer Count", value: "1–12 layers", cite: [3] },
    { label: "Min Line/Space", value: "25/25 μm", cite: [3] },
    { label: "Applications", value: "Smartphones, wearables, laptops", cite: [1] },
  ],
  customers: ["Apple (primary)", "Android OEMs", "Automotive"],
  earningsInsights: [
    {
      quarter: "Q4 2025",
      insight: "FPC segment delivered record revenue, driven by content increase in flagship smartphones.",
      cite: [1],
    },
  ],
};
```
