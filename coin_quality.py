# coin_quality.py -- Coin quality analyser
# Scores each pair on 6 dimensions relevant to the aggressive momentum strategy
# Run: python coin_quality.py [--timeframe 1h] [--days 30]

import ccxt
import pandas as pd
import numpy as np
import argparse, sys, time

RSI_PERIOD = 14
MA_SHORT, MA_MEDIUM, MA_LONG = 10, 20, 50
BB_WINDOW = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
VOL_SMA_PERIOD = 20
RATE_LIMIT_DELAY = 0.05

WATCHLIST = [
    "BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT",
    "ADA/USDT","AVAX/USDT","ARB/USDT","OP/USDT","NEAR/USDT",
    "APT/USDT","FIL/USDT","LINK/USDT","DOT/USDT","ATOM/USDT",
    "UNI/USDT","LTC/USDT","ETC/USDT","XLM/USDT",
]

def get_kucoin():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def fetch(symbol, tf, days):
    ex = get_kucoin()
    since = ex.parse8601((pd.Timestamp.utcnow()-pd.Timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z'))
    raw = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    return df.sort_index()

def indicators(df):
    if df.empty or len(df) < max(RSI_PERIOD, MA_LONG, BB_WINDOW) + 10:
        return df
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    o = df["open"]
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100-(100/(1+gain/loss.replace(0,np.nan)))
    df["ma10"] = c.rolling(MA_SHORT).mean()
    df["ma20"] = c.rolling(MA_MEDIUM).mean()
    df["ma50"] = c.rolling(MA_LONG).mean() if len(df)>=MA_LONG else df["ma20"]
    df["vol_sma"] = v.rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = v/df["vol_sma"]
    bb_std = c.rolling(BB_WINDOW).std()
    df["bb_mid"] = c.rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"]+2*bb_std
    df["bb_lower"] = df["bb_mid"]-2*bb_std
    bb_r = df["bb_upper"]-df["bb_lower"]
    df["bb_pct"] = (c-df["bb_lower"])/bb_r.replace(0,np.nan)
    df["atr"] = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1).rolling(ATR_PERIOD).mean()
    df["atr_pct"] = df["atr"]/c*100  # ATR as % of price
    plus_dm = h.diff(); minus_dm = -l.diff()
    plus_dm[plus_dm<0]=0; minus_dm[minus_dm<0]=0
    tr = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    atr_s = tr.rolling(ADX_PERIOD).mean()
    df["plus_di"] = 100*(plus_dm.rolling(ADX_PERIOD).mean()/atr_s)
    df["minus_di"] = 100*(minus_dm.rolling(ADX_PERIOD).mean()/atr_s)
    dx = 100*(df["plus_di"]-df["minus_di"]).abs()/(df["plus_di"]+df["minus_di"])
    df["adx"] = dx.rolling(ADX_PERIOD).mean()
    df["ret"] = c.pct_change()
    df["vs_ma20"] = (c-df["ma20"])/df["ma20"]*100
    df["trend_strength"] = df["adx"]/100
    return df

def regime_score(df, lookback=30):
    """Score how well this pair's regime suits our strategy (0-100)."""
    if df.empty or len(df) < lookback+10:
        return 50
    c = df["close"]
    rsi_vals = df["rsi"].iloc[-lookback:]
    adx_vals = df["adx"].iloc[-lookback:]
    rsi_swings = rsi_vals.max()-rsi_vals.min()
    # Ideal: ADX 30-60 (trending but not overextended), RSI oscillation 20-40
    adx_avg = adx_vals.mean()
    ideal_adx = 30 <= adx_avg <= 60
    ideal_rsi = 20 <= rsi_swings <= 45
    score = 50
    if ideal_adx: score += 25
    elif adx_avg > 60: score += 10  # still OK, a bit strong
    if ideal_rsi: score += 25
    elif rsi_swings < 20: score -= 10  # too flat
    elif rsi_swings > 45: score -= 5   # too volatile
    return min(100, max(0, score))

def trend_consistency(df, lookback=30):
    """% of candles that move in the same direction as the overall trend (0-100)."""
    if df.empty or len(df) < lookback+5:
        return 50
    ret = df["ret"].iloc[-lookback:]
    adx = df["adx"].iloc[-lookback:]
    overall_trend = adx.mean() > 30
    if overall_trend:
        # Count how often price moves with trend on each candle
        ma20_dir = (df["ma20"].iloc[-1] / df["ma20"].iloc[-lookback] - 1) > 0
        if ma20_dir:
            aligned = (ret > 0).mean()
        else:
            aligned = (ret < 0).mean()
    else:
        # Range-bound: count oscillations
        crosses = ((df["ma10"]>df["ma20"]) != (df["ma10"].shift(1)>df["ma20"].shift(1))).iloc[-lookback:].sum()
        # More crosses = more oscillations = better for mean-reversion
        ideal_crosses = 4  # some but not too many
        cross_score = 1 - abs(crosses - ideal_crosses) / ideal_crosses
        aligned = cross_score
    return min(100, max(0, round(aligned*100)))

def volatility_suitability(df):
    """
    Score whether this pair's volatility suits our 3:1 R:R aggressive setup.
    ATR% tells us if the pair moves enough to give us room for our stops.
    Too low = no movement, too high = unpredictable swings.
    Ideal range: 1.5% - 8% ATR%.
    """
    if df.empty or "atr_pct" not in df.columns:
        return 50
    atr_vals = df["atr_pct"].iloc[-30:].dropna()
    if atr_vals.empty:
        return 50
    atr_med = atr_vals.median()
    if atr_med < 0.5:
        return 20   # too flat, no room
    elif 0.5 <= atr_med < 1.5:
        return 50   # workable
    elif 1.5 <= atr_med <= 8:
        return 100  # ideal
    elif 8 < atr_med <= 15:
        return 70  # volatile but manageable
    else:
        return 40  # extremely volatile

def volume_quality(df, lookback=30):
    """Score volume quality: is there real volume behind moves? (0-100)."""
    if df.empty or len(df) < lookback:
        return 50
    vol_r = df["vol_ratio"].iloc[-lookback:]
    avg_ratio = vol_r.mean()
    spike_ratio = (vol_r > 1.5).mean()  # % of candles with real volume
    # Ideal: avg ratio 0.8-2.0, spikes 10-30% of the time
    avg_score = 100 if 0.8<=avg_ratio<=2.5 else (50 if 0.5<=avg_ratio<0.8 else 25)
    spike_score = 100 if 0.1<=spike_ratio<=0.35 else (50 if 0.35<spike_ratio<=0.5 else 25)
    return round((avg_score*0.4 + spike_score*0.6))

def rsi_pulsation(df, lookback=30):
    """
    How well does RSI oscillate between extremes? Good coins hit oversold/overbought
    regularly, giving us clean entry zones. (0-100).
    """
    if df.empty or len(df) < lookback:
        return 50
    rsi = df["rsi"].iloc[-lookback:]
    times_oversold = (rsi < 35).mean()   # ideal: 10-25% of candles
    times_overbought = (rsi > 65).mean()  # ideal: 10-25% of candles
    osc_range = rsi.max() - rsi.min()
    ideal_osc = 25 <= osc_range <= 50
    osc_score = 100 if ideal_osc else (50 if 15<=osc_range<25 else 25)
    zone_score = 100 if 0.1<=times_oversold<=0.3 else (50 if 0.05<=times_oversold<0.1 else 25)
    return round(osc_score*0.5 + zone_score*0.5)

def level_respect(df, lookback=20):
    """
    Does price respect technical levels (MA, BB, support/resistance)?
    High respect = stops don't get hunted, entries are cleaner.
    Scores: does price tend to bounce off BB bands and respect MAs?
    """
    if df.empty or len(df) < lookback+5:
        return 50
    c = df["close"]
    bb_l = df["bb_lower"]
    bb_u = df["bb_upper"]
    bb_m = df["bb_mid"]
    ma20 = df["ma20"]
    ma50 = df["ma50"]

    # Does price bounce from BB lower?
    touches_lower = ((c - bb_l).abs() / bb_l < 0.005).iloc[-lookback:].mean()
    bounces_lower = ((c > c.shift(1)) & (c.shift(1) <= bb_l.shift(1))).iloc[-lookback:].mean()
    bb_respect = 100 * (1 - touches_lower) + 100 * bounces_lower / 2

    # Does price respect MA20?
    ma_crosses = ((c>ma20) != (c.shift(1)>ma20.shift(1))).iloc[-lookback:].sum()
    ideal_crosses = 3
    ma_score = max(0, 100 - abs(ma_crosses-ideal_crosses)*15)

    # Does price stay within BB bands?
    inside_bb = ((c > bb_l) & (c < bb_u)).iloc[-lookback:].mean()
    inside_score = inside_bb * 100

    combined = bb_respect*0.3 + ma_score*0.35 + inside_score*0.35
    return min(100, max(0, round(combined)))

def backtest_quality(df, risk_pct=5.0, rr=3.0, capital=58.0):
    """
    Quick backtest on available data. Returns key metrics without full trade log.
    """
    if df.empty or len(df) < 60:
        return {"ret": 0, "wr": 0, "dd": 0, "trades": 0}
    df_bt = df.copy()
    trades = []
    peak = capital
    max_dd = 0.0
    pos = None

    for i in range(30, len(df_bt)):
        row = df_bt.iloc[i]
        if pos is None:
            adx = row.get("adx", 0)
            rsi = row.get("rsi", 50)
            if adx < 25 or rsi < 30 or rsi > 70:
                continue
            if rsi < 40:  # oversold bounce
                entry = row["close"]
                stop = row["bb_lower"] * 0.995 if not np.isnan(row["bb_lower"]) else entry * 0.97
                stop_pct = max((entry-stop)/entry*100, 0.5)
                tp = entry + (entry-stop)*rr
                units = capital*(risk_pct/100)/(entry*stop_pct/100)
                pos = {"entry": entry, "stop": stop, "tp": tp, "units": units}
        else:
            lo, hi = row["low"], row["high"]
            if lo <= pos["stop"] <= hi:
                pnl = pos["units"]*(pos["stop"]-pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak-capital)/peak*100)
                trades.append({"pnl": pnl})
                pos = None
            elif hi >= pos["tp"] >= lo:
                pnl = pos["units"]*(pos["tp"]-pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak-capital)/peak*100)
                trades.append({"pnl": pnl})
                pos = None
            elif i - len(trades) - 30 > 24:  # max hold 24 candles
                pnl = pos["units"]*(row["close"]-pos["entry"])
                capital += pnl
                peak = max(peak, capital)
                max_dd = max(max_dd, (peak-capital)/peak*100)
                trades.append({"pnl": pnl})
                pos = None

    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] <= 0)
    return {
        "ret": round((capital/58-1)*100, 1),
        "wr": round(wins/(wins+losses)*100, 0) if (wins+losses)>0 else 0,
        "dd": round(max_dd, 1),
        "trades": len(trades),
        "wins": wins, "losses": losses,
    }

def score_to_grade(score):
    if score >= 85: return "A+", "[A+]"
    elif score >= 75: return "A", "[A]"
    elif score >= 65: return "B+", "[B+]"
    elif score >= 55: return "B", "[B]"
    elif score >= 45: return "C", "[C]"
    elif score >= 35: return "D", "[D]"
    else: return "F", "[F]"

def main():
    parser = argparse.ArgumentParser(description="Coin quality analyser")
    parser.add_argument("--timeframe", "-t", default="1h", choices=["15m","1h","4h","1d"])
    parser.add_argument("--days", "-d", type=int, default=30)
    parser.add_argument("--min-score", type=float, default=0)
    args = parser.parse_args()

    print()
    print("=" * 90)
    print(f"  COIN QUALITY ANALYSER  |  {args.timeframe}  |  last {args.days} days")
    print("=" * 90)
    print()
    print("  Scores each pair on 6 dimensions relevant to our aggressive momentum strategy:")
    print()
    print("  DIMENSION          WHAT IT MEASURES")
    print("  -----------------  -----------------------------------------------------------")
    print("  Regime Fit          Does market regime suit our strategy? (ADX, RSI range)")
    print("  Trend Consistency   Does price follow through on moves or chop around?")
    print("  Volatility Suit.    Is there enough movement for 3:1 R:R without whipsawing?")
    print("  Volume Quality      Is volume real behind moves? Spikes + average quality")
    print("  RSI Pulsation       Does RSI oscillate to extremes, giving us entry zones?")
    print("  Level Respect       Does price respect MA/BB levels (stops don't get hunted)?")
    print()
    print("=" * 90)

    results = []
    for i, pair in enumerate(WATCHLIST):
        sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] Analysing {pair}...")
        sys.stdout.flush()

        try:
            df = fetch(pair, args.timeframe, args.days)
        except ccxt.BadSymbol:
            sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair} not available on KuCoin   \n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue

        if df.empty:
            sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair} no data   \n")
            sys.stdout.flush()
            time.sleep(RATE_LIMIT_DELAY)
            continue

        df = indicators(df)

        r_fit = regime_score(df)
        t_cons = trend_consistency(df)
        vol_s = volume_quality(df)
        rsi_p = rsi_pulsation(df)
        lvl_r = level_respect(df)
        bt = backtest_quality(df)

        # Composite: weighted average
        composite = round(
            r_fit    * 0.15 +
            t_cons   * 0.15 +
            vol_s    * 0.15 +
            rsi_p    * 0.20 +
            lvl_r    * 0.15 +
            bt["wr"]/100 * 20  # backtest win rate as last 20%
        )

        results.append({
            "symbol": pair,
            "regime_fit": r_fit,
            "trend_cons": t_cons,
            "vol_suit": vol_s,
            "vol_qual": vol_s,   # same calc, alias for display
            "rsi_puls": rsi_p,
            "level_resp": lvl_r,
            "composite": composite,
            "bt_ret": bt["ret"],
            "bt_wr": bt["wr"],
            "bt_dd": bt["dd"],
            "bt_trades": bt["trades"],
            "atr_pct": round(df["atr_pct"].iloc[-1], 2) if "atr_pct" in df.columns else 0,
        })

        sys.stdout.write(f"\r  [{i+1}/{len(WATCHLIST)}] {pair:<12} "
                         f"Regime={r_fit:>3}  Trend={t_cons:>3}  Vol={vol_s:>3}  "
                         f"RSI={rsi_p:>3}  Lvls={lvl_r:>3}  "
                         f"WR={bt['wr']:>3.0f}%  Ret={bt['ret']:>+6.1f}%\n")
        sys.stdout.flush()
        time.sleep(RATE_LIMIT_DELAY)

    print()
    print("=" * 90)
    print(f"\n  FULL RANKINGS  (composite score / 100):\n")
    hdr = f"  {'#':<3}  {'Pair':<12}  {'Grade':<4}  {'Comp':>5}  {'Reg':>4}  {'Trnd':>4}  " \
          f"{'Vol':>4}  {'RSI':>4}  {'Lvls':>4}  {'WR':>5}  {'Ret%':>7}  {'DD%':>6}  {'Trades':>6}  {'ATR%':>5}"
    print(hdr)
    print(f"  {'-'*3}  {'-'*12}  {'-'*4}  {'-'*5}  {'-'*4}  {'-'*4}  " \
          f"{'-'*4}  {'-'*4}  {'-'*4}  {'-'*5}  {'-'*7}  {'-'*6}  {'-'*6}  {'-'*5}")

    sorted_results = sorted(results, key=lambda x: -x["composite"])
    for rank, r in enumerate(sorted_results, 1):
        grade, _ = score_to_grade(r["composite"])
        print(f"  {rank:<3}  {r['symbol']:<12}  {grade:<4}  "
              f"{r['composite']:>5}  {r['regime_fit']:>4}  {r['trend_cons']:>4}  "
              f"{r['vol_suit']:>4}  {r['rsi_puls']:>4}  {r['level_resp']:>4}  "
              f"{r['bt_wr']:>5.0f}% {r['bt_ret']:>+7.1f}% {r['bt_dd']:>6.1f}% "
              f"{r['bt_trades']:>6}  {r['atr_pct']:>5.2f}%")

    # Tiers
    a_grade = [x for x in results if score_to_grade(x["composite"])[0] in ("A+","A","B+")]
    c_grade = [x for x in results if score_to_grade(x["composite"])[0] in ("B","C")]
    d_grade = [x for x in results if score_to_grade(x["composite"])[0] in ("D","F")]

    print()
    print("=" * 90)
    print("  TIER SUMMARY\n")
    a_sorted = sorted(a_grade, key=lambda x: -x["composite"])
    c_sorted = sorted(c_grade, key=lambda x: -x["composite"])
    d_sorted = sorted(d_grade, key=lambda x: -x["composite"])
    print(f"  [A] TRADE    (Grade B+ or above):   {[x['symbol'] for x in a_sorted]}")
    print(f"  [B] CAUTION  (Grade B or C):        {[x['symbol'] for x in c_sorted]}")
    print(f"  [C] AVOID    (Grade D or below):    {[x['symbol'] for x in d_sorted]}")
    print()
    print("  INTERPRETATION GUIDE:")
    print()
    print("  Regime Fit:        >70 = trending market, good for momentum entries")
    print("                     50-70 = mixed, use mean-reversion settings")
    print("                     <50 = ranging/choppy, skip or use tight stops")
    print()
    print("  Trend Consistency: >60 = price follows through, our stops work")
    print("                     <40 = price chops, whipsaw city")
    print()
    print("  Volatility Suit.:  >70 = ATR 1.5-8%, ideal for 3:1 R:R")
    print("                     <40 = ATR <1% (no room) or >15% (unpredictable)")
    print()
    print("  Volume Quality:     >70 = real volume behind moves, clean signals")
    print("                     <40 = wash trading, unreliable")
    print()
    print("  RSI Pulsation:      >65 = RSI hits extremes regularly, clean zones")
    print("                     <40 = RSI stays flat, no entry signal")
    print()
    print("  Level Respect:      >65 = price respects MA/BB, stops don't get hunted")
    print("                     <40 = noise market, entries unreliable")
    print()
    print(f"  Composite Score:    Weighted composite. Higher = better overall fit for strategy.")
    print()
    print("=" * 90)
    print("  NOTE: Scores based on last 30-90 days of data. Market conditions change.")
    print("=" * 90)
    print()

if __name__ == "__main__":
    main()
