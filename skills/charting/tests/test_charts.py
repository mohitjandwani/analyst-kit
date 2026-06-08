"""Builder tests — assert the chart contract each builder emits (see SKILL.md)."""
import json
import math

from pipeline import charts, cli, process


def test_revenue_margins_contract(aapl_income):
    out = charts.revenue_margins(aapl_income, n=5)
    assert out["axis"]["type"] == "category" and len(out["axis"]["categories"]) == 5
    assert [a["id"] for a in out["yAxes"]] == ["money", "pct"]
    assert out["yAxes"][1]["percent"] and out["yAxes"][1]["opposite"]
    names = [s["name"] for s in out["series"]]
    assert names == ["Revenue", "Net income", "Net margin"]
    # Margin line computed correctly from the same revenue/net income.
    row = sorted(aapl_income, key=lambda r: r["date"])[-1]
    assert math.isclose(out["series"][2]["data"][-1],
                        round(row["netIncome"] / row["revenue"] * 100, 2), abs_tol=0.01)


def test_revenue_yoy_percent_axis_leading_gap(aapl_income):
    out = charts.revenue_yoy(aapl_income, n=12, lag=1)
    assert out["yAxes"][0]["percent"] is True
    assert out["series"][0]["data"][0] is None


def test_revenue_trend_carries_flags(aapl_income):
    out = charts.revenue_trend(aapl_income, flags=[{"x": "FY2024", "title": "Event"}])
    assert out["flags"] == [{"x": "FY2024", "title": "Event"}]
    assert out["series"][0]["kind"] == "line"


def test_line_shift_offsets_and_labels(aapl_income):
    # shift +2 → two leading None gaps and a labelled series name.
    out = charts._line(["a", "b", "c", "d", "e"],
                       [{"name": "PMI", "values": [10, 20, 30, 40, 50], "role": "primary", "shift": 2}],
                       percent=True, currency="", title="t", subtitle="", value_label="v")
    assert out["series"][0]["data"][:2] == [None, None]
    assert out["series"][0]["data"][2:] == [10, 20, 30]
    assert out["series"][0]["name"] == "PMI (shift +2)"


def test_segments_variants(aapl_segmentation):
    stacked = charts.segments(aapl_segmentation, variant="stacked", n=5)
    assert stacked["meta"]["variant"] == "stacked"
    assert "unit" in stacked["yAxes"][0] and "percent" not in stacked["yAxes"][0]
    pct = charts.segments(aapl_segmentation, variant="percent", n=5)
    assert pct["yAxes"][0]["percent"] is True and pct["meta"]["variant"] == "percent"
    assert all(s["role"] == "segment" for s in stacked["series"])


def test_waterfall_contract_reconciles(aapl_income):
    row = sorted(aapl_income, key=lambda r: r["date"])[-1]
    out = charts.waterfall(row)
    data = out["series"][0]["data"]
    assert out["series"][0]["kind"] == "waterfall"
    assert data[-1]["isSum"] and data[2]["isIntermediateSum"]
    # Scaled deltas sum back to net income (in $B).
    divisor = 1e9
    total = sum(p["y"] for p in data if "y" in p)
    assert math.isclose(total, row["netIncome"] / divisor, abs_tol=0.01)
    # Cost deltas are negative + tagged.
    assert data[1]["y"] < 0 and data[1]["role"] == "negative"


def test_dividend_yield_dual_axis(aapl_dividends):
    out = charts.dividend_yield(aapl_dividends, n_years=5)
    assert [a["id"] for a in out["yAxes"]] == ["div", "yld"]
    assert out["yAxes"][1]["percent"] and out["yAxes"][1]["opposite"]
    assert out["series"][0]["kind"] == "column" and out["series"][0]["yAxis"] == "div"
    assert out["series"][1]["kind"] == "line" and out["series"][1]["yAxis"] == "yld"


def test_surprise_sign_roles(aapl_earnings):
    out = charts.surprise(aapl_earnings, metric="eps", n=8)
    assert out["yAxes"][0]["percent"] and out["meta"]["zeroLine"]
    rows = sorted([e for e in aapl_earnings if e["epsActual"] is not None],
                  key=lambda x: x["date"])[-8:]
    for point, e in zip(out["series"][0]["data"], rows):
        expected = round((e["epsActual"] - e["epsEstimated"]) / abs(e["epsEstimated"]) * 100, 2)
        assert point["y"] == expected
        assert point["role"] == ("positive" if expected >= 0 else "negative")


def test_estimate_vs_reported_roles_scaled(aapl_earnings):
    out = charts.estimate_vs_reported(aapl_earnings, metric="revenue", n=8)
    assert [s["role"] for s in out["series"]] == ["estimate", "primary"]
    assert out["yAxes"][0]["unit"] == "B"  # revenue scaled to $B
    assert out["meta"]["variant"] == "grouped"


def test_price_candlestick_and_line(aapl_price):
    cs = charts.price(aapl_price, primary=True,
                      flags=[{"date": "2025-05-02", "title": "Q2"}])
    assert cs["axis"]["type"] == "datetime" and cs["meta"]["stock"]
    assert cs["series"][0]["kind"] == "candlestick"
    assert len(cs["series"][0]["data"][0]) == 5  # [ts, o, h, l, c]
    assert cs["flags"][0]["x"] == 1746144000000  # 2025-05-02 UTC ms
    ln = charts.price(aapl_price, primary=False)
    assert ln["series"][0]["kind"] == "line"
    assert len(ln["series"][0]["data"][0]) == 2  # [ts, close]


def test_price_with_revenue_maps_fiscal_to_datetime(aapl_price, aapl_income_q):
    out = charts.price_with_revenue(aapl_price, aapl_income_q)
    assert out["axis"]["type"] == "datetime" and out["meta"]["stock"]
    assert [s["kind"] for s in out["series"]] == ["candlestick", "column"]
    # revenue (left) + price (right, opposite, 2dp)
    assert [a["id"] for a in out["yAxes"]] == ["rev", "price"]
    assert out["yAxes"][1]["opposite"] and out["yAxes"][1]["decimals"] == 2
    # fiscal revenue columns are placed (and sized) inside the price window
    pmin = min(process.to_millis(r["date"]) for r in aapl_price)
    pmax = max(process.to_millis(r["date"]) for r in aapl_price)
    rev = out["series"][1]
    assert rev["opts"]["pointRange"] > 0 and rev["opts"]["opacity"] == 0.5
    assert all(pmin <= ts <= pmax for ts, _ in rev["data"])
    assert len(out["series"][0]["data"][0]) == 5  # candlestick [ts,o,h,l,c]


def test_price_with_revenue_reaction_uses_earnings_date(aapl_price, aapl_income_q):
    out = charts.price_with_revenue(aapl_price, aapl_income_q, mode="reaction")
    rev = out["series"][1]
    assert rev["kind"] == "line" and rev["opts"]["lineWidth"] == 0  # markers only
    assert rev["opts"]["marker"]["enabled"]
    # each marker sits on a real earnings/filing date (not the period end)
    filing_ms = {process.to_millis(r["filingDate"]) for r in aapl_income_q if r.get("filingDate")}
    assert rev["data"] and all(ts in filing_ms for ts, _ in rev["data"])


def test_price_with_revenue_growth_is_percent_line(aapl_price, aapl_income_q):
    out = charts.price_with_revenue(aapl_price, aapl_income_q, mode="growth")
    assert out["yAxes"][0]["percent"] is True
    g = out["series"][1]
    assert g["kind"] == "line" and g["opts"]["marker"]["radius"] >= 4  # prominent dots
    assert out["meta"]["mode"] == "growth"


def test_compare_price_rebased_lines(aapl_price, msft_price):
    out = charts.compare_price_rebased([("AAPL", aapl_price), ("MSFT", msft_price)])
    assert out["axis"]["type"] == "datetime" and out["meta"]["stock"]
    assert [s["kind"] for s in out["series"]] == ["line", "line"]
    # each company's price rebased to 100 at the window start
    assert out["series"][0]["data"][0][1] == 100.0
    assert out["series"][1]["data"][0][1] == 100.0
    assert "percent" not in out["yAxes"][0]  # an index, not a percent


def test_compare_rebased_starts_at_100(aapl_income, msft_income):
    out = charts.compare_rebased([("AAPL", aapl_income), ("MSFT", msft_income)], n=5)
    assert len(out["series"]) == 2
    for s in out["series"]:
        assert s["data"][0] == 100.0
    assert "percent" not in out["yAxes"][0]  # it's an index, not a percent


def test_all_contracts_json_serializable():
    payloads = cli.build_contracts()
    assert len(payloads) >= 12
    for name, payload in payloads.items():
        round_tripped = json.loads(json.dumps(payload))  # no NaN/Inf, no non-JSON
        assert round_tripped["series"], name
        assert "type" in round_tripped["axis"], name
        assert round_tripped["title"], name
