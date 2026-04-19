# Roger v2.0 — KuCoin Momentum Trading System

Regime-aware momentum scanner and backtester for KuCoin USDT pairs, built with Freqtrade 2026.3.

## Overview

- **Timeframe:** 1h (intra-hour scalp strategy)
- **Exchange:** KuCoin (paper/dry-run)
- **R:R:** 3.5:1 (stop = 2%, target ≈ 7%)
- **Risk per trade:** 5% of capital
- **Universe:** 44 filtered pairs (quality grade B+ or above, full backtest return ≥ 0)

## Strategy

Roger Momentum enters on multi-confirmation setups within detected market regime:

1. **Regime detection** — STRONG_TREND / TRENDING / RANGE_BOUND / CHOPPY using ADX + MA cross
2. **Scoring** — bull_div=+2, vol_spike=+1; enter when score ≥ 2
3. **RSI override** — block LONG when RSI > 75, block SHORT when RSI < 25 (~18% of signals blocked)
4. **Direction** — LONG in uptrends, SHORT in downtrends

## Scripts

| File | Purpose |
|------|---------|
| `scanner.py` | Live signal scanner — regime, scoring, entry/stop/target levels |
| `coin_quality_full.py` | Full pipeline: quality scan → backtest → ranked watchlist |
| `backtest_full.py` | Per-pair backtest with/without RSI override |
| `coin_quality.py` | 6-dimension quality grader (standalone) |
| `rr_tune.py` | R:R ratio optimizer across all pairs |
| `trade_analysis.py` | Trade-level breakdown with duration stats |
| `scan_cron.py` | Cron wrapper for hourly scanning |
| `strategies/roger_strategy.py` | Freqtrade IStrategy (for live trading) |

## Backtest Results

30-day hourly data, 5% risk per trade, 3.5:1 R:R, WITH RSI override:

| Metric | Value |
|--------|-------|
| Pairs | 44 |
| Total trades | ~400 |
| Win rate | 26% |
| Per-pair avg return | +554.5% |
| Top performer | LIGHT/USDT (+400%) |
| RSI blocked | ~18% of signals |

## Key Findings

- 3.5:1 is the optimal R:R for this strategy (tested 2:1 → 4:1)
- Quality grades measure market character, not strategy profitability — full backtest is the authority
- Filter on full backtest result, not quick_bt (quick_bt has no RSI override, underestimates many pairs)
- Trades resolve in ~1 hour on average — this is a scalp, not a swing hold
- DASH, FIL, FET, TAO are always loss-making — exclude from universe

## Setup

```bash
pip install ccxt pandas numpy talib freqtrade
python scanner.py --top 10 --timeframe 1h
```

## Disclaimer

This is a personal trading tool. Not financial advice. Paper trade before using real capital.
