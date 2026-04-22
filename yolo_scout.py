"""YOLO Scout — newly listed / waking coins on KuCoin.
Tracks coins with <100 bars of history = genuinely new listings.
Monitors for pre-pump volume patterns.
"""
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

TRACKED_COINS = {
    "OFC/USDT": "OFC",
    "ARKM/USDT": "ARKM",
}

def analyse_coin(sym, label):
    df = get_ohlcv(sym, "1hour", limit=150)
    if df.empty:
        print(f"\n{label}: No data")
        return

    df["rsi"] = rsi(df["close"])
    df["vol_sma"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma"]
    df["price_chg_4h"] = df["close"].pct_change(4)
    df["price_chg_12h"] = df["close"].pct_change(12)
    df["price_chg_24h"] = df["close"].pct_change(24)
    df["vol_change"] = df["volume"].pct_change()

    session_low = df["low"].min()
    session_high = df["high"].max()
    current_price = df["close"].iloc[-1]
    session_range_pct = (current_price - session_low) / (session_high - session_low) * 100 if session_high > session_low else 50
    bars_of_history = len(df)
    first_bar = df["time"].iloc[0].strftime("%Y-%m-%d")
    rsi_now = df["rsi"].iloc[-1]
    rsi_4h = df["rsi"].shift(4).iloc[-1] if len(df) >= 4 else rsi_now
    vol_ratio = df["vol_ratio"].iloc[-1]
    vol_20avg = df["vol_sma"].iloc[-1]
    vol_now = df["volume"].iloc[-1]
    vol_above = (df["vol_ratio"] > 1.0).tail(6).sum()
    vol_trend = df["vol_change"].tail(4).mean()
    price_12h_ago = df["close"].iloc[-13] if len(df) >= 13 else df["close"].iloc[0]
    price_rally = (current_price - price_12h_ago) / price_12h_ago * 100

    print(f"\n{'='*60}")
    print(f"{label} ({sym}) — {bars_of_history} bars | since {first_bar}")
    print(f"Price:   ${current_price:.5f} ({df['price_chg_24h'].iloc[-1]*100:+.1f}% 24h)")
    print(f"RSI:     {rsi_now:.1f} ({'RISING' if rsi_now > rsi_4h else 'FALLING'}, was {rsi_4h:.0f})")
    print(f"Range:   ${session_low:.5f} - ${session_high:.5f} | position: {session_range_pct:.0f}%")
    print(f"Vol:     {vol_now:,.0f} / {vol_20avg:,.0f} avg = {vol_ratio:.2f}x")
    print(f"Vol above avg (last 6h): {vol_above}/6 bars")
    print(f"12h rally: {price_rally:+.1f}%")

    print(f"\n--- Last 8 bars ---")
    print(f"{'Time':<18} {'Close':>8} {'Vol':>10} {'VolR':>5} {'RSI':>5}")
    for _, r in df.tail(8).iterrows():
        ts = r["time"].strftime("%m-%d %H:%M")
        print(f"{ts:<18} {r['close']:>8.5f} {r['volume']:>10,.0f} {r['vol_ratio']:>5.2f} {r['rsi']:>5.1f}")

    print(f"\n--- YOLO Verdict ---")
    if vol_above >= 4 and rsi_now < 70:
        signal = "YOLO CANDIDATE — volume confirmed, RSI room to run"
    elif vol_above >= 3 and rsi_now < 65:
        signal = "CAUTION — volume there but watch RSI"
    elif bars_of_history < 30:
        signal = "NEW COIN — limited history, treat as high risk"
    else:
        signal = "DORMANT — waiting for volume confirmation"

    print(f"  {signal}")
    print(f"  Range position: {'still early' if session_range_pct < 60 else 'advanced — better entry was earlier'}")
    print(f"  Vol trend: {'INCREASING' if vol_trend > 0 else 'DECREASING'}")
    return {
        "symbol": sym,
        "label": label,
        "bars": bars_of_history,
        "price": current_price,
        "rsi": rsi_now,
        "vol_ratio": vol_ratio,
        "vol_above_6h": vol_above,
        "range_pct": session_range_pct,
        "signal": signal,
    }

def main():
    print(f"\n[EARLY MOVER SCOUT] {datetime.now().strftime('%Y-%m-%d %H:%M')} AEST")
    results = []
    for sym, label in TRACKED_COINS.items():
        r = analyse_coin(sym, label)
        if r:
            results.append(r)
    return results

if __name__ == "__main__":
    main()
