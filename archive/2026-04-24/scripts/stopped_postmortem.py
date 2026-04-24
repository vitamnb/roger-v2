"""Post-mortem on stopped-out trades — were entries premature?"""
import sqlite3, requests
from datetime import datetime

KUCOIN_API = "https://api.kucoin.com/api/v1"

def get_ohlcv(symbol, limit=60):
    params = {"symbol": symbol.replace("/", "-"), "type": "1hour", "limit": limit}
    r = requests.get(f"{KUCOIN_API}/market/candles", params=params, timeout=10)
    bars = r.json().get("data", [])
    if not bars:
        return None
    cols = ["time","open","close","high","low","vol","turnover"]
    import pandas as pd
    df = pd.DataFrame(bars, columns=cols)
    for c in ["open","close","high","low","vol"]:
        df[c] = pd.to_numeric(df[c])
    df["time"] = pd.to_datetime(df["time"].astype(float), unit="s")
    return df.sort_values("time").reset_index(drop=True)

def analyse_trade(pair, entry_dt_str, entry_px, stop_px, initial_stop_pct):
    """For a given trade, look at the 20 bars before and after entry."""
    df = get_ohlcv(pair, limit=120)
    if df is None:
        print(f"No data for {pair}")
        return

    # Find the entry bar
    entry_px = float(entry_px)
    stop_px = float(stop_px)
    stop_dist_pct = abs(entry_px - stop_px) / entry_px * 100

    # Find the closest bar to entry time
    entry_ts = None
    for _, row in df.iterrows():
        if abs(float(row["close"]) - entry_px) < entry_px * 0.02:
            entry_ts = row["time"]
            break

    if entry_ts is None:
        # Try by time
        try:
            target = datetime.strptime(entry_dt_str, "%Y-%m-%d %H:%M:%S")
        except:
            try:
                target = datetime.strptime(entry_dt_str, "%Y-%m-%dT%H:%M:%S")
            except:
                target = datetime.fromisoformat(entry_dt_str.replace("Z","+00:00"))

            entry_ts = df.iloc[(df["time"] - target).abs().argsort().iloc[0]]["time"]
        entry_idx = df[df["time"] <= entry_ts].index[-1] if len(df[df["time"] <= entry_ts]) > 0 else max(0, len(df)-24)
    else:
        entry_idx = df[df["time"] == entry_ts].index[0]

    pre = df.iloc[max(0, entry_idx-20):entry_idx].copy()
    post = df.iloc[entry_idx:min(len(df), entry_idx+24)].copy()

    print(f"\n{'='*70}")
    print(f"{pair} | Entry: ${entry_px:.5f} | Stop: ${stop_px:.5f} ({stop_dist_pct:.2f}% away)")
    print(f"{'='*70}")

    # Pre-entry: what was the setup?
    if len(pre) > 0:
        pre_rsi_ago3 = None
        if len(pre) >= 3:
            pre_rsi_ago3 = float(pre.iloc[-3]["close"])
        entry_bar = pre.iloc[-1] if len(pre) > 0 else None
        print(f"\n[PRE-ENTRY] {len(pre)} bars before entry")
        print(f"  Entry bar close: ${entry_bar['close']:.5f}  vol: {entry_bar['vol']:,.0f}")
        if entry_bar['close'] < entry_bar['open']:
            direction = "RED candle at entry"
        else:
            direction = "GREEN candle at entry"
        print(f"  Entry candle: {direction}")

    # Post-entry analysis
    if len(post) > 0:
        post = post.reset_index(drop=True)
        in_profit = []
        against = []
        max_drawdown = 0
        best_up = 0
        bar_of_best = 0
        for i, row in post.iterrows():
            move_pct = (row["close"] - entry_px) / entry_px * 100
            if i == 0:
                first_move = move_pct
            if move_pct > best_up:
                best_up = move_pct
                bar_of_best = i
            if move_pct > 0:
                in_profit.append(move_pct)
            else:
                against.append(move_pct)

        entry_move = (post.iloc[0]["close"] - entry_px) / entry_px * 100

        print(f"\n[POST-ENTRY] first 24 bars:")
        print(f"  Bar 0 open: ${post.iloc[0]['open']:.5f} -> close: ${post.iloc[0]['close']:.5f}  first move: {first_move:+.2f}%")
        print(f"  Best moment: bar {bar_of_best} at ${post.iloc[bar_of_best]['close']:.5f} = {best_up:+.2f}%")
        print(f"  Time in profit: {len(in_profit)}/{len(post)} bars")
        print(f"  Time against:   {len(against)}/{len(post)} bars")

        # How far did it dip?
        post["dd"] = (post["low"] - entry_px) / entry_px * 100
        max_dd_idx = post["dd"].idxmin()
        max_dd = post.loc[max_dd_idx, "dd"]
        max_dd_bar = post.index.get_loc(max_dd_idx) if isinstance(max_dd_idx, int) else 0
        max_dd_time = post.loc[max_dd_idx, "time"]

        print(f"  Worst dip after entry: {max_dd:+.2f}% at bar {max_dd_bar} ({max_dd_time.strftime('%m-%d %H:%M')})")

        # Stop distance analysis
        print(f"\n[STOP ANALYSIS]")
        print(f"  Our stop distance: {stop_dist_pct:.2f}%")
        print(f"  Drawdown after entry: {abs(max_dd):.2f}%")
        stopped_early = abs(max_dd) < stop_dist_pct
        never_profitable = len(in_profit) == 0
        print(f"  Was stopped BEFORE hitting our stop? {stopped_early}")
        print(f"  Never went in profit? {never_profitable}")
        if never_profitable:
            print(f"  >> ENTRY WAS PREMATURE — price never confirmed direction")
        elif stopped_early and abs(max_dd) < 1.5:
            print(f"  >> STOPPED OUT EARLY — tight stop was hit before any real move")
        elif stopped_early:
            print(f"  >> STOPPED OUT — dip exceeded stop before recovery")

        print(f"\n[BAR CHART — post entry]")
        print(f"{'Bar':>4} {'Time':>12} {'Close':>10} {'Move%':>7} {'Low%':>6} {'Vol':>10}")
        for i, row in post.iterrows():
            move = (row["close"] - entry_px) / entry_px * 100
            low_move = (row["low"] - entry_px) / entry_px * 100
            ts = row["time"].strftime("%m-%d %H:%M")
            print(f"{i:>4} {ts:>12} ${row['close']:>9.5f} {move:>+6.2f}% {low_move:>+6.2f}% {row['vol']:>10,.0f}")

def main():
    conn = sqlite3.connect(r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite")
    c = conn.cursor()
    c.execute("SELECT pair, open_date, open_rate, close_date, close_rate, exit_reason, is_open FROM trades WHERE is_open = 0 ORDER BY open_date")
    closed = c.fetchall()
    conn.close()

    print("[STOPPED OUT POST-MORTEM]")
    print("Analysis: for each trade, check if price EVER went in profit after entry")
    print("Also check: was the entry bar a red flag? (price already reversing)")

    for trade in closed:
        pair, open_date, open_rate, close_date, close_rate, exit_reason, is_open = trade
        if close_rate and open_rate:
            analyse_trade(pair, str(open_date), open_rate, close_rate, 2.0)
            print()

if __name__ == "__main__":
    main()