---
id: 30-nvda-amd-segments
skills: [sec-filings, financialmodellingprep, charting, reporting]
requiresEnv: [FMP_API_KEY]
timeoutMs: 1200000
---

Compare NVIDIA (NVDA) and AMD (AMD) in the data-center GPU race using each company's
own reported segment revenue — not totals.

The two companies slice their businesses differently and report on different calendars
(AMD on calendar quarters; NVIDIA on fiscal quarters ending roughly one month later),
so the report must be explicit about both:

1. From each company's quarterly earnings releases or 10-Q/10-K segment disclosures,
   extract segment revenue for the last 8 quarters: NVIDIA's "Data Center" and "Gaming"
   segments, and AMD's "Data Center" and "Gaming" segments. Use the figures as reported;
   note anywhere the segment definitions are not truly comparable (for example NVIDIA's
   Data Center includes networking).
2. Align the series by closest calendar quarter and state the alignment rule used
   (e.g. NVDA fiscal quarter ending late April mapped to calendar Q1).

Deliver a single report with: a chart of Data Center segment revenue for both companies
over the 8 quarters (absolute USD, since both report in USD), a chart or table of
year-over-year growth for both companies' Data Center and Gaming segments, NVIDIA's
Data Center revenue as a multiple of AMD's in each quarter, and a short analysis of
whether the gap is widening or narrowing. Every number must trace to a cited filing or
earnings release.

Assemble the final deliverable with the reporting skill: a branded PDF report written to `output/30-nvda-amd-segments.pdf`.
