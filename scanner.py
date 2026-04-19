# scanner.py -- KuCoin momentum scanner v4
# Includes: volume spike, RSI divergence, support/resistance, candlestick patterns
# Run: python scanner.py [--timeframe 1h] [--top 20]
# Requirements: ccxt, pandas, numpy

import ccxt
import pandas as pd
import numpy as np
import argparse
import sys
import time
import os
from datetime import datetime

# -- Config ---------------------------------------------------------------------
RSI_PERIOD = 14
MA_SHORT = 10
MA_MEDIUM = 20
MA_LONG = 50
VOL_SMA_PERIOD = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
BB_WINDOW = 20
BB_STD = 2
DEFAULT_TIMEFRAME = "1h"
DEFAULT_TOP = 20
MAX_PAIRS = 50
RATE_LIMIT_DELAY = 0.05
DEFAULT_RISK_PCT = 2.0
DEFAULT_RR = 3.5
WATCHLIST_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\daily_watchlist.txt"
# ------------------------------------------------------------------------------

# -- Exchange ------------------------------------------------------------------

def get_kucoin():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def load_daily_watchlist(top_n=50):
    """Load today's quality-filtered watchlist.
    Returns list of (symbol, grade, comp) tuples sorted by composite desc.
    Falls back to None if file doesn't exist or is empty."""
    if not os.path.exists(WATCHLIST_FILE):
        return None
    pairs = []
    for line in open(WATCHLIST_FILE):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("Date"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            sym, grade, comp = parts[0], parts[1], int(parts[2])
            pairs.append((sym, grade, comp))
    if not pairs:
        return None
    return pairs[:top_n]

def get_top_pairs(exchange, limit=MAX_PAIRS):
    try:
        raw = exchange.public_get_market_allticker()
        tickers = raw.get("data", {}).get("ticker", [])
    except Exception:
        return DEFAULT_WATCHLIST[:limit]
    usdt_tickers = []
    for t in tickers:
        sym = t.get("symbol", "")
        if "/USDT" in sym and t.get("active", True):
            vol = float(t.get("vol", 0) or 0) * float(t.get("last", 0) or 0)
            if vol > 0:
                usdt_tickers.append((sym, vol))
    usdt_tickers.sort(key=lambda x: x[1], reverse=True)
    pairs = [s[0] for s in usdt_tickers[:limit]]
    return pairs if pairs else DEFAULT_WATCHLIST[:limit]

DEFAULT_WATCHLIST = [
    "BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT",
    "ADA/USDT","AVAX/USDT","ARB/USDT","OP/USDT","NEAR/USDT",
    "APT/USDT","FIL/USDT","LINK/USDT","DOT/USDT","ATOM/USDT",
    "MATIC/USDT","UNI/USDT","LTC/USDT","ETC/USDT","XLM/USDT",
]

def fetch_ohlcv(exchange, symbol, timeframe, limit=200):
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles,
                          columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df
    except Exception:
        return pd.DataFrame()

# -- Indicators ----------------------------------------------------------------

def add_indicators(df):
    """Add all indicators: RSI, MAs, volume, Bollinger, ATR, ADX."""
    if df.empty or len(df) < max(RSI_PERIOD, MA_LONG, BB_WINDOW) + 10:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    # MAs
    df["ma10"] = close.rolling(MA_SHORT).mean()
    df["ma20"] = close.rolling(MA_MEDIUM).mean()
    df["ma50"] = close.rolling(MA_LONG).mean() if len(df) >= MA_LONG else df["ma20"]

    # Volume
    df["vol_sma"] = volume.rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = volume / df["vol_sma"]

    # Volume change (is volume increasing or dying?)
    df["vol_change"] = volume.pct_change()
    df["vol_change_sma"] = df["vol_change"].rolling(10).mean()

    vol_avg = df["vol_sma"]  # reference for later use

    # Bollinger Bands
    bb_std = close.rolling(BB_WINDOW).std()
    df["bb_mid"] = close.rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_percent"] = (close - df["bb_lower"]) / bb_range.replace(0, np.nan)

    # Price vs MAs
    df["price_vs_ma10"] = (close - df["ma10"]) / df["ma10"] * 100
    df["price_vs_ma20"] = (close - df["ma20"]) / df["ma20"] * 100
    df["price_vs_ma50"] = (close - df["ma50"]) / df["ma50"] * 100 if MA_LONG else 0

    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()

    # ADX and directional indicators
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_s = tr.rolling(ADX_PERIOD).mean()
    df["plus_di"] = 100 * (plus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    df["minus_di"] = 100 * (minus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"])
    df["adx"] = dx.rolling(ADX_PERIOD).mean()

    # Swing highs/lows
    df["swing_low"] = low.rolling(5).min()
    df["swing_high"] = high.rolling(5).max()
    df["swing_low_10"] = low.rolling(10).min()
    df["swing_high_10"] = high.rolling(10).max()

    # Previous values
    df["rsi_prev"] = df["rsi"].shift(1)
    df["rsi_prev2"] = df["rsi"].shift(2)
    df["close_prev"] = close.shift(1)
    df["close_prev2"] = close.shift(2)
    df["volume_prev"] = volume.shift(1)

    # ---- Candlestick Patterns ----
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]

    # Doji (indecision)
    body = (c - o).abs()
    range_c = h - l
    df["doji"] = (body / range_c.replace(0, np.nan) < 0.1) & (range_c > 0)

    # Hammer / Hanging Man (single candle reversal)
    body_top = pd.concat([c, o], axis=1).max(axis=1)
    body_bottom = pd.concat([c, o], axis=1).min(axis=1)
    lower_shadow = body_bottom - l
    upper_shadow = h - body_top
    body_height = body
    df["hammer"] = (
        (lower_shadow > body_height * 2.0) &
        (upper_shadow < body_height * 0.5) &
        (df["rsi"] < 55) &
        (body_height < range_c * 0.3)
    )

    # Engulfing (two candles)
    prev_body_top = df["open"].shift(1)
    prev_body_bottom = df["close"].shift(1)
    prev_bearish = df["close"].shift(1) < df["open"].shift(1)
    curr_bullish = c > o
    df["engulfing_bull"] = (
        prev_bearish &
        curr_bullish &
        (o < prev_body_top) &
        (c > prev_body_bottom)
    )

    # Morning Star (3 candles - bottom reversal)
    c1 = df["close"].shift(2) < df["open"].shift(2)  # bearish
    c2_small = (df["close"].shift(1) - df["open"].shift(1)).abs() < body_height.shift(1) * 0.5
    c3 = df["close"] > df["open"]
    c3_close_above_c1_mid = df["close"] > (df["open"].shift(2) + df["close"].shift(2)) / 2
    df["morning_star"] = c1 & c2_small & c3 & c3_close_above_c1_mid

    # Three White Soldiers (3 bullish candles in a row, higher closes)
    w1 = df["close"] > df["open"]
    w2 = (df["close"].shift(1) > df["open"].shift(1)) & (df["close"] > df["close"].shift(1))
    w3 = (df["close"].shift(2) > df["open"].shift(2)) & (df["close"].shift(1) > df["close"].shift(2))
    w_inc = (df["close"] - df["open"]) > (df["close"].shift(1) - df["open"].shift(1))
    df["three_white_soldiers"] = w1 & w2 & w3 & w_inc

    # ---- RSI Divergence ----
    # Bullish divergence: price makes lower low, RSI makes higher low
    price_low = close.rolling(5).min()
    rsi_low = df["rsi"].rolling(5).min()
    price_swing = (close == price_low).astype(int)
    rsi_swing = (df["rsi"] == rsi_low).astype(int)

    df["price_at_swing_low"] = price_swing
    df["rsi_at_swing_low"] = rsi_swing

    # Detect divergence: price at local low but RSI higher than previous local low
    df["div_price_swing"] = price_swing & (~rsi_swing.shift(1, fill_value=False))
    df["div_rsi_higher"] = (df["rsi"] > df["rsi"].shift(5)) & price_swing
    df["bullish_divergence"] = (
        (close < close.shift(5)) &  # price lower than 5 bars ago
        (df["rsi"] > df["rsi"].shift(5)) &  # RSI higher than 5 bars ago
        (df["rsi"] < 60)  # not overbought
    )
    df["bearish_divergence"] = (
        (close > close.shift(5)) &
        (df["rsi"] < df["rsi"].shift(5)) &
        (df["rsi"] > 40)
    )

    # ---- Volume Spike ----
    df["volume_spike_2x"] = volume > df["vol_sma"] * 2
    df["volume_spike_1_5x"] = volume > df["vol_sma"] * 1.5
    df["volume_drying"] = volume < df["vol_sma"] * 0.3

    # ---- Breakout ----
    df["resistance_1h"] = df["swing_high"].shift(1)
    df["support_1h"] = df["swing_low"].shift(1)
    df["resistance_broken"] = close > df["resistance_1h"]
    df["support_broken"] = close < df["support_1h"]

    return df

# -- Regime Detection -----------------------------------------------------------

def detect_regime(df, lookback=30):
    if df.empty or len(df) < lookback + ADX_PERIOD:
        return None

    close = df["close"]
    ma10 = df["ma10"]
    ma20 = df["ma20"]

    adx = df["adx"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    rsi_avg = df["rsi"].iloc[-lookback:].mean()
    rsi_range = df["rsi"].iloc[-lookback:].max() - df["rsi"].iloc[-lookback:].min()
    ma10_above_20 = (ma10 > ma20).iloc[-lookback:].mean()
    oscillates = min(abs(((close - ma20) / ma20 > 0).iloc[-lookback:].mean() - 0.5) * 2, 1.0)
    ma_crosses = int(((ma10 > ma20) != (ma10.shift(1) > ma20.shift(1))).iloc[-lookback:].sum())

    trend_s, chop_s = 0.0, 0.0
    if adx >= 30: trend_s += 0.4
    elif adx >= 20: trend_s += 0.2; chop_s += 0.1
    else: chop_s += 0.4
    if ma10_above_20 > 0.8: trend_s += 0.3
    elif ma10_above_20 < 0.3: chop_s += 0.3
    if oscillates < 0.3: trend_s += 0.2
    elif oscillates > 0.6: chop_s += 0.2
    if ma_crosses <= 3: trend_s += 0.2
    elif ma_crosses >= 8: chop_s += 0.3
    if rsi_range < 15: chop_s += 0.3
    elif rsi_avg > 58 or rsi_avg < 42: trend_s += 0.2

    total = trend_s + chop_s
    trend_pct = trend_s / total * 100 if total > 0 else 50
    chop_pct = chop_s / total * 100 if total > 0 else 50

    if trend_pct >= 60:
        regime = "STRONG_TREND" if adx >= 40 else "TRENDING"
    elif chop_pct >= 60:
        regime = "LOW_VOL" if df["bb_percent"].iloc[-1] < 0.1 else "CHOPPY"
    else:
        regime = "RANGE_BOUND"

    ma20_slope = (ma20.iloc[-1] / ma20.iloc[-10] - 1) * 100 if len(df) >= 10 else 0

    if regime in ("STRONG_TREND", "TRENDING"):
        direction = "LONG" if ma20_slope > 0 else "SHORT"
    elif regime == "RANGE_BOUND":
        direction = "LONG" if rsi < 45 else ("SHORT" if rsi > 55 else "NEUTRAL")
    else:
        direction = "NEUTRAL"

    # Regime-specific thresholds
    if regime == "STRONG_TREND":
        t = {"rsi_lo": 45, "rsi_hi": 55, "min_vol": 0.8, "entry": "momentum",
             "stop_mult": 1.0, "tp_mult": 3.0, "max_hold": 72}
    elif regime == "TRENDING":
        t = {"rsi_lo": 40, "rsi_hi": 55, "min_vol": 0.8, "entry": "momentum",
             "stop_mult": 1.25, "tp_mult": 2.5, "max_hold": 48}
    elif regime == "RANGE_BOUND":
        t = {"rsi_lo": 35, "rsi_hi": 50, "min_vol": 0.8, "entry": "mean_rev",
             "stop_mult": 2.0, "tp_mult": 2.0, "max_hold": 24}
    else:  # CHOPPY / LOW_VOL
        t = {"rsi_lo": 30, "rsi_hi": 45, "min_vol": 1.0, "entry": "mean_rev",
             "stop_mult": 2.5, "tp_mult": 1.5, "max_hold": 12}

    return {
        "regime": regime, "direction": direction,
        "adx": round(adx, 1), "rsi": round(rsi, 1),
        "rsi_avg": round(rsi_avg, 1), "trend_pct": round(trend_pct, 1),
        "chop_pct": round(chop_pct, 1), "ma_crosses": ma_crosses,
        "ma_slope": round(ma20_slope, 2), "thresholds": t,
    }

# -- Support / Resistance ------------------------------------------------------

def find_supports(df, lookback=20):
    """Find significant support and resistance zones."""
    if df.empty or len(df) < lookback + 5:
        return None, None
    recent = df.tail(lookback)
    price = float(df["close"].iloc[-1])
    # Support: lowest low in lookback period, must be below current price
    lows = recent["low"].dropna()
    supports = [l for l in lows if l < price * 0.99]
    resistance = float(recent["swing_high"].max())
    support = float(min(supports)) if supports else None
    return support, resistance

# -- Entry Signal (multi-confirmation) -----------------------------------------

def score_signal(df, regime_info):
    """
    Multi-confirmation scoring: each confirmed factor adds points.
    Higher score = more conviction.
    """
    if df.empty or regime_info is None:
        return None, {}

    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    t = dict(regime_info["thresholds"])
    t["stop_mult"] = 1.5  # override with fixed stop mult
    score = 0
    confirms = {}

    # RSI Extreme Override -- block signals when RSI is too extreme
    # RSI < 25 = deeply oversold -- don't short, wait for bounce
    # RSI > 75 = deeply overbought -- don't long, wait for pullback
    RSI_BLOCK_SHORT = 25
    RSI_BLOCK_LONG = 75
    if regime_info["direction"] == "SHORT" and row["rsi"] < RSI_BLOCK_SHORT:
        return None, {"blocked": "rsi_extreme_oversold"}
    if regime_info["direction"] == "LONG" and row["rsi"] > RSI_BLOCK_LONG:
        return None, {"blocked": "rsi_extreme_overbought"}

    # Must have: price above MA20 in long regime, below in short
    if regime_info["direction"] == "LONG":
        if row["price_vs_ma20"] > 0:
            score += 15
            confirms["above_ma20"] = True
        else:
            return None, {}
    elif regime_info["direction"] == "SHORT":
        if row["price_vs_ma20"] < 0:
            score += 15
            confirms["below_ma20"] = True
        else:
            return None, {}

    # RSI in buy zone (regime-adaptive)
    rsi_lo = t["rsi_lo"]
    if t["entry"] == "momentum":
        if row["rsi"] > rsi_lo and prev["rsi"] <= rsi_lo:
            score += 20
            confirms["rsi_cross_up"] = True
        elif rsi_lo < row["rsi"] < 55:
            score += 10
            confirms["rsi_in_zone"] = True
    elif t["entry"] == "mean_rev":
        if row["rsi"] < rsi_lo:
            score += 20
            confirms["rsi_oversold"] = True

    # Volume confirmation
    vol_spike = row.get("volume_spike_1_5x", False)
    vol_ok = row.get("vol_ratio", 1) >= t["min_vol"]
    if vol_spike:
        score += 25
        confirms["volume_spike"] = True
    elif vol_ok:
        score += 10
        confirms["volume_ok"] = True

    # BB% near lower band (bounce setup)
    if 0 < row["bb_percent"] < 0.3:
        score += 20
        confirms["bb_lower"] = True
    elif 0.3 <= row["bb_percent"] < 0.6:
        score += 10
        confirms["bb_mid"] = True

    # Candlestick confirmations
    if row.get("hammer") and confirms.get("rsi_oversold"):
        score += 15
        confirms["hammer"] = True
    if row.get("engulfing_bull"):
        score += 15
        confirms["engulfing"] = True
    if row.get("morning_star"):
        score += 20
        confirms["morning_star"] = True
    if row.get("bullish_divergence"):
        score += 20
        confirms["bull_div"] = True

    # Volume trend: is volume growing or fading?
    if row.get("vol_change", 0) > 0:
        score += 5
        confirms["vol_growing"] = True

    # MA alignment (strong trend confirmation)
    if regime_info["regime"] in ("STRONG_TREND", "TRENDING"):
        if row["price_vs_ma10"] > 0 and row["price_vs_ma20"] > 0:
            score += 10
            confirms["ma_aligned"] = True

    return score, confirms

# -- Risk Management -----------------------------------------------------------

def calc_levels(df, entry_price, regime_info, risk_pct=DEFAULT_RISK_PCT, rr=DEFAULT_RR):
    row = df.iloc[-1]
    t = {"stop_mult": 1.5, "tp_mult": regime_info["thresholds"]["tp_mult"]}
    mult = t["stop_mult"]
    atr = row.get("atr", 0)

    # Stop placement
    bb_lower = row["bb_lower"]
    swing_low = row["swing_low"]

    if row["bb_percent"] < 0.3 and not np.isnan(bb_lower) and bb_lower > 0:
        stop = bb_lower * 0.995
    elif not np.isnan(swing_low) and regime_info["direction"] == "LONG":
        stop = swing_low * 0.995
    elif not np.isnan(atr) and atr > 0:
        stop = entry_price - atr * mult
    else:
        stop = entry_price * (1 - risk_pct / 100)

    stop_pct = (entry_price - stop) / entry_price * 100
    stop_pct = max(stop_pct, 0.5)
    tp_price = entry_price + (entry_price - stop) * t["tp_mult"]
    tp_pct = t["tp_mult"] * stop_pct

    # Position size
    risk_amount = 58 * (risk_pct / 100)
    units = risk_amount / (entry_price * stop_pct / 100)
    cost = units * entry_price
    if cost > 58:
        units = 58 / entry_price
        cost = 58
        risk_amount = units * entry_price * (stop_pct / 100)

    return {
        "stop_price": round(stop, 8),
        "stop_pct": round(stop_pct, 2),
        "tp_price": round(tp_price, 8),
        "tp_pct": round(tp_pct, 2),
        "units": round(units, 4),
        "risk_amt": round(risk_amount, 4),
        "cost": round(cost, 4),
    }

# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="KuCoin momentum scanner v4")
    parser.add_argument("--timeframe", "-t", default=DEFAULT_TIMEFRAME,
                        choices=["15m","1h","4h","1d"])
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--capital", type=float, default=58.0)
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--rr", type=float, default=DEFAULT_RR)
    parser.add_argument("--min-score", type=float, default=40)
    args = parser.parse_args()

    print(f"\n{'='*90}")
    print(f"[SCANNER v4] KuCoin -- Momentum + Volume + Divergence + Candles + Regime")
    print(f"   Timeframe: {args.timeframe}  |  Top {args.top} signals")
    print(f"   Capital: ${args.capital:.2f}  |  Risk: {args.risk}%/trade")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")

    exchange = get_kucoin()
    watchlist = load_daily_watchlist(top_n=MAX_PAIRS)
    if watchlist:
        pairs = [s[0] for s in watchlist]
        print(f"[*] Loaded {len(pairs)} pairs from daily watchlist.")
        print(f"    (Quality-filtered, QBt>=0 + Grade B+ or above)\n")
    else:
        pairs = get_top_pairs(exchange, limit=MAX_PAIRS)
        print(f"[*] Loaded {len(pairs)} pairs by volume (unfiltered fallback).")
        print(f"    Run coin_quality_full.py to generate the quality watchlist.\n")

    all_regimes = []
    all_signals = []

    for i, symbol in enumerate(pairs):
        sys.stdout.write(f"  [{i+1}/{len(pairs)}] {symbol:<15}")
        sys.stdout.flush()

        df = fetch_ohlcv(exchange, symbol, args.timeframe)
        if df.empty:
            print(f"\r               \r", end="")
            time.sleep(RATE_LIMIT_DELAY)
            continue

        df = add_indicators(df)
        regime_info = detect_regime(df)
        if regime_info is None:
            print(f"\r               \r", end="")
            time.sleep(RATE_LIMIT_DELAY)
            continue

        all_regimes.append((symbol, regime_info))

        score, confirms = score_signal(df, regime_info)
        support, resistance = find_supports(df)

        row = df.iloc[-1]

        if score and score >= args.min_score:
            entry = float(row["close"])
            levels = calc_levels(df, entry, regime_info, args.risk, args.rr)

            # Build confirmation string
            conf_parts = []
            for k, v in confirms.items():
                conf_parts.append(k)

            signal_tags = []
            if regime_info["thresholds"]["entry"] == "momentum":
                signal_tags.append("momentum")
            if regime_info["thresholds"]["entry"] == "mean_rev":
                signal_tags.append("mean_rev")

            all_signals.append({
                "symbol": symbol,
                "regime": regime_info["regime"],
                "direction": regime_info["direction"],
                "score": score,
                "adx": regime_info["adx"],
                "rsi": regime_info["rsi"],
                "entry": entry,
                "support": support,
                "resistance": resistance,
                "vol_ratio": round(row["vol_ratio"], 2),
                "vol_spike": bool(row.get("volume_spike_1_5x", False)),
                "confirmations": ", ".join(conf_parts[:6]),
                **levels,
            })

        print(f"\r               \r", end="")
        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n{'='*90}")

    # -- Regime overview
    print(f"\n[REGIME OVERVIEW]")
    print(f"  {'Pair':<12} {'Regime':<16} {'Dir':<8} {'ADX':>5} {'RSI':>5}  {'Trend%':>7} {'Chop%':>6}  {'Entry'}")
    print(f"  {'-'*12} {'-'*16} {'-'*8} {'-'*5} {'-'*5}  {'-'*7} {'-'*6}  {'-'*6}")
    for sym, r in sorted(all_regimes, key=lambda x: -x[1]["adx"]):
        print(f"  {sym:<12} {r['regime']:<16} {r['direction']:<8} {r['adx']:>5.1f} {r['rsi']:>5.1f}  "
              f"{r['trend_pct']:>6.1f}% {r['chop_pct']:>5.1f}%  {r['thresholds']['entry']}")

    # -- Signals
    if not all_signals:
        print(f"\n[!] No signals found (min score: {args.min_score})")
        print(f"\n[APPROACHING -- within 10 points of threshold]:")
        near = [(s[0], s[1]) for s in [(sym, detect_regime(fetch_ohlcv(exchange, sym, args.timeframe), 30) or {}) for sym in pairs[:20]]]
        near = [(sym, r) for sym, r in near if r.get("rsi", 50) < r.get("thresholds", {}).get("rsi_lo", 40) + 15]
        near.sort(key=lambda x: x[1].get("rsi", 50))
        for sym, r in near[:5]:
            lo = r.get("thresholds", {}).get("rsi_lo", 40)
            print(f"  {sym:<12} RSI={r['rsi']:.1f}  zone=<{lo:.0f}  [{r['regime']}]")
        print()
        return

    all_signals.sort(key=lambda x: x["score"], reverse=True)

    print(f"\n[SIGNALS] Top Setups (score >= {args.min_score}):\n")
    print(f"  {'Symbol':<12} {'Regime':<14} {'Dir':<6} {'Score':>6}  {'Entry':>12}  "
          f"{'Support':>12} {'Resistance':>12}  {'Vol':>5} {'Confirms'}")
    print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*6}  {'-'*12}  "
          f"{'-'*12} {'-'*12}  {'-'*5} {'-'*25}")
    for s in all_signals[:args.top]:
        sup = '${:.6f}'.format(s["support"]) if s["support"] else "N/A"
        res = '${:.6f}'.format(s["resistance"]) if s["resistance"] else "N/A"
        vol_s = str(s["vol_ratio"]) + "x"
        print(f"  {s['symbol']:<12} {s['regime']:<14} {s['direction']:<6} {s['score']:>6}  "
              f"{s['entry']:>12.6f}  {sup:>12} {res:>12}  "
              f"{vol_s:>5} {s['confirmations'][:25]}")

    print(f"\n[SIGNAL DETAIL] Top 3:\n")
    for s in all_signals[:3]:
        print(f"  {s['symbol']} | {s['regime']} | {s['direction']} | Score: {s['score']}")
        print(f"  Entry:   ${s['entry']:.6f}")
        print(f"  Stop:    ${s['stop_price']:.6f}  (-{s['stop_pct']:.1f}%)")
        print(f"  TP:      ${s['tp_price']:.6f}  (+{s['tp_pct']:.1f}%)")
        print(f"  Units:   {s['units']:,.4f}  |  Risk: ${s['risk_amt']:.2f}  |  Cost: ${s['cost']:.2f}")
        print(f"  Vol:     {s['vol_ratio']}x avg  |  Spike: {s['vol_spike']}")
        print(f"  Confirms: {s['confirmations']}")
        print()

    print(f"{'='*90}")
    print(f"[LEGEND]")
    print(f"  Confirmations:")
    print(f"    rsi_cross_up  = RSI crossed above zone threshold")
    print(f"    rsi_in_zone   = RSI in buy zone")
    print(f"    rsi_oversold  = RSI deeply oversold (mean reversion)")
    print(f"    volume_spike  = Volume > 1.5x average (significant activity)")
    print(f"    volume_ok     = Volume above regime minimum")
    print(f"    bb_lower      = Price near lower Bollinger Band (bounce setup)")
    print(f"    above_ma20    = Price above 20 MA (trend confirming)")
    print(f"    hammer        = Hammer candlestick + RSI confirm")
    print(f"    engulfing     = Bullish engulfing candle")
    print(f"    morning_star  = Morning star reversal (3-candle)")
    print(f"    bull_div      = Bullish RSI divergence (price low, RSI higher)")
    print(f"  Regimes:")
    print(f"    STRONG_TREND  = Strong directional momentum, follow it")
    print(f"    TRENDING      = Confirmed trend, momentum entries")
    print(f"    RANGE_BOUND   = Oscillating, mean reversion plays")
    print(f"    CHOPPY        = Avoid or very selective")
    print(f"\n  Scores are Roger's opinion, not financial advice.\n")

if __name__ == "__main__":
    main()
