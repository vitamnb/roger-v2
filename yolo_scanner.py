"""
yolo_scanner.py — Momentum scanner for KuCoin.
Finds top movers by 24h change, analyses volume + RSI patterns.
Run: python yolo_scanner.py
"""
import requests
import time
import numpy as np
from datetime import datetime

KUCOIN_API = "https://api.kucoin.com"

def get_all_tickers():
    """One call — all tickers with 24h change baked in."""
    r = requests.get(f"{KUCOIN_API}/api/v1/market/allTickers", timeout=15)
    r.raise_for_status()
    data = r.json()["data"]
    return {t["symbol"]: t for t in data["ticker"]}

def get_klines(symbol, kline_type="1hour", limit=120):
    r = requests.get(f"{KUCOIN_API}/api/v1/market/candles", params={
        "symbol": symbol, "type": kline_type, "limit": limit
    }, timeout=10)
    if r.status_code != 200:
        return None
    try:
        return r.json()["data"]
    except:
        return None

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def analyse_symbol(symbol, tickers):
    """Analyse one symbol using bulk ticker + individual klines."""
    ticker = tickers.get(symbol, {})
    try:
        price = float(ticker.get("last", 0))
        if price <= 0:
            return None

        # 24h change from ticker
        change_24h = float(ticker.get("changeRate", 0)) * 100

        candles = get_klines(symbol, "1hour", 120)
        if not candles or len(candles) < 25:
            return None

        closes = np.array([float(c[2]) for c in candles])
        volumes = np.array([float(c[5]) for c in candles])

        rsi_14 = calc_rsi(closes, 14)
        rsi_7 = calc_rsi(closes, 7)

        # Volume ratio: last 5h avg vs prior 20h avg
        if len(volumes) >= 25:
            vol_recent = np.mean(volumes[-5:])
            vol_prior = np.mean(volumes[-25:-5])
            vol_ratio = vol_recent / vol_prior if vol_prior > 0 else 1.0
        else:
            vol_ratio = 1.0

        # Pump %: current price vs 24h low
        if len(closes) >= 24:
            low_24h = np.min(closes[-24:])
            pump_pct = (price - low_24h) / low_24h * 100
        else:
            pump_pct = 0

        # Range position: where is price in 24h range
        if len(closes) >= 24:
            high_24h = np.max(closes[-24:])
            low_24h = np.min(closes[-24:])
            range_pos = (price - low_24h) / (high_24h - low_24h) * 100 if high_24h != low_24h else 50
        else:
            range_pos = 50

        return {
            "symbol": symbol.replace("-USDT", ""),
            "price": price,
            "change_24h": change_24h,
            "rsi_14": rsi_14,
            "rsi_7": rsi_7,
            "vol_ratio": vol_ratio,
            "pump_pct": pump_pct,
            "range_pos": range_pos,
        }
    except Exception as e:
        return None

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching all KuCoin tickers...")
    tickers = get_all_tickers()
    usdt = {s: t for s, t in tickers.items() if s.endswith("-USDT")}
    print(f"Total USDT pairs: {len(usdt)}")

    # Sort by 24h change rate
    sorted_pairs = sorted(
        [t for t in usdt.values() if t.get("changeRate") is not None],
        key=lambda x: float(x.get("changeRate", 0)),
        reverse=True
    )

    print(f"\n{'='*100}")
    print(f"{'TOP 30 KUCOIN MOVERS (24h)':^100}")
    print(f"{'='*100}")
    headers = f"{'Symbol':<12} {'Price':<14} {'24h %':<10} {'RSI(14)':<9} {'RSI(7)':<8} {'Vol ratio':<10} {'Pump%':<9} {'Range%':<8}"
    print(headers)
    print("-" * 100)

    results = []
    checked = 0
    checked_symbols = set()

    for t in sorted_pairs:
        if checked >= 60:  # enough to fill top 30 with valid data
            break
        sym = t["symbol"]
        if sym in checked_symbols:
            continue
        checked_symbols.add(sym)

        analysis = analyse_symbol(sym, tickers)
        checked += 1
        if analysis:
            results.append(analysis)
            r14 = f"{analysis['rsi_14']:.1f}" if analysis['rsi_14'] else "N/A"
            r7 = f"{analysis['rsi_7']:.1f}" if analysis['rsi_7'] else "N/A"
            vr = f"{analysis['vol_ratio']:.2f}x"
            pump = f"{analysis['pump_pct']:.1f}%"
            rangep = f"{analysis['range_pos']:.0f}%"
            print(f"{sym:<12} ${analysis['price']:<13.6f} {analysis['change_24h']:>+8.2f}%  "
                  f"{r14:<9} {r7:<8} {vr:<10} {pump:<9} {rangep:<8}")
        time.sleep(0.07)

    # Pattern analysis
    print(f"\n{'='*60}")
    print(f"{'PATTERN ANALYSIS':^60}")
    print(f"{'='*60}")

    rsi_vals = [r["rsi_14"] for r in results if r.get("rsi_14")]
    vr_vals = [r["vol_ratio"] for r in results if r.get("vol_ratio")]
    pump_vals = [r["pump_pct"] for r in results if r.get("pump_pct")]
    range_vals = [r["range_pos"] for r in results if r.get("range_pos")]

    print(f"\nSample size: {len(results)} top movers by 24h change")
    print(f"Avg RSI(14):         {np.mean(rsi_vals):.1f}  (neutral ~50, overbought >70)")
    print(f"Avg vol ratio (5v/20v): {np.mean(vr_vals):.2f}x  (>1.5x = surge)")
    print(f"Avg pump from 24h low: {np.mean(pump_vals):.1f}%")
    print(f"Avg range position:   {np.mean(range_vals):.0f}%  (50% = mid, >80% = near top)")
    print(f"Coins with RSI > 70:   {len([r for r in rsi_vals if r > 70])}/{len(rsi_vals)} ({len([r for r in rsi_vals if r > 70])/max(len(rsi_vals),1)*100:.0f}%)")
    print(f"Coins with vol > 2x:   {len([r for r in vr_vals if r > 2])}/{len(vr_vals)} ({len([r for r in vr_vals if r > 2])/max(len(vr_vals),1)*100:.0f}%)")
    print(f"Coins with pump > 10%: {len([r for r in pump_vals if r > 10])}/{len(pump_vals)} ({len([r for r in pump_vals if r > 10])/max(len(pump_vals),1)*100:.0f}%)")
    print(f"Coins at >80% of 24h range: {len([r for r in range_vals if r > 80])}/{len(range_vals)}")

    # Correlations
    print(f"\n--- Correlations ---")
    if len(rsi_vals) == len(pump_vals) and np.std(pump_vals) > 0 and np.std(rsi_vals) > 0:
        corr_rsi_pump = np.corrcoef(np.array(rsi_vals), np.array(pump_vals))[0,1]
        print(f"RSI(14) vs Pump%:      {corr_rsi_pump:+.3f}  (+ = higher RSI, higher pump — trending together)")
    if len(vr_vals) == len(pump_vals) and np.std(vr_vals) > 0 and np.std(pump_vals) > 0:
        corr_vr_pump = np.corrcoef(np.array(vr_vals), np.array(pump_vals))[0,1]
        print(f"Vol ratio vs Pump%:    {corr_vr_pump:+.3f}  (+ = vol surge causes bigger pump)")
    if len(rsi_vals) == len(vr_vals) and np.std(rsi_vals) > 0 and np.std(vr_vals) > 0:
        corr_rsi_vr = np.corrcoef(np.array(rsi_vals), np.array(vr_vals))[0,1]
        print(f"RSI(14) vs Vol ratio:  {corr_rsi_vr:+.3f}")

    # RSI distribution
    print(f"\n--- RSI(14) Distribution ---")
    for lo, hi, label in [(0, 30, "Oversold (0-30)"), (30, 50, "Neutral low (30-50)"), (50, 70, "Neutral high (50-70)"), (70, 85, "Overbought (70-85)"), (85, 100, "Extreme (85+)")]:
        count = len([r for r in rsi_vals if lo <= r < hi])
        bar = "#" * count
        print(f"  {lo:3d}-{hi:3d} {label:<22}: {bar} ({count})")

    # Cross with our universe
    print(f"\n{'='*60}")
    print(f"{'CROSS WITH OUR UNIVERSE':^60}")
    print(f"{'='*60}")
    our_pairs = ["JUP", "FET", "H", "ARIA", "BNRENSHENG", "VIRTUAL", "WIF", "AVAX", "ETH", "DOGE", "SOL", "BTC", "BNB", "LINK", "UNI", "ADA", "XRP", "SHIB", "ENJ", "CRV", "NEAR", "KCS", "RENDER", "THETA", "HBAR", "WLD", "ORDI", "SIREN", "HIGH"]
    found = {r["symbol"]: r for r in results if r["symbol"] in our_pairs}
    for sym in [s for s in our_pairs if s in found]:
        r = found[sym]
        print(f"  {sym:<12} 24h={r['change_24h']:+.2f}%  RSI={r.get('rsi_14', 0):.1f}  vol_ratio={r.get('vol_ratio', 0):.2f}x  pump={r.get('pump_pct', 0):.1f}%  range={r.get('range_pos', 0):.0f}%")

    if not found:
        print("  None of our pairs are in the top 60 movers right now.")

    # YOLO candidate screening
    print(f"\n{'='*60}")
    print(f"{'YOLO CANDIDATE SCREEN':^60}")
    print(f"{'='*60}")
    print("Criteria for momentum entries:")
    print("  - RSI(14) 40-65 (room to run, not overheated)")
    print("  - Vol ratio > 1.5x (volume confirming the move)")
    print("  - Pump 5-25% (significant but not exhausted)")
    print("  - Range pos 30-80% (not yet at absolute top)")
    print()
    candidates = [
        r for r in results
        if r.get("rsi_14") and 40 <= r["rsi_14"] <= 65
        and r.get("vol_ratio", 0) > 1.5
        and 5 <= r.get("pump_pct", 0) <= 25
        and 30 <= r.get("range_pos", 0) <= 80
    ]
    candidates.sort(key=lambda x: x["vol_ratio"], reverse=True)
    if candidates:
        print(f"Found {len(candidates)} candidates:")
        for r in candidates[:10]:
            print(f"  {r['symbol']:<12} 24h={r['change_24h']:+.2f}%  RSI={r['rsi_14']:.1f}  vol={r['vol_ratio']:.2f}x  pump={r['pump_pct']:.1f}%")
    else:
        print("No candidates meet all 4 criteria right now.")

if __name__ == "__main__":
    main()
