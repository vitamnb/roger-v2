# Scalping Research Brief — April 26, 2026

## Key Finding: 38 Strategies Tested, 2 Survived

Source: Curupira.dev (quant team publishing failures, not just wins)

**Kill rate: 94.7%** — Most scalping strategies die on:
- Tick data verification (OHLC inflates results 4x)
- Walk-forward testing (edge evaporates OOS)
- Cross-asset transfer (works on one pair only)
- Transaction costs (spread + slippage kills thin edges)

---

## The One That Survived: Cascade-Fade Scalper

**Premise:** Fade liquidation cascade overshoots on crypto perps.

**How it works:**
1. Detect velocity spike (cumulative displacement over 5 x 1m bars)
2. Volume confirmation (3x average — distinguishes cascade from gap)
3. Enter opposite direction at cascade bottom
4. **Time-based exit** (sub-5 minute hold) — NOT target-based

**Results by asset:**

| Asset | Profit Factor | Win Rate | Signals/Day | Status |
|-------|--------------|----------|-------------|--------|
| SOL | ~2.5 | High | ~1.6 | THRIVING |
| ETH | ~2.9 | ~67% | ~1.3 | BEST |
| BTC | ~1.5 | Low | Sparse | DEAD |

**Why BTC died:** Deep order books absorb forced selling efficiently. Overshoots shrink.

**Why SOL thrives:** Thin books, retail leverage, memecoin adjacency = violent cascades.

**Walk-forward:** ALL 5 windows green across all parameter thresholds. Structural edge, not fitted.

---

## What Dies in Scalping

| Strategy | Why It Died |
|----------|-------------|
| Fair Value Gap (FVG) | PF 4.28 on daily OHLC → PF 0.80 on 5m tick. Close-based SL/TP fabricated results |
| Entropy Collapse | 44 trades on EURUSD 1H looked good. 0.76 PF on EURGBP. Tick data: -17 bps |
| Jump Trend | 14 "optimal" configs in 17 windows. No stable parameters |
| Asian FVG Raid | 34 trades: 70.6% WR. 234 trades: 48.7% WR. Small sample illusion |
| Holding Pattern | +91 pips on bars, -452 pips on ticks. Signal was OHLC artifact |

**Lesson:** Pattern-based scalping = graveyard. Structural edge = survival.

---

## Why Our Current Setup Can't Do This

| Requirement | Our Setup | Gap |
|-------------|-----------|-----|
| Perpetual futures | KuCoin spot only | No access to liquidation data |
| 1m tick data | CCXT 1h candles | No microstructure |
| Funding rate data | Not available | Can't measure positioning |
| OI + liquidation heatmaps | Not available | Can't detect cascade zones |

**Options:**

**A. KuCoin Futures** — freqtrade supports it, but requires futures config (different API endpoints, margin requirements)

**B. Hyperliquid** — What Curupira uses. Better perp infrastructure, lower fees. Requires new exchange setup.

**C. Spot-compatible scalping** — Different edge entirely. Ideas below.

---

## Spot-Compatible Scalping Ideas

| Approach | Data Needed | Edge Source | Feasibility |
|----------|------------|-------------|--------------|
| Order book imbalance | L2 order book | Bid/ask ratio predicts short-term direction | Medium — KuCoin has L2 |
| VWAP mean reversion | 15m OHLC + volume | Price vs VWAP on range days | High — can test now |
| Range breakout + fail | 15m OHLC | False breakout, retrace to range | Medium — needs regime filter |
| Cross-exchange arb | Spot prices across 2+ exchanges | Price dislocation | Low — latency sensitive |
| Funding rate proxy | KuCoin futures funding | Spot follows perp funding | Medium — indirect signal |

---

## Recommendation

**Phase 1 (Now):** Test VWAP mean reversion on 15m using our existing data + freqtrade.
- Buy when price touches lower VWAP band + RSI < 40
- Sell at VWAP midpoint or upper band
- Filter: Only trade when ADX < 25 (range regime)

**Phase 2 (If Phase 1 works):** Research KuCoin futures API for liquidation cascade fading.
- Requires: futures account, different freqtrade config, perp data feeds
- Risk: Higher complexity, margin requirements

**Phase 3 (Longer term):** Hyperliquid integration for true microstructure scalping.

---

## Key Metrics for Any Scalping Strategy

| Metric | Minimum | Target |
|--------|---------|--------|
| Profit Factor | >1.2 | >1.5 |
| Win Rate | >55% | >60% |
| Trades/day | >2 | >5 |
| Avg hold time | <30 min | <10 min |
| Max drawdown | <10% | <5% |
| Walk-forward windows | All green | All green + PF >1.5 |

---

## Bottom Line

The only validated scalping edge found: **liquidation cascade fading on perps**. This is structural, not pattern-based. Our spot-only setup cannot access it.

For spot: VWAP mean reversion in range regimes is the most testable hypothesis. But historical success rate of scalping strategies is ~5%. The graveyard is 95% of attempts.

**Question for you:** Do you want to:
1. Test VWAP range scalping on 15m (spot, low risk)
2. Explore KuCoin futures setup (perps, higher complexity)
3. Stay focused on 1h swing trades (proven edge, ignore scalping)
4. Something else
