"""Offline unit tests for the XBRL cover-page parser in edgar.py.

No network — these feed a hand-built dei instance fragment through the pure
parser (`parse_dei_instance`) and assert the things that bite in real filings:
the dei facts are extracted, xsi:nil facts are skipped, and dimensional contexts
(the registered-securities block) resolve to their member so a TradingSymbol can
be matched to the right security.

    pytest skills/sec-filings/tests -q
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

import edgar  # noqa: E402


# A minimal but real-shaped extracted instance (*_htm.xml) for an 8-K cover page:
# two contexts (base + a CommonStock-dimensioned one), a nil fact to skip, and a
# TradingSymbol scoped to the dimensional context.
SAMPLE_INSTANCE = """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2025"
      xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
      xmlns:us-gaap="http://fasb.org/us-gaap/2025"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <context id="c-1">
    <entity><identifier scheme="http://www.sec.gov/CIK">0000320193</identifier></entity>
    <period><startDate>2026-04-30</startDate><endDate>2026-04-30</endDate></period>
  </context>
  <context id="c-2">
    <entity>
      <identifier scheme="http://www.sec.gov/CIK">0000320193</identifier>
      <segment>
        <xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonStockMember</xbrldi:explicitMember>
      </segment>
    </entity>
    <period><startDate>2026-04-30</startDate><endDate>2026-04-30</endDate></period>
  </context>
  <dei:DocumentType contextRef="c-1">8-K</dei:DocumentType>
  <dei:EntityRegistrantName contextRef="c-1">Apple Inc.</dei:EntityRegistrantName>
  <dei:AmendmentFlag contextRef="c-1">false</dei:AmendmentFlag>
  <dei:EntityTaxIdentificationNumber contextRef="c-1" xsi:nil="true"/>
  <dei:TradingSymbol contextRef="c-2">AAPL</dei:TradingSymbol>
  <dei:SecurityExchangeName contextRef="c-2">NASDAQ</dei:SecurityExchangeName>
</xbrl>
"""


def _facts():
    return edgar.parse_dei_instance(SAMPLE_INSTANCE)


def test_extracts_dei_facts():
    by_tag = {f["tag"]: f["value"] for f in _facts()}
    assert by_tag["dei:DocumentType"] == "8-K"
    assert by_tag["dei:EntityRegistrantName"] == "Apple Inc."
    assert by_tag["dei:AmendmentFlag"] == "false"


def test_skips_nil_facts():
    tags = {f["tag"] for f in _facts()}
    assert "dei:EntityTaxIdentificationNumber" not in tags  # xsi:nil -> dropped, not ""


def test_resolves_dimensional_member():
    trading = next(f for f in _facts() if f["tag"] == "dei:TradingSymbol")
    assert trading["value"] == "AAPL"
    # member keeps its QName prefix (us-gaap: standard vs aapl: company-custom) —
    # this is how a TradingSymbol is matched to its registered security.
    assert trading["member"] == "us-gaap:CommonStockMember"
    assert trading["context"] == "2026-04-30"


def test_base_context_has_no_member():
    doctype = next(f for f in _facts() if f["tag"] == "dei:DocumentType")
    assert doctype["member"] == ""


def test_ignores_non_dei_namespaces():
    # No us-gaap *facts* exist in a cover page (us-gaap appears only as a context
    # dimension); the parser must return dei facts only.
    assert all(f["tag"].startswith("dei:") for f in _facts())
