#!/usr/bin/env python3
"""Shared SEC EDGAR helpers for the sec-filings skill.

Pure Python standard library — no pip install, no API key. SEC EDGAR is a free,
public, authoritative source. SEC's fair-access policy requires a descriptive
User-Agent that identifies you with a contact email; **without it every request
returns HTTP 403** (this is the #1 reason naive fetches fail). Set your own with:

    export SEC_EDGAR_UA="your-app your-name you@example.com"

A valid default is built in, so nothing is required. The point of this module is
that *every* SEC request goes through http_get(), which always sends the header —
so you never hit the 403 trap. NEVER fetch sec.gov with the WebFetch tool: it
cannot set a User-Agent and SEC will 403 it.

CLI (so the agent never needs WebFetch for lookups):
    python edgar.py cik AAPL                 # ticker -> CIK + title
    python edgar.py filings AAPL 10-K -n 5   # list filings of a form, newest first
    python edgar.py doc AAPL 10-K            # primary-document URL of the latest 10-K
    python edgar.py attachments AAPL 8-K     # accession folder: exhibits (EX-99.1) + XBRL members
    python edgar.py cover AAPL 8-K           # dei cover-page XBRL facts (an 8-K's ONLY XBRL)
    python edgar.py concept AAPL NetIncomeLoss   # one financial concept across periods (facts API)
    python edgar.py facts AAPL --grep Revenue    # discover which XBRL tags a company exposes

Import for custom pulls:
    from edgar import (http_get, resolve_cik, filings, latest_filing, document_url,
                       accession_files, find_exhibits, cover_page_facts,
                       companyconcept, companyfacts)
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.request

# SEC asks for a real contact. Override via SEC_EDGAR_UA. The default is valid
# but please set your own email so the SEC can reach you if your traffic spikes.
UA = os.environ.get(
    "SEC_EDGAR_UA",
    "hedge-fund-analyst sec-filings-skill contact@example.com",
)

_HEADERS = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}


def http_get(url, raw=False, tries=4, sleep=0.25):
    """GET with the required User-Agent, gzip handling, and retry/backoff.

    Returns str (or bytes if raw=True), or None on terminal failure. A short
    sleep after each call keeps us well under SEC's ~10 req/sec fair-access cap.
    This is the ONLY way this skill talks to SEC — do not bypass it with WebFetch
    or a bare curl (both omit the User-Agent and get a 403).
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                time.sleep(sleep)
                return data if raw else data.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - surface only after final retry
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))
    print(f"  ! GET failed ({last}): {url}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Ticker -> CIK
# ---------------------------------------------------------------------------
_TICKER_MAP = None


def _ticker_map():
    """{TICKER: (cik10, title)} from the official map, cached per process."""
    global _TICKER_MAP
    if _TICKER_MAP is None:
        txt = http_get("https://www.sec.gov/files/company_tickers.json")
        _TICKER_MAP = {}
        if txt:
            for row in json.loads(txt).values():
                # Dotted tickers (BRK.B) are stored dash-form (BRK-B) upstream.
                t = str(row["ticker"]).upper()
                _TICKER_MAP[t] = (str(row["cik_str"]).zfill(10), row.get("title", ""))
    return _TICKER_MAP


def resolve_cik(identifier):
    """Return (cik10, title). Accepts a CIK (digits) or a ticker.

    Handles the two identity traps: dotted tickers are normalized to dash form
    (BRK.B -> BRK-B), and multi-class tickers share one CIK (GOOGL/GOOG both ->
    1652044). Raises ValueError if a ticker is unknown.
    """
    s = str(identifier).strip()
    if re.fullmatch(r"\d{1,10}", s):
        cik = s.zfill(10)
        sub = get_submissions(cik)
        return cik, (sub.get("name") if sub else "")
    norm = s.upper().replace(".", "-")
    hit = _ticker_map().get(norm)
    if not hit:
        raise ValueError(
            f"Unknown ticker {s!r}. Pass a CIK, or check company_tickers.json."
        )
    return hit


# ---------------------------------------------------------------------------
# Submissions / filing list
# ---------------------------------------------------------------------------
def get_submissions(cik10):
    """The submissions JSON for a CIK (must be zero-padded to 10 in the path)."""
    txt = http_get(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    return json.loads(txt) if txt else None


def _rows_from_recent(rec):
    """Zip the column-oriented filings.recent arrays into a list of dict rows."""
    n = len(rec.get("form", []))

    def col(name):
        return rec.get(name, [""] * n)

    return [
        {
            "form": col("form")[i],
            "filed": col("filingDate")[i],
            "period": col("reportDate")[i],
            "accession": col("accessionNumber")[i],
            "primary_doc": col("primaryDocument")[i],
            "items": col("items")[i],
            "acceptance": col("acceptanceDateTime")[i],
        }
        for i in range(n)
    ]


def filings(cik10, form=None, limit=50, include_history=False):
    """Filing rows newest-first, optionally filtered to an EXACT form.

    Form matching is exact and case/space-sensitive ("10-K" != "10-K/A"; "DEF 14A"
    has a space). `filings.recent` caps at ~1000 filings — set include_history=True
    to also walk the overflow files (filings.files[]) for older history.
    """
    sub = get_submissions(cik10)
    if not sub:
        return []
    rows = _rows_from_recent(sub["filings"]["recent"])
    if include_history:
        for f in sub["filings"].get("files", []):
            txt = http_get(f"https://data.sec.gov/submissions/{f['name']}")
            if txt:
                # Overflow files are a flat dict of arrays (no .recent wrapper).
                rows += _rows_from_recent(json.loads(txt))
    if form:
        rows = [r for r in rows if r["form"] == form]
    rows.sort(key=lambda r: r["filed"], reverse=True)
    return rows[:limit] if limit else rows


def latest_filing(cik10, form="10-K", accession=None):
    """The newest filing of `form`, or the row matching a specific accession."""
    rows = filings(cik10, form=None if accession else form, limit=0,
                   include_history=bool(accession))
    if accession:
        acc = accession.replace("-", "")
        for r in rows:
            if r["accession"].replace("-", "") == acc:
                return r
        return None
    return rows[0] if rows else None


def document_url(cik10, row):
    """Build the canonical Archives URL for a filing's primary document.

    Falls back to the folder index.json to discover the primary .htm when the
    submissions feed didn't name one.
    """
    nodash = row["accession"].replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{nodash}"
    doc = row.get("primary_doc")
    if not doc:
        idx = http_get(f"{base}/index.json")
        if idx:
            items = json.loads(idx)["directory"]["item"]
            htms = [it["name"] for it in items if it["name"].lower().endswith((".htm", ".html"))]
            doc = htms[0] if htms else None
    return f"{base}/{doc}" if doc else None


# ---------------------------------------------------------------------------
# Accession folder: exhibits + XBRL members (the 8-K "attachments")
# ---------------------------------------------------------------------------
def accession_files(cik10, accession):
    """Every file in a filing's accession folder, each with a resolved `url`.

    This is the manifest for "the attachments included with an 8-K": the primary
    .htm (cover page), the exhibits (EX-99.1 press release, EX-10.x contracts, …),
    and the XBRL members (the `*_htm.xml` instance, `*_pre/_lab/_def/_cal.xml`
    linkbases, the rendered `R*.htm` statements, FilingSummary.xml, MetaLinks.json).
    """
    nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{nodash}"
    txt = http_get(f"{base}/index.json")
    if not txt:
        return []
    items = json.loads(txt)["directory"]["item"]
    for it in items:
        it["url"] = f"{base}/{it['name']}"
    return items


def find_exhibits(cik10, accession):
    """Accession files that are exhibits (EX-*), newest filings name them e.g.
    `a8-kex991...htm`. Returns the human-readable HTML exhibits; on an Item 2.02
    earnings 8-K, EX-99.1 is the press release with the financial tables.

    Hand an exhibit's `url` to parse_filing.py (`--url`) to read it — those tables
    are PLAIN HTML, not XBRL (verified), so the facts API won't have them until the
    matching 10-Q/10-K is filed.
    """
    out = []
    for it in accession_files(cik10, accession):
        name = it["name"].lower()
        if name.endswith((".htm", ".html")) and ("ex99" in name or "ex-99" in name
                                                  or re.search(r"ex\d", name)):
            out.append(it)
    return out


# ---------------------------------------------------------------------------
# XBRL — cover-page dei facts (an 8-K's ONLY XBRL)
# ---------------------------------------------------------------------------
def _local(tag):
    """Strip the {namespace} prefix ElementTree puts on qualified names."""
    return tag.rsplit("}", 1)[-1]


def cover_page_facts(cik10, accession):
    """Cover-page dei: facts from a filing's extracted XBRL instance (*_htm.xml).

    Every 8-K/10-K/10-Q carries inline-XBRL on its COVER PAGE only (document type,
    period, registrant identity, item flags, registered securities). For an 8-K
    this is the *entire* XBRL payload — there are NO us-gaap financial facts
    (verified: 0 ix:nonFraction; us-gaap appears only as context dimension members
    for the registered-securities block, never as a fact).

    Returns [{tag, value, context, member}], where `member` resolves the dimension
    (e.g. which registered security a TradingSymbol belongs to) when present.
    """
    inst = next((f for f in accession_files(cik10, accession)
                 if f["name"].endswith("_htm.xml")), None)
    if not inst:
        return []
    xml = http_get(inst["url"])
    return parse_dei_instance(xml) if xml else []


def parse_dei_instance(xml):
    """Pure XBRL-instance parser: dei: facts + resolved context period/member.

    Split out from the network so it is unit-testable offline. Skips xsi:nil facts;
    resolves each fact's contextRef to a period (instant or endDate) and, when the
    context carries an explicitMember dimension, the member local name.
    """
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml.encode("utf-8", "replace") if isinstance(xml, str) else xml)

    # Map context id -> short {period, member} descriptor.
    contexts = {}
    for ctx in root.iter():
        if _local(ctx.tag) != "context":
            continue
        period, member = "", ""
        for sub in ctx.iter():
            ln = _local(sub.tag)
            if ln in ("instant", "endDate"):
                period = (sub.text or "").strip()
            elif ln == "explicitMember":
                member = _local((sub.text or "").strip())  # e.g. CommonStockMember
        contexts[ctx.get("id")] = {"period": period, "member": member}

    facts = []
    for el in root.iter():
        ns = el.tag.split("}", 1)[0].lstrip("{") if "}" in el.tag else ""
        if "/dei/" not in ns:
            continue
        attrib = {_local(k): v for k, v in el.attrib.items()}
        if attrib.get("nil") == "true":
            continue
        ctx = contexts.get(attrib.get("contextRef", ""), {})
        facts.append({
            "tag": f"dei:{_local(el.tag)}",
            "value": (el.text or "").strip(),
            "context": ctx.get("period", ""),
            "member": ctx.get("member", ""),
        })
    return facts


# ---------------------------------------------------------------------------
# XBRL — financial NUMBERS via SEC's pre-computed facts API
# ---------------------------------------------------------------------------
# This is the RIGHT source for financial numbers: SEC has already extracted every
# us-gaap fact and applied scale/sign/units, so you avoid the iXBRL gotchas. It
# covers 10-K/10-Q/20-F facts — NOT 8-K earnings tables (those aren't XBRL).
def companyconcept(cik10, tag, taxonomy="us-gaap"):
    """All reported values of one concept for one company. None if untagged."""
    txt = http_get(f"https://data.sec.gov/api/xbrl/companyconcept/"
                   f"CIK{cik10}/{taxonomy}/{tag}.json")
    return json.loads(txt) if txt else None


def companyfacts(cik10):
    """Every XBRL fact SEC has for a company (large). Use to DISCOVER tag names —
    revenue is company-specific (Apple: RevenueFromContractWithCustomerExcluding
    AssessedTax, not Revenues), so never hardcode a tag without checking here."""
    txt = http_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json")
    return json.loads(txt) if txt else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv):
    p = argparse.ArgumentParser(description="SEC EDGAR lookups (UA-compliant; no WebFetch).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("cik", help="ticker -> CIK + title")
    pc.add_argument("identifier")

    pf = sub.add_parser("filings", help="list filings of a form, newest first")
    pf.add_argument("identifier")
    pf.add_argument("form", nargs="?", default=None)
    pf.add_argument("-n", "--limit", type=int, default=10)
    pf.add_argument("--history", action="store_true", help="include pre-1000 overflow history")

    pd_ = sub.add_parser("doc", help="primary-document URL of the latest filing of a form")
    pd_.add_argument("identifier")
    pd_.add_argument("form", nargs="?", default="10-K")

    pa = sub.add_parser("attachments", help="list a filing's accession folder (exhibits + XBRL)")
    pa.add_argument("identifier")
    pa.add_argument("form", nargs="?", default="8-K")
    pa.add_argument("--accession", help="specific accession (else: latest of form)")

    pcov = sub.add_parser("cover", help="dei cover-page XBRL facts (an 8-K's only XBRL)")
    pcov.add_argument("identifier")
    pcov.add_argument("form", nargs="?", default="8-K")
    pcov.add_argument("--accession", help="specific accession (else: latest of form)")

    pcon = sub.add_parser("concept", help="all values of one XBRL concept (facts API)")
    pcon.add_argument("identifier")
    pcon.add_argument("tag", help="e.g. RevenueFromContractWithCustomerExcludingAssessedTax")
    pcon.add_argument("--tax", default="us-gaap", help="taxonomy (default us-gaap; also dei)")

    pfa = sub.add_parser("facts", help="discover which XBRL tags a company exposes")
    pfa.add_argument("identifier")
    pfa.add_argument("--grep", help="case-insensitive substring filter on tag name")

    a = p.parse_args(argv)
    cik, title = resolve_cik(a.identifier)

    if a.cmd == "cik":
        print(f"{cik}\t{title}")
    elif a.cmd == "filings":
        rows = filings(cik, form=a.form, limit=a.limit, include_history=a.history)
        print(f"# {title} (CIK {cik}) — {len(rows)} filing(s)"
              + (f" of {a.form}" if a.form else ""))
        for r in rows:
            extra = f"  items={r['items']}" if r["items"] else ""
            print(f"{r['filed']}  {r['form']:<10} {r['accession']}  period={r['period']}{extra}")
    elif a.cmd == "doc":
        row = latest_filing(cik, form=a.form)
        if not row:
            print(f"No {a.form} found for {title} (CIK {cik}).", file=sys.stderr)
            return 1
        url = document_url(cik, row)
        print(f"# {title} — {a.form} filed {row['filed']} (period {row['period']})", file=sys.stderr)
        print(url)

    elif a.cmd in ("attachments", "cover"):
        row = latest_filing(cik, form=a.form, accession=a.accession)
        if not row:
            print(f"No {a.form} found for {title} (CIK {cik}).", file=sys.stderr)
            return 1
        acc = row["accession"]
        if a.cmd == "attachments":
            print(f"# {title} — {row['form']} {acc} (filed {row['filed']}, items={row['items']})")
            for it in accession_files(cik, acc):
                print(f"{str(it.get('size','')):>10}  {it['name']:<45}  {it['url']}")
        else:  # cover
            facts = cover_page_facts(cik, acc)
            print(f"# {title} — {row['form']} {acc}: {len(facts)} dei cover-page fact(s)")
            for f in facts:
                tail = f"  [{f['member']}]" if f["member"] else ""
                print(f"  {f['tag']:<42} {f['value']}{tail}")

    elif a.cmd == "concept":
        data = companyconcept(cik, a.tag, a.tax)
        if not data:
            print(f"No {a.tax}:{a.tag} for {title}. Try `facts {a.identifier} --grep <part>` "
                  f"to find the right tag (revenue is company-specific).", file=sys.stderr)
            return 1
        print(f"# {title} — {a.tax}:{a.tag} — {data.get('label','')}")
        for unit, vals in data.get("units", {}).items():
            print(f"## unit={unit}  ({len(vals)} facts; showing latest 6)")
            for v in vals[-6:]:
                period = v.get("end") or v.get("start", "")
                print(f"  {period}  {v.get('val'):>22,}  fy{v.get('fy')} {v.get('fp','')} {v.get('form')}")

    elif a.cmd == "facts":
        data = companyfacts(cik)
        if not data:
            print(f"No company facts for {title}.", file=sys.stderr)
            return 1
        g = a.grep.lower() if a.grep else None
        shown = 0
        for tax, tags in data.get("facts", {}).items():
            for tag in sorted(tags):
                if g and g not in tag.lower():
                    continue
                units = tags[tag].get("units", {})
                n = sum(len(v) for v in units.values())
                print(f"{tax}:{tag}  ({n} facts, units={list(units)})")
                shown += 1
        print(f"# {title}: {shown} concept(s)" + (f" matching {a.grep!r}" if g else ""),
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
