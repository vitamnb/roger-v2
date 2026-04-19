# backtest_full.py -- Full backtest with v4 scanner filters
# Compares WITH vs WITHOUT RSI extreme override
# Run: python backtest_full.py

import ccxt
import pandas as pd
import numpy as np
import sys, time

RSI_PERIOD = 14
MA_SHORT, MA_MEDIUM, MA_LONG = 10, 20, 50
BB_WINDOW = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
VOL_SMA_PERIOD = 20
RSI_BLOCK_SHORT = 25
RSI_BLOCK_LONG = 75
RATE_LIMIT_DELAY = 0.05

WATCHLIST = [
    "BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT",
    "ADA/USDT","AVAX/USDT","ARB/USDT","OP/USDT","NEAR/USDT",
    "APT/USDT","FIL/USDT","LINK/USDT","DOT/USDT","ATOM/USDT",
    "MATIC/USDT","UNI/USDT","LTC/USDT","ETC/USDT","XLM/USDT",
]

def get_kucoin():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def fetch_ohlcv(symbol, tf, days):
    ex = get_kucoin()
    since = ex.parse8601((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z'))
    raw = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df.sort_index()

def add_indicators(df):
    if df.empty or len(df) < max(RSI_PERIOD, MA_LONG, BB_WINDOW) + 10:
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
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_pct"] = (c - df["bb_lower"]) / bb_range.replace(0, np.nan)
    df["vs_ma20"] = (c - df["ma20"]) / df["ma20"] * 100
    df["vs_ma50"] = (c - df["ma50"]) / df["ma50"] * 100 if MA_LONG else 0
    tr1 = h - l
    tr2 = (h - c.shift(1)).abs()
    tr3 = (l - c.shift(1)).abs()
    df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()
    df["swing_low"] = l.rolling(5).min()
    df["swing_high"] = h.rolling(5).max()
    plus_dm = h.diff(); minus_dm = -l.diff()
    plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm < 0] = 0
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_s = tr.rolling(ADX_PERIOD).mean()
    df["plus_di"] = 100 * (plus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    df["minus_di"] = 100 * (minus_dm.rolling(ADX_PERIOD).mean() / atr_s)
    dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"])
    df["adx"] = dx.rolling(ADX_PERIOD).mean()
    df["rsi_prev"] = df["rsi"].shift(1)
    body = (c - o).abs()
    rng = h - l
    body_top = pd.concat([c, o], axis=1).max(axis=1)
    df["hammer"] = (
        ((body_top - l) > body * 2.0) &
        ((h - body_top) < body * 0.5) &
        (df["rsi"] < 55) &
        (body < rng * 0.3)
    )
    prev_bearish = df["close"].shift(1) < df["open"].shift(1)
    df["engulfing"] = (
        prev_bearish &
        (c > o) &
        (o < df["open"].shift(1)) &
        (c > df["close"].shift(1))
    )
    df["bull_div"] = (
        (c < c.shift(5)) &
        (df["rsi"] > df["rsi"].shift(5)) &
        (df["rsi"] < 60)
    )
    df["vol_spike"] = v > df["vol_sma"] * 1.5
    return df

def detect_regime(df, lookback=30):
    if df.empty or len(df) < lookback + ADX_PERIOD:
        return None
    c = df["close"]
    ma10 = df["ma10"]
    ma20 = df["ma20"]
    adx = df["adx"].iloc[-1]
    rsi = df["rsi"].iloc[-1]
    rsi_avg = df["rsi"].iloc[-lookback:].mean()
    rsi_range = df["rsi"].iloc[-lookback:].max() - df["rsi"].iloc[-lookback:].min()
    ma10_20 = (ma10 > ma20).iloc[-lookback:].mean()
    osc = min(abs(((c - ma20) / ma20 > 0).iloc[-lookback:].mean() - 0.5) * 2, 1.0)
    xs = int(((ma10 > ma20) != (ma10.shift(1) > ma20.shift(1))).iloc[-lookback:].sum())
    ts, cs = 0.0, 0.0
    if adx >= 30: ts += 0.4
    elif adx >= 20: ts += 0.2; cs += 0.1
    else: cs += 0.4
    if ma10_20 > 0.8: ts += 0.3
    elif ma10_20 < 0.3: cs += 0.3
    if osc < 0.3: ts += 0.2
    elif osc > 0.6: cs += 0.2
    if xs <= 3: ts += 0.2
    elif xs >= 8: cs += 0.3
    if rsi_range < 15: cs += 0.3
    elif rsi_avg > 58 or rsi_avg < 42: ts += 0.2
    tot = ts + cs
    tp = ts / tot * 100 if tot > 0 else 50
    cp = cs / tot * 100 if tot > 0 else 50
    if tp >= 60:
        reg = "STRONG_TREND" if adx >= 40 else "TRENDING"
    elif cp >= 60:
        reg = "LOW_VOL" if df["bb_pct"].iloc[-1] < 0.1 else "CHOPPY"
    else:
        reg = "RANGE_BOUND"
    slope = (ma20.iloc[-1] / ma20.iloc[-10] - 1) * 100 if len(df) >= 10 else 0
    if reg in ("STRONG_TREND", "TRENDING"):
        d = "LONG" if slope > 0 else "SHORT"
    elif reg == "RANGE_BOUND":
        d = "LONG" if rsi < 45 else ("SHORT" if rsi > 55 else "NEUTRAL")
    else:
        d = "NEUTRAL"
    if reg == "STRONG_TREND":
        t = {"rsi_lo": 45, "rsi_hi": 55, "entry": "momentum", "stop_mult": 1.0, "tp_mult": 3.0}
    elif reg == "TRENDING":
        t = {"rsi_lo": 40, "rsi_hi": 55, "entry": "momentum", "stop_mult": 1.25, "tp_mult": 2.5}
    elif reg == "RANGE_BOUND":
        t = {"rsi_lo": 35, "rsi_hi": 50, "entry": "mean_rev", "stop_mult": 2.0, "tp_mult": 2.0}
    else:
        t = {"rsi_lo": 30, "rsi_hi": 45, "entry": "mean_rev", "stop_mult": 2.5, "tp_mult": 1.5}
    return {"regime": reg, "direction": d, "adx": adx, "rsi": rsi, "t": t}

def score_signal(df, r, use_override=True):
    if df.empty or r is None:
        return None, {}
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    t = r["t"]
    sc = 0
    conf = {}

    # RSI EXTREME OVERRIDE
    if use_override:
        if r["direction"] == "SHORT" and row["rsi"] < RSI_BLOCK_SHORT:
            return None, {"blocked": "rsi_extreme_oversold"}
        if r["direction"] == "LONG" and row["rsi"] > RSI_BLOCK_LONG:
            return None, {"blocked": "rsi_extreme_overbought"}

    # Direction filter
    if r["direction"] == "LONG":
        if row["vs_ma20"] > 0:
            sc += 15; conf["above_ma20"] = True
        else:
            return None, {}
    elif r["direction"] == "SHORT":
        if row["vs_ma20"] < 0:
            sc += 15; conf["below_ma20"] = True
        else:
            return None, {}
    else:
        return None, {}

    # RSI zone
    if t["entry"] == "momentum":
        if row["rsi"] > t["rsi_lo"] and prev["rsi"] <= t["rsi_lo"]:
            sc += 20; conf["rsi_cross"] = True
        elif t["rsi_lo"] < row["rsi"] < 55:
            sc += 10; conf["rsi_zone"] = True
    elif t["entry"] == "mean_rev":
        if row["rsi"] < t["rsi_lo"]:
            sc += 20; conf["rsi_oversold"] = True

    # Volume
    if row.get("vol_spike", False):
        sc += 25; conf["vol_spike"] = True
    elif row["vol_ratio"] >= 0.8:
        sc += 10; conf["vol_ok"] = True

    # Bollinger Bands
    if 0 < row["bb_pct"] < 0.3:
        sc += 20; conf["bb_lower"] = True
    elif 0.3 <= row["bb_pct"] < 0.6:
        sc += 10; conf["bb_mid"] = True

    # Candlestick patterns
    if row.get("hammer") and conf.get("rsi_oversold"):
        sc += 15; conf["hammer"] = True
    if row.get("engulfing"):
        sc += 15; conf["engulfing"] = True
    if row.get("bull_div"):
        sc += 20; conf["bull_div"] = True

    return sc, conf

def run_backtest(df, capital, risk_pct, rr, use_override):
    trades = []
    peak = capital
    max_dd = 0.0
    pos = None
    rsi_blocked = 0
    total_sigs = 0

    for i in range(30, len(df)):
        row = df.iloc[i]
        ts = df.index[i]

        if pos is None:
            r = detect_regime(df.iloc[:i+1])
            if r is None:
                continue
            s, conf = score_signal(df.iloc[:i+1], r, use_override)
            total_sigs += 1
            if s is None:
                if conf.get("blocked"):
                    rsi_blocked += 1
                continue
            if s < 40:
                continue

            entry = row["close"]
            bb_l = row["bb_lower"]
            sw_l = row["swing_low"]
            atr = row.get("atr", 0)

            if row["bb_pct"] < 0.3 and not np.isnan(bb_l) and bb_l > 0:
                stop = bb_l * 0.995
            elif not np.isnan(sw_l):
                stop = sw_l * 0.995
            elif not np.isnan(atr) and atr > 0:
                stop = entry - atr * r["t"]["stop_mult"]
            else:
                stop = entry * (1 - risk_pct / 100)

            stop_pct = max((entry - stop) / entry * 100, 0.5)
            tp = entry + (entry - stop) * rr
            units = capital * (risk_pct / 100) / (entry * stop_pct / 100)
            pos = {
                "entry": entry, "stop": stop, "tp": tp,
                "units": units, "stop_pct": stop_pct,
                "entry_idx": i, "entry_ts": ts
            }
        else:
            lo, hi = row["low"], row["high"]
            ep = pos["entry"]
            sp_ = pos["stop"]
            tp_ = pos["tp"]

            if lo <= sp_ <= hi:
                xp, exit_reason = sp_, "stop"
            elif hi >= tp_ >= lo:
                xp, exit_reason = tp_, "tp"
            elif row["rsi"] > 80:
                xp, exit_reason = row["close"], "rsi_overbought"
            elif row["vs_ma20"] < -3:
                xp, exit_reason = row["close"], "trend_broken"
            else:
                continue

            pnl = pos["units"] * (xp - ep)
            capital += pnl
            max_dd = max(max_dd, (peak - capital) / peak * 100)
            peak = max(peak, capital)
            dur = i - pos["entry_idx"]
            ret_pct = (xp - ep) / ep * 100
            trades.append({
                "pnl": pnl, "ret": ret_pct, "ex": exit_reason,
                "cap": capital, "dur": dur
            })
            pos = None

    return trades, {
        "capital": capital, "peak": peak, "max_dd": max_dd,
        "rsi_blocked": rsi_blocked, "total_sigs": total_sigs,
        "trades": len(trades)
    }

def run_pair(symbol, tf, days, risk_pct, rr, capital=58.0):
    try:
        df = fetch_ohlcv(symbol, tf, days)
    except ccxt.BadSymbol:
        return None
    if df.empty:
        return None
    df = add_indicators(df)
    df = add_indicators(df)
    t1, c1 = run_backtest(df, capital, risk_pct, rr, use_override=True)
    t2, c2 = run_backtest(df, capital, risk_pct, rr, use_override=False)
    wins1 = sum(1 for x in t1 if x["pnl"] > 0)
    loss1 = sum(1 for x in t1 if x["pnl"] <= 0)
    wins2 = sum(1 for x in t2 if x["pnl"] > 0)
    loss2 = sum(1 for x in t2 if x["pnl"] <= 0)
    avg_w = np.mean([x["ret"] for x in t1 if x["pnl"] > 0]) if wins1 else 0
    avg_l = np.mean([x["ret"] for x in t1 if x["pnl"] <= 0]) if loss1 else 0
    return {
        "symbol": symbol,
        "trades": len(t1),
        "ret": round((c1["capital"] / capital - 1) * 100, 2),
        "ret_noov": round((c2["capital"] / capital - 1) * 100, 2),
        "dd": round(c1["max_dd"], 2),
        "dd_noov": round(c2["max_dd"], 2),
        "blocked": c1["rsi_blocked"],
        "total_sigs": c1["total_sigs"],
        "wins": wins1, "losses": loss1,
        "wins_noov": wins2, "losses_noov": loss2,
        "avg_win": round(avg_w, 2),
        "avg_loss": round(avg_l, 2),
    }

def main():
    print()
    print("=" * 85)
    print("  BACKTEST v4 -- Conservative vs Aggressive, WITH vs WITHOUT RSI Override")
    print("=" * 85)

    configs = [
        ("CONSERVATIVE", "4h", 90, 2.0, 2.0),
        ("AGGRESSIVE",   "1h", 30, 5.0, 3.0),
    ]

    for config_name, tf, days, risk_pct, rr in configs:
        print()
        print("=" * 85)
        print(f"  {config_name}  |  {tf}  |  {days} days  |  {risk_pct}% risk  |  {rr}:1 R:R  |  $58")
        print("=" * 85)

        results = []
        for i, pair in enumerate(WATCHLIST):
            sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair}  ")
            sys.stdout.flush()
            r = run_pair(pair, tf, days, risk_pct, rr, 58.0)
            if r:
                results.append(r)
                sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair:<12} {r['trades']} trades, "
                                 f"ret={r['ret']:+.1f}%  |  noOV={r['ret_noov']:+.1f}%  |  "
                                 f"blocked={r['blocked']}/{r['total_sigs']}\n")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair:<12}  no data\n")
                sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)

        print()
        hdr = f"  {'Pair':<12} {'Trades':>7}  {'WR':>5}  {'AvgW':>6}  {'AvgL':>7}  "
        hdr += f"{'Ret%':>7}  {'MaxDD%':>7}  {'NoOV%':>7}  {'NoDD%':>6}  {'Blk':>6}"
        print(hdr)
        print(f"  {'--'*6}  {'--'*4}  {'--'*3}  {'--'*3}  {'--'*4}  "
              f"{'--'*4}  {'--'*5}  {'--'*4}  {'--'*3}  {'--'*3}")
        for r in sorted(results, key=lambda x: -x["ret"]):
            wr = r["wins"] / (r["wins"] + r["losses"]) * 100 if (r["wins"] + r["losses"]) > 0 else 0
            print(f"  {r['symbol']:<12} {r['trades']:>7}  "
                  f"{wr:>5.0f}%  {r['avg_win']:>+6.2f}%  {r['avg_loss']:>+7.2f}%  "
                  f"{r['ret']:>+7.1f}%  {r['dd']:>7.1f}%  "
                  f"{r['ret_noov']:>+7.1f}%  {r['dd_noov']:>6.1f}%  "
                  f"{r['blocked']:>6}")

        tot_ret = sum(r["ret"] for r in results)
        tot_ret_noov = sum(r["ret_noov"] for r in results)
        tot_blocked = sum(r["blocked"] for r in results)
        tot_sigs = sum(r["total_sigs"] for r in results)
        tot_trades = sum(r["trades"] for r in results)
        tot_w = sum(r["wins"] for r in results)
        tot_l = sum(r["losses"] for r in results)
        wr = tot_w / (tot_w + tot_l) * 100 if (tot_w + tot_l) > 0 else 0
        print()
        print(f"  TOTALS:  {tot_trades} trades  |  {tot_w}W/{tot_l}L  |  WR={wr:.0f}%")
        print(f"  Combined return:  {tot_ret:+.1f}%  WITH override")
        print(f"  Combined return:  {tot_ret_noov:+.1f}%  WITHOUT override")
        print(f"  RSI blocked: {tot_blocked}/{tot_sigs} signals ({tot_blocked/max(tot_sigs,1)*100:.0f}%)")
        print(f"  Avg trades/pair: {tot_trades/len(results):.1f}")
        print()

    print("=" * 85)
    print("  NOTE: Fees, slippage, and liquidity NOT modelled.")
    print("  Past performance does not guarantee future results.")
    print("=" * 85)
    print()

if __name__ == "__main__":
    main()
