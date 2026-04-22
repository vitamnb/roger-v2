"""KuCoin top gainers today — scan + fundamentals."""
import requests

KUCOIN_API = "https://api.kucoin.com/api/v1"

def get_all_tickers():
    raw = requests.get(f"{KUCOIN_API}/market/allTickers", timeout=10)
    tickers = (raw.json().get("data") or {}).get("ticker", []) or []
    return tickers

def get_coin_info(symbol):
    """Fetch basic coin info from KuCoin."""
    sym = symbol.replace("/", "-")
    r = requests.get(f"{KUCOIN_API}/market/detail?symbol={sym}", timeout=5)
    return r.json().get("data", {})

def main():
    tickers = get_all_tickers()
    usdt = [t for t in tickers if "/USDT" in t["symbol"] or t.get("symbolName", "").endswith("-USDT")]

    # Sort by 24h change
    def chg(t):
        try: return float(t.get("changeRate", 0) or 0)
        except: return 0

    usdt.sort(key=chg, reverse=True)

    print("\n============================================================")
    print("[KUCOIN TOP GAINERS — 24h]")
    print(f"Scanned: {len(usdt)} USDT pairs")
    print("============================================================\n")

    # Top 20 gainers
    gainers = usdt[:20]

    print(f"{'Rank':<5} {'Symbol':<14} {'Price':>10} {'24h Chg':>8} {'Vol ($)':>12}  {'Pattern'}")
    print(f"{'-'*4} {'-'*13} {'-'*10} {'-'*8} {'-'*12}  {'-'*20}")

    for i, t in enumerate(gainers, 1):
        sym = t["symbol"]
        try:
            price = float(t.get("last", 0) or 0)
            chg_pct = float(t.get("changeRate", 0) or 0) * 100
            vol_val = float(t.get("volValue", 0) or 0)
            open_px = float(t.get("open", 0) or 0)
        except:
            continue

        # Pattern detection
        if chg_pct > 20:
            pattern = "PUMP — extreme move"
        elif chg_pct > 10:
            pattern = "Strong gain — watch"
        elif chg_pct > 5:
            pattern = "Moderate gain"
        else:
            pattern = "Small gain"

        print(f"  {i:<4} {sym:<14} ${price:>9.5f} {chg_pct:>+7.1f}% {vol_val:>11,.0f}  {pattern}")

    print("\n============================================================")
    print("[TOP 10 DETAIL + FUNDAMENTALS CHECK]")
    print("============================================================\n")

    for i, t in enumerate(gainers[:10], 1):
        sym = t["symbol"]
        try:
            price = float(t.get("last", 0) or 0)
            chg_pct = float(t.get("changeRate", 0) or 0) * 100
            vol_val = float(t.get("volValue", 0) or 0)
            high_24 = float(t.get("high", 0) or 0)
            low_24 = float(t.get("low", 0) or 0)
            buy = float(t.get("buy", 0) or 0)
            sell = float(t.get("sell", 0) or 0)
        except:
            continue

        # Range within day
        if low_24 > 0 and price > 0:
            day_range = (price - low_24) / (high_24 - low_24) * 100 if (high_24 - low_24) > 0 else 50
        else:
            day_range = 50

        # Bid/ask spread — tight = liquid market
        if buy > 0 and sell > 0:
            spread = (sell - buy) / buy * 100
        else:
            spread = None

        print(f"  {i}. {sym}")
        print(f"     Price: ${price:.6f}  24h: {chg_pct:+.1f}%  Vol: ${vol_val:,.0f}")
        print(f"     Day range: {day_range:.0f}% (low={low_24:.5f} high={high_24:.5f})")
        if spread is not None:
            print(f"     Bid/ask spread: {spread:.3f}%", "TIGHT" if spread < 0.5 else "")
        print()
        try:
            info = get_coin_info(sym)
            if info:
                print(f"     Markets: {info.get('marketMinOrderSize', 'N/A')}")
        except:
            pass
        print()

if __name__ == "__main__":
    main()
