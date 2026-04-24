"""Follow-up scan on top gainers with fundamentals."""
import requests, json

KUCOIN_API = "https://api.kucoin.com/api/v1"

def coin_info(sym):
    r = requests.get(f"{KUCOIN_API}/market/detail?symbol={sym}", timeout=5)
    return r.json().get("data", {})

def get_listing_date(sym):
    """Estimate listing by checking earliest candle."""
    params = {"symbol": sym, "type": "1hour", "limit": 1}
    r = requests.get(f"{KUCOIN_API}/market/candles", params=params, timeout=5)
    data = r.json().get("data", [])
    if data:
        from datetime import datetime
        ts = float(data[0][0])
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    return "unknown"

def fundamentals(sym):
    info = coin_info(sym)
    listing = get_listing_date(sym)
    return {
        "baseCurrency": info.get("baseCurrency", ""),
        "quoteCurrency": info.get("quoteCurrency", ""),
        "pricePrecision": info.get("pricePrecision", ""),
        "minSize": info.get("marketMinOrderSize", ""),
        "listed": listing,
    }

SYMBOLS = ["CHIP-USDT","RAVE-USDT","TRIA-USDT","MET-USDT","XION-USDT","BAS-USDT","SHR-USDT"]

for sym in SYMBOLS:
    try:
        f = fundamentals(sym)
        print(f"{sym}: listed={f['listed']} base={f['baseCurrency']} minSize={f['minSize']} pricePrec={f['pricePrecision']}")
    except Exception as e:
        print(f"{sym}: error {e}")