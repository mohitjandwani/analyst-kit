#!/usr/bin/env python3
"""Technical-analysis engine: OHLCV JSON -> indicators, regime, scorecard, levels,
and chart contracts for the charting skill.

Pure Python (no third-party deps) so the skill runs anywhere a python3 exists.

Usage:
  python3 scripts/indicators.py prices.json --out-dir out/ \
      [--timeframe daily|weekly] [--symbol AAPL] [--currency $] \
      [--risk-pct 1.0] [--capital 100000] [--no-adjust]

Input: a JSON array of bars [{date, open, high, low, close, volume}, ...]
(any order), or an FMP-style wrapper {symbol, historical: [...]} — auto-detected.
If bars carry adjClose, OHLC are proportionally adjusted unless --no-adjust.

Outputs (in --out-dir):
  analysis.json             regime, scorecard, signals, entry/exit levels, snapshot
  dashboard-contract.json   4-pane chart contract: price+overlays / volume / MACD / RSI
  levels-contract.json      close + supertrend with entry/stop/target plotLines
"""

import argparse
import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# series primitives (all return lists aligned to input, None during warmup)
# ---------------------------------------------------------------------------

def sma(vals, n):
    out = [None] * len(vals)
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= n:
            acc -= vals[i - n]
        if i >= n - 1:
            out[i] = acc / n
    return out


def ema(vals, n, start=0):
    """EMA seeded with the SMA of the first n values from `start`."""
    out = [None] * len(vals)
    if len(vals) - start < n:
        return out
    seed = sum(vals[start:start + n]) / n
    out[start + n - 1] = seed
    k = 2.0 / (n + 1)
    for i in range(start + n, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


def wilder(vals, n, start=0):
    """Wilder smoothing (RSI/ATR convention): seed = mean of first n, then
    (prev*(n-1) + v) / n."""
    out = [None] * len(vals)
    if len(vals) - start < n:
        return out
    seed = sum(vals[start:start + n]) / n
    out[start + n - 1] = seed
    for i in range(start + n, len(vals)):
        out[i] = (out[i - 1] * (n - 1) + vals[i]) / n
    return out


def rolling_max(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        out[i] = max(vals[i - n + 1:i + 1])
    return out


def rolling_min(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        out[i] = min(vals[i - n + 1:i + 1])
    return out


def rolling_std(vals, n):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        w = vals[i - n + 1:i + 1]
        m = sum(w) / n
        out[i] = math.sqrt(sum((x - m) ** 2 for x in w) / n)
    return out


# ---------------------------------------------------------------------------
# indicators
# ---------------------------------------------------------------------------

def rsi(closes, n):
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = wilder(gains[1:], n)
    al = wilder(losses[1:], n)
    out = [None] * len(closes)
    for i in range(len(ag)):
        if ag[i] is None:
            continue
        if al[i] == 0:
            out[i + 1] = 100.0 if ag[i] > 0 else 50.0
        else:
            out[i + 1] = 100.0 - 100.0 / (1.0 + ag[i] / al[i])
    return out


def true_range(highs, lows, closes):
    tr = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr.append(max(highs[i] - lows[i],
                      abs(highs[i] - closes[i - 1]),
                      abs(lows[i] - closes[i - 1])))
    return tr


def atr(highs, lows, closes, n=14):
    return wilder(true_range(highs, lows, closes), n)


def macd(closes, fast=12, slow=26, sig=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [None if (a is None or b is None) else a - b for a, b in zip(ef, es)]
    first = next((i for i, v in enumerate(line) if v is not None), None)
    signal = [None] * len(closes)
    if first is not None:
        vals = line[first:]
        sig_part = ema(vals, sig)
        for i, v in enumerate(sig_part):
            signal[first + i] = v
    hist = [None if (a is None or b is None) else a - b for a, b in zip(line, signal)]
    return line, signal, hist


def bollinger(closes, n=20, k=2.0):
    mid = sma(closes, n)
    sd = rolling_std(closes, n)
    upper = [None if m is None else m + k * s for m, s in zip(mid, sd)]
    lower = [None if m is None else m - k * s for m, s in zip(mid, sd)]
    width = [None if (u is None or m in (None, 0)) else (u - l) / m
             for u, l, m in zip(upper, lower, mid)]
    pctb = [None if (u is None or u == l) else (c - l) / (u - l)
            for c, u, l in zip(closes, upper, lower)]
    return mid, upper, lower, width, pctb


def donchian(highs, lows, n=20):
    """Prior-window channel (excludes the current bar) so a close above
    `hi` is a genuine Turtle-style breakout, with no lookahead."""
    hi = [None] * len(highs)
    lo = [None] * len(lows)
    for i in range(n, len(highs)):
        hi[i] = max(highs[i - n:i])
        lo[i] = min(lows[i - n:i])
    return hi, lo


def adx(highs, lows, closes, n=14):
    m = len(closes)
    plus_dm, minus_dm = [0.0], [0.0]
    for i in range(1, m):
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
    tr = true_range(highs, lows, closes)
    sp = wilder(plus_dm[1:], n)
    sm = wilder(minus_dm[1:], n)
    st = wilder(tr[1:], n)
    pdi = [None] * m
    mdi = [None] * m
    dx = []
    for i in range(len(sp)):
        if sp[i] is None or st[i] in (None, 0):
            dx.append(None)
            continue
        p = 100.0 * sp[i] / st[i]
        q = 100.0 * sm[i] / st[i]
        pdi[i + 1], mdi[i + 1] = p, q
        dx.append(100.0 * abs(p - q) / (p + q) if (p + q) > 0 else 0.0)
    first = next((i for i, v in enumerate(dx) if v is not None), None)
    out = [None] * m
    if first is not None and len(dx) - first >= n:
        w = wilder(dx[first:], n)
        for i, v in enumerate(w):
            out[first + i + 1] = v
    return out, pdi, mdi


def obv(closes, volumes):
    out = [0.0]
    for i in range(1, len(closes)):
        v = volumes[i] or 0
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + v)
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - v)
        else:
            out.append(out[-1])
    return out


def supertrend(highs, lows, closes, n=10, mult=3.0):
    """Returns (line, direction) — direction +1 long / -1 short."""
    a = atr(highs, lows, closes, n)
    m = len(closes)
    line = [None] * m
    direction = [None] * m
    fu = [None] * m  # final upper band
    fl = [None] * m  # final lower band
    for i in range(m):
        if a[i] is None:
            continue
        hl2 = (highs[i] + lows[i]) / 2.0
        bu = hl2 + mult * a[i]
        bl = hl2 - mult * a[i]
        pu, pl = fu[i - 1] if i else None, fl[i - 1] if i else None
        fu[i] = bu if (pu is None or bu < pu or closes[i - 1] > pu) else pu
        fl[i] = bl if (pl is None or bl > pl or closes[i - 1] < pl) else pl
        prev_dir = direction[i - 1] if i and direction[i - 1] is not None else 1
        if prev_dir == 1:
            direction[i] = -1 if closes[i] < fl[i] else 1
        else:
            direction[i] = 1 if closes[i] > fu[i] else -1
        line[i] = fl[i] if direction[i] == 1 else fu[i]
    return line, direction


def chandelier(highs, lows, closes, atr_vals, n=22, mult=3.0):
    """Long/short trailing exits: highest close - k*ATR / lowest close + k*ATR."""
    hi_close = rolling_max(closes, n)
    lo_close = rolling_min(closes, n)
    long_exit = [None if (h is None or a is None) else h - mult * a
                 for h, a in zip(hi_close, atr_vals)]
    short_exit = [None if (l is None or a is None) else l + mult * a
                  for l, a in zip(lo_close, atr_vals)]
    return long_exit, short_exit


def last_pivot(vals, span=2, kind="low"):
    """Most recent confirmed fractal pivot (needs `span` bars on each side)."""
    cmp = (lambda a, b: a <= b) if kind == "low" else (lambda a, b: a >= b)
    for i in range(len(vals) - span - 1, span - 1, -1):
        window = vals[i - span:i] + vals[i + 1:i + span + 1]
        if all(cmp(vals[i], w) for w in window):
            return vals[i]
    return None


# ---------------------------------------------------------------------------
# data loading / resampling
# ---------------------------------------------------------------------------

def load_bars(path, adjust=True):
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        raw = raw.get("historical") or raw.get("data") or []
    bars = []
    for r in raw:
        if r.get("close") is None or r.get("date") is None:
            continue
        o, h, l, c = (float(r.get(k, r["close"]) or r["close"])
                      for k in ("open", "high", "low", "close"))
        adj = r.get("adjClose")
        if adjust and adj is not None and c:
            f_ = float(adj) / c
            o, h, l, c = o * f_, h * f_, l * f_, float(adj)
        bars.append({"date": str(r["date"])[:10], "open": o, "high": h,
                     "low": l, "close": c,
                     "volume": float(r.get("volume") or 0)})
    seen = {}
    for b in bars:
        seen[b["date"]] = b  # last wins on duplicate dates
    return sorted(seen.values(), key=lambda b: b["date"])


def _ymd(date_str):
    y, m, d = (int(x) for x in date_str.split("-"))
    return y, m, d


def _iso_week(date_str):
    import datetime
    y, m, d = _ymd(date_str)
    iso = datetime.date(y, m, d).isocalendar()
    return iso[0], iso[1]


def resample(bars, timeframe):
    """daily bars -> weekly (ISO week) or monthly. Bar date = last trading day."""
    if timeframe == "daily":
        return bars
    key = _iso_week if timeframe == "weekly" else (lambda d: _ymd(d)[:2])
    out, cur, cur_key = [], None, None
    for b in bars:
        k = key(b["date"])
        if k != cur_key:
            if cur:
                out.append(cur)
            cur = dict(b)
            cur_key = k
        else:
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]
            cur["volume"] += b["volume"]
            cur["date"] = b["date"]
    if cur:
        out.append(cur)
    return out


def to_millis(date_str):
    import datetime
    y, m, d = _ymd(date_str)
    return int(datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc).timestamp() * 1000)


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

# layer-1 long-term MA per timeframe (40w SMA = 200d; 10m SMA = ~200d)
LONG_MA = {"daily": 200, "weekly": 40, "monthly": 10}


def compute(bars, timeframe):
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    vols = [b["volume"] for b in bars]
    n_long = LONG_MA[timeframe]

    ind = {"close": closes, "high": highs, "low": lows, "volume": vols}
    ind["sma20"] = sma(closes, 20)
    ind["sma50"] = sma(closes, 50)
    ind["sma_long"] = sma(closes, n_long)
    ind["ema20"] = ema(closes, 20)
    ind["rsi14"] = rsi(closes, 14)
    ind["rsi2"] = rsi(closes, 2)
    ind["macd"], ind["macd_signal"], ind["macd_hist"] = macd(closes)
    (ind["bb_mid"], ind["bb_up"], ind["bb_lo"],
     ind["bb_width"], ind["bb_pctb"]) = bollinger(closes)
    ind["atr14"] = atr(highs, lows, closes, 14)
    ind["adx14"], ind["pdi"], ind["mdi"] = adx(highs, lows, closes, 14)
    ind["don_hi"], ind["don_lo"] = donchian(highs, lows, 20)
    ind["obv"] = obv(closes, vols)
    ind["vol_sma20"] = sma(vols, 20)
    ind["st_line"], ind["st_dir"] = supertrend(highs, lows, closes)
    ind["ch_long"], ind["ch_short"] = chandelier(highs, lows, closes, ind["atr14"])
    ind["n_long"] = n_long
    return ind


def classify_regime(ind, timeframe):
    i = len(ind["close"]) - 1
    c, a = ind["close"][i], ind["adx14"][i]
    ml = ind["sma_long"][i]
    widths = [w for w in ind["bb_width"][-120:] if w is not None]
    w = ind["bb_width"][i]
    squeeze = bool(widths and w is not None
                   and w <= sorted(widths)[max(0, len(widths) // 10 - 1)])
    slope = None
    if ml is not None and len(ind["close"]) > 20 and ind["sma_long"][i - 20] is not None:
        slope = "up" if ml > ind["sma_long"][i - 20] else "down"
    if a is None or ml is None:
        label = "unknown (not enough history)"
    elif a >= 25:
        label = "trending-up" if c > ml else "trending-down"
    elif a < 20:
        label = "range"
    else:
        label = "transitional"
    return {
        "timeframe": timeframe,
        "label": label,
        "adx14": round(a, 1) if a is not None else None,
        "close_vs_long_ma": (None if ml is None else
                             f"{(c / ml - 1) * 100:+.1f}% vs SMA{ind['n_long']}"),
        "long_ma_slope": slope,
        "bb_squeeze": squeeze,
        "plus_di": round(ind["pdi"][i], 1) if ind["pdi"][i] is not None else None,
        "minus_di": round(ind["mdi"][i], 1) if ind["mdi"][i] is not None else None,
    }


def _vote(cond_pos, cond_neg):
    if cond_pos:
        return 1
    if cond_neg:
        return -1
    return 0


def scorecard(ind):
    i = len(ind["close"]) - 1
    c, ml = ind["close"][i], ind["sma_long"][i]
    h = ind["macd_hist"]
    r = ind["rsi14"][i]
    checks = {}
    checks["close_vs_long_ma"] = 0 if ml is None else _vote(c > ml, c < ml)
    if h[i] is not None and i >= 2 and h[i - 2] is not None:
        checks["macd_hist"] = _vote(h[i] > h[i - 1] > h[i - 2],
                                    h[i] < h[i - 1] < h[i - 2])
    else:
        checks["macd_hist"] = 0
    checks["rsi14_vs_50"] = 0 if r is None else _vote(r > 50, r < 50)
    up_v, dn_v = [], []
    for j in range(max(1, i - 19), i + 1):
        (up_v if ind["close"][j] >= ind["close"][j - 1] else dn_v).append(ind["volume"][j])
    if up_v and dn_v and (sum(up_v) or sum(dn_v)):
        mu, md = sum(up_v) / len(up_v), sum(dn_v) / len(dn_v)
        checks["volume_bias"] = _vote(mu > md * 1.1, md > mu * 1.1)
    else:
        checks["volume_bias"] = 0
    score = sum(checks.values())
    return {"checks": checks, "score": score,
            "verdict": ("long bias — tradeable" if score >= 2 else
                        "short bias — tradeable" if score <= -2 else
                        "no edge — stand aside")}


def detect_signals(ind, lookback=3):
    i = len(ind["close"]) - 1
    c = ind["close"]
    sig = []

    def recent(fn, name, direction):
        for j in range(i, max(i - lookback, 0), -1):
            if fn(j):
                sig.append({"signal": name, "direction": direction,
                            "bars_ago": i - j, "date": None, "idx": j})
                return

    recent(lambda j: ind["don_hi"][j] is not None and c[j] > ind["don_hi"][j],
           "donchian-20 breakout", "long")
    recent(lambda j: ind["don_lo"][j] is not None and c[j] < ind["don_lo"][j],
           "donchian-20 breakdown", "short")
    recent(lambda j: (ind["rsi2"][j] is not None and ind["sma_long"][j] is not None
                      and ind["rsi2"][j] < 10 and c[j] > ind["sma_long"][j]),
           "RSI(2) dip above long MA (Connors)", "long")
    recent(lambda j: (j > 0 and ind["st_dir"][j] is not None
                      and ind["st_dir"][j - 1] is not None
                      and ind["st_dir"][j] != ind["st_dir"][j - 1]),
           "supertrend flip", "long" if ind["st_dir"][i] == 1 else "short")
    recent(lambda j: (j > 0 and None not in (ind["macd"][j], ind["macd_signal"][j],
                                             ind["macd"][j - 1], ind["macd_signal"][j - 1])
                      and (ind["macd"][j] - ind["macd_signal"][j])
                      * (ind["macd"][j - 1] - ind["macd_signal"][j - 1]) < 0),
           "MACD signal cross",
           "long" if (ind["macd"][i] or 0) > (ind["macd_signal"][i] or 0) else "short")
    recent(lambda j: (j > 0 and None not in (ind["sma50"][j], ind["sma_long"][j],
                                             ind["sma50"][j - 1], ind["sma_long"][j - 1])
                      and (ind["sma50"][j] - ind["sma_long"][j])
                      * (ind["sma50"][j - 1] - ind["sma_long"][j - 1]) < 0),
           "50/long-MA cross",
           "long" if (ind["sma50"][i] or 0) > (ind["sma_long"][i] or 0) else "short")
    recent(lambda j: (j > 0 and ind["bb_lo"][j] is not None and ind["bb_lo"][j - 1] is not None
                      and c[j - 1] < ind["bb_lo"][j - 1] and c[j] > ind["bb_lo"][j]),
           "Bollinger lower-band re-entry", "long")
    recent(lambda j: (j > 0 and ind["bb_up"][j] is not None and ind["bb_up"][j - 1] is not None
                      and c[j - 1] > ind["bb_up"][j - 1] and c[j] < ind["bb_up"][j]),
           "Bollinger upper-band re-entry", "short")
    r = ind["rsi14"][i]
    if r is not None and r >= 70:
        sig.append({"signal": "RSI(14) overbought (>70) — trend strength in an uptrend, "
                              "fade only in a range", "direction": "context",
                    "bars_ago": 0, "idx": i})
    if r is not None and r <= 30:
        sig.append({"signal": "RSI(14) oversold (<30) — trend strength in a downtrend, "
                              "buy only in a range/above long MA", "direction": "context",
                    "bars_ago": 0, "idx": i})
    return sig


def build_levels(ind, bars, risk_pct, capital):
    i = len(ind["close"]) - 1
    c = ind["close"][i]
    a = ind["atr14"][i]
    swing_lo = last_pivot(ind["low"], kind="low")
    swing_hi = last_pivot(ind["high"], kind="high")

    def plan(side):
        sign = 1 if side == "long" else -1
        stops = {}
        if a is not None:
            stops["atr_2x"] = c - sign * 2 * a
            stops["atr_3x"] = c - sign * 3 * a
        structural = swing_lo if side == "long" else swing_hi
        if structural is not None and a is not None:
            # structural stop only if it isn't absurdly far (>3.5 ATR)
            if abs(c - structural) <= 3.5 * a:
                stops["structural_swing"] = structural
        if not stops:
            return None
        # prefer the structural stop, else 2.5x ATR
        suggested = stops.get("structural_swing",
                              c - sign * 2.5 * a if a is not None else None)
        dist = abs(c - suggested)
        targets = {"r2": c + sign * 2 * dist, "r3": c + sign * 3 * dist}
        if side == "long":
            if ind["bb_up"][i] is not None:
                targets["opposite_band"] = ind["bb_up"][i]
            if swing_hi is not None:
                targets["prior_swing"] = swing_hi
            trail = {"chandelier_3atr": ind["ch_long"][i],
                     "supertrend": ind["st_line"][i] if ind["st_dir"][i] == 1 else None}
        else:
            if ind["bb_lo"][i] is not None:
                targets["opposite_band"] = ind["bb_lo"][i]
            if swing_lo is not None:
                targets["prior_swing"] = swing_lo
            trail = {"chandelier_3atr": ind["ch_short"][i],
                     "supertrend": ind["st_line"][i] if ind["st_dir"][i] == -1 else None}
        sizing = None
        if capital and dist > 0:
            risk_amount = capital * risk_pct / 100.0
            shares = math.floor(risk_amount / dist)
            sizing = {"capital": capital, "risk_pct": risk_pct,
                      "risk_amount": round(risk_amount, 2),
                      "stop_distance": round(dist, 4), "shares": shares,
                      "notional": round(shares * c, 2),
                      "pct_of_capital": round(shares * c / capital * 100, 1)}
        rnd = lambda v: None if v is None else round(v, 4)
        return {"entry_ref": rnd(c),
                "stops": {k: rnd(v) for k, v in stops.items()},
                "suggested_stop": rnd(suggested),
                "stop_distance_atr": rnd(dist / a) if a else None,
                "targets": {k: rnd(v) for k, v in targets.items()},
                "trail": {k: rnd(v) for k, v in trail.items()},
                "sizing": sizing}

    return {"atr14": round(a, 4) if a is not None else None,
            "long": plan("long"), "short": plan("short"),
            "time_stop_hint": "mean-reversion entries: exit if not working in 5-10 bars"}


# ---------------------------------------------------------------------------
# chart contracts (the charting skill's input format)
# ---------------------------------------------------------------------------

def _pts(dates_ms, vals):
    return [[t, None if v is None else round(v, 4)] for t, v in zip(dates_ms, vals)]


def dashboard_contract(ind, bars, symbol, timeframe, currency, signals):
    ts = [to_millis(b["date"]) for b in bars]
    candles = [[t, round(b["open"], 4), round(b["high"], 4),
                round(b["low"], 4), round(b["close"], 4)]
               for t, b in zip(ts, bars)]
    band = [[t, None, None] if (l is None or u is None) else [t, round(l, 4), round(u, 4)]
            for t, l, u in zip(ts, ind["bb_lo"], ind["bb_up"])]
    n_long = ind["n_long"]
    flags = [{"x": ts[s["idx"]], "title": s["signal"].split(" (")[0]}
             for s in signals if s.get("direction") in ("long", "short")][:3]
    return {
        "title": f"{symbol} — technical dashboard ({timeframe})",
        "subtitle": f"{bars[0]['date']} – {bars[-1]['date']}",
        "axis": {"type": "datetime"},
        "yAxes": [
            # offset 0 anchors every pane's axis at the plot edge — without it
            # Highcharts stacks the four axes side-by-side and squeezes the plot
            {"id": "price", "name": "Price", "currency": currency, "decimals": 2,
             "opts": {"top": "0%", "height": "54%", "offset": 0}},
            {"id": "vol", "name": "Volume", "unit": "M",
             "opts": {"top": "56%", "height": "12%", "offset": 0}},
            {"id": "macd", "name": "MACD", "decimals": 2,
             "opts": {"top": "70%", "height": "14%", "offset": 0}},
            {"id": "rsi", "name": "RSI", "decimals": 0,
             "opts": {"top": "86%", "height": "14%", "offset": 0, "min": 0, "max": 100,
                      "plotBands": [{"from": 30, "to": 70,
                                     "color": "rgba(120,130,140,0.08)"}]}},
        ],
        "series": [
            {"name": "Price", "kind": "candlestick", "yAxis": "price",
             "role": "primary", "data": candles, "opts": {"zIndex": 5}},
            {"name": "Bollinger (20,2)", "kind": "arearange", "yAxis": "price",
             "role": "neutral", "data": band,
             "opts": {"fillOpacity": 0.08, "lineWidth": 0, "zIndex": 1,
                      "enableMouseTracking": False}},
            {"name": "EMA20", "kind": "line", "yAxis": "price", "role": "neutral",
             "data": _pts(ts, ind["ema20"]), "opts": {"lineWidth": 1, "zIndex": 3}},
            {"name": "SMA50", "kind": "line", "yAxis": "price", "role": "secondary",
             "data": _pts(ts, ind["sma50"]), "opts": {"lineWidth": 1.5, "zIndex": 3}},
            {"name": f"SMA{n_long}", "kind": "line", "yAxis": "price", "role": "total",
             "data": _pts(ts, ind["sma_long"]), "opts": {"lineWidth": 2, "zIndex": 3}},
            {"name": "Volume", "kind": "column", "yAxis": "vol", "role": "neutral",
             "data": _pts(ts, [v / 1e6 for v in ind["volume"]]),
             "opts": {"showInLegend": False}},
            {"name": "Vol SMA20", "kind": "line", "yAxis": "vol", "role": "secondary",
             "data": _pts(ts, [None if v is None else v / 1e6 for v in ind["vol_sma20"]]),
             "opts": {"lineWidth": 1, "showInLegend": False}},
            {"name": "MACD hist", "kind": "column", "yAxis": "macd", "role": "neutral",
             "data": _pts(ts, ind["macd_hist"]), "opts": {"showInLegend": False}},
            {"name": "MACD", "kind": "line", "yAxis": "macd", "role": "primary",
             "data": _pts(ts, ind["macd"]),
             "opts": {"lineWidth": 1, "showInLegend": False}},
            {"name": "Signal", "kind": "line", "yAxis": "macd", "role": "estimate",
             "data": _pts(ts, ind["macd_signal"]),
             "opts": {"lineWidth": 1, "showInLegend": False}},
            {"name": "RSI(14)", "kind": "line", "yAxis": "rsi", "role": "secondary",
             "data": _pts(ts, ind["rsi14"]),
             "opts": {"lineWidth": 1.5, "showInLegend": False}},
        ],
        "flags": flags or None,
        "meta": {"chart": "ta-dashboard", "stock": True, "symbol": symbol,
                 "currency": currency, "timeframe": timeframe},
    }


def levels_contract(ind, bars, symbol, timeframe, currency, levels, bias):
    ts = [to_millis(b["date"]) for b in bars]
    tail = max(0, len(bars) - 120)  # zoom to the recent window where levels matter
    ts_t = ts[tail:]
    plan = levels.get(bias) or levels.get("long")
    plot_lines = []
    if plan:
        def pl(value, color, dash, label):
            if value is not None:
                plot_lines.append({"value": value, "color": color, "dashStyle": dash,
                                   "width": 1.5, "zIndex": 4,
                                   "label": {"text": label, "align": "right",
                                             "style": {"fontSize": "10px"}}})
        pl(plan["entry_ref"], "#555f6b", "Solid", "entry ref")
        pl(plan["suggested_stop"], "#c0392b", "Dash", "stop")
        pl(plan["targets"].get("r2"), "#1e8449", "Dash", "target 2R")
        pl(plan["trail"].get("chandelier_3atr"), "#8395a7", "Dot", "chandelier trail")
    # plotLines don't extend the axis — widen it so stop/targets stay visible
    span = [v for v in ind["close"][tail:] if v is not None]
    span += [p["value"] for p in plot_lines]
    axis_opts = {"plotLines": plot_lines}
    if span:
        axis_opts["softMin"] = round(min(span) * 0.998, 4)
        axis_opts["softMax"] = round(max(span) * 1.002, 4)
    return {
        "title": f"{symbol} — entry/exit levels ({bias})",
        "subtitle": f"last {len(ts_t)} {timeframe} bars · stop/targets from ATR(14) "
                    f"and structure",
        "axis": {"type": "datetime"},
        "yAxes": [{"id": "price", "name": "Price", "currency": currency, "decimals": 2,
                   "opts": axis_opts}],
        "series": [
            {"name": "Close", "kind": "line", "yAxis": "price", "role": "primary",
             "data": _pts(ts_t, ind["close"][tail:]), "opts": {"zIndex": 3}},
            {"name": "Supertrend (10,3)", "kind": "line", "yAxis": "price",
             "role": "estimate", "data": _pts(ts_t, ind["st_line"][tail:]),
             "opts": {"lineWidth": 1}},
            {"name": "Donchian 20 hi", "kind": "line", "yAxis": "price",
             "role": "positive", "data": _pts(ts_t, ind["don_hi"][tail:]),
             "opts": {"lineWidth": 1, "dashStyle": "Dot"}},
            {"name": "Donchian 20 lo", "kind": "line", "yAxis": "price",
             "role": "negative", "data": _pts(ts_t, ind["don_lo"][tail:]),
             "opts": {"lineWidth": 1, "dashStyle": "Dot"}},
        ],
        "meta": {"chart": "ta-levels", "stock": False, "symbol": symbol,
                 "currency": currency, "timeframe": timeframe},
    }


# ---------------------------------------------------------------------------
# report-ready tables (pre-formatted strings — reporting lays out, never computes)
# ---------------------------------------------------------------------------

def fmt_money(v, currency):
    return "—" if v is None else f"{currency}{v:,.2f}"


def report_tables(levels, score, regime, currency, bias):
    plan = levels.get(bias) or {}
    rows = []
    if plan:
        atr_mult = plan["stop_distance_atr"]
        rows = [["Entry reference", fmt_money(plan["entry_ref"], currency)],
                ["Suggested stop", f"{fmt_money(plan['suggested_stop'], currency)}"
                                   + (f" ({atr_mult:.1f}× ATR)" if atr_mult else "")],
                ["Target 2R", fmt_money(plan["targets"].get("r2"), currency)],
                ["Target 3R", fmt_money(plan["targets"].get("r3"), currency)],
                ["Chandelier trail", fmt_money(plan["trail"].get("chandelier_3atr"), currency)]]
        if plan.get("sizing"):
            s = plan["sizing"]
            rows.append(["Position size",
                         f"{s['shares']:,} sh ≈ {fmt_money(s['notional'], currency)} "
                         f"({s['pct_of_capital']}% of capital, risking "
                         f"{fmt_money(s['risk_amount'], currency)})"])
    name = {"close_vs_long_ma": "Close vs long MA", "macd_hist": "MACD histogram",
            "rsi14_vs_50": "RSI(14) vs 50", "volume_bias": "Volume bias"}
    sc_rows = [[name[k], {1: "bullish (+1)", 0: "neutral (0)", -1: "bearish (−1)"}[v]]
               for k, v in score["checks"].items()]
    sc_rows.append(["Total", f"{score['score']:+d} — {score['verdict']}"])
    return {
        "levels": {"columns": ["Level", "Value"], "rows": rows},
        "scorecard": {"columns": ["Check", "Vote"], "rows": sc_rows},
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def snapshot(ind, bars, n=10):
    i0 = max(0, len(bars) - n)
    rnd = lambda v, d=2: None if v is None else round(v, d)
    return [{"date": bars[j]["date"], "close": rnd(ind["close"][j]),
             "sma50": rnd(ind["sma50"][j]), "sma_long": rnd(ind["sma_long"][j]),
             "rsi14": rnd(ind["rsi14"][j], 1), "rsi2": rnd(ind["rsi2"][j], 1),
             "macd_hist": rnd(ind["macd_hist"][j], 3), "adx14": rnd(ind["adx14"][j], 1),
             "atr14": rnd(ind["atr14"][j], 3), "bb_pctb": rnd(ind["bb_pctb"][j], 2),
             "don_hi": rnd(ind["don_hi"][j]), "don_lo": rnd(ind["don_lo"][j]),
             "supertrend": "long" if ind["st_dir"][j] == 1 else "short"}
            for j in range(i0, len(bars))]


def analyze(bars_daily, timeframe, symbol, currency, risk_pct, capital):
    warnings = []
    bars = resample(bars_daily, timeframe)
    if len(bars) < LONG_MA[timeframe] + 20:
        warnings.append(f"only {len(bars)} {timeframe} bars — SMA{LONG_MA[timeframe]} "
                        f"regime layer needs {LONG_MA[timeframe] + 20}; "
                        f"fetch more history for a reliable regime call")
    if len(bars) < 60:
        raise SystemExit(f"need at least 60 {timeframe} bars, got {len(bars)}")
    ind = compute(bars, timeframe)

    higher_tf = {"daily": "weekly", "weekly": "monthly"}.get(timeframe)
    higher_regime = None
    if higher_tf:
        hbars = resample(bars_daily, higher_tf)
        if len(hbars) >= LONG_MA[higher_tf] + 20:
            higher_regime = classify_regime(compute(hbars, higher_tf), higher_tf)
        else:
            warnings.append(f"not enough history for the {higher_tf} regime layer "
                            f"({len(hbars)} bars)")

    regime = classify_regime(ind, timeframe)
    score = scorecard(ind)
    signals = detect_signals(ind)
    for s in signals:
        s["date"] = bars[s.pop("idx")]["date"] if "idx" in s else None
    levels = build_levels(ind, bars, risk_pct, capital)
    bias = "long" if score["score"] >= 0 else "short"
    if not all(ind["volume"]):
        warnings.append("some bars have zero/missing volume — volume checks are weak")

    analysis = {
        "meta": {"symbol": symbol, "timeframe": timeframe, "as_of": bars[-1]["date"],
                 "bars": len(bars), "currency": currency, "warnings": warnings},
        "regime_higher_tf": higher_regime,
        "regime": regime,
        "scorecard": score,
        "bias": bias,
        "signals": signals,
        "levels": levels,
        "tables": report_tables(levels, score, regime, currency, bias),
        "recent": snapshot(ind, bars),
    }
    sigs_for_chart = detect_signals(ind)  # keep idx version for flag placement
    dash = dashboard_contract(ind, bars, symbol, timeframe, currency, sigs_for_chart)
    lvl = levels_contract(ind, bars, symbol, timeframe, currency, levels, bias)
    return analysis, dash, lvl


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prices", help="OHLCV JSON (array of bars or FMP wrapper)")
    p.add_argument("--out-dir", default="out")
    p.add_argument("--timeframe", choices=["daily", "weekly"], default="daily")
    p.add_argument("--symbol", default=None)
    p.add_argument("--currency", default="$")
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--capital", type=float, default=None)
    p.add_argument("--no-adjust", action="store_true",
                   help="don't scale OHLC by adjClose")
    args = p.parse_args(argv)

    symbol = args.symbol
    if symbol is None:
        with open(args.prices) as f:
            raw = json.load(f)
        symbol = raw.get("symbol", "?") if isinstance(raw, dict) else "?"

    bars = load_bars(args.prices, adjust=not args.no_adjust)
    analysis, dash, lvl = analyze(bars, args.timeframe, symbol, args.currency,
                                  args.risk_pct, args.capital)

    os.makedirs(args.out_dir, exist_ok=True)
    paths = {}
    for name, obj in [("analysis.json", analysis),
                      ("dashboard-contract.json", dash),
                      ("levels-contract.json", lvl)]:
        path = os.path.join(args.out_dir, name)
        with open(path, "w") as f:
            json.dump(obj, f, indent=1)
        paths[name] = path

    print(json.dumps({"written": paths,
                      "regime": analysis["regime"]["label"],
                      "score": analysis["scorecard"]["score"],
                      "verdict": analysis["scorecard"]["verdict"],
                      "warnings": analysis["meta"]["warnings"]}, indent=1))


if __name__ == "__main__":
    main()
