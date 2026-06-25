#!/usr/bin/env python3
"""Shared SEC EDGAR helpers for 13F retrieval.

Pure Python standard library — no pip install, no API key. SEC EDGAR is a free,
public, authoritative source. SEC only requires a descriptive User-Agent that
identifies you with a contact email (their fair-access policy). Set one with:

    export SEC_EDGAR_UA="your-app your-name you@example.com"

Import these helpers for custom pulls instead of re-implementing the HTTP call:
    from edgar import resolve_cik, latest_13f, parse_infotable, aggregate
"""
import gzip
import json
import os
import pathlib
import re
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

# SEC asks for a real contact. Honor an explicit SEC_EDGAR_UA; otherwise derive a
# stable per-install contact from the analyst-kit user id (~/.analyst-kit/user-id,
# generated once on first run) so installs don't all share one User-Agent — SEC's
# fair-access policy throttles by UA. Falls back to a generic default if no id yet.
def _ak_home():
    h = os.environ.get("AK_HOME")
    if not h:
        try:
            h = (pathlib.Path.home() / ".analyst-kit" / "home-path").read_text().strip() or None
        except OSError:
            h = None
    return pathlib.Path(h) if h else pathlib.Path.home() / ".analyst-kit"


def _default_ua():
    try:
        uid = (_ak_home() / "user-id").read_text().strip()
    except OSError:
        uid = ""
    return "analyst-kit akit%s@gmail.com" % uid if uid.isdigit() \
        else "analyst-kit 13f-analysis-skill contact@example.com"


UA = os.environ.get("SEC_EDGAR_UA") or _default_ua()


def http_get(url, raw=False, tries=4, sleep=0.25):
    """GET with the required User-Agent, gzip handling, and retry/backoff.

    Returns str (or bytes if raw=True), or None on terminal failure. A short
    sleep after each call keeps us well under SEC's 10 req/sec fair-access cap.
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
            )
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
    print(f"  ! GET failed ({last}): {url}")
    return None


def _localname(tag):
    return tag.split("}")[-1].lower()


# ---------------------------------------------------------------------------
# Finding a fund (filer) by name
# ---------------------------------------------------------------------------
def find_filers(name, count=40):
    """Search EDGAR by *filer* name (prefix match) and return [(cik10, name)].

    Uses browse-edgar getcompany, which matches the registered company/filer
    name — the correct tool for "who filed this 13F?". (Do NOT use full-text
    search for this: full-text matches the *contents* of filings, so searching
    "Berkshire Hathaway" returns every fund that *holds* Berkshire, not
    Berkshire itself.)
    """
    q = urllib.parse.quote(name)
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        f"&company={q}&type=13F-HR&dateb=&owner=include&count={count}&output=atom"
    )
    txt = http_get(url)
    if not txt:
        return []
    try:
        root = ET.fromstring(txt.encode("utf-8"))
    except ET.ParseError:
        return []

    # Single definitive match: a top-level <company-info> with <conformed-name>.
    for ci in root.iter():
        if _localname(ci.tag) != "company-info":
            continue
        cik = name_el = None
        for ch in ci:
            ln = _localname(ch.tag)
            if ln == "cik":
                cik = (ch.text or "").strip()
            elif ln == "conformed-name":
                name_el = (ch.text or "").strip()
        if cik and name_el:
            return [(cik.zfill(10), name_el)]

    # Multi match: each <entry> carries a <company-info><cik> and a <title>.
    out, seen = [], set()
    for entry in root.iter():
        if _localname(entry.tag) != "entry":
            continue
        cik = title = None
        for el in entry.iter():
            ln = _localname(el.tag)
            if ln == "cik" and not cik:
                cik = (el.text or "").strip()
            elif ln == "title" and not title:
                title = (el.text or "").strip()
        if cik and cik not in seen:
            seen.add(cik)
            out.append((cik.zfill(10), title or "(name unavailable)"))
    return out


def resolve_cik(name_or_cik):
    """Return (cik10, filer_name). Accepts a CIK (digits) or a fund name.

    Raises ValueError if a name matches zero or multiple filers — in that case
    pass an explicit CIK (run find_fund.py to list candidates).
    """
    s = str(name_or_cik).strip()
    if re.fullmatch(r"\d{1,10}", s):
        cik = s.zfill(10)
        sub = get_submissions(cik)
        return cik, (sub.get("name") if sub else "(unknown)")
    matches = find_filers(s)
    if not matches:
        raise ValueError(f"No 13F filer found for {s!r}. Try find_fund.py with a firm name.")
    if len(matches) > 1:
        lines = []
        for c, n in matches[:15]:
            real, rows = submissions_summary(c)
            latest = rows[0]["period"] if rows else "no 13F"
            lines.append(f"    {c}  {real or n}  (latest {latest})")
        raise ValueError(
            f"{len(matches)} filers match {s!r} — pass an explicit CIK:\n"
            + "\n".join(lines)
        )
    return matches[0]


# ---------------------------------------------------------------------------
# Filings
# ---------------------------------------------------------------------------
def get_submissions(cik10):
    txt = http_get(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    return json.loads(txt) if txt else None


def submissions_summary(cik10):
    """Return (entity_name, [13F filings newest-first]) in a single fetch.

    The EDGAR filer-search atom omits the entity name for multi-matches, so the
    authoritative name comes from the submissions JSON. Each filing row:
    {accession, form, filed, period}.
    """
    sub = get_submissions(cik10)
    if not sub:
        return None, []
    rec = sub["filings"]["recent"]
    n = len(rec["form"])
    rows = [
        {
            "accession": rec["accessionNumber"][i].replace("-", ""),
            "form": rec["form"][i],
            "filed": rec["filingDate"][i],
            "period": rec.get("reportDate", [""] * n)[i],
        }
        for i in range(n)
        if rec["form"][i] in ("13F-HR", "13F-HR/A")
    ]
    rows.sort(key=lambda r: r["filed"], reverse=True)
    return sub.get("name"), rows


def list_13f(cik10):
    """All 13F-HR / 13F-HR/A filings, newest first."""
    return submissions_summary(cik10)[1]


def latest_13f(cik10, period=None):
    """Latest 13F-HR filing, or the one matching a given report period
    (YYYY-MM-DD)."""
    rows = list_13f(cik10)
    if period:
        rows = [r for r in rows if r["period"] == period]
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Information table (the holdings)
# ---------------------------------------------------------------------------
def parse_infotable(cik10, accession):
    """Return raw holdings line items from a filing's information-table XML.

    Each item: {issuer, class, cusip, value, shares, shtype, putcall}. A single
    issuer can appear on multiple lines (different share classes, accounts, or
    option positions) — call aggregate() to roll up by issuer.
    """
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{accession}"
    idx = http_get(f"{base}/index.json")
    if not idx:
        return None
    items = json.loads(idx)["directory"]["item"]
    xmls = [it["name"] for it in items if it["name"].lower().endswith(".xml")]
    # The info table is the XML that is NOT the cover page (primary_doc.xml).
    for fname in [x for x in xmls if "primary_doc" not in x.lower()] or xmls:
        raw = http_get(f"{base}/{fname}", raw=True)
        if not raw:
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            continue
        if _localname(root.tag) != "informationtable" and not any(
            _localname(c.tag) == "infotable" for c in root
        ):
            continue
        holdings = []
        for it in root:
            if _localname(it.tag) != "infotable":
                continue
            rec = {}
            for ch in it.iter():
                ln, v = _localname(ch.tag), (ch.text or "").strip()
                if ln == "nameofissuer":
                    rec["issuer"] = v
                elif ln == "titleofclass":
                    rec["class"] = v
                elif ln == "cusip":
                    rec["cusip"] = v.upper()
                elif ln == "value":
                    rec["value"] = int(float(v or 0))
                elif ln == "sshprnamt":
                    rec["shares"] = int(float(v or 0))
                elif ln == "sshprnamttype":
                    rec["shtype"] = v
                elif ln == "putcall":
                    rec["putcall"] = v
            if rec:
                holdings.append(rec)
        if holdings:
            return holdings
    return None


def reported_in_thousands(holdings):
    """Detect whether VALUE is reported in $thousands rather than whole dollars.

    Post-2023 SEC rules mandate whole dollars, but many filers still report in
    thousands. Detect empirically: implied price = value / shares. For whole
    dollars this is a real share price ($10-$1000); for thousands it is ~1000x
    too small (<$1). Median across the book is robust to penny stocks.
    """
    pps = [
        h["value"] / h["shares"]
        for h in holdings
        if h.get("shtype") == "SH" and h.get("shares") and not h.get("putcall")
    ]
    return bool(pps) and statistics.median(pps) < 5.0


def aggregate(holdings):
    """Normalize units to whole USD and roll up by issuer (CUSIP first 6 = the
    issuer-level identifier). Returns positions sorted by value desc, each:
    {issuer, cusip, cusip6, value_usd, shares, pct, derivative}."""
    mult = 1000 if reported_in_thousands(holdings) else 1
    agg = defaultdict(
        lambda: {"value": 0, "shares": 0, "deriv": set(), "names": defaultdict(int), "cusip": ""}
    )
    for h in holdings:
        key = (h.get("cusip", "") or h.get("issuer", ""))[:6] or h.get("issuer", "")
        a = agg[key]
        a["value"] += h["value"] * mult
        a["cusip"] = h.get("cusip", a["cusip"])
        if h.get("putcall"):
            a["deriv"].add(h["putcall"])
        else:
            a["shares"] += h.get("shares", 0)
        a["names"][h.get("issuer", "?")] += 1
    total = sum(a["value"] for a in agg.values()) or 1
    positions = [
        {
            "issuer": max(a["names"].items(), key=lambda x: x[1])[0],
            "cusip": a["cusip"],
            "cusip6": key,
            "value_usd": a["value"],
            "shares": a["shares"],
            "pct": 100 * a["value"] / total,
            "derivative": "/".join(sorted(a["deriv"])),
        }
        for key, a in agg.items()
    ]
    positions.sort(key=lambda p: -p["value_usd"])
    return positions, mult == 1000
