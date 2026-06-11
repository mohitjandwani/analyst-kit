"""Offline tests for the technical-analysis engine — synthetic bars, no network."""

import datetime
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import indicators as ti  # noqa: E402


# ---------------------------------------------------------------------------
# synthetic data
# ---------------------------------------------------------------------------

def make_bars(n, price_fn, vol_fn=lambda i, up: 1_000_000 + (200_000 if up else 0)):
    base = datetime.date(2023, 1, 2)
    bars, prev = [], price_fn(0)
    for i in range(n):
        c = price_fn(i)
        o = prev
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        bars.append({"date": (base + datetime.timedelta(days=i)).isoformat(),
                     "open": o, "high": h, "low": l, "close": c,
                     "volume": float(vol_fn(i, c >= o))})
        prev = c
    return bars


def trend_bars(n=420):
    # exponential drift: momentum keeps building, so MACD histogram rises
    return make_bars(n, lambda i: 100.0 * (1.003 ** i))


def range_bars(n=420):
    # fast oscillation (period ~16 bars) -> directional moves cancel, ADX stays low
    return make_bars(n, lambda i: 100.0 + 4.0 * math.sin(i / 2.5))


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def test_sma_known_values():
    out = ti.sma([1, 2, 3, 4, 5], 3)
    assert out == [None, None, 2.0, 3.0, 4.0]


def test_ema_seeds_with_sma_then_recurses():
    out = ti.ema([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None]
    assert out[2] == 2.0                      # seed = SMA(1,2,3)
    assert out[3] == pytest.approx(3.0)       # 4*0.5 + 2*0.5
    assert out[4] == pytest.approx(4.0)


def test_wilder_smoothing():
    out = ti.wilder([2, 2, 2, 10], 2)
    assert out[1] == 2.0
    assert out[2] == 2.0
    assert out[3] == pytest.approx((2.0 + 10) / 2)


def test_rsi_extremes_and_balance():
    up = list(range(1, 40))
    assert ti.rsi(up, 14)[-1] == 100.0
    # alternating equal gains/losses -> RSI oscillates tightly around 50
    alt = [100 + (1 if i % 2 else 0) for i in range(40)]
    assert ti.rsi(alt, 14)[-1] == pytest.approx(50.0, abs=5)


def test_atr_on_constant_range_bars():
    bars = make_bars(40, lambda i: 100.0)  # every bar: high-low = 1.0
    a = ti.atr([b["high"] for b in bars], [b["low"] for b in bars],
               [b["close"] for b in bars], 14)
    assert a[-1] == pytest.approx(1.0)


def test_macd_is_ema_diff_and_hist_is_line_minus_signal():
    closes = [100 + 0.5 * i for i in range(80)]
    line, signal, hist = ti.macd(closes)
    e12, e26 = ti.ema(closes, 12), ti.ema(closes, 26)
    assert line[-1] == pytest.approx(e12[-1] - e26[-1])
    assert hist[-1] == pytest.approx(line[-1] - signal[-1])


def test_bollinger_collapses_on_constant_series():
    closes = [50.0] * 30
    mid, up, lo, width, pctb = ti.bollinger(closes)
    assert up[-1] == lo[-1] == mid[-1] == 50.0
    assert width[-1] == 0.0
    assert pctb[-1] is None  # band has zero height -> undefined


def test_donchian_excludes_current_bar():
    highs = [10.0] * 25 + [20.0]
    lows = [5.0] * 26
    hi, lo = ti.donchian(highs, lows, 20)
    assert hi[-1] == 10.0  # today's new high not in its own channel
    assert lo[-1] == 5.0


def test_adx_directional_in_uptrend():
    bars = trend_bars(200)
    a, pdi, mdi = ti.adx([b["high"] for b in bars], [b["low"] for b in bars],
                         [b["close"] for b in bars])
    assert a[-1] is not None and 0 <= a[-1] <= 100
    assert pdi[-1] > mdi[-1]


def test_supertrend_long_in_uptrend_and_below_price():
    bars = trend_bars(120)
    line, direction = ti.supertrend([b["high"] for b in bars],
                                    [b["low"] for b in bars],
                                    [b["close"] for b in bars])
    assert direction[-1] == 1
    assert line[-1] < bars[-1]["close"]


def test_obv_accumulates_with_rises():
    assert ti.obv([1, 2, 1, 3], [10, 10, 10, 10]) == [0, 10, 0, 10]


# ---------------------------------------------------------------------------
# loading / resampling
# ---------------------------------------------------------------------------

def test_load_bars_unwraps_fmp_and_adjusts(tmp_path):
    p = tmp_path / "prices.json"
    p.write_text(json.dumps({"symbol": "TEST", "historical": [
        {"date": "2024-01-03", "open": 100, "high": 110, "low": 90,
         "close": 100, "adjClose": 50, "volume": 7},
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9,
         "close": 10, "adjClose": 10, "volume": 5},
    ]}))
    bars = ti.load_bars(str(p))
    assert [b["date"] for b in bars] == ["2024-01-02", "2024-01-03"]  # sorted
    assert bars[1]["close"] == 50.0       # adjClose wins
    assert bars[1]["open"] == 50.0        # OHLC scaled by adj factor 0.5
    assert bars[1]["high"] == 55.0


def test_weekly_resample_aggregates_ohlcv():
    # Mon 2024-01-01 .. Wed 2024-01-10 spans two ISO weeks
    bars = [{"date": (datetime.date(2024, 1, 1) + datetime.timedelta(days=i)).isoformat(),
             "open": 10.0 + i, "high": 20.0 + i, "low": 5.0 + i,
             "close": 15.0 + i, "volume": 100.0} for i in range(10)]
    weekly = ti.resample(bars, "weekly")
    assert len(weekly) == 2
    w1 = weekly[0]
    assert w1["open"] == 10.0 and w1["close"] == 15.0 + 6  # Mon open, Sun close
    assert w1["high"] == 20.0 + 6 and w1["low"] == 5.0
    assert w1["volume"] == 700.0


# ---------------------------------------------------------------------------
# regime / scorecard / levels / contracts
# ---------------------------------------------------------------------------

def test_uptrend_classified_and_long_biased():
    analysis, dash, lvl = ti.analyze(trend_bars(), "daily", "UP", "$", 1.0, 100_000)
    assert analysis["regime"]["label"] == "trending-up"
    assert analysis["scorecard"]["score"] >= 2
    assert analysis["bias"] == "long"
    assert analysis["regime_higher_tf"]["timeframe"] == "weekly"


def test_range_not_called_a_trend():
    analysis, _, _ = ti.analyze(range_bars(), "daily", "RNG", "$", 1.0, None)
    assert analysis["regime"]["label"] in ("range", "transitional")
    assert analysis["regime"]["adx14"] < 25


def test_levels_and_sizing_math():
    analysis, _, _ = ti.analyze(trend_bars(), "daily", "UP", "$", 1.0, 100_000)
    plan = analysis["levels"]["long"]
    c = plan["entry_ref"]
    assert plan["suggested_stop"] < c
    dist = c - plan["suggested_stop"]
    assert plan["targets"]["r2"] == pytest.approx(c + 2 * dist, rel=1e-3)
    s = plan["sizing"]
    assert s["risk_amount"] == 1000.0
    # sizing property: never risks more than the budget, and is maximal within it
    assert s["shares"] * s["stop_distance"] <= s["risk_amount"] + 0.5
    assert (s["shares"] + 1) * s["stop_distance"] > s["risk_amount"] - 0.5


def test_dashboard_contract_is_valid_for_charting():
    _, dash, lvl = ti.analyze(trend_bars(), "daily", "UP", "$", 1.0, None)
    axis_ids = {a["id"] for a in dash["yAxes"]}
    assert all(s["yAxis"] in axis_ids for s in dash["series"])
    assert dash["meta"]["stock"] is True
    kinds = {s["name"]: s["kind"] for s in dash["series"]}
    assert kinds["Price"] == "candlestick"
    assert kinds["Bollinger (20,2)"] == "arearange"
    candle = next(s for s in dash["series"] if s["kind"] == "candlestick")
    assert len(candle["data"][0]) == 5            # [ts, o, h, l, c]
    band = next(s for s in dash["series"] if s["kind"] == "arearange")
    assert len(band["data"][-1]) == 3             # [ts, lo, up]
    # panes: every yAxis carries top/height except none
    assert all("top" in a["opts"] and "height" in a["opts"] for a in dash["yAxes"])
    # levels chart draws the plan as plotLines
    assert len(lvl["yAxes"][0]["opts"]["plotLines"]) >= 2


def test_weekly_timeframe_end_to_end():
    analysis, dash, _ = ti.analyze(trend_bars(1500), "weekly", "UP", "$", 1.0, None)
    assert analysis["meta"]["timeframe"] == "weekly"
    assert analysis["regime"]["label"] == "trending-up"
    assert "SMA40" in analysis["regime"]["close_vs_long_ma"]
    assert analysis["regime_higher_tf"]["timeframe"] == "monthly"


def test_short_history_warns_but_runs():
    analysis, _, _ = ti.analyze(trend_bars(120), "daily", "X", "$", 1.0, None)
    assert any("bars" in w for w in analysis["meta"]["warnings"])


def test_cli_writes_all_outputs(tmp_path):
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(trend_bars(300)))
    out = tmp_path / "out"
    ti.main([str(prices), "--out-dir", str(out), "--symbol", "TST"])
    for f in ("analysis.json", "dashboard-contract.json", "levels-contract.json"):
        assert (out / f).exists()
    analysis = json.loads((out / "analysis.json").read_text())
    assert analysis["meta"]["symbol"] == "TST"
    assert analysis["tables"]["levels"]["rows"]  # pre-formatted for reporting
