#!/usr/bin/env python3
"""Index a large SEC filing and BM25-search it for the sections you need.

This is **step 1 of the two-step read pipeline** (see SKILL.md):

  1. parse_filing.py  — index the (often 300+ page) filing and rank the handful
     of sections most relevant to a question. Writes each top section to its own
     small file. (THIS SCRIPT.)
  2. Haiku sub-agents  — spawn one cheap claude-haiku-4-5 sub-agent per top
     section file to extract the precise answer; synthesize. (Done by the host
     agent — instructions in SKILL.md.)

Why not just read the whole filing? A 10-K blows past any sensible context window
and buries the answer in boilerplate. Lexical BM25 over section-sized chunks finds
the right pages cheaply and deterministically (no embeddings, no network, no LLM),
and the per-section Haiku pass keeps extraction accurate *and* cheap.

Pure Python standard library only — no pip install. Fetching goes through
edgar.http_get(), which always sends the SEC-required User-Agent (never WebFetch).

CLI:
    # latest 10-K of a ticker, find supply-chain risk language:
    python parse_filing.py AAPL --form 10-K --query "supply chain concentration risk" --top 5

    # BM25 is lexical — repeat --query with rephrasings for recall (rank-fused):
    python parse_filing.py RBLX --form 8-K --query "bookings three months ended" \
        --query "reconciliation of revenue to bookings" --query "key metrics bookings growth"

    # a specific filing by accession, or a direct document URL:
    python parse_filing.py AAPL --accession 0000320193-25-000079 --query "segment revenue"
    python parse_filing.py --url https://www.sec.gov/Archives/.../aapl-20250927.htm --query "MD&A liquidity"

    # no --query: print the section map (detected Items + char ranges) so you can pick.

Outputs: writes top sections to <out-dir>/<accession>/sec_NN.txt and a machine-
readable results.json, and prints a ranked table to stdout.
"""
import argparse
import json
import math
import os
import re
import sys
from html.parser import HTMLParser

import edgar

# ---------------------------------------------------------------------------
# 1. HTML / iXBRL -> plain text
# ---------------------------------------------------------------------------
# Subtrees whose text is machine-only and must never be indexed. Note this is a
# NAMED set, not "anything namespaced": inline facts like <ix:nonFraction> and
# <ix:nonNumeric> wrap *visible* rendered prose/numbers and must be kept — only
# the iXBRL metadata containers below are hidden.
_SKIP_TAGS = {
    "script", "style", "head", "title",
    "ix:header", "ix:hidden", "ix:references", "ix:resources",
}
_BLOCK_TAGS = {
    "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "section", "article", "ul", "ol", "td", "th", "blockquote",
}
_VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "col", "source"}


class _TextExtractor(HTMLParser):
    """Strip tags to readable text, dropping iXBRL plumbing and hidden facts.

    Modern filings are *inline XBRL*: the prose is wrapped in <ix:...> tags and a
    large <ix:header> block of machine-only facts is hidden via display:none. We
    skip the ix: namespace and any display:none subtree so only visible prose
    survives, and emit a newline on block boundaries so paragraphs stay separate.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._stack = []  # (tagname, skipping?) — skipping propagates to children

    def _skipping(self):
        return bool(self._stack) and self._stack[-1][1]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _VOID_TAGS:
            if tag == "br" and not self._skipping():
                self.parts.append("\n")
            return
        style = (dict(attrs).get("style") or "").replace(" ", "").lower()
        skip = tag in _SKIP_TAGS or "display:none" in style
        self._stack.append((tag, skip or self._skipping()))
        if not self._skipping() and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _VOID_TAGS:
            return
        # Pop to the matching tag, tolerating unclosed/mis-nested markup.
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if not self._skipping() and data.strip():
            self.parts.append(data)


def html_to_text(html):
    """Visible prose from a filing's HTML/iXBRL, with whitespace normalized."""
    p = _TextExtractor()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t ]+", " ", text)       # collapse runs of spaces / nbsp
    text = re.sub(r" *\n *", "\n", text)             # trim around newlines
    text = re.sub(r"\n{3,}", "\n\n", text)           # cap blank-line runs
    return text.strip()


# ---------------------------------------------------------------------------
# 2. Section headers + chunking
# ---------------------------------------------------------------------------
_ITEM_RE = re.compile(r"(?im)^\s*(item\s+\d+[a-z]?)\b[.:)\-\s]")
_PART_RE = re.compile(r"(?im)^\s*(part\s+[ivx]+)\b")


def section_headers(text):
    """Sorted [(char_pos, label)] of every Item / Part header in the text.

    Includes table-of-contents echoes (filings repeat 'Item 1A' in the TOC and
    again at the real section). That's fine: chunk labels are advisory, and the
    body chunk always out-ranks the one-line TOC chunk under BM25.
    """
    hits = []
    for m in _ITEM_RE.finditer(text):
        hits.append((m.start(), m.group(1).title()))
    for m in _PART_RE.finditer(text):
        hits.append((m.start(), m.group(1).title()))
    hits.sort()
    return hits


def _label_for(pos, headers):
    """Nearest header at or before `pos` (binary-ish scan over sorted headers)."""
    label = ""
    for hp, hl in headers:
        if hp <= pos:
            label = hl
        else:
            break
    return label


def chunk_text(text, chunk_chars=6000, overlap=800):
    """Sliding-window chunks with overlap, each tagged with its section label.

    Char windows (not token windows) keep offsets exact and map cleanly back to
    the source. ~6000 chars ≈ a section-sized slice — small enough for a Haiku
    sub-agent, large enough to hold a coherent answer.
    """
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be positive")
    step = max(1, chunk_chars - overlap)
    headers = section_headers(text)
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_chars, n)
        body = text[start:end]
        if body.strip():
            chunks.append({
                "idx": len(chunks),
                "start": start,
                "end": end,
                "item": _label_for(start, headers),
                "text": body,
            })
        if end >= n:
            break
        start += step
    return chunks


# ---------------------------------------------------------------------------
# 3. Okapi BM25 (pure Python, zero dependencies)
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(s):
    return [t for t in _TOKEN_RE.findall(s.lower()) if len(t) > 1]


class BM25:
    """Okapi BM25 over a list of pre-tokenized documents (k1=1.5, b=0.75)."""

    def __init__(self, corpus, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.docs = corpus
        self.N = len(corpus)
        self.doc_len = [len(d) for d in corpus]
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        self.tf = []
        df = {}
        for d in corpus:
            freq = {}
            for t in d:
                freq[t] = freq.get(t, 0) + 1
            self.tf.append(freq)
            for t in freq:
                df[t] = df.get(t, 0) + 1
        # Smoothed idf; the +1 inside log keeps it non-negative for common terms.
        self.idf = {
            t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }

    def score(self, query_tokens, i):
        if not self.avgdl:
            return 0.0
        freq, dl, s = self.tf[i], self.doc_len[i], 0.0
        for t in query_tokens:
            f = freq.get(t)
            if not f:
                continue
            s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (
                f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            )
        return s

    def rank(self, query_tokens, top=5):
        scored = [(self.score(query_tokens, i), i) for i in range(self.N)]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [(i, sc) for sc, i in scored[:top] if sc > 0]


def fuse_search(text, queries, top=5, chunk_chars=6000, overlap=800, rrf_k=60):
    """Multi-query BM25 with Reciprocal Rank Fusion (chunk + index built ONCE).

    BM25 is purely lexical, so one phrasing misses sections that say the same
    thing in other words ("bookings" vs "reconciliation of bookings to revenue").
    Run several query variants and fuse: each variant ranks the chunks, and a
    chunk's fused score is sum(1 / (rrf_k + rank)) over the variants that
    surfaced it. Fusion is by RANK, not raw score — BM25 scores are not
    comparable across queries (idf changes with the terms), ranks always are.
    A section that any single variant ranks highly therefore still surfaces,
    which is the recall win; a section several variants agree on outranks it.

    Returns result dicts shaped like search_text() plus `rrf` (fused score) and
    `queries` (which variants hit the chunk). `score` is the chunk's best BM25
    across variants, kept for display only — order is decided by `rrf`.
    """
    chunks = chunk_text(text, chunk_chars=chunk_chars, overlap=overlap)
    if not chunks:
        return []
    bm = BM25([tokenize(c["text"]) for c in chunks])
    fused = {}  # chunk idx -> accumulator
    for q in queries:
        qt = tokenize(q)
        for rank, (i, score) in enumerate(bm.rank(qt, top=top), 1):
            e = fused.setdefault(i, {"rrf": 0.0, "best": 0.0, "queries": [], "qtok": set()})
            e["rrf"] += 1.0 / (rrf_k + rank)
            e["best"] = max(e["best"], score)
            e["queries"].append(q)
            e["qtok"].update(qt)
    ranked = sorted(fused.items(), key=lambda kv: (-kv[1]["rrf"], kv[0]))[:top]
    results = []
    for rank, (i, e) in enumerate(ranked, 1):
        c = chunks[i]
        results.append({
            "rank": rank,
            "score": round(e["best"], 4),
            "rrf": round(e["rrf"], 4),
            "queries": e["queries"],
            "item": c["item"],
            "start": c["start"],
            "end": c["end"],
            "snippet": _snippet(c["text"], sorted(e["qtok"])),
            "text": c["text"],
        })
    return results


def search_text(text, query, top=5, chunk_chars=6000, overlap=800):
    """Single-query convenience over fuse_search() — same result shape.

    With one query, RRF ordering is identical to plain BM25 ordering (1/(k+rank)
    is monotonic in rank), so this stays exactly backward-compatible.
    """
    return fuse_search(text, [query], top=top, chunk_chars=chunk_chars, overlap=overlap)


def _snippet(text, query_tokens, width=240):
    """A short window around the first query-term hit (for the ranked table)."""
    low = text.lower()
    pos = -1
    for t in query_tokens:
        p = low.find(t)
        if p != -1 and (pos == -1 or p < pos):
            pos = p
    if pos == -1:
        pos = 0
    a = max(0, pos - width // 3)
    return re.sub(r"\s+", " ", text[a:a + width]).strip()


# ---------------------------------------------------------------------------
# 4. Resolve the filing, run the search, write section files
# ---------------------------------------------------------------------------
def resolve_document_url(identifier=None, form="10-K", accession=None, url=None):
    """Return (url, meta) for the document to parse. meta describes the filing."""
    if url:
        return url, {"source": "url", "url": url}
    if not identifier:
        raise ValueError("Pass a ticker/CIK, or --url.")
    cik, title = edgar.resolve_cik(identifier)
    row = edgar.latest_filing(cik, form=form, accession=accession)
    if not row:
        raise ValueError(f"No {form} found for {title or identifier} (CIK {cik}).")
    durl = edgar.document_url(cik, row)
    if not durl:
        raise ValueError(f"Could not locate the primary document for {row['accession']}.")
    return durl, {
        "company": title, "cik": cik, "form": row["form"],
        "filed": row["filed"], "period": row["period"],
        "accession": row["accession"], "url": durl,
    }


def _slug(meta):
    return (meta.get("accession") or meta.get("url", "filing")).replace("-", "").split("/")[-1][:40]


def main(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("identifier", nargs="?", help="ticker or CIK (omit if using --url)")
    p.add_argument("--form", default="10-K", help="exact form to fetch (default 10-K)")
    p.add_argument("--accession", help="specific filing accession (else: latest of --form)")
    p.add_argument("--url", help="direct primary-document URL (skips resolution)")
    p.add_argument("--query", action="append",
                   help="what to search for; REPEAT the flag with rephrasings to boost "
                        "recall (results are rank-fused); omit to print the section map")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--chunk-chars", type=int, default=6000)
    p.add_argument("--overlap", type=int, default=800)
    p.add_argument("--out-dir", default="sec-output")
    a = p.parse_args(argv)

    url, meta = resolve_document_url(a.identifier, a.form, a.accession, a.url)
    print(f"# fetching {url}", file=sys.stderr)
    html = edgar.http_get(url)
    if not html:
        print("Fetch failed (see error above). Is SEC_EDGAR_UA reachable?", file=sys.stderr)
        if a.url:
            print("hint: a 404 here usually means a GUESSED filename — exhibit names are "
                  "arbitrary and never predictable. List the real URLs instead:\n"
                  "  python edgar.py exhibits <ticker> <form> --accession <acc>\n"
                  "Do NOT fall back to WebFetch (sec.gov 403s it).", file=sys.stderr)
        return 1
    text = html_to_text(html)
    out = os.path.join(a.out_dir, _slug(meta))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "filing.txt"), "w") as f:
        f.write(text)

    # No query -> emit the section map and stop.
    if not a.query:
        headers = section_headers(text)
        print(f"# {meta.get('company','')} {meta.get('form','')} — {len(text):,} chars, "
              f"{len(headers)} section headers")
        for pos, label in headers:
            print(f"  char {pos:>8}  {label}")
        print(f"\nFull text written to {out}/filing.txt")
        return 0

    queries = a.query
    results = fuse_search(text, queries, top=a.top,
                          chunk_chars=a.chunk_chars, overlap=a.overlap)
    if not results:
        print(f"No BM25 matches for {queries!r} in this filing.", file=sys.stderr)
        return 2

    # Write each top section to its own file for the Haiku sub-agents to read.
    written = []
    for r in results:
        fname = os.path.join(out, f"sec_{r['rank']:02d}.txt")
        header = (f"# {meta.get('company','')} {meta.get('form','')} "
                  f"({meta.get('filed','')}) — {r['item'] or 'section'}\n"
                  f"# source: {url}\n"
                  f"# chars {r['start']}-{r['end']}  rank {r['rank']}  rrf {r['rrf']}  "
                  f"bm25 {r['score']}\n"
                  f"# queries: {' | '.join(r['queries'])}\n\n")
        with open(fname, "w") as f:
            f.write(header + r["text"])
        r["file"] = fname
        written.append(r)

    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump({"filing": meta, "queries": queries,
                   "results": [{k: v for k, v in r.items() if k != "text"} for r in written]},
                  f, indent=2)

    print(f"# {meta.get('company','')} {meta.get('form','')} "
          f"({meta.get('filed','')})  {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}: "
          + " | ".join(repr(q) for q in queries))
    print(f"# top {len(written)} sections -> {out}/  (also results.json)\n")
    for r in written:
        hits = f"  ({len(r['queries'])}/{len(queries)} queries)" if len(queries) > 1 else ""
        print(f"  [{r['rank']}] rrf={r['rrf']:<7} bm25={r['score']:<8} "
              f"{r['item'] or 'section':<10} {r['file']}{hits}")
        print(f"      …{r['snippet']}…\n")
    print("Next: spawn one claude-haiku-4-5 sub-agent per sec_NN.txt to extract the "
          "answer (see SKILL.md → 'Step 2').", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
