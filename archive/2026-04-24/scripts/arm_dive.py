import requests
KUCOIN_API = "https://api.kucoin.com/api/v1"
r = requests.get(f"{KUCOIN_API}/market/candles?symbol=ARKM-USDT&type=1hour&limit=72", timeout=10)
data = r.json().get("data", [])
print(f"ARKM 1h bars: {len(data)}")
if data:
    import pandas as pd
    df = pd.DataFrame(data, columns=["time","open","close","high","low","vol","turnover"])
    for c in ["open","close","high","low","vol"]:
        df[c] = pd.to_numeric(df[c])
    df["time"] = pd.to_datetime(df["time"].astype(float), unit="s")
    df = df.sort_values("time").reset_index(drop=True)
    df["volume"] = df["vol"]
    print(f"First bar: {df['time'].iloc[0].strftime('%Y-%m-%d')}")
    print(f"Last bar:  {df['time'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"Bars of history: {len(df)}")
    print(f"Current price: ${df['close'].iloc[-1]:.5f}")
    print(f"Session range: ${df['low'].min():.5f} - ${df['high'].max():.5f}")
    vol_20avg = df["volume"].rolling(20).mean().iloc[-1]
    vol_now = df["volume"].iloc[-1]
    print(f"Vol 20h avg: {vol_20avg:,.0f}  current: {vol_now:,.0f}  ratio: {vol_now/vol_20avg:.2f}x" if vol_20avg > 0 else "No vol avg")
