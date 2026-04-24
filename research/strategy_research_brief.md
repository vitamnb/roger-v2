# Crypto Strategy Research Brief
**Date:** 2026-04-24
**Prepared by:** Roger
**Sources:** Academic papers, quant research, statistical studies

---

## Executive Summary

The research validates your instinct about multiple strategies, but delivers a harsh verdict on candlestick patterns. Here's what the data actually says:

| Strategy Family | Verdict | Evidence Strength |
|---|---|---|
| **Trend Following** | ✅ Works in crypto | Strong — multiple rigorous backtests |
| **Multi-Strategy + Regime Switching** | ✅ Recommended | Moderate — growing academic support |
| **Mean Reversion** | ⚠️ Mixed results | Weak — outperformed by momentum in recent years |
| **Breakout / Volatility Squeeze** | ✅ Promising | Moderate — needs pair-specific validation |
| **Candlestick Patterns** | ❌ Doesn't work | Strong — statistically disproven |

---

## 1. Trend Following in Crypto: The Winner

### Key Paper: Nguyen (2026) — "AdaptiveTrend"
**Most rigorous crypto trend-following study to date.** 150+ pairs, 36 months out-of-sample (2022–2024).

**Performance:**
- Sharpe ratio: **2.41**
- Max drawdown: **−12.7%**
- Annualized return: **40.5%**
- Calmar ratio: **3.18**
- 142 trades/month across portfolio

**What makes it work:**

1. **6-hour timeframe (H6)** — The optimal balance. Higher frequency = too much turnover. Daily = misses short-lived momentum signals. H6 aligns with funding rate cycles.

2. **Dynamic trailing stops** — ATR-based, volatility-calibrated. This was the #1 performance driver (+ablation: +0.73 Sharpe). Not fixed stops — they adapt to local volatility.

3. **Monthly reoptimization** — Parameters (entry threshold, ATR multiplier, lookback) recalibrated monthly. Fixed parameters = −28.6% drawdown vs −12.7% with optimization.

4. **Market-cap filtering** — Top 15 assets by market cap for longs. Avoids illiquid garbage that trends to zero.

5. **70/30 long-short allocation** — Captures crypto's structural positive drift while maintaining downside protection. Dollar-neutral (50/50) underperformed.

**Regime performance:**
| Market | Annual Return | Sharpe | Win Rate |
|---|---|---|---|
| Bull (>15% BTC) | +68.3% | 3.42 | 54.2% |
| Sideways | +18.7% | 1.87 | 47.8% |
| Bear (<−15% BTC) | −4.2% | −0.31 | 41.3% |

**Key insight:** Trend following makes money in bulls, loses only slightly in bears, and grinds sideways in chop. The asymmetric payoff is the edge.

---

## 2. Candlestick Patterns: The Harsh Truth

### Key Paper: Tobi Lux (Feb 2026) — Follow-Up Experiment
**The most rigorous statistical test of candlestick patterns to date.** 61 patterns, S&P 500, 25 years of data, 10,000 permutation tests.

**Methodology:**
- Tested patterns with/without trend filters
- Compared pattern-triggered returns vs random entries
- Permutation tests for statistical significance
- Tested both mean returns AND win rates

**Results:**
- **27 patterns** had enough occurrences (>50 in 25 years)
- After rigorous testing: **only 2 patterns** showed tiny statistical edge
- **CLOSINGMARUBOZU** and **MARUBOZU**: +0.4% to +0.7% over random
- All other patterns: **indistinguishable from random**
- Win rates after patterns were **LOWER** than random entries

**The brutal verdict:**
> "Candlestick patterns do not have predictive power. Is there anyone who can prove the opposite by statistical means?"

**Why this matters for you:**
I know you believe in price action and candlestick patterns. The data says they're the weakest signal in the scanner. We should drop them entirely and reallocate those confirmation points to proven factors.

**Exception:** The Lux study was on S&P 500 (traditional markets). Crypto's 24/7 volatility and retail flow might create more pattern validity. But there's NO rigorous crypto-specific candlestick study that proves this. Until one exists, we should treat patterns as entertainment, not edge.

---

## 3. Mean Reversion: The Underperformer

### Key Paper: Ekström (2025) — "Bitcoin trading performance evaluation"
**Master's thesis comparing momentum vs mean reversion in Bitcoin (2020–2025).**

**Findings:**
- Momentum strategies outperformed mean reversion in 4 of 5 years
- Mean reversion worked in 2022 (bear market) but failed in 2023–2024
- Transaction costs killed mean reversion more than momentum
- Higher turnover = more costs = eroded edge

**Why mean reversion struggles in crypto:**
- Trends persist longer than expected (momentum effect)
- "Cheap" often gets cheaper (see: Luna, FTX tokens)
- Reversions are violent but unpredictable — hard to time entries
- In bull markets, mean reversion is constantly fighting the trend

**When it works:**
- Range-bound markets (ADX < 20)
- Major support levels (not BB% — actual horizontal supports)
- After capitulation events (extreme fear)

**Verdict:** Keep as a secondary strategy, not primary. Only deploy when regime detector says "choppy."

---

## 4. Breakout / Volatility Squeeze: The Dark Horse

### Key Sources: Multiple PyQuantLab studies (2024–2025)

**Concept:** Low volatility → compression → expansion. When Bollinger Bands squeeze (width < lowest 120 bars), a large move often follows.

**What the research says:**
- Bollinger Band squeeze has moderate predictive power for volatility expansion
- Direction of breakout is NOT predicted — just that a move is coming
- Need additional directional filter (trend, momentum)
- Works better on higher timeframes (4h, daily)

**Why it's promising:**
- Different regime from trend following
- Captures the "calm before the storm"
- Can be combined with trend direction for asymmetric bets
- Low correlation with mean reversion strategies

**Verdict:** Include as Strategy #3. Use BB width < 5th percentile as squeeze detection, combine with momentum direction for entry.

---

## 5. Multi-Strategy Portfolio Allocation

### Key Paper: Gray (2022) — "Multi-Strategy Portfolios Algorithmically Applied to Crypto"

**The case for running multiple strategies:**
1. **Correlation < 1.0** — Trend and mean reversion often have negative correlation
2. **Regime adaptation** — Deploy capital to whichever strategy is working
3. **Drawdown smoothing** — When trend following chops, breakout might catch the move

**Recommended allocation framework:**

```
Regime Detection (weekly):
├── Bull market (BTC +15% rolling 60d):
│   ├── Trend Following: 60%
│   ├── Breakout: 30%
│   └── Mean Reversion: 10% (only deep dips)
│
├── Sideways (BTC −15% to +15%):
│   ├── Mean Reversion: 50%
│   ├── Breakout: 30%
│   └── Trend Following: 20%
│
└── Bear market (BTC < −15%):
    ├── Trend Following (SHORT): 50%
    ├── Mean Reversion: 30%
    └── Cash: 20%
```

**Kill switches:**
- Any strategy with 3 consecutive months negative expectancy → pause
- Any strategy with >20% drawdown → reduce allocation by 50%
- Market regime shift → reallocate within 1 week

---

## 6. What Actually Matters: The Evidence Hierarchy

From most to least important based on research:

| Rank | Factor | Evidence | Impact |
|---|---|---|---|
| 1 | **Dynamic trailing stops** | Nguyen + Kaminski & Lo | +0.73 Sharpe |
| 2 | **Timeframe selection** | H6 optimal | Avoids overtrading |
| 3 | **Market-cap filtering** | Top-15 only | Avoids illiquid traps |
| 4 | **Regime detection** | ADX + MA cross | Right strategy for right market |
| 5 | **Asymmetric allocation** | 70/30 long-short | Captures structural drift |
| 6 | **Monthly reoptimization** | Parameter stability | Adapts to non-stationarity |
| 7 | **Volume confirmation** | Our own research | Prevents fakeouts |
| 8 | **Candlestick patterns** | Lux (2026) | None — drop it |

---

## 7. Recommended v3 Strategy Architecture

### Strategy 1: AdaptiveTrend (Primary)
- **Timeframe:** 6h (not 1h — research says H6 is optimal)
- **Entry:** Momentum score > threshold (rate-of-change over lookback)
- **Stop:** Dynamic trailing stop, ATR × 2.5
- **TP:** No fixed TP — let trailing stop ride
- **Pairs:** Top 15 by market cap, filtered by rolling Sharpe > 1.3
- **Allocation:** 50–70% of capital depending on regime

### Strategy 2: Range Mean Reversion (Secondary)
- **Timeframe:** 1h
- **Entry:** RSI < 30 + price at major horizontal support + volume OK
- **Stop:** Support break −1%
- **TP:** Resistance level or fixed 5%
- **Pairs:** BTC, ETH, SOL only (liquid, mean-revert better)
- **Allocation:** 20–30%, only when regime = RANGE_BOUND

### Strategy 3: Volatility Breakout (Opportunistic)
- **Timeframe:** 4h
- **Entry:** BB width < 5th percentile + momentum direction
- **Stop:** ATR × 3 (wide — breakout volatility)
- **TP:** 2× stop distance or trailing stop
- **Pairs:** Any liquid pair
- **Allocation:** 10–20%, when squeeze detected

---

## 8. What to Test First

Priority order for `mtf_research.py` validation:

1. **AdaptiveTrend core** — Momentum + trailing stop on H6, BTC/ETH/SOL only
2. **Timeframe comparison** — H1 vs H4 vs H6 vs D1 for momentum
3. **Stop type comparison** — Fixed vs ATR vs trailing vs none
4. **Breakout squeeze** — BB width filter + direction on 4h
5. **Mean reversion** — RSI oversold + support on 1h (expect weak results)
6. **Multi-strategy combo** — All three together with regime switching

---

## Bottom Line for You

You were right about:
- ✅ Multiple strategies
- ✅ Regime-based allocation
- ✅ Scaling with market cycle
- ✅ Volume confirmation
- ✅ Dynamic risk management

The research disagrees with:
- ❌ Candlestick patterns as primary signal
- ❌ 1h timeframe for trend following (H6 is better)
- ❌ Fixed stops (dynamic trailing wins)
- ❌ Mean reversion as primary strategy

**The path forward:**
1. Build AdaptiveTrend (Strategy 1) — validated by best research
2. Validate through `mtf_research.py`
3. Add breakout squeeze (Strategy 3)
4. Keep mean reversion (Strategy 2) as backup for sideways markets
5. Wire regime detector to switch between them

Want me to start coding Strategy 1 (AdaptiveTrend) and running it through the backtester?
