#!/usr/bin/env python3
"""
scanner_v3.py — Clean momentum scanner
Kept: regime detection, multi-confirmation scoring, volume spike, majors bias
Dropped: candlestick patterns, bull/bear debate, yolo, whale boost

Output: JSON to stdout (for programmatic use) + optional human-readable
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import json
import argparse
import sys

# -- Config -------------------------------------------------------------------
RSI_PERIOD = 14
MA_SHORT = 10
MA_MEDIUM = 20
MA_LONG = 50
VOL_SMA_PERIOD = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
BB_WINDOW = 20
BB_STD = 2
MAJORS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
RATE_LIMIT_DELAY = 0.05
DEFAULT_RR = 3.0

# -- Exchange -----------------------------------------------------------------

def get_exchange():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})


def fetch_ohlcv(exchange, symbol, timeframe="1h", limit=200):
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        print(f"  [WARN] {symbol}: {e}", file=sys.stderr)
        return pd.DataFrame()


# -- Indicators --------------------------------------------------------------

def add_indicators(df):
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
    df["ma50"] = close.rolling(MA_LONG).mean()

    # Volume
    df["vol_sma"] = volume.rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = volume / df["vol_sma"]

    # Bollinger Bands
    bb_std = close.rolling(BB_WINDOW).std()
    df["bb_mid"] = close.rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_percent"] = (close - df["bb_lower"]) / bb_range.replace(0, np.nan)

    # Price vs MAs
    df["price_vs_ma20"] = (close - df["ma20"]) / df["ma20"] * 100

    # ATR
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()

    # ADX
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

    # Swing levels
    df["swing_low"] = low.rolling(5).min()
    df["swing_high"] = high.rolling(5).max()

    # Previous values
    df["rsi_prev"] = df["rsi"].shift(1)
    df["close_prev"] = close.shift(1)

    return df


# -- Regime Detection ---------------------------------------------------------

def detect_regime(df, lookback=30):
    if df.empty or len(df) < lookback + ADX_PERIOD:
        return None

    close = df["close"]
    ma10 = df["ma10"]
    ma20 = df["ma20"]
    adx_series = df["adx"]
    rsi_series = df["rsi"]

    if adx_series is None or rsi_series is None:
        return None

    adx = adx_series.iloc[-1]
    rsi = rsi_series.iloc[-1]
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
        regime = "CHOPPY"
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
    else:
        t = {"rsi_lo": 30, "rsi_hi": 45, "min_vol": 1.0, "entry": "mean_rev",
             "stop_mult": 2.5, "tp_mult": 1.5, "max_hold": 12}

    return {
        "regime": regime, "direction": direction,
        "adx": round(adx, 1), "rsi": round(rsi, 1),
        "trend_pct": round(trend_pct, 1), "chop_pct": round(chop_pct, 1),
        "ma_crosses": ma_crosses, "thresholds": t,
    }


# -- Signal Scoring -----------------------------------------------------------

def score_signal(df, regime_info):
    if df.empty or regime_info is None:
        return None, {}

    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    t = dict(regime_info["thresholds"])

    # LONG ONLY for spot
    if regime_info["direction"] == "SHORT":
        return None, {"blocked": "short_not_supported"}

    score = 0
    confirms = {}

    # RSI extreme override
    if regime_info["direction"] == "LONG" and row["rsi"] > 75:
        return None, {"blocked": "rsi_extreme_overbought"}

    # Must have price above MA20 in long regime
    if regime_info["direction"] == "LONG":
        if row["price_vs_ma20"] > 0:
            score += 15
            confirms["above_ma20"] = True
        else:
            return None, {}

    # RSI in buy zone
    rsi_lo = t["rsi_lo"]
    if t["entry"] == "momentum":
        if row["rsi"] > rsi_lo and prev["rsi"] <= rsi_lo:
            score += 25
            confirms["rsi_cross_up"] = True
        elif rsi_lo < row["rsi"] < 55:
            score += 10
            confirms["rsi_in_zone"] = True
    elif t["entry"] == "mean_rev":
        if row["rsi"] < rsi_lo:
            score += 25
            confirms["rsi_oversold"] = True

    # Volume confirmation
    vol_spike = row.get("vol_ratio", 1) >= 2.0
    vol_ok = row.get("vol_ratio", 1) >= t["min_vol"]
    if vol_spike:
        score += 25
        confirms["volume_spike"] = True
    elif vol_ok:
        score += 10
        confirms["volume_ok"] = True

    # BB% near lower band (bounce setup)
    bb_pct = row["bb_percent"]
    if 0 < bb_pct < 0.3:
        score += 20
        confirms["bb_lower"] = True
    elif 0.3 <= bb_pct < 0.6:
        score += 10
        confirms["bb_mid"] = True

    # MA alignment in trends
    if regime_info["regime"] in ("STRONG_TREND", "TRENDING"):
        if row["price_vs_ma20"] > 0 and (row["close"] > row["ma10"]):
            score += 10
            confirms["ma_aligned"] = True

    return score, confirms


# -- Risk Levels -------------------------------------------------------------

def calc_levels(df, entry_price, regime_info, risk_pct=2.0):
    row = df.iloc[-1]
    mult = regime_info["thresholds"]["stop_mult"]
    atr = row.get("atr", 0)

    # Stop placement
    bb_lower = row["bb_lower"]
    swing_low = row["swing_low"]

    if row["bb_percent"] < 0.3 and not np.isnan(bb_lower) and bb_lower > 0:
        stop = bb_lower * 0.995
    elif not np.isnan(swing_low):
        stop = swing_low * 0.995
    elif not np.isnan(atr) and atr > 0:
        stop = entry_price - atr * mult
    else:
        stop = entry_price * (1 - risk_pct / 100)

    stop_pct = (entry_price - stop) / entry_price * 100
    stop_pct = max(stop_pct, 0.5)
    tp_price = entry_price + (entry_price - stop) * regime_info["thresholds"]["tp_mult"]
    tp_pct = regime_info["thresholds"]["tp_mult"] * stop_pct

    return {
        "stop_price": round(float(stop), 8),
        "stop_pct": round(float(stop_pct), 2),
        "tp_price": round(float(tp_price), 8),
        "tp_pct": round(float(tp_pct), 2),
    }


# -- Majors Bias --------------------------------------------------------------

def get_majors_bias(exchange, timeframe="1h"):
    results = []
    for symbol in MAJORS:
        df = fetch_ohlcv(exchange, symbol, timeframe)
        if df.empty:
            continue
        df = add_indicators(df)
        regime = detect_regime(df)
        if regime:
            results.append({"symbol": symbol, **regime})

    long_count = sum(1 for r in results if r["direction"] == "LONG")
    short_count = sum(1 for r in results if r["direction"] == "SHORT")

    if long_count >= 3:
        bias = "BULLISH"
    elif short_count >= 3:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return bias, results


# -- Main Scan ----------------------------------------------------------------

def scan_pair(exchange, symbol, timeframe="1h"):
    df = fetch_ohlcv(exchange, symbol, timeframe)
    if df.empty or len(df) < 60:
        return None

    df = add_indicators(df)
    regime = detect_regime(df)
    if not regime:
        return None

    score, confirms = score_signal(df, regime)
    if score is None or score < 50:
        return None

    entry_price = float(df["close"].iloc[-1])
    levels = calc_levels(df, entry_price, regime)

    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "regime": regime["regime"],
        "direction": regime["direction"],
        "adx": regime["adx"],
        "rsi": round(float(df["rsi"].iloc[-1]), 1),
        "score": score,
        "confirms": confirms,
        "entry_price": round(entry_price, 8),
        "stop_price": levels["stop_price"],
        "stop_pct": levels["stop_pct"],
        "tp_price": levels["tp_price"],
        "tp_pct": levels["tp_pct"],
        "vol_ratio": round(float(df["vol_ratio"].iloc[-1]), 2),
        "bb_percent": round(float(df["bb_percent"].iloc[-1]), 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Scanner v3")
    parser.add_argument("--pairs", nargs="+", default=MAJORS, help="Pairs to scan")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--min-score", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    exchange = get_exchange()

    # Get majors bias first
    bias, majors_detail = get_majors_bias(exchange, args.timeframe)

    results = []
    for symbol in args.pairs:
        signal = scan_pair(exchange, symbol, args.timeframe)
        if signal and signal["score"] >= args.min_score:
            results.append(signal)

    output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "market_bias": bias,
        "majors_detail": majors_detail,
        "signals": results,
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"\n[SCAN] {len(results)} signals found")
        print(f"Market bias: {bias}")
        for s in results:
            print(f"\n  {s['symbol']} | Score: {s['score']} | {s['regime']}")
            print(f"    Entry: {s['entry_price']} | Stop: {s['stop_price']} ({s['stop_pct']}%) | TP: {s['tp_price']} ({s['tp_pct']}%)")
            print(f"    Confirms: {', '.join(s['confirms'].keys())}")


if __name__ == "__main__":
    main()
