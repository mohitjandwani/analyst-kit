---
name: 13f-analysis
type: capability
description: >
  Fetch and read U.S. institutional 13F-HR filings (quarterly long-equity holdings)
  for any fund manager from SEC EDGAR — free, no API key. Resolve a fund to its
  filing entity (CIK), pull the latest or a historical quarter's holdings as a
  ranked CSV with values normalized to whole dollars and positions rolled up by
  issuer, and interpret them without the common traps. Triggers: "get the 13F for
  X", "latest 13F holdings of Y", "what does <fund> own", "pull <manager>'s 13F",
  "find the CIK for <fund>", "who filed this 13F", "13F analysis of Z".
---

# 13F analysis — institutional holdings from SEC EDGAR

13F-HR is the quarterly filing where large U.S. managers (≥ $100M) disclose their
**long** positions in U.S.-listed equities. SEC EDGAR is the free, authoritative
source — **no API key, no account**. This skill wraps the two dominant requests —
**find a fund's filing entity** and **pull its holdings** — into self-contained
scripts that run **without reading any reference file**.

## Setup

- **Runtime:** Python 3 (standard library only — no `pip install`, no key).
- **Be a good citizen:** SEC's fair-access policy asks for a User-Agent that
  identifies you with a contact email. Set one (optional; a default is built in):
  ```bash
  export SEC_EDGAR_UA="your-app your-name you@example.com"
  ```
  Stay under ~10 requests/sec (the scripts self-throttle).

## Common operations — just run the script (no reference reading needed)

Scripts are in `scripts/`. Run them from there (they import `edgar.py`).

### 1 · Simplest path — get a fund's latest 13F by CIK
The most reliable input is the CIK. Verified CIKs for a roster of well-known funds
are in [`references/known-funds.md`](references/known-funds.md).
```bash
python fetch_13f.py 0001067983          # Berkshire Hathaway — latest quarter
```
Prints a ranked holdings table and writes `13f-output/<filer>_<period>.csv`
(rank, issuer, CUSIP, value_usd, % of portfolio, shares, derivative flag).
Values are normalized to whole dollars and rolled up by issuer.

### 2 · Don't know the registered name? Search for the filer
```bash
python find_fund.py "pershing square"   # -> CIK + registered name + latest 13F
python find_fund.py "tiger"             # broad term -> lists every match
```
Searches by **filer name** (the right way — see the note below), then feed the
CIK it prints to `fetch_13f.py`. You can also pass a name straight to
`fetch_13f.py "Pershing Square Capital Management"`; if the name is ambiguous it
lists the candidate CIKs and asks you to pick one.

> **Why filer-name search, not full-text search?** EDGAR full-text search matches
> the *contents* of filings. A manager whose name is also a popular holding (e.g.
> "Berkshire Hathaway") will return every fund that *holds* it, not the filer.
> `find_fund.py` uses the filer-name index and avoids that trap. Caveat: it
> prefix-matches the **firm** name — search "Duquesne", not "Druckenmiller".

### 3 · A specific past quarter (e.g. to diff quarter-over-quarter)
```bash
python fetch_13f.py 0001067983 --period 2025-12-31
```
Pull two consecutive periods and compare **share counts** to see new buys, adds,
trims, and exits — that change is where the real signal is (not the dollar value,
which also moves with price).

## Output layout

```
13f-output/
  BERKSHIRE_HATHAWAY_INC_2026-03-31.csv   # ranked, normalized, rolled-up holdings
  ...                                     # one CSV per fund/period
```

## Reading the results correctly — don't skip this

A 13F is a **delayed (≤45 days), long-only, U.S.-equity, self-reported** snapshot.
Before drawing conclusions, read [`references/reading-13f.md`](references/reading-13f.md).
The two mistakes that most often produce wrong conclusions:

1. **The data is not clean / not guaranteed accurate.** Unit confusion (values in
   thousands vs. whole dollars), fat-finger share counts, bad CUSIPs, and
   superseding amendments are all common. `fetch_13f.py` auto-detects and
   normalizes units (and flags when it does) — but still sanity-check outliers
   (`value ÷ shares` should ≈ the real share price).
2. **It shows only longs — no shorts, no hedges.** No short positions, cash,
   bonds, FX, commodities, foreign-listed shares, or private holdings. And long
   **puts/calls are included but invert the meaning** — a `Put` row (see the
   `derivative` column) is usually bearish/a hedge. So a 13F can badly
   misrepresent a hedged or macro fund's true book; it's far more reliable for
   concentrated long-only managers.

## References (read only when you need them)

- [`references/known-funds.md`](references/known-funds.md) — verified CIKs and
  direct EDGAR links for a roster of well-known funds (Berkshire, Pershing,
  Duquesne, Appaloosa, Third Point, Trian, Fairholme, Greenlight/DME, Icahn,
  Baupost, TCI, Viking, Tiger Global, Himalaya, Coatue, Lone Pine, Praetorian),
  plus the entity-resolution traps (e.g. Greenlight files under DME Capital;
  Kuppy under Praetorian PR; Citrini files no 13F).
- [`references/reading-13f.md`](references/reading-13f.md) — how to read the
  information table and the full list of mistakes to avoid.

`scripts/edgar.py` exposes reusable helpers (`resolve_cik`, `find_filers`,
`latest_13f`, `parse_infotable`, `aggregate`, `submissions_summary`) — import them
for custom pulls (cross-fund overlap, quarter-over-quarter diffs) instead of
re-implementing the HTTP and XML parsing.
