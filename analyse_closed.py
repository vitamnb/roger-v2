"""Analyse specific closed trades — entry quality, RSI at entry, regime context."""
import sqlite3
import requests
import pandas as pd

DB = r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite"
KUCOIN_API = "https://api.kucoin.com/api/v1"

def get_ohlcv(symbol, timeframe="1h", limit=150):
    # KuCoin uses 1hour not 1h
    tf_map = {"15m": "15min", "1h": "1hour", "4h": "4hour", "1d": "1day"}
    tf = tf_map.get(timeframe, timeframe)
    params = {"symbol": symbol.replace("/", "-"), "type": tf, "limit": limit}
    resp = requests.get(f"{KUCOIN_API}/market/candles", params=params, timeout=10)
    data = resp.json().get("data", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=["time","open","close","high","low","volume","turnover"])
    for c in ["open","close","high","low","volume"]:
        df[c] = pd.to_numeric(df[c])
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df.sort_values("time").reset_index(drop=True)

def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyse_trade(row):
    sym = row["pair"]
    entry = float(row["open_rate"])
    close_px = float(row["close_rate"])
    stop_pct = abs(float(row["stop_loss_pct"]))
    exit_reason = str(row.get("exit_reason") or "")
    entry_dt = pd.to_datetime(row["open_date"])
    entry_ts = int(entry_dt.timestamp())
    dur = row.get("duration_hours")

    df = get_ohlcv(sym, "1h", limit=200)
    if df.empty or len(df) < 20:
        print(f"\n{sym}: no data")
        return

    df["rsi"] = calc_rsi(df["close"])

    # Find entry bar
    entry_time = entry_dt
    df["diff"] = abs((df["time"] - entry_time).dt.total_seconds())
    entry_idx = df["diff"].idxmin()
    entry_bar = df.loc[entry_idx]

    rsi_at_entry = entry_bar["rsi"] if not pd.isna(entry_bar["rsi"]) else None
    vol_now = float(entry_bar["volume"])
    vol_avg = df["volume"].mean()
    vol_ratio = vol_now / vol_avg if vol_avg > 0 else 0
    entry_hour = entry_bar["time"].hour

    # Post-entry: next 10 bars
    after = df[df["time"] > entry_bar["time"]].head(10)
    high_after = float(after["high"].max()) if len(after) else entry
    low_after = float(after["low"].min()) if len(after) else entry
    pump_pct = (high_after - entry) / entry * 100
    drawdown_pct = (low_after - entry) / entry * 100

    # Outcome
    outcome = "SL" if "stop" in exit_reason.lower() else exit_reason.upper()

    print(f"\n{'='*55}")
    print(f"Trade: {sym}")
    print(f"Outcome: {outcome}")
    print(f"Entry: ${entry:.5f} | Exit: ${close_px:.5f} | Stop: {stop_pct:.0f}%")
    print(f"Entry: {entry_hour}:00 UTC | Duration: {dur:.1f}h")
    if rsi_at_entry:
        print(f"RSI at entry: {rsi_at_entry:.1f}")
    print(f"Volume ratio: {vol_ratio:.2f}x (entry bar vs 20h avg)")
    print(f"Post-entry: high +{pump_pct:.1f}% / low {drawdown_pct:.1f}%")
    print(f"Max drawdown after entry: {drawdown_pct:.1f}%")

    if rsi_at_entry:
        if rsi_at_entry > 75:
            print(f"  [WARN] RSI {rsi_at_entry:.0f} - OVERBOUGHT at entry")
        elif rsi_at_entry > 65:
            print(f"  [WARN] RSI {rsi_at_entry:.0f} - warm zone, limited upside")
        elif rsi_at_entry > 50:
            print(f"  [OK] RSI {rsi_at_entry:.0f} - neutral zone")
        else:
            print(f"  [OK] RSI {rsi_at_entry:.0f} - oversold bounce zone")

    if vol_ratio < 0.5:
        print(f"  [WARN] Volume {vol_ratio:.2f}x - THIN, fake breakout risk")
    elif vol_ratio < 0.9:
        print(f"  [WARN] Volume {vol_ratio:.2f}x - below average")
    else:
        print(f"  [OK] Volume {vol_ratio:.2f}x - healthy")

    issues = []
    if rsi_at_entry and rsi_at_entry > 65:
        issues.append(f"Entry RSI warm ({rsi_at_entry:.0f})")
    if vol_ratio < 0.7:
        issues.append(f"Low volume ({vol_ratio:.2f}x)")
    if pump_pct > 4 and drawdown_pct < -1:
        issues.append(f"Post-entry pump +{pump_pct:.0f}% but reversed")

    if pump_pct < 1 and drawdown_pct < -2:
        issues.append(f"Steady decline from entry")
    if not issues:
        print(f"  No major red flags in entry quality. Stop did its job.")
    else:
        print(f"  Issues found: {' | '.join(issues)}")

def main():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT pair, open_rate, close_rate, open_date, close_date,
               stop_loss_pct, exit_reason, max_rate, min_rate
        FROM trades WHERE is_open = 0
        ORDER BY open_date
    """, conn)
    conn.close()

    # compute duration
    df["duration_hours"] = df.apply(lambda r: round(
        (pd.to_datetime(r["close_date"]) - pd.to_datetime(r["open_date"])).total_seconds() / 3600, 2
    ) if r["open_date"] and r["close_date"] else None, axis=1)

    print(f"Analysing {len(df)} closed trade(s)...\n")
    for _, row in df.iterrows():
        analyse_trade(row)

if __name__ == "__main__":
    main()
