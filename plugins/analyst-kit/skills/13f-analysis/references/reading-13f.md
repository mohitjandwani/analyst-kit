# How to read a 13F (and the mistakes that burn people)

## What a 13F actually is

Form **13F-HR** is a quarterly filing required of institutional investment
managers that exercise discretion over **≥ $100M** in *Section 13(f) securities*
(mostly U.S.-exchange-listed stocks, ADRs, and certain options/convertibles).
They must file within **45 days of quarter-end**. The meat is the
**information table**: one row per holding.

### The columns (information table)

| Field (XML tag) | Meaning |
|---|---|
| `nameOfIssuer` | Issuer name, as the filer typed it (formatting varies, errors happen) |
| `titleOfClass` | Share class / security description |
| `cusip` | 9-char CUSIP. **First 6 chars = the issuer**; chars 7–8 = the specific issue |
| `value` | Market value at quarter-end. **Units vary — see below** |
| `sshPrnamt` | Share count *or* principal amount |
| `sshPrnamtType` | `SH` = shares · `PRN` = principal (e.g. a convertible bond). Don't mix them |
| `putCall` | Blank = common/long · `Put` · `Call`. **Read this — it flips the meaning** |
| `investmentDiscretion`, `votingAuthority` | Who controls the position |

### Reading it correctly

1. **Aggregate by issuer.** One issuer routinely appears on many rows — multiple
   share classes, multiple internal managers/accounts, plus separate option
   lines. Roll up by **CUSIP first-6** to get the real position. (`fetch_13f.py`
   does this; raw EDGAR does not.)
2. **Portfolio weight** = position value ÷ total table value. This is the single
   most useful derived number — it shows conviction far better than rank.
3. **Quarter-over-quarter is where the signal is.** Pull two consecutive periods
   (`--period`) and diff: new buys, adds, trims, full exits. A single snapshot is
   just a photo; the *change* is the story.

---

## Top mistakes (read before you trust a single number)

### 1. Assuming the data is accurate and clean — it isn't
13Fs are **self-reported, lightly validated, and full of errors**:
- **Unit confusion (the big one).** Pre-2023 the SEC reported `value` in
  *thousands*; rules now say whole dollars — but **many filers still report in
  thousands**, and some mislabel. A fund's "$5M portfolio" that is really $5B is
  a units error. *Always sanity-check:* `value ÷ shares` should ≈ the real share
  price. If it's ~1000× too small, the filing is in thousands. (`fetch_13f.py`
  auto-detects and normalizes; it prints a flag when it does.)
- **Fat-finger share counts, wrong/stale CUSIPs, duplicate rows, misclassified
  put/call.** Treat any single outsized position as suspect until you eyeball it.
- **Amendments supersede.** A `13F-HR/A` can restate or replace the original.
  Always take the *latest* filing for a period, and note whether it's an
  amendment.
- **Confidential treatment.** Managers can ask the SEC to *delay* disclosure of a
  position they're still building. Those rows are **missing** from the original
  filing and show up quarters later — so a 13F can silently under-report.

### 2. A 13F shows only LONG positions — it does **not** show hedges or shorts
This is the error that turns "13F analysis" into bad conclusions:
- **No short positions.** Shorts are never disclosed. A fund that looks heavily
  long tech could be net-neutral or net-short after shorts you can't see.
- **No cash, most bonds, FX, commodities, futures, swaps, or private holdings.**
- **No foreign-listed equities** (non-U.S. lines). A global fund's 13F is only
  its U.S.-listed sleeve.
- **Puts and calls *are* included — and they invert the meaning.** A row with
  `putCall = Put` is typically a **bearish/hedge** position, not a bullish bet.
  Counting it as "long" is exactly backwards. Always read the `putCall` column
  (surfaced as the `derivative` flag in our output).

⇒ For a **market-neutral, macro, or multi-strat** fund, the 13F may represent a
small and *misleading* slice of the real book. It's far more reliable for
**long-only / concentrated value/growth** managers (e.g. Berkshire, Pershing,
Himalaya) than for hedged shops.

### 3. The snapshot is up to 45 days stale
The table is a photo at **quarter-end**, published up to 45 days later. By the
time you read it the manager may have already sold. Don't trade off a 13F as if
it were live positioning — use it for *what changed*, not *what to buy today*.

### 4. Options are reported at notional, not premium
Put/call rows carry the **market value of the underlying shares**, not the
option's cost. A "$2B call position" might be a few million dollars of premium.
Don't add option notional to share value and call it "exposure."

### 5. Value ≠ cost basis ≠ conviction change
`value` is market value at quarter-end. A position's weight can *rise* purely
because the stock went up — with the manager buying nothing. To infer intent,
compare **share counts** quarter-over-quarter, not dollar values.

### 6. Wrong entity / CIK
Funds have look-alike entities: the flagship fund vs. the family office vs. a
former adviser shell (e.g. *Greenlight Capital Inc* stopped filing — Einhorn now
files under *DME Capital Management*; *Duquesne Capital* is the wound-down old
fund, *Duquesne Family Office* is the live one). Resolve to the **right CIK**
(see `known-funds.md`) before drawing conclusions.

---

## Bottom line
A 13F is a **delayed, long-only, U.S.-equity, self-reported** snapshot. It is
excellent for tracking concentrated long-only managers and for spotting
quarter-over-quarter changes — and misleading if you treat it as a complete,
accurate, current portfolio. Sanity-check units, roll up by CUSIP6, read the
put/call column, and diff across quarters.
