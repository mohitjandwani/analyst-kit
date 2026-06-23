#!/usr/bin/env python3
"""Find a fund's SEC CIK when you don't know its exact registered name.

    python find_fund.py "pershing square"
    python find_fund.py "tiger"            # broad term -> lists all matches

Searches EDGAR by *filer* name (prefix match). Prints CIK + registered name +
latest 13F-HR for each candidate, so you can pick the right entity and feed its
CIK to fetch_13f.py.

Why not full-text search? EDGAR full-text search matches the *contents* of
filings. Searching a manager whose name is also a popular holding (e.g.
"Berkshire Hathaway") returns every fund that *holds* it, not the filer itself.
Filer-name search (this script) avoids that trap. Caveat: getcompany matches the
START of the registered name, so search the firm ("Duquesne"), not the person
("Druckenmiller").
"""
import sys

from edgar import find_filers, submissions_summary


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = " ".join(argv[1:])
    matches = find_filers(name)
    if not matches:
        print(f"No 13F filer found for {name!r}.")
        print("Tips: search the firm name (not the manager's name); try a shorter prefix.")
        return 1
    print(f"{len(matches)} filer(s) matching {name!r}:\n")
    for cik, fname in matches:
        real, rows = submissions_summary(cik)
        if rows:
            r = rows[0]
            latest = f"latest {r['form']} period {r['period']} (filed {r['filed']}, {len(rows)} on file)"
        else:
            latest = "no 13F-HR on file"
        print(f"  CIK {cik}  {real or fname}")
        print(f"      {latest}")
        print(f"      https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR")
    if len(matches) == 1:
        print(f"\nNext: python fetch_13f.py {matches[0][0]}")
    else:
        print("\nNext: pick the right CIK above, then: python fetch_13f.py <CIK>")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
