import ccxt
exchange = ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})
raw = exchange.request("market/allTickers", "public", "GET")
# Correct path based on actual structure
tickers = raw.get("data", {}).get("ticker", []) or []
print(f"Tickers: {len(tickers)}")
usdt = [t["symbol"] for t in tickers if "/USDT" in t["symbol"] or t.get("symbolName","").endswith("-USDT")]
print(f"USDT count: {len(usdt)}")
print(f"First 10 USDT: {usdt[:10]}")
