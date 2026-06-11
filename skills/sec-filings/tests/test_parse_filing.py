"""Offline unit tests for the sec-filings parse pipeline.

No network, no API key — these exercise the pure functions that do the work:
iXBRL/HTML stripping, section-aware chunking, and BM25 ranking. They guard the
"it must always work" goal: the index+search step has no external dependency to
break.

    pytest skills/sec-filings/tests -q
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

import parse_filing as pf  # noqa: E402


# --- A tiny but realistic inline-XBRL fragment ------------------------------
SAMPLE_HTML = """
<html><head><title>10-K</title><style>.x{color:red}</style></head>
<body>
  <ix:header><ix:hidden><ix:nonNumeric>MACHINE_ONLY_FACT</ix:nonNumeric></ix:hidden></ix:header>
  <div style="display:none">DO_NOT_INDEX hidden xbrl noise</div>
  <p>Item 1. Business</p>
  <p>The Company designs and sells consumer hardware worldwide.</p>
  <p>Item 1A. Risk Factors</p>
  <p>Our operations depend on a concentrated <ix:nonFraction>supply chain</ix:nonFraction>
     in a single region; a disruption there would materially harm results.</p>
  <p>Item 7. Management's Discussion and Analysis</p>
  <p>Liquidity remained strong with substantial cash and marketable securities.</p>
  <script>var ignore = "scripts must never be indexed";</script>
</body></html>
"""


def test_html_to_text_keeps_prose_drops_plumbing():
    text = pf.html_to_text(SAMPLE_HTML)
    assert "designs and sells consumer hardware" in text
    assert "supply chain" in text                 # ix: inline tag unwrapped, text kept
    # iXBRL header, display:none subtree, <script> and <style> are all dropped:
    for noise in ("MACHINE_ONLY_FACT", "DO_NOT_INDEX", "scripts must never", "color:red"):
        assert noise not in text


def test_section_headers_detected_in_order():
    text = pf.html_to_text(SAMPLE_HTML)
    labels = [label for _, label in pf.section_headers(text)]
    assert labels == ["Item 1", "Item 1A", "Item 7"]


def test_chunking_covers_text_with_overlap():
    text = "abcdefghij" * 200  # 2000 chars
    chunks = pf.chunk_text(text, chunk_chars=500, overlap=100)
    assert len(chunks) > 1
    # Contiguous coverage: each chunk starts before the previous one ended (overlap).
    for prev, cur in zip(chunks, chunks[1:]):
        assert cur["start"] < prev["end"]
        assert cur["start"] == prev["start"] + (500 - 100)
    assert chunks[-1]["end"] == len(text)


def test_chunk_carries_nearest_section_label():
    text = pf.html_to_text(SAMPLE_HTML)
    # Small windows so each Item lands in its own chunk; the label is the
    # nearest preceding header.
    chunks = pf.chunk_text(text, chunk_chars=120, overlap=20)
    risk_chunks = [c for c in chunks if "concentrated" in c["text"]]
    assert risk_chunks and risk_chunks[0]["item"] == "Item 1A"


def test_bm25_ranks_the_relevant_section_first():
    text = pf.html_to_text(SAMPLE_HTML)
    results = pf.search_text(text, "supply chain concentration risk",
                             top=3, chunk_chars=120, overlap=20)
    assert results, "expected at least one BM25 hit"
    assert "supply chain" in results[0]["text"].lower()
    assert results[0]["item"] == "Item 1A"
    # A liquidity query should instead surface the MD&A section (Item 7). With a
    # tiny window the matching prose may straddle two overlapping chunks, so the
    # meaningful invariant is the winning *section*, not an exact substring.
    liq = pf.search_text(text, "liquidity cash marketable securities",
                         top=3, chunk_chars=120, overlap=20)
    assert liq and liq[0]["item"] == "Item 7"


def test_no_match_returns_empty():
    text = pf.html_to_text(SAMPLE_HTML)
    assert pf.search_text(text, "cryptocurrency staking derivatives") == []


def test_fuse_search_multi_query_improves_recall():
    text = pf.html_to_text(SAMPLE_HTML)
    # One phrasing only surfaces the risk section; the fused pair must surface
    # BOTH the risk section and the MD&A liquidity section in a single pass.
    single = pf.search_text(text, "supply chain concentration risk",
                            top=3, chunk_chars=120, overlap=20)
    assert all(r["item"] != "Item 7" for r in single)
    fused = pf.fuse_search(text,
                           ["supply chain concentration risk",
                            "liquidity cash marketable securities"],
                           top=4, chunk_chars=120, overlap=20)
    items = {r["item"] for r in fused}
    assert {"Item 1A", "Item 7"} <= items
    # Each result records which variants surfaced it.
    for r in fused:
        assert r["queries"] and r["rrf"] > 0


def test_fuse_search_single_query_matches_search_text_order():
    text = pf.html_to_text(SAMPLE_HTML)
    q = "liquidity cash marketable securities"
    a = [(r["start"], r["end"]) for r in pf.search_text(text, q, top=3, chunk_chars=120, overlap=20)]
    b = [(r["start"], r["end"]) for r in pf.fuse_search(text, [q], top=3, chunk_chars=120, overlap=20)]
    assert a == b


def test_tokenize_drops_single_chars_and_lowercases():
    assert pf.tokenize("A Supply-Chain, 2024!") == ["supply", "chain", "2024"]
