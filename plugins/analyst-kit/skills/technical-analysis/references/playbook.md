# Technical Indicator Playbook

*When to use what, what to do when it fails, and how to combine signals for
entries/exits. The engine (`scripts/indicators.py`) computes everything here; this
document is the interpretation layer.*

---

## 1. When to Use Which Indicator

**Golden rule: match the indicator to the market regime.** Trend indicators lose money
in ranges; oscillators lose money in trends. Identify regime first, then pick the tool.

### Step 0 — Identify the regime

| Test | Trending | Ranging |
|---|---|---|
| ADX(14) | > 25 | < 20 |
| Price vs long MA (200d / 40w / 10m) | Consistently one side | Whipsawing across it |
| Bollinger Band width | Expanding | Contracting / flat |

(`analysis.json → regime` runs exactly these tests; `regime_higher_tf` runs them one
timeframe up.)

### Indicator selection table

| Regime / Goal | Use | Why | Avoid |
|---|---|---|---|
| **Strong trend — ride it** | EMA(20/50), Supertrend, ADX, MACD line, Donchian channels | Stay in as long as structure holds | RSI/Stochastic (stay "overbought" for months) |
| **Range — fade extremes** | RSI(2 or 14), Bollinger Bands, %B | Mean reversion works when price oscillates | MA crossovers (constant whipsaw) |
| **Breakout — catch new trend** | Donchian 20-day high, Bollinger squeeze, volume surge (>2× avg), ATR expansion | Volatility compression precedes expansion | Lagging MAs (too late) |
| **Confirm momentum** | MACD histogram, ROC, RSI > 50/< 50 | Validates direction before entry | Using alone as entry |
| **Time the exact entry** | Candlestick patterns (engulfing, hammer) at support/resistance | Fine-grained timing only | Patterns in isolation (≈ coin flip) |
| **Set stops & size** | ATR(14) | Adapts to volatility; 2–3× ATR stop | Fixed % stops (ignore volatility) |
| **Validate with volume** | OBV, VWAP, volume MA | Moves without volume fail more often | — |

### Indicator cheat sheet

| Indicator | Type | Best timeframe | One-line job |
|---|---|---|---|
| SMA/EMA 50/200 | Trend | Daily/weekly | Define the trend; trade only with it |
| MACD | Trend+momentum | Daily | Trend turns (line cross) + strength (histogram) |
| RSI(14) | Oscillator | Any | <30 oversold / >70 overbought — *in ranges only* |
| RSI(2) | Oscillator | Daily | Buy dips <10 **above** the long MA (Connors) |
| Bollinger Bands | Volatility | Any | Squeeze = breakout coming; touch = stretch |
| ATR | Volatility | Any | Stop distance & position size, never direction |
| ADX | Trend strength | Daily | Regime filter (>25 trend, <20 range) |
| Donchian | Breakout | Daily/weekly | Turtle-style entries/exits |
| OBV / VWAP | Volume | Intraday–daily | Is the move real? |
| Supertrend | Trend | Daily | Simple trail + direction flag |

---

## 2. When an Indicator Turns Out Wrong

**Reframe: indicators are never "right" — they're probabilistic. Plan the failure
before entry, not after.**

### Before every trade, define invalidation

| Element | Rule of thumb |
|---|---|
| Stop-loss | 2–3× ATR from entry, or below the signal candle/swing low — whichever is structural |
| Position size | Risk 0.5–2% of capital per trade: `size = risk_amount / stop_distance` |
| Time stop | Mean-reversion trade not working in 5–10 bars → exit, thesis stale |
| Signal invalidation | The condition that triggered entry reverses (e.g., close back inside breakout level) → exit, don't wait for stop |

### Failure response playbook

| Situation | Wrong response | Right response |
|---|---|---|
| Stop hit | Average down, "it'll come back" | Take the loss. The stop *is* the plan working |
| Breakout fails (close back in range) | Hold and hope | Exit immediately; failed breakouts often reverse hard (good fade setups) |
| MA crossover whipsaws repeatedly | Tweak parameters after each loss | Regime changed to range → switch toolset or stand aside |
| RSI oversold keeps falling | Keep buying every dip | "Oversold" in a downtrend = trend strength. Add trend filter (only buy if price > long MA) |
| Indicator diverges from price | Trust the indicator | Price is the boss. Divergence is context, never a trigger |
| 3–5 losses in a row | Revenge trade bigger | Halve size or pause; check if regime flipped |

### Diagnosing repeated failure (in order)

1. **Regime mismatch?** — using trend tools in a range or vice versa. *Cause of most
   failures.*
2. **No volume/trend confirmation?** — add one filter, not five.
3. **Costs eating edge?** — many signals are profitable pre-cost only. Backtest with
   5–15 bps slippage+fees.
4. **Overfit?** — if it only works with RSI=13.5 on Tuesdays, it's noise. Robust
   signals survive parameter changes.
5. **Edge genuinely decayed?** — track live vs backtest; retire strategies whose
   rolling Sharpe goes negative for months.

**Key mindset: a wrong signal is a cost of business, not a flaw to fix. Judge over 50+
trades (expectancy = win% × avg win − loss% × avg loss), never per trade.**

---

## 3. Entries & Exits — Reading Multiple Indicators Side by Side

### The confluence stack (3 layers, one indicator each)

More indicators ≠ better. RSI + Stochastic + Williams %R = the same oscillator three
times (multicollinearity). Pick **one per category**:

| Layer | Question | Pick one |
|---|---|---|
| 1. Regime/Trend | Should I be long at all? | long-MA slope, ADX, weekly Supertrend |
| 2. Setup/Momentum | Is pressure building my way? | MACD histogram, RSI vs 50, pullback to 20-EMA |
| 3. Trigger | Exact bar to act | Donchian breakout, candle pattern, band re-entry |

**Entry = all 3 layers agree.** Example long: price > long MA (1) + MACD hist rising
(2) + close above 20-day high (3).

### Scorecard method (systematic side-by-side)

Score each layer −1 / 0 / +1; trade only at ±2 or ±3. The engine's
`analysis.json → scorecard` implements exactly this:

| Check | Bullish +1 | Bearish −1 |
|---|---|---|
| Close vs long MA | Above | Below |
| MACD histogram | Rising | Falling |
| RSI(14) | >50 | <50 |
| Volume vs 20-avg | High on up bars | High on down bars |

### Exits — decide before entry, mechanical after

| Exit type | Rule | Use for |
|---|---|---|
| Initial stop | 2–3× ATR or below swing low | Every trade, always |
| Trailing stop | Chandelier: highest close − 3×ATR; or Supertrend flip | Trend trades — lets winners run |
| Target | Opposite band / prior high / 2R | Mean-reversion trades |
| Signal exit | Layer 1 or 2 flips against you | All trades |
| Time stop | N bars without progress | Mean reversion |

**Asymmetry rule: enter on confluence (strict, all layers), exit on first breakdown
(loose, any layer). Protects capital, keeps winners.**

### Practical dashboard

The `dashboard-contract.json` the engine emits is this layout: price + 50/long-SMA +
Bollinger → volume → MACD histogram → RSI. One glance = all 3 layers.
**Multi-timeframe:** the engine computes the regime one timeframe up automatically —
trade only in the higher timeframe's direction.

---

## One-page summary

1. Regime first (ADX/long-MA) → trend tools in trends, oscillators in ranges.
2. One indicator per layer: regime → momentum → trigger. Three correlated oscillators
   = one opinion, not three.
3. Define stop (ATR-based), size (% risk), and invalidation **before** entry.
4. Wrong signals are normal; broken process (no stop, regime mismatch, overfit) is not.
5. Strict entries, fast exits. Judge over 50+ trades, not one.

*Educational material, not financial advice. Backtest with costs before risking
capital.*
