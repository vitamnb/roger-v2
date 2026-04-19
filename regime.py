# regime.py -- Market regime detector
# Classifies market state to adapt entry/exit strategy
# Run standalone: python regime.py [--timeframe 1h]
# Or import: from regime import detect_regime, get_adaptive_thresholds

import ccxt
import pandas as pd
import numpy as np
import argparse
import sys
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
# ------------------------------------------------------------------------------

# -- Indicators ----------------------------------------------------------------

def adx(high, low, close, period=14):
    """Calculate ADX and directional indicators."""
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()

    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_val = dx.rolling(period).mean()

    return adx_val, plus_di, minus_di

def detect_regime(df, lookback=30):
    """
    Classify the market regime over the last `lookback` candles.
    Returns a dict with regime classification and supporting metrics.
    """
    if df.empty or len(df) < max(50, lookback + ADX_PERIOD):
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # MA alignment
    ma10 = close.rolling(MA_SHORT).mean()
    ma20 = close.rolling(MA_MEDIUM).mean()
    ma50 = close.rolling(MA_LONG).mean()

    ma10_above_20 = (ma10 > ma20).iloc[-lookback:].mean()
    ma10_above_50 = (ma10 > ma50).iloc[-lookback:].mean() if len(df) >= MA_LONG else 0
    ma20_above_50 = (ma20 > ma50).iloc[-lookback:].mean() if len(df) >= MA_LONG else 0

    # MA slope (normalized)
    ma20_slope = (ma20.iloc[-1] / ma20.iloc[-10] - 1) * 100 if len(df) >= 10 else 0
    ma10_slope = (ma10.iloc[-1] / ma10.iloc[-5] - 1) * 100 if len(df) >= 5 else 0

    # RSI position
    rsi = df["rsi"].iloc[-1] if "rsi" in df.columns else 50
    rsi_avg = df["rsi"].iloc[-lookback:].mean() if "rsi" in df.columns else 50
    rsi_range = df["rsi"].iloc[-lookback:].max() - df["rsi"].iloc[-lookback:].min()

    # ADX (trend strength)
    adx_val, plus_di, minus_di = adx(high, low, close, ADX_PERIOD)
    adx_now = adx_val.iloc[-1] if not adx_val.isna().all() else 0
    adx_avg = adx_val.iloc[-lookback:].mean()

    # Volume
    vol_sma = volume.rolling(VOL_SMA_PERIOD).mean()
    vol_avg = volume.iloc[-lookback:].mean()
    vol_current = volume.iloc[-1]
    vol_ratio = vol_current / vol_avg if vol_avg > 0 else 1.0
    vol_ratio_avg = (volume.iloc[-lookback:] / vol_sma.iloc[-lookback:]).mean()

    # BB width (volatility)
    bb_std = close.rolling(BB_WINDOW).std()
    bb_width = (bb_std / close.rolling(BB_WINDOW).mean()).iloc[-1]

    # Range-bound check: how often does price oscillate around MA20?
    price_vs_ma20 = ((close - ma20) / ma20 * 100).iloc[-lookback:]
    oscillates = (price_vs_ma20 > 0).mean()
    range_score = min(abs(oscillates - 0.5) * 2, 1.0)  # 0 = always same side, 1 = 50/50 split

    # Volatility (ATR-based)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(ATR_PERIOD).mean()
    atr_pct = (atr.iloc[-1] / close.iloc[-1] * 100) if not atr.isna().all() and close.iloc[-1] > 0 else 0

    # Count MA crosses in last lookback candles
    ma_crosses = ((ma10 > ma20) != (ma10.shift(1) > ma20.shift(1))).iloc[-lookback:].sum()

    # Score each regime
    trend_score = 0.0
    chop_score = 0.0

    # ADX contribution
    if adx_now >= 30:
        trend_score += 0.4
    elif adx_now >= 20:
        trend_score += 0.2
        chop_score += 0.1
    else:
        chop_score += 0.4

    # MA alignment
    if ma10_above_20 > 0.8:
        trend_score += 0.3
    elif ma10_above_20 < 0.3:
        chop_score += 0.3

    # Oscillation (low oscillation = trending, high = choppy)
    if range_score < 0.3:
        trend_score += 0.2
    elif range_score > 0.6:
        chop_score += 0.2

    # MA cross frequency
    if ma_crosses <= 3:
        trend_score += 0.2
    elif ma_crosses >= 8:
        chop_score += 0.3

    # RSI concentration (chopped = RSI stuck around 50)
    if rsi_range < 15:
        chop_score += 0.3
    elif rsi_avg > 58 or rsi_avg < 42:
        trend_score += 0.2

    # Normalize
    total = trend_score + chop_score
    if total > 0:
        trend_pct = trend_score / total * 100
        chop_pct = chop_score / total * 100
    else:
        trend_pct, chop_pct = 50, 50

    # Determine regime label
    if trend_pct >= 60:
        if adx_now >= 40:
            regime = "STRONG_TREND"
        else:
            regime = "TRENDING"
    elif chop_pct >= 60:
        if bb_width < 0.02:
            regime = "LOW_VOL"
        else:
            regime = "CHOPPY"
    else:
        regime = "RANGE_BOUND"

    # Trend direction
    if regime in ("STRONG_TREND", "TRENDING"):
        direction = "LONG" if ma20_slope > 0 else "SHORT"
    elif regime == "RANGE_BOUND":
        # Still determine slight bias
        direction = "LONG" if rsi < 45 else ("SHORT" if rsi > 55 else "NEUTRAL")
    else:
        direction = "NEUTRAL"

    # Adaptive entry thresholds based on regime
    thresholds = get_adaptive_thresholds(regime)

    return {
        "regime": regime,
        "direction": direction,
        "trend_score": round(trend_pct, 1),
        "chop_score": round(chop_pct, 1),
        "adx": round(adx_now, 1),
        "rsi": round(rsi, 1),
        "rsi_avg": round(rsi_avg, 1),
        "rsi_range": round(rsi_range, 1),
        "ma_crosses": int(ma_crosses),
        "ma20_slope": round(ma20_slope, 3),
        "vol_ratio": round(vol_ratio, 2),
        "vol_ratio_avg": round(vol_ratio_avg, 2),
        "atr_pct": round(atr_pct, 2),
        "bb_width": round(bb_width, 4),
        "ma10_above_20": round(ma10_above_20 * 100, 1),
        "oscillates": round(range_score, 2),
        "lookback": lookback,
        "thresholds": thresholds,
    }

def get_adaptive_thresholds(regime):
    """
    Return recommended entry/exit thresholds for each regime.
    """
    base = {
        "rsi_buy_zone": (40, 55),   # buy when RSI in this range
        "rsi_sell_zone": (50, 70),  # sell when RSI in this range (for shorts)
        "min_vol_ratio": 0.8,
        "max_vol_ratio": 5.0,
        "entry_type": "momentum",   # momentum = ride the trend, mean_rev = fade extremes
        "stop_multiplier": 1.5,     # ATR multiplier for stops
        "tp_multiplier": 2.5,       # R:R for exits
        "max_hold_bars": 48,        # exit after this many bars if no target hit
    }

    if regime == "STRONG_TREND":
        return {
            **base,
            "rsi_buy_zone": (45, 55),
            "entry_type": "momentum",
            "stop_multiplier": 1.0,
            "tp_multiplier": 3.0,
            "max_hold_bars": 72,
        }
    elif regime == "TRENDING":
        return {
            **base,
            "rsi_buy_zone": (40, 55),
            "entry_type": "momentum",
            "stop_multiplier": 1.25,
            "tp_multiplier": 2.5,
            "max_hold_bars": 48,
        }
    elif regime == "RANGE_BOUND":
        return {
            **base,
            "rsi_buy_zone": (35, 50),
            "entry_type": "mean_rev",
            "stop_multiplier": 2.0,
            "tp_multiplier": 2.0,
            "max_hold_bars": 24,
        }
    elif regime == "CHOPPY":
        return {
            **base,
            "rsi_buy_zone": (30, 45),
            "entry_type": "mean_rev",
            "stop_multiplier": 2.5,
            "tp_multiplier": 1.5,
            "max_hold_bars": 12,
        }
    else:  # LOW_VOL
        return {
            **base,
            "rsi_buy_zone": (40, 50),
            "entry_type": "wait",
            "stop_multiplier": 2.0,
            "tp_multiplier": 2.0,
            "max_hold_bars": 24,
        }

def get_entry_signal(df, regime_info):
    """
    Given current regime, determine if an entry signal fires.
    Much stricter in choppy/low-vol regimes.
    """
    if df.empty or regime_info is None:
        return False, "no_data"

    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    t = regime_info["thresholds"]
    rsi_lo, rsi_hi = t["rsi_buy_zone"]

    regime = regime_info["regime"]
    entry_type = t["entry_type"]

    if entry_type == "wait":
        return False, "wait_mode"

    if entry_type == "momentum":
        # Trend continuation: RSI pullback then cross up through zone
        rsi_cross = (row["rsi"] > rsi_lo) & (prev["rsi"] <= rsi_lo)
        price_ok = row.get("price_vs_ma", 0) > 0
        vol_ok = row.get("vol_ratio", 1) >= t["min_vol_ratio"]
        if rsi_cross and price_ok and vol_ok:
            return True, f"momentum_entry_rsi_reclaim"
        return False, "no_signal"

    elif entry_type == "mean_rev":
        # Mean reversion: RSI at extreme, bouncing
        rsi_extreme = (row["rsi"] < rsi_lo) and (prev["rsi"] < rsi_lo)
        bb_lower = row["bb_percent"] < 0.3 if "bb_percent" in row.index else False
        vol_ok = row.get("vol_ratio", 1) >= t["min_vol_ratio"]
        if rsi_extreme and bb_lower and vol_ok:
            return True, "mean_rev_bounce"
        return False, "no_signal"

    return False, "no_signal"

# -- CLI -----------------------------------------------------------------------

def compute_all_indicators(df):
    """Add all needed indicators to a raw OHLCV dataframe."""
    if df.empty or len(df) < 30:
        return df

    d = df["close"].diff()
    g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
    l = (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + g / l.replace(0, np.nan)))

    df["ma10"] = df["close"].rolling(MA_SHORT).mean()
    df["ma20"] = df["close"].rolling(MA_MEDIUM).mean()
    df["ma50"] = df["close"].rolling(MA_LONG).mean()

    df["vol_sma"] = df["volume"].rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma"]

    bb_std = df["close"].rolling(BB_WINDOW).std()
    df["bb_mid"] = df["close"].rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_percent"] = (df["close"] - df["bb_lower"]) / bb_range.replace(0, np.nan)

    df["price_vs_ma"] = (df["close"] - df["ma20"]) / df["ma20"] * 100

    return df

def main():
    parser = argparse.ArgumentParser(description="Market regime detector")
    parser.add_argument("--timeframe", "-t", default="1h", choices=["15m","1h","4h"])
    parser.add_argument("--symbol", "-s", default="BTC/USDT")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"[REGIME DETECTOR]")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    exchange = ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    exchange.load_markets()

    # Multi-pair regime check
    pairs = ["BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","ADA/USDT","ARB/USDT","LINK/USDT"]

    print(f"  {'Pair':<12} {'Regime':<16} {'Dir':<8} {'ADX':>5} {'RSI':>5}  "
          f"{'Trend%':>7} {'Chop%':>6} {'MAxs':>4}  {'Entry Type':<10} {'Signal'}")
    print(f"  {'-'*12} {'-'*16} {'-'*8} {'-'*5} {'-'*5}  "
          f"{'-'*7} {'-'*6} {'-'*4}  {'-'*10} {'-'*10}")

    for pair in pairs:
        sys.stdout.write(f"  Checking {pair}...")
        sys.stdout.flush()

        try:
            candles = exchange.fetch_ohlcv(pair, args.timeframe, limit=200)
        except Exception as e:
            print(f"\r  {pair:<12} Error: {e}")
            continue

        if not candles:
            print(f"\r  {pair:<12} No data")
            continue

        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)

        df = compute_all_indicators(df)
        regime_info = detect_regime(df)

        if regime_info is None:
            print(f"\r  {pair:<12} Insufficient data")
            continue

        has_signal, signal_name = get_entry_signal(df, regime_info)
        sig_str = signal_name if not has_signal else signal_name + " <<<"

        print(f"\r  {pair:<12} {regime_info['regime']:<16} {regime_info['direction']:<8} "
              f"{regime_info['adx']:>5.1f} {regime_info['rsi']:>5.1f}  "
              f"{regime_info['trend_score']:>6.1f}% {regime_info['chop_score']:>5.1f}% "
              f"{regime_info['ma_crosses']:>4}  "
              f"{regime_info['thresholds']['entry_type']:<10} {sig_str}")

    print(f"\n{'='*60}")
    print(f"[REGIME GUIDE]")
    print(f"  STRONG_TREND  -- Follow momentum. Entries on RSI pullback. Target 3:1 R:R.")
    print(f"  TRENDING       -- Momentum entries. RSI reclaim from 40-55 zone.")
    print(f"  RANGE_BOUND    -- Mean reversion. Buy RSI < 35, sell RSI > 55. Tight stops.")
    print(f"  CHOPPY         -- Wait or very selective fades. Stops wide. Target 1.5:1.")
    print(f"  LOW_VOL        -- Sit this out. No edge until volatility picks up.")
    print(f"\n  Direction: LONG = bullish trend, SHORT = bearish trend, NEUTRAL = no bias")
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
