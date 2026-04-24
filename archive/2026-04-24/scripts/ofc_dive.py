"""OFC — YOLO candidate deep dive."""
import requests
import pandas as pd
import numpy as np
from datetime import datetime

KUCOIN_API = "https://api.kucoin.com/api/v1"

def get_ohlcv(symbol, timeframe="1hour", limit=120):
    params = {"symbol": symbol.replace("/", "-"), "type": timeframe, "limit": limit}
    resp = requests.get(f"{KUCOIN_API}/market/candles", params=params, timeout=10)
    data = resp.json().get("data", [])
    if not data:
        return pd.DataFrame()
    cols = ["time", "open", "close", "high", "low", "volume", "turnover"]
    df = pd.DataFrame(data, columns=cols)
    for c in ["open", "close", "high", "low", "volume"]:
        df[c] = pd.to_numeric(df[c])
    df["time"] = pd.to_datetime(df["time"].astype(float), unit="s")
    return df.sort_values("time").reset_index(drop=True)

def rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

sym = "OFC/USDT"
df = get_ohlcv(sym, "1hour", limit=120)
if df.empty:
    print("No data")
    exit()

df["rsi"] = rsi(df["close"])
df["vol_sma"] = df["volume"].rolling(20).mean()
df["vol_ratio"] = df["volume"] / df["vol_sma"]
df["price_chg_4h"] = df["close"].pct_change(4)
df["price_chg_12h"] = df["close"].pct_change(12)
df["price_chg_24h"] = df["close"].pct_change(24)
df["vol_change"] = df["volume"].pct_change()

# Session stats (all available data = current "pump cycle")
session_low = df["low"].min()
session_high = df["high"].max()
current_price = df["close"].iloc[-1]
session_range_pct = (current_price - session_low) / (session_high - session_low) * 100 if session_high > session_low else 50

print(f"\n{'='*60}")
print(f"OFC/USDT — {len(df)} bars | 1h")
print(f"Session: {df['time'].iloc[0].strftime('%m-%d %H:%M')} -> {df['time'].iloc[-1].strftime('%m-%d %H:%M')} AEST")
print(f"Price:   ${current_price:.5f} ({df['price_chg_24h'].iloc[-1]*100:+.1f}% 24h)")
print(f"RSI:     {df['rsi'].iloc[-1]:.1f}")
print(f"\n--- Session Stats ---")
print(f"Range:   ${session_low:.5f} - ${session_high:.5f}")
print(f"Position in range: {session_range_pct:.0f}% (0%=bottom, 100%=top)")
print(f"Max vol spike: {df['vol_ratio'].max():.1f}x")

print(f"\n--- Last 15 bars ---")
print(f"{'Time':<18} {'Close':>8} {'Chg%':>6} {'Vol':>10} {'VolR':>5} {'RSI':>5}")
for _, r in df.tail(15).iterrows():
    chg = r["price_chg_4h"] * 100
    print(f"{r['time'].strftime('%m-%d %H:%M'):<18} {r['close']:>8.5f} {chg:>+6.1f}% {r['volume']:>10,.0f} {r['vol_ratio']:>5.1f} {r['rsi']:>5.1f}")

# YOLO signals
print(f"\n{'='*60}")
print("YOLO SCOUT:")
vol_above = (df["vol_ratio"] > 1.0).tail(6).sum()
vol_trend = df["vol_change"].tail(4).mean()
rsi_now = df["rsi"].iloc[-1]
rsi_4h = df["rsi"].shift(4).iloc[-1]
price_12h_ago = df["close"].iloc[-13] if len(df) >= 13 else df["close"].iloc[0]
price_rally = (current_price - price_12h_ago) / price_12h_ago * 100

print(f"  Volume above avg (last 6h): {vol_above}/6 bars")
print(f"  Volume trend: {'INCREASING' if vol_trend > 0 else 'DECREASING'} ({vol_trend*100:+.1f}% avg chg)")
print(f"  RSI: {rsi_now:.0f} — {'still room to run' if rsi_now < 70 else 'EXTENDED — caution'}")
print(f"  RSI 4h ago: {rsi_4h:.0f} -> now {rsi_now:.0f} ({'RISING' if rsi_now > rsi_4h else 'FALLING'})")
print(f"  Position in range: {session_range_pct:.0f}%")
print(f"\n  12h price rally: {price_rally:+.1f}%")
if price_rally > 20:
    print(f"  Flag: LARGE RALLY — {'aggressive entry, already up big' if session_range_pct > 80 else 'still early in range'}")
elif price_rally > 5:
    print(f"  Flag: MODERATE MOVE — {'still early' if session_range_pct < 60 else 'late entry risk'}")
else:
    print(f"  Flag: EARLY STAGE — price still building, watch for break")

if vol_above >= 4 and vol_trend > 0 and rsi_now < 70:
    print(f"\n  >> YOLO CANDIDATE: YES — volume confirmed, still early")
elif vol_above >= 3 and rsi_now < 65:
    print(f"\n  >> YOLO CANDIDATE: CAUTION — volume there but watch RSI")
else:
    print(f"\n  >> YOLO CANDIDATE: NO — volume or RSI not confirming")
