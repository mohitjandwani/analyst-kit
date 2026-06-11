---
name: analyst-playbook
type: capability
description: >
  How to structure any financial analysis before fetching a single number: decide the
  deliverable (report/deck vs financial-model update), align fiscal calendars and data
  frequencies, normalize units, route each data series to the right skill, and apply
  sector-specific conventions (reporting calendars, KPIs, seasonality, valuation norms)
  from per-sector playbooks loaded on demand. Triggers: "how should I structure this
  analysis", "compare X and Y", "analyze <company> properly", "what matters for this
  sector", "which metrics should I use for X", "build an analysis plan for Y".
---

# Analyst playbook — structure the analysis before touching data

Work through the four steps below **in order, before fetching any data**. Each one
prevents a class of silently-wrong analysis: wrong deliverable, misaligned periods,
apples-to-oranges units, or sector conventions ignored.

## 1. Decide the deliverable first

Every engagement resolves to one of two deliverables. Decide which — it changes what
you collect and how you normalize:

- **A report or presentation deck** → finish with the **reporting** skill (storyline
  contract → branded PDF). Collect series wide enough to chart and cite.
- **A financial-model update** (new actuals into a maintained model — a spreadsheet
  or model file) → the **model-updater** skill. *It has not shipped yet*: until it
  does, write the normalized series and your assumptions to clearly-named files,
  and say in your output that the model-update step was done as files.

If the user didn't say which, a comparison/question is a report; "update", "refresh",
or "push the new quarter" language is a model update.

## 2. Alignment checklist — run it for every entity

1. **Reporting calendar.** Find each entity's fiscal year end before anything else
   (FMP's fiscal-period data, or the cover of the latest 10-K). Watch the classic
   offenders: January-ending fiscal years (NVDA, many retailers), the retail 4-5-4
   calendar, June/August year ends, Taiwan's monthly revenue cadence.
2. **Common period axis.** Comparing entities on different calendars: pick ONE
   axis (usually the more constrained entity's fiscal quarters), re-bin the other's
   data into it (aggregate months into the target quarters; never interpolate),
   and **state the mapping you used** in the deliverable.
3. **Units.** Different currencies, or an index (search interest, survey, PMI)
   against dollars → compare **year-over-year growth, never raw levels**. Same
   currency and same metric definition → absolute comparison is allowed.
4. **Derived numbers come from scripts.** YoY/growth/margins via the charting
   skill's Polars pipeline (`python3 -m pipeline.cli yoy … --lag 4` quarterly,
   `--lag 12` monthly) — never computed in your head.

## 3. Route each series to the right skill

| Series | Skill |
|---|---|
| US/global GAAP fundamentals, prices, transcripts, fiscal periods | financialmodellingprep |
| Taiwan-listed anything; monthly revenue | finmind |
| Segment revenue, MD&A, risk factors, anything inside a filing | sec-filings |
| Non-GAAP KPIs (bookings, DAU, ARR, comps) — never in fundamentals APIs | sec-filings (8-K earnings exhibits, EX-99.x) |
| Institutional holdings | 13f-analysis |
| Growth math + chart contracts | charting (Polars pipeline + render) |
| Final document | reporting |

## 4. Apply the sector playbook

Sector conventions decide what "correct" means (a retailer compared on calendar
quarters is simply wrong). List this skill's `references/` directory and read the
playbook matching each entity's sector — for cross-sector comparisons read each one.
If no playbook matches, open `references/_template.md` and use its section headings
as your checklist for that sector.

Playbooks are deliberately not enumerated here: new sector files drop into
`references/` without changing this document.
