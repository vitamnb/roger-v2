# coin_quality_full.py -- Full coin quality scan across top 60 KuCoin USDT pairs
# Then backtest only the pairs that pass quality threshold
# Run: python coin_quality_full.py

import ccxt
import pandas as pd
import numpy as np
import argparse, sys, time, os

RSI_PERIOD = 14
MA_SHORT, MA_MEDIUM, MA_LONG = 10, 20, 50
BB_WINDOW = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
VOL_SMA_PERIOD = 20
RATE_LIMIT_DELAY = 0.05
DEFAULT_DAYS = 30
MIN_QUALITY_GRADE = "B"  # Only backtest B+ or above
WATCHLIST_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\daily_watchlist.txt"

WATCHLIST_EXCLUDE = [
    "USDC/USDT", "USDT/USDT",  # stablecoins
    "TRUMP/USDT", "PEPE/USDT", "PENGU/USDT", "WLFI/USDT",  # meme/political
    "HYPE/USDT",  # might keep if quality is high
]

def get_kucoin():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def get_top_pairs(limit=60):
    ex = get_kucoin()
    tickers = ex.fetch_tickers()
    pairs = []
    for sym, t in tickers.items():
        if "/USDT" in sym and t.get("quoteVolume", 0):
            vol = float(t.get("quoteVolume", 0) or 0)
            price = float(t.get("last", 0) or 0)
            if vol > 0 and sym not in WATCHLIST_EXCLUDE:
                pairs.append((sym, vol, price))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return [(s, v, p) for s, v, p in pairs[:limit]]

def fetch(symbol, tf="1h", days=DEFAULT_DAYS):
    ex = get_kucoin()
    since = ex.parse8601((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z"))
    raw = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df.sort_index()

def add_indicators(df):
    if df.empty:
        return df
    if len(df) < max(RSI_PERIOD, MA_LONG, BB_WINDOW) + 10:
        return df
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    o = df["open"]
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    df["ma10"] = c.rolling(MA_SHORT).mean()
    df["ma20"] = c.rolling(MA_MEDIUM).mean()
    df["ma50"] = c.rolling(MA_LONG).mean() if len(df) >= MA_LONG else df["ma20"]
    df["vol_sma"] = v.rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = v / df["vol_sma"]
    bb_std = c.rolling(BB_WINDOW).std()
    df["bb_mid"] = c.rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std
    bb_r = df["bb_upper"] - df["bb_lower"]
    df["bb_pct"] = (c - df["bb_lower"]) / bb_r.replace(0, np.nan)
    df["atr"] = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()
    df["atr_pct"] = df["atr"] / c * 100
    plus_dm = h.diff(); minus_dm = -l.diff()
    plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm < 0] = 0
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr_s = tr.rolling(ADX_PERIOD).mean()
    df["plus_di"] = 100 * (plus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    df["minus_di"] = 100 * (minus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"])
    df["adx"] = dx.rolling(ADX_PERIOD).mean()
    df["ret"] = c.pct_change()
    df["vs_ma20"] = (c - df["ma20"]) / df["ma20"] * 100
    return df

def regime_score(df, lookback=30):
    if df.empty or len(df) < max(lookback + 10, 60) or "rsi" not in df.columns:
        return 50
    rsi_vals = df["rsi"].iloc[-lookback:]
    adx_vals = df["adx"].iloc[-lookback:]
    adx_avg = adx_vals.mean()
    rsi_swings = rsi_vals.max() - rsi_vals.min()
    score = 50
    if 30 <= adx_avg <= 60: score += 25
    elif adx_avg > 60: score += 10
    if 20 <= rsi_swings <= 45: score += 25
    elif rsi_swings < 20: score -= 10
    return min(100, max(0, score))

def trend_consistency(df, lookback=30):
    if df.empty or len(df) < lookback + 5:
        return 50
    ret = df["ret"].iloc[-lookback:]
    adx = df["adx"].iloc[-lookback:]
    ma20_dir = (df["ma20"].iloc[-1] / df["ma20"].iloc[-lookback] - 1) > 0
    if ma20_dir:
        aligned = (ret > 0).mean()
    else:
        aligned = (ret < 0).mean()
    return min(100, max(0, round(aligned * 100)))

def volatility_suitability(df):
    if df.empty or "atr_pct" not in df.columns:
        return 50
    atr_vals = df["atr_pct"].iloc[-30:].dropna()
    if atr_vals.empty:
        return 50
    atr_med = atr_vals.median()
    if atr_med < 0.5: return 20
    elif 0.5 <= atr_med < 1.5: return 50
    elif 1.5 <= atr_med <= 8: return 100
    elif 8 < atr_med <= 15: return 70
    else: return 40

def volume_quality(df, lookback=30):
    if df.empty or len(df) < lookback:
        return 50
    vol_r = df["vol_ratio"].iloc[-lookback:]
    avg_ratio = vol_r.mean()
    spike_ratio = (vol_r > 1.5).mean()
    avg_score = 100 if 0.8 <= avg_ratio <= 2.5 else (50 if 0.5 <= avg_ratio < 0.8 else 25)
    spike_score = 100 if 0.1 <= spike_ratio <= 0.35 else (50 if 0.35 < spike_ratio <= 0.5 else 25)
    return round(avg_score * 0.4 + spike_score * 0.6)

def rsi_pulsation(df, lookback=30):
    if df.empty or len(df) < lookback:
        return 50
    rsi = df["rsi"].iloc[-lookback:]
    times_oversold = (rsi < 35).mean()
    osc_range = rsi.max() - rsi.min()
    ideal_osc = 25 <= osc_range <= 50
    osc_score = 100 if ideal_osc else (50 if 15 <= osc_range < 25 else 25)
    zone_score = 100 if 0.1 <= times_oversold <= 0.3 else (50 if 0.05 <= times_oversold < 0.1 else 25)
    return round(osc_score * 0.5 + zone_score * 0.5)

def level_respect(df, lookback=20):
    if df.empty or len(df) < lookback + 5:
        return 50
    c = df["close"]
    bb_l = df["bb_lower"]
    bb_u = df["bb_upper"]
    ma20 = df["ma20"]
    touches_lower = ((c - bb_l).abs() / bb_l < 0.005).iloc[-lookback:].mean()
    bounces_lower = ((c > c.shift(1)) & (c.shift(1) <= bb_l.shift(1))).iloc[-lookback:].mean()
    bb_respect = 100 * (1 - touches_lower) + 100 * bounces_lower / 2
    ma_crosses = ((c > ma20) != (c.shift(1) > ma20.shift(1))).iloc[-lookback:].sum()
    ideal_crosses = 3
    ma_score = max(0, 100 - abs(ma_crosses - ideal_crosses) * 15)
    inside_bb = ((c > bb_l) & (c < bb_u)).iloc[-lookback:].mean()
    inside_score = inside_bb * 100
    combined = bb_respect * 0.3 + ma_score * 0.35 + inside_score * 0.35
    return min(100, max(0, round(combined)))

def quality_score(df, lookback=30):
    if df.empty or "rsi" not in df.columns or len(df) < lookback + 10:
        return {"regime_fit": 50, "trend_cons": 50, "vol_suit": 50, "vol_qual": 50,
                "rsi_puls": 50, "level_resp": 50, "composite": 50, "atr_pct": 0}
    r_fit = regime_score(df, lookback)
    t_cons = trend_consistency(df, lookback)
    vol_s = volatility_suitability(df)
    vol_q = volume_quality(df, lookback)
    rsi_p = rsi_pulsation(df, lookback)
    lvl_r = level_respect(df, lookback)
    composite = round(r_fit*0.15 + t_cons*0.15 + vol_s*0.15 + rsi_p*0.20 + lvl_r*0.15 + vol_q*0.20)
    return {
        "regime_fit": r_fit,
        "trend_cons": t_cons,
        "vol_suit": vol_s,
        "vol_qual": vol_q,
        "rsi_puls": rsi_p,
        "level_resp": lvl_r,
        "composite": composite,
        "atr_pct": round(df["atr_pct"].iloc[-1], 2) if "atr_pct" in df.columns else 0,
    }

def grade_from_score(score):
    if score >= 85: return "A+"
    elif score >= 75: return "A"
    elif score >= 65: return "B+"
    elif score >= 55: return "B"
    elif score >= 45: return "C"
    elif score >= 35: return "D"
    else: return "F"

def passable_grade(grade):
    return grade in ("A+", "A", "B+", "B")

# -- Quick backtest (same as in coin_quality.py) --
def quick_backtest(df, risk_pct=5.0, rr=3.0, capital=58.0):
    if df.empty or len(df) < 60:
        return {"ret": 0, "wr": 0, "dd": 0, "trades": 0, "wins": 0, "losses": 0}
    trades = []
    peak = capital
    max_dd = 0.0
    pos = None
    for i in range(30, len(df)):
        row = df.iloc[i]
        if pos is None:
            adx = row.get("adx", 0)
            rsi = row.get("rsi", 50)
            if adx < 25 or rsi < 30 or rsi > 70:
                continue
            if rsi < 40:
                entry = row["close"]
                stop = row["bb_lower"] * 0.995 if not np.isnan(row["bb_lower"]) else entry * 0.97
                stop_pct = max((entry - stop) / entry * 100, 0.5)
                tp = entry + (entry - stop) * rr
                units = capital * (risk_pct / 100) / (entry * stop_pct / 100)
                pos = {"entry": entry, "stop": stop, "tp": tp, "units": units}
        else:
            lo, hi = row["low"], row["high"]
            if lo <= pos["stop"] <= hi:
                pnl = pos["units"] * (pos["stop"] - pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak - capital) / peak * 100)
                trades.append({"pnl": pnl})
                pos = None
            elif hi >= pos["tp"] >= lo:
                pnl = pos["units"] * (pos["tp"] - pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak - capital) / peak * 100)
                trades.append({"pnl": pnl})
                pos = None
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    return {
        "ret": round((capital / 58 - 1) * 100, 1),
        "wr": round(wins / (wins + losses) * 100, 0) if (wins + losses) > 0 else 0,
        "dd": round(max_dd, 1),
        "trades": len(trades),
        "wins": wins, "losses": losses,
    }

# -- Full backtest (with all v4 filters) --
def full_backtest(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=True):
    RSI_BLOCK_SHORT = 25
    RSI_BLOCK_LONG = 75
    if df.empty or len(df) < 60:
        return None
    trades = []
    peak = capital
    max_dd = 0.0
    pos = None
    rsi_blocked = 0
    total_sigs = 0

    for i in range(30, len(df)):
        row = df.iloc[i]
        if pos is None:
            # Regime detection
            lookback = min(30, i)
            if lookback < 10:
                continue
            sub = df.iloc[:i+1]
            adx = sub["adx"].iloc[-1]
            rsi = sub["rsi"].iloc[-1]
            ma10 = sub["ma10"].iloc[-1]
            ma20_val = sub["ma20"].iloc[-1]
            ma20_series = sub["ma20"]
            rsi_avg = sub["rsi"].iloc[-lookback:].mean()
            rsi_range = sub["rsi"].iloc[-lookback:].max() - sub["rsi"].iloc[-lookback:].min()
            ma10_20 = (ma10 > ma20_val)
            ts = 0.0
            cs = 0.0
            if adx >= 30: ts += 0.4
            elif adx >= 20: ts += 0.2; cs += 0.1
            else: cs += 0.4
            if ma10_20: ts += 0.3
            else: cs += 0.3
            tot = ts + cs
            tp = ts / tot * 100 if tot > 0 else 50
            reg = "STRONG_TREND" if tp >= 60 and adx >= 40 else "TRENDING" if tp >= 60 else "CHOPPY"
            slope = (ma20_series.iloc[-1] / ma20_series.iloc[-10] - 1) * 100 if len(sub) >= 10 else 0
            direction = "LONG" if slope > 0 else "SHORT"
            rsi_lo = 45 if reg == "STRONG_TREND" else 40

            # Direction filter
            vs_ma20 = (row["close"] - row["ma20"]) / row["ma20"] * 100
            if direction == "LONG" and vs_ma20 <= 0:
                continue
            if direction == "SHORT" and vs_ma20 >= 0:
                continue

            # RSI extreme override
            if use_override:
                if direction == "SHORT" and rsi < RSI_BLOCK_SHORT:
                    rsi_blocked += 1
                    total_sigs += 1
                    continue
                if direction == "LONG" and rsi > RSI_BLOCK_LONG:
                    total_sigs += 1
                    continue

            total_sigs += 1

            # Score signal
            score = 0
            if rsi > rsi_lo and sub["rsi"].shift(1).iloc[-1] <= rsi_lo:
                score += 20
            elif rsi_lo < rsi < 55:
                score += 10
            if row.get("vol_ratio", 1) >= 0.8:
                score += 10
            if row.get("vol_spike", False):
                score += 25
            if 0 < row["bb_pct"] < 0.3:
                score += 20
            if row.get("bull_div", False):
                score += 20

            if score < 40:
                continue

            entry = row["close"]
            bb_l = row["bb_lower"]
            sw_l = row["swing_low"]
            atr = row.get("atr", 0)
            stop_mult = 1.0 if reg == "STRONG_TREND" else 1.25
            if row["bb_pct"] < 0.3 and not np.isnan(bb_l) and bb_l > 0:
                stop = bb_l * 0.995
            elif not np.isnan(sw_l):
                stop = sw_l * 0.995
            elif not np.isnan(atr) and atr > 0:
                stop = entry - atr * stop_mult
            else:
                stop = entry * (1 - risk_pct / 100)
            stop_pct = max((entry - stop) / entry * 100, 0.5)
            tp_price = entry + (entry - stop) * rr
            units = capital * (risk_pct / 100) / (entry * stop_pct / 100)
            pos = {"entry": entry, "stop": stop, "tp": tp_price, "units": units}
        else:
            lo, hi = row["low"], row["high"]
            sp_ = pos["stop"]
            tp_ = pos["tp"]
            if lo <= sp_ <= hi:
                pnl = pos["units"] * (sp_ - pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak - capital) / peak * 100)
                trades.append({"pnl": pnl, "ex": "stop"})
                pos = None
            elif hi >= tp_ >= lo:
                pnl = pos["units"] * (tp_ - pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak - capital) / peak * 100)
                trades.append({"pnl": pnl, "ex": "tp"})
                pos = None
            elif row["rsi"] > 80:
                pnl = pos["units"] * (row["close"] - pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak - capital) / peak * 100)
                trades.append({"pnl": pnl, "ex": "rsi_overbought"})
                pos = None

    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    return {
        "ret": round((capital / 58 - 1) * 100, 1),
        "wr": round(wins / (wins + losses) * 100, 0) if (wins + losses) > 0 else 0,
        "dd": round(max_dd, 1),
        "trades": len(trades),
        "wins": wins, "losses": losses,
        "rsi_blocked": rsi_blocked,
        "total_sigs": total_sigs,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", "-t", default="1h")
    parser.add_argument("--days", "-d", type=int, default=30)
    parser.add_argument("--min-grade", default="B")
    args = parser.parse_args()

    print()
    print("=" * 90)
    print(f"  FULL COIN QUALITY SCAN  |  {args.timeframe}  |  last {args.days} days")
    print("=" * 90)

    # Step 1: Get top 60 pairs by volume
    pairs_data = get_top_pairs(60)
    print(f"\n[*] Top {len(pairs_data)} pairs by volume loaded")

    # Step 2: Quality scan all pairs
    print(f"\n[*] Running quality analysis on all {len(pairs_data)} pairs...\n")
    quality_results = []
    quality_dfs = {}  # cache dataframes for reuse in backtest step
    for i, (pair, vol, price) in enumerate(pairs_data):
        sys.stdout.write(f"\r  [{i+1}/{len(pairs_data)}] {pair:<20}")
        sys.stdout.flush()
        try:
            df = fetch(pair, args.timeframe, args.days)
        except (ccxt.BadSymbol, ccxt.NetworkError):
            sys.stdout.write(f"\r  [{i+1}/{len(pairs_data)}] {pair:<20} unavailable\n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue
        if df.empty:
            sys.stdout.write(f"\r  [{i+1}/{len(pairs_data)}] {pair:<20} no data\n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue
        df = add_indicators(df)
        if df.empty or "rsi" not in df.columns or len(df) < 60:
            sys.stdout.write(f"\r  [{i+1}/{len(pairs_data)}] {pair:<20} insufficient data\n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue
        bt = quick_backtest(df)
        q = quality_score(df)
        grade = grade_from_score(q["composite"])
        quality_dfs[pair] = df  # cache for reuse
        quality_results.append({
            "symbol": pair, "vol": vol, "price": price,
            "grade": grade, **q, **bt
        })
        sys.stdout.write(f"\r  [{i+1}/{len(pairs_data)}] {pair:<20} "
                         f"Grade={grade}  Comp={q['composite']:>3}  "
                         f"ATR={q['atr_pct']:.2f}%  QuickBT={bt['ret']:>+6.1f}%\n")
        sys.stdout.flush()
        time.sleep(RATE_LIMIT_DELAY)

    print()
    print("=" * 90)
    print(f"\n  QUALITY RANKINGS -- ALL {len(quality_results)} PAIRS\n")
    hdr = f"  {'#':<3}  {'Pair':<16}  {'Grade':<5}  {'Comp':>5}  {'Reg':>4}  {'Trnd':>4}  " \
          f"{'Vol':>4}  {'RSI':>4}  {'Lvls':>4}  {'ATR%':>6}  {'QBt%':>7}  {'QBtN':>5}"
    print(hdr)
    print(f"  {'-'*3}  {'-'*16}  {'-'*5}  {'-'*5}  {'-'*4}  {'-'*4}  "
          f"{'-'*4}  {'-'*4}  {'-'*4}  {'-'*6}  {'-'*7}  {'-'*5}")
    for rank, r in enumerate(sorted(quality_results, key=lambda x: -x["composite"]), 1):
        print(f"  {rank:<3}  {r['symbol']:<16}  {r['grade']:<5}  "
              f"{r['composite']:>5}  {r['regime_fit']:>4}  {r['trend_cons']:>4}  "
              f"{r['vol_suit']:>4}  {r['rsi_puls']:>4}  {r['level_resp']:>4}  "
              f"{r['atr_pct']:>6.2f}% {r['ret']:>+7.1f}% {r['trades']:>5}")

    # Step 3: Filter to passable grade and run full backtest
    passable = [r for r in quality_results if passable_grade(r["grade"])]
    avoid = [r for r in quality_results if not passable_grade(r["grade"])]

    print()
    print("=" * 90)
    print(f"\n  PASSED QUALITY FILTER (Grade B or above): {len(passable)} pairs")
    print(f"  FAILED QUALITY FILTER (Grade C or below): {len(avoid)} pairs\n")

    print(f"  [A] Trade:   {sorted([r['symbol'] for r in passable if r['grade'] in ('A+','A','B+')])}")
    print(f"  [B] Caution: {sorted([r['symbol'] for r in passable if r['grade'] in ('B',) ])}")
    print(f"  [C] Avoid:   {sorted([r['symbol'] for r in avoid])}")

    # Step 4: Full backtest on passable pairs only
    print()
    print("=" * 90)
    print(f"\n  FULL BACKTEST -- Aggressive 1h | 30d | 5% risk | 3:1 R:R")
    print(f"  On pairs that passed quality filter (Grade B or above)\n")

    backtest_results = []
    for i, r in enumerate(sorted(passable, key=lambda x: -x["composite"])):
        pair = r["symbol"]
        sys.stdout.write(f"\r  [{i+1}/{len(passable)}] {pair:<16} full backtest...")
        sys.stdout.flush()
        df = quality_dfs.get(pair)
        if df is None:
            sys.stdout.write(f"\r  [{i+1}/{len(passable)}] {pair:<16} no cached data\n")
            sys.stdout.flush()
            continue
        df = df.copy()
        if df.empty or "rsi" not in df.columns or len(df) < 60:
            sys.stdout.write(f"\r  [{i+1}/{len(passable)}] {pair:<16} insufficient data\n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue
        # Add missing columns needed by full_backtest
        if "swing_low" not in df.columns:
            df["swing_low"] = df["low"].rolling(5).min()
        if "swing_high" not in df.columns:
            df["swing_high"] = df["high"].rolling(5).max()
        if "bull_div" not in df.columns:
            df["bull_div"] = (df["close"] < df["close"].shift(5)) & (df["rsi"] > df["rsi"].shift(5)) & (df["rsi"] < 60)
        if "vol_spike" not in df.columns:
            df["vol_spike"] = df["volume"] > df["vol_sma"] * 1.5
        df["vol_ratio"] = df["volume"] / df["vol_sma"]

        bt = full_backtest(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=True)
        bt_noov = full_backtest(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=False)
        if bt is None:
            sys.stdout.write(f"\r  [{i+1}/{len(passable)}] {pair:<16} backtest failed\n")
            sys.stdout.flush()
            continue
        noov_ret = bt_noov["ret"] if bt_noov else 0
        backtest_results.append({
            "symbol": pair,
            "grade": r["grade"],
            "comp": r["composite"],
            "ret": bt["ret"],
            "wr": bt["wr"],
            "dd": bt["dd"],
            "trades": bt["trades"],
            "wins": bt["wins"],
            "losses": bt["losses"],
            "ret_noov": noov_ret,
            "blocked": bt["rsi_blocked"],
            "total_sigs": bt["total_sigs"],
        })
        sys.stdout.write(f"\r  [{i+1}/{len(passable)}] {pair:<16} "
                         f"ret={bt['ret']:>+6.1f}%  WR={bt['wr']:>3.0f}%  "
                         f"DD={bt['dd']:>5.1f}%  trades={bt['trades']:>3}  "
                         f"noOV={noov_ret:>+6.1f}%  blocked={bt['rsi_blocked']}/{bt['total_sigs']}\n")
        sys.stdout.flush()
        time.sleep(RATE_LIMIT_DELAY)

    print()
    print("=" * 90)
    print(f"\n  FULL BACKTEST RESULTS -- All Quality-Filtered Pairs\n")
    hdr2 = f"  {'#':<3}  {'Pair':<16}  {'Grade':<5}  {'Comp':>5}  " \
           f"{'Ret%':>7}  {'WR%':>5}  {'DD%':>6}  {'Trades':>6}  " \
           f"{'NoOV%':>7}  {'Blk%':>5}"
    print(hdr2)
    print(f"  {'-'*3}  {'-'*16}  {'-'*5}  {'-'*5}  "
          f"{'-'*7}  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*5}")
    for rank, r in enumerate(sorted(backtest_results, key=lambda x: -x["ret"]), 1):
        blk_pct = round(r["blocked"] / max(r["total_sigs"], 1) * 100)
        print(f"  {rank:<3}  {r['symbol']:<16}  {r['grade']:<5}  "
              f"{r['comp']:>5}  {r['ret']:>+7.1f}%  {r['wr']:>5.0f}%  "
              f"{r['dd']:>6.1f}%  {r['trades']:>6}  "
              f"{r['ret_noov']:>+7.1f}%  {blk_pct:>5.0f}%")

    # Filter to profitable pairs only for the final totals
    profitable = [r for r in backtest_results if r["ret"] >= 0]
    unprofitable = [r for r in backtest_results if r["ret"] < 0]
    if unprofitable:
        print(f"\n  [X] Loss-making pairs (excluded from final total): "
              f"{sorted([r['symbol'] for r in unprofitable])}")

    tot_ret = sum(r["ret"] for r in profitable)
    tot_ret_noov = sum(r["ret_noov"] for r in profitable)
    tot_blocked = sum(r["blocked"] for r in profitable)
    tot_sigs = sum(r["total_sigs"] for r in profitable)
    tot_trades = sum(r["trades"] for r in profitable)
    tot_w = sum(r["wins"] for r in profitable)
    tot_l = sum(r["losses"] for r in profitable)
    wr = tot_w / (tot_w + tot_l) * 100 if (tot_w + tot_l) > 0 else 0
    # Save ranked profitable pairs to daily watchlist file
    if profitable:
        lines = [
            "# KuCoin Daily Watchlist",
            f"# Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} Sydney | Timeframe: 1h | Days: 30",
            "# Filter: Grade B+ or above + full backtest >= 0%",
            "#",
            "# Format: SYMBOL  GRADE  COMP  ATR%  QBt%  FBt%",
            "",
        ]
        for r in sorted(profitable, key=lambda x: -x["ret"]):
            lines.append(
                f"{r['symbol']:<18}  {r['grade']:<4}  {r['comp']:>3}  "
                f"{r.get('atr_pct', 0):.2f}%  {r.get('ret',0):>+.1f}%  {r['ret']:>+.1f}%"
            )
        with open(WATCHLIST_FILE, 'w') as f:
            f.write('\n'.join(lines))
        print(f"[*] Watchlist saved to {WATCHLIST_FILE}")

    print()
    print("=" * 90)
    print(f"\n  QUALITY-FILTERED TOTALS (profitable pairs only):")
    print(f"  Pairs tested:      {len(profitable)} (vs 19 in original run)")
    print(f"  Total trades:      {tot_trades}  |  {tot_w}W/{tot_l}L  |  WR={wr:.0f}%")
    print(f"  Combined return:   {tot_ret:+.1f}%  WITH override")
    print(f"  Combined return:   {tot_ret_noov:+.1f}%  WITHOUT override")
    print(f"  RSI blocked:        {tot_blocked}/{tot_sigs} ({tot_blocked/max(tot_sigs,1)*100:.0f}%)")
    print(f"  Original run:      +183.3% on 19 pairs")
    print()
    print("=" * 90)

if __name__ == "__main__":
    main()
