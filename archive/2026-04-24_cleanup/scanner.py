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

# Bull/Bear integration
BULL_BEAR_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\branches\signal_test\bull_bear_results.json"

def load_bull_bear_scores():
    """Load pre-computed bull/bear conviction scores."""
    if not os.path.exists(BULL_BEAR_FILE):
        return {}
    try:
        with open(BULL_BEAR_FILE) as f:
            data = json.load(f)
            return data.get('results', {})
    except:
        return {}

def get_bull_bear_conviction(pair, bb_scores):
    """Get bull/bear conviction for a pair."""
    pair_key = pair.replace('/', '_')
    data = bb_scores.get(pair_key, {})
    if not data or 'verdict' not in data:
        return None
    verdict = data['verdict']
    score = verdict.get('score', 0)
    conf = verdict.get('confidence', 0.5)
    
    if score >= 50 and conf >= 0.6:
        return f"STRONG ({score:+d})"
    elif score >= 30 and conf >= 0.5:
        return f"MODERATE ({score:+d})"
    elif score > 0:
        return f"WEAK ({score:+d})"
    elif score == 0:
        return f"NEUTRAL"
    else:
        return f"AVOID ({score:+d})"

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
MAJORS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]
# Chain tags for sector context
CHAIN_TAGS = {
    "ETH/USDT": "Ethereum",
    "SOL/USDT": "Solana",
    "BTC/USDT": "Bitcoin",
    "XRP/USDT": "Ripple",
}
RATE_LIMIT_DELAY = 0.05
DEFAULT_RISK_PCT = 2.0
DEFAULT_RR = 3.5
WATCHLIST_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\daily_watchlist.txt"
WHALE_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\whale_watchlist.txt"
VOL_WAKE_THRESHOLD = 2.0   # volume spike required to flag as "newly active"
VOL_WAKE_LOOKBACK = 20      # bars to compare avg volume against
# ------------------------------------------------------------------------------

# -- Exchange ------------------------------------------------------------------

def load_whale_scores():
    """Load whale activity scores from whale_watchlist.txt.
    Returns dict: symbol -> whale_score (0-100)
    """
    scores = {}
    if not os.path.exists(WHALE_FILE):
        return scores
    for line in open(WHALE_FILE):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            symbol = parts[0].strip()
            score = 50  # default
            for part in parts[1:]:
                part = part.strip()
                if part.startswith("score="):
                    try:
                        score = int(part.split("=")[1].strip())
                    except:
                        pass
            scores[symbol] = score
    return scores

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
        # Format: "  1.  | ENA/USDT   | A+    | 89"
        line = line.replace("|", "")
        parts = line.split()
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 4:
            comp_raw = parts[3].replace('%', '')
            sym, grade, comp = parts[1], parts[2], int(float(comp_raw))
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
    au_pairs = load_au_pairs()
    usdt_tickers = []
    for t in tickers:
        sym = t.get("symbol", "")
        if "/USDT" in sym and t.get("active", True):
            base = sym.replace("/USDT", "")
            if au_pairs is not None and base not in au_pairs:
                continue  # Skip pairs not on KuCoin AU
            vol = float(t.get("vol", 0) or 0) * float(t.get("last", 0) or 0)
            if vol > 0:
                usdt_tickers.append((sym, vol))
    usdt_tickers.sort(key=lambda x: x[1], reverse=True)
    pairs = [s[0] for s in usdt_tickers[:limit]]
    return pairs if pairs else DEFAULT_WATCHLIST[:limit]

AU_PAIRS_FILE = os.path.join(os.path.dirname(__file__), "kucoin_au_pairs.txt")

def load_au_pairs():
    path = AU_PAIRS_FILE
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return {line.strip() for line in f if line.strip()}

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
    ma10 = df["ma10"] if "ma10" in df.columns else (df["ma20"] if "ma20" in df.columns else df["close"])
    ma20 = df["ma20"] if "ma20" in df.columns else df["close"]
    adx_series = df["adx"] if "adx" in df.columns else None
    rsi_series = df["rsi"] if "rsi" in df.columns else None

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

    # LONG ONLY -- block SHORT signals for spot trading
    if regime_info["direction"] == "SHORT":
        return None, {"blocked": "short_not_supported"}

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
    risk_amount = 1000 * (risk_pct / 100)
    units = risk_amount / (entry_price * stop_pct / 100)
    cost = units * entry_price
    if cost > 1000:
        units = 1000 / entry_price
        cost = 1000

    return {
        "stop_price": round(stop, 8),
        "stop_pct": round(stop_pct, 2),
        "tp_price": round(tp_price, 8),
        "tp_pct": round(tp_pct, 2),
        "units": round(units, 4),
        "risk_amt": round(risk_amount, 4),
        "cost": round(cost, 4),
    }

# -- Majors Bias Report ------------------------------------------------------

def run_majors_bias(exchange, timeframe):
    """Run regime check on major pairs and output a directional bias report."""
    print(f"\n{'='*70}")
    print(f"[MAJORS BIAS CHECK] {datetime.now().strftime('%Y-%m-%d %H:%M')} AEST")
    print(f"   BTC | ETH | SOL | XRP — chain context included")
    print(f"{'='*70}\n")

    results = []
    for symbol in MAJORS:
        df = fetch_ohlcv(exchange, symbol, timeframe)
        if df.empty:
            continue
        df = add_indicators(df)
        regime = detect_regime(df)
        if regime is None:
            continue
        r = regime
        chain = CHAIN_TAGS.get(symbol, "Unknown")
        # Signal strength indicator
        if r["regime"] == "STRONG_TREND" and r["direction"] == "LONG":
            bias = "++"
        elif r["regime"] == "STRONG_TREND" and r["direction"] == "SHORT":
            bias = "--"
        elif r["regime"] == "TRENDING" and r["direction"] == "LONG":
            bias = "+"
        elif r["regime"] == "TRENDING" and r["direction"] == "SHORT":
            bias = "-"
        elif r["regime"] == "RANGE_BOUND":
            bias = "~"
        else:
            bias = "-"
        results.append({
            "symbol": symbol,
            "chain": chain,
            "regime": r["regime"],
            "direction": r["direction"],
            "adx": r["adx"],
            "rsi": r["rsi"],
            "bias": bias,
            "thresholds": r["thresholds"],
        })

    # Header
    print(f"  {'Symbol':<12} {'Chain':<10} {'Regime':<14} {'Dir':<8} {'ADX':>5} {'RSI':>5}  {'Signal'}")
    print(f"  {'-'*12} {'-'*10} {'-'*14} {'-'*8} {'-'*5} {'-'*5}  {'-'*6}")
    for r in results:
        bias_str = r["bias"] + " " * max(0, 3 - len(r["bias"]))
        regime_str = r["regime"][:14]
        print(f"  {r['symbol']:<12} {r['chain']:<10} {regime_str:<14} {r['direction']:<8} "
              f"{r['adx']:>5.1f} {r['rsi']:>5.1f}  [{bias_str}]")

    # Overall bias verdict
    btc = next((r for r in results if r["symbol"] == "BTC/USDT"), None)
    btc_bull = btc and btc["direction"] == "LONG" and btc["regime"] in ("STRONG_TREND", "TRENDING")
    btc_bear = btc and btc["direction"] == "SHORT" and btc["regime"] in ("STRONG_TREND", "TRENDING")

    eth = next((r for r in results if r["symbol"] == "ETH/USDT"), None)
    eth_bull = eth and eth["direction"] == "LONG" and eth["regime"] in ("STRONG_TREND", "TRENDING")

    sol = next((r for r in results if r["symbol"] == "SOL/USDT"), None)
    sol_bull = sol and sol["direction"] == "LONG" and sol["regime"] in ("STRONG_TREND", "TRENDING")

    long_count = sum(1 for r in results if r["direction"] == "LONG")
    short_count = sum(1 for r in results if r["direction"] == "SHORT")

    print()
    if btc_bear:
        verdict = "BEARISH — BTC in downtrend, reduce exposure or skip LONG signals"
    elif btc_bull and long_count >= 3:
        verdict = "BULLISH — BTC confirmed + majority aligned, trust LONG signals"
    elif btc_bull and long_count >= 2:
        verdict = "CAUTIOUSLY BULLISH — BTC confirmed, watching for confirmation"
    elif btc_bull and long_count == 1:
        verdict = "BTC BULL / ALTS NEUTRAL — BTC leading, alt signals lower confidence"
    elif long_count >= 3:
        verdict = "MIXED (no BTC confirmation) — alts moving but BTC unclear"
    elif short_count >= 3:
        verdict = "BEARISH — majority short signals, stay out or size down"
    elif short_count > 0 and long_count > 0:
        verdict = f"MIXED — {long_count} LONG / {short_count} SHORT, be selective"
    else:
        verdict = "UNCLEAR — no strong directional signal across majors"

    print(f"  >>> MARKET BIAS: {verdict}")
    print(f"\n{'='*70}")
    print(f"  Chain watch:")
    eth_bull = any(r["symbol"] == "ETH/USDT" and r["direction"] == "LONG" for r in results)
    sol_bull = any(r["symbol"] == "SOL/USDT" and r["direction"] == "LONG" for r in results)
    if eth_bull:
        print(f"    ETH chain HOT — watch ERC-20 plays (check ETH tokens for momentum)")
    if sol_bull:
        print(f"    SOL chain HOT — watch SPL tokens for follow-through)")
    if not eth_bull and not sol_bull:
        print(f"    No chain momentum detected — stay patient")
    print(f"{'='*70}\n")

    return results

def run_newly_active_alert(exchange, timeframe="1hour", lookback=20, vol_mult=2.0):
    """"Scan all USDT pairs for ones with sudden volume spikes — pre-pump detection."""
    print(f"\n{'='*70}")
    print(f"[NEWLY ACTIVE ALERT] {datetime.now().strftime('%Y-%m-%d %H:%M')} AEST")
    print(f"   Looking for coins waking up — vol spike vs {lookback}-bar avg")
    print(f"{'='*70}\n")

    try:
        raw = exchange.request("market/allTickers", "public", "GET")
        tickers = (raw.get("data") or {}).get("ticker", []) or []
    except Exception as e:
        print(f"Failed to fetch ticker list: {e}")
        return []

    # Top 100 USDT pairs by volume — scan only these for speed
    usdt_tickers = [
        t for t in tickers
        if "/USDT" in t["symbol"] or t.get("symbolName", "").endswith("-USDT")
    ]
    usdt_tickers.sort(key=lambda x: float(x.get("volValue", 0) or 0), reverse=True)
    usdt_pairs = [t["symbol"] for t in usdt_tickers[:100]]
    print(f"[*] Scanning {len(usdt_pairs)} USDT pairs for volume wake-ups...\n")

    alerts = []
    scanned = 0

    for sym in usdt_pairs:
        try:
            df = fetch_ohlcv(exchange, sym, timeframe, limit=lookback + 5)
            if df.empty or len(df) < lookback:
                continue

            recent_vol = df["volume"].iloc[-3:].mean()
            hist_avg   = df["volume"].iloc[-lookback:-3].mean()
            if hist_avg <= 0:
                continue

            vol_ratio = recent_vol / hist_avg

            if vol_ratio >= vol_mult:
                price_now    = float(df["close"].iloc[-1])
                price_6h_ago = float(df["close"].iloc[-7]) if len(df) >= 7 else float(df["close"].iloc[0])
                price_chg   = (price_now - price_6h_ago) / price_6h_ago * 100

                alerts.append({
                    "symbol": sym,
                    "vol_ratio": round(vol_ratio, 2),
                    "recent_vol": int(recent_vol),
                    "hist_avg": int(hist_avg),
                    "price_chg_6h": round(price_chg, 2),
                    "price_now": price_now,
                })
            scanned += 1
        except Exception:
            continue
        time.sleep(0.05)

    if not alerts:
        print(f"[+] No newly active pairs detected. Scanned {scanned} pairs.")
        return []

    alerts.sort(key=lambda x: -x["vol_ratio"])

    print(f"[!] {len(alerts)} newly active pair(s) detected:\n")
    print(f"  {'Symbol':<14} {'Vol Ratio':>9} {'6h Chg':>7} {'Price':>10}  {'Note'}")
    print(f"  {'-'*14} {'-'*9} {'-'*7} {'-'*10}  {'-'*30}")
    for a in alerts:
        if a["vol_ratio"] >= 3.0:
            note = "VOL SPIKE - strong early signal"
        elif a["price_chg_6h"] > 10:
            note = "Already pumped - may be late"
        elif a["price_chg_6h"] > 5:
            note = "Early move - watch for continuation"
        else:
            note = "Waking up - watch for break"
        print(f"  {a['symbol']:<14} {a['vol_ratio']:>8.1f}x {a['price_chg_6h']:>+7.1f}% "
              f"${a['price_now']:>9.5f}  {note}")
    print(f"\n  Total scanned: {scanned} pairs")
    print(f"{'='*70}\n")
    return alerts


def rsi(close):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

def main():
    parser = argparse.ArgumentParser(description="KuCoin momentum scanner v4")
    parser.add_argument("--timeframe", "-t", default=DEFAULT_TIMEFRAME,
                        choices=["15m","1h","4h","1d"])
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--capital", type=float, default=1000.0)
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--rr", type=float, default=DEFAULT_RR)
    parser.add_argument("--min-score", type=float, default=40)
    parser.add_argument("--majors", action="store_true",
                        help="Run majors bias check: BTC, ETH, SOL, XRP regime report")
    parser.add_argument("--newly-active", action="store_true",
                        help="Scan for newly waking up coins with volume spikes")
    args = parser.parse_args()

    # -- Majors bias mode (no scan needed)
    if args.majors:
        exchange = get_kucoin()
        run_majors_bias(exchange, args.timeframe)
        return

    if args.newly_active:
        exchange = get_kucoin()
        run_newly_active_alert(exchange, args.timeframe)
        return

    print(f"\n{'='*90}")
    print(f"[SCANNER v4] KuCoin -- Momentum + Volume + Divergence + Candles + Regime")
    print(f"   Timeframe: {args.timeframe}  |  Top {args.top} signals")
    print(f"   Capital: ${args.capital:.2f}  |  Risk: {args.risk}%/trade")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")

    exchange = get_kucoin()
    whale_scores = load_whale_scores()
    if whale_scores:
        scored = sum(1 for v in whale_scores.values() if v > 50)
        print(f"[*] Loaded whale scores for {len(whale_scores)} pairs ({scored} with ACCUMULATION signal).")
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

            whale_score = whale_scores.get(symbol, 50)
            whale_boost = max(0, whale_score - 50) * 0.2  # +0 to +10 for ACCUMULATION pairs
            boosted_score = score + whale_boost

            # Calculate bull/bear conviction score
            rsi_val = regime_info["rsi"]
            ema_dist = round(row.get("ema12_dist_pct", 0), 2)
            vol_ratio = round(row["vol_ratio"], 2)
            
            bull_pts = 0
            bear_pts = 0
            
            if 35 <= rsi_val <= 45:
                bull_pts += 30
            elif rsi_val < 35:
                bull_pts += 15
            elif rsi_val > 70:
                bear_pts += 25
            elif rsi_val > 55:
                bear_pts += 10
            
            if -1.5 <= ema_dist <= 1.5:
                bull_pts += 20
            elif ema_dist > 3:
                bear_pts += 15
            elif ema_dist < -3:
                bear_pts += 20
            
            if vol_ratio >= 2.0:
                bull_pts += 15
            elif vol_ratio >= 1.5:
                bull_pts += 10
            elif vol_ratio < 1.0:
                bear_pts += 10
            
            total_pts = bull_pts + bear_pts
            if total_pts > 0:
                bb_score = int(((bull_pts - bear_pts) / total_pts) * 100)
            else:
                bb_score = 0
            bb_score = max(-100, min(100, bb_score))
            
            if bb_score >= 50:
                bb_rec = "ENTER"
            elif bb_score >= 30:
                bb_rec = "ENTER"
            elif bb_score > 0:
                bb_rec = "REDUCE"
            else:
                bb_rec = "SKIP"

            all_signals.append({
                "symbol": symbol,
                "regime": regime_info["regime"],
                "direction": regime_info["direction"],
                "score": score,
                "boosted_score": round(boosted_score, 1),
                "whale_score": whale_score,
                "adx": regime_info["adx"],
                "rsi": regime_info["rsi"],
                "ema_dist": ema_dist,
                "entry": entry,
                "support": support,
                "resistance": resistance,
                "vol_ratio": vol_ratio,
                "vol_spike": bool(row.get("volume_spike_1_5x", False)),
                "confirmations": ", ".join(conf_parts[:6]),
                "bull_bear_score": bb_score,
                "bull_bear_rec": bb_rec,
                "bull_bear_size": 50 if bb_score >= 50 else (25 if bb_score >= 30 else (15 if bb_score > 0 else 0)),
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
        near = []
        for sym in pairs[:20]:
            try:
                r = detect_regime(fetch_ohlcv(exchange, sym, args.timeframe), 30)
                if r:
                    near.append((sym, r))
            except Exception:
                pass
        near = [(sym, r) for sym, r in near if r.get("rsi", 50) < r.get("thresholds", {}).get("rsi_lo", 40) + 15]
        near.sort(key=lambda x: x[1].get("rsi", 50))
        for sym, r in near[:5]:
            lo = r.get("thresholds", {}).get("rsi_lo", 40)
            print(f"  {sym:<12} RSI={r['rsi']:.1f}  zone=<{lo:.0f}  [{r['regime']}]")
        print()
        return

    all_signals.sort(key=lambda x: x["boosted_score"], reverse=True)

    bb_scores = load_bull_bear_scores()
    
    print(f"\n[SIGNALS] Top Setups (score >= {args.min_score}):\n")
    print(f"  {'Symbol':<12} {'Regime':<14} {'Dir':<6} {'Score':>6}  {'BB':<12} {'Entry':>12}  "
          f"{'Support':>12} {'Resistance':>12}  {'Vol':>5} {'Confirms'}")
    print(f"  {'-'*12} {'-'*14} {'-'*6} {'-'*6}  {'-'*12} {'-'*12}  "
          f"{'-'*12} {'-'*12}  {'-'*5} {'-'*25}")
    for s in all_signals[:args.top]:
        sup = '${:.6f}'.format(s["support"]) if s["support"] else "N/A"
        res = '${:.6f}'.format(s["resistance"]) if s["resistance"] else "N/A"
        vol_s = str(s["vol_ratio"]) + "x"
        whale_s = str(s.get('whale_score', 50)) + "/100"
        boost_delta = round(s.get('boosted_score', s['score']) - s['score'], 1)
        boost_s = ("+" + str(boost_delta)) if boost_delta > 0 else "-"
        bb = get_bull_bear_conviction(s['symbol'], bb_scores) or "N/A"
        print(f"  {s['symbol']:<12} {s['regime']:<14} {s['direction']:<6} {s['score']:>6} {bb:<12} "
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
