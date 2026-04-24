"""TP comparison: 3% vs 5% vs 7% on live open trades + recent history.
Tests on JUP, H, SIREN (stopped out) and current open trades."""
import ccxt, pandas as pd, numpy as np
from datetime import datetime

RSI_PERIOD = 14
BB_WINDOW = 20
VOL_SMA = 20

PAIRS = ["JUP/USDT","H/USDT","SIREN/USDT","FET/USDT","AAVE/USDT","ENA/USDT","ARKM/USDT","IAG/USDT"]
TP_TARGETS = [3, 5, 7]
STOP_PCT = 2.0  # fixed 2% stop
DAYS = 30

def fetch(symbol, days=30):
    ex = ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    since = ex.parse8601((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z'))
    raw = ex.fetch_ohlcv(symbol, "1h", since=since, limit=1000)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw, columns=["t","open","high","low","close","vol"])
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    df.set_index("t", inplace=True)
    return df.sort_index()

def add_indicators(df):
    c, h, l, v = df["close"], df["high"], df["low"], df["vol"]
    o = df["open"]
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    bb_mid = c.rolling(BB_WINDOW).mean()
    bb_std = c.rolling(BB_WINDOW).std()
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_pct"] = (c - df["bb_lower"]) / (bb_mid + 2*bb_std - df["bb_lower"])
    df["vol_sma"] = v.rolling(VOL_SMA).mean()
    df["vol_ratio"] = v / df["vol_sma"]
    df["swing_low"] = l.rolling(5).min()
    df["green"] = c > o
    return df

def sim_trades(df, tp_pct, stop_pct=STOP_PCT, entry_rsi_max=35, bb_pct_max=0.20, prev_green=True):
    """Simulate trades with given TP and stop, green candle filter."""
    trades = []
    for i in range(max(RSI_PERIOD+5, 25), len(df)):
        row = df.iloc[i]
        prev = df.iloc[i-1]

        # Entry: RSI < threshold, BB% < threshold, prev candle green
        rsi_ok = row["rsi"] < entry_rsi_max
        bb_ok = 0 < row["bb_pct"] < bb_pct_max
        green_ok = not prev_green or (prev["green"] and prev["close"] > prev["open"])
        if not (rsi_ok and bb_ok and green_ok):
            continue

        entry = row["close"]
        stop = entry * (1 - stop_pct/100)
        tp = entry * (1 + tp_pct/100)
        units = 1.0  # fixed unit per trade for comparison

        for j in range(i+1, min(i+72, len(df))):
            bar = df.iloc[j]
            lo, hi = bar["low"], bar["high"]
            # Stop hit
            if lo <= stop <= hi:
                ret = (stop - entry) / entry * 100
                trades.append({"pair": df.index[i].strftime("%Y-%m-%d"), "ret": ret, "exit": "stop", "bars": j-i, "tp_hit": False, "tp_pct": tp_pct, "entry_price": entry})
                break
            # TP hit
            if hi >= tp >= lo:
                ret = (tp - entry) / entry * 100
                trades.append({"pair": df.index[i].strftime("%Y-%m-%d"), "ret": ret, "exit": "tp", "bars": j-i, "tp_hit": True, "tp_pct": tp_pct, "entry_price": entry})
                break
            # Max hold 72 bars (3 days)
            if j == i + 71:
                ret = (bar["close"] - entry) / entry * 100
                trades.append({"pair": df.index[i].strftime("%Y-%m-%d"), "ret": ret, "exit": "timeout", "bars": 72, "tp_hit": False, "tp_pct": tp_pct, "entry_price": entry})
                break
    return trades

def stats(trades, tp_pct):
    if not trades:
        return None
    rets = [t["ret"] for t in trades]
    wins = [t for t in trades if t["ret"] > 0]
    tps = [t for t in trades if t["tp_hit"]]
    loss = [t for t in trades if not t["tp_hit"]]
    avg_win = sum(t["ret"] for t in wins)/len(wins) if wins else 0
    avg_loss = sum(t["ret"] for t in loss)/len(loss) if loss else 0
    wr = len(wins)/len(trades)*100 if trades else 0
    # Expectancy
    exp = (wr/100 * avg_win) + ((100-wr)/100 * avg_loss) if trades else 0
    return {
        "tp": tp_pct,
        "trades": len(trades),
        "wins": len(wins),
        "loss": len(loss),
        "wr": wr,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "exp": exp,
        "tps": len(tps),
        "avg_hold": sum(t["bars"] for t in trades)/len(trades) if trades else 0,
    }

print("=" * 70)
print(f"TP COMPARISON — {DAYS} days | stop={STOP_PCT}% | green candle filter ON")
print("=" * 70)

all_results = {}

for pair in PAIRS:
    df = fetch(pair, DAYS)
    if df.empty:
        print(f"\n{pair}: no data")
        continue
    df = add_indicators(df)

    print(f"\n--- {pair} ({len(df)} bars, {len(df)-25} eligible signals) ---")

    pair_results = {}
    for tp in TP_TARGETS:
        t = sim_trades(df, tp)
        s = stats(t, tp)
        pair_results[tp] = s
        if s:
            print(f"  TP={tp}%: {s['trades']} trades | WR={s['wr']:.0f}% | exp={s['exp']:+.2f}% | avg_win={s['avg_win']:+.2f}% | avg_loss={s['avg_loss']:+.2f}% | TPs hit: {s['tps']}/{s['trades']} | avg hold: {s['avg_hold']:.0f} bars")

    all_results[pair] = pair_results

print("\n" + "=" * 70)
print("SUMMARY ACROSS ALL PAIRS")
print("=" * 70)
print(f"\n{'TP':>4} | {'Trds':>5} | {'WR':>5} | {'Exp':>6} | {'AvgW':>6} | {'AvgL':>6} | {'TPsHit':>7}")
print("-" * 60)
totals = {tp: {"trades":0,"wins":0,"exp":0,"avg_win":0,"avg_loss":0,"tps":0} for tp in TP_TARGETS}
for pair, prs in all_results.items():
    for tp, s in prs.items():
        if s:
            totals[tp]["trades"] += s["trades"]
            totals[tp]["wins"] += s["wins"]
            totals[tp]["exp"] += s["exp"]
            totals[tp]["avg_win"] += s["avg_win"]
            totals[tp]["avg_loss"] += s["avg_loss"]
            totals[tp]["tps"] += s["tps"]

for tp in TP_TARGETS:
    t = totals[tp]
    n = t["trades"]
    if n > 0:
        wr = t["wins"]/n*100
        avg_win = t["avg_win"]/len([p for p in all_results if all_results[p].get(tp)]) if len(all_results) > 0 else 0
        exp = t["exp"]/len([p for p in all_results if all_results[p].get(tp)]) if len(all_results) > 0 else 0
        print(f"  {tp}% | {n:>5} | {wr:>4.0f}% | {exp:>+6.2f} | {t['avg_win']/len([p for p in all_results if all_results[p].get(tp)]):>+6.2f} | {t['avg_loss']/len([p for p in all_results if all_results[p].get(tp)]):>+6.2f} | {t['tps']:>7}")
    else:
        print(f"  {tp}% |   N/A")
