import ccxt
exchange = ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})
# Try market/allTickers
try:
    raw = exchange.request("market/allTickers", "public", "GET")
    print("request() worked:", type(raw))
    print(raw)
except Exception as e:
    print("request() failed:", e)

# Try public_get equivalent
try:
    raw2 = exchange.public_get_market_allticker()
    print("public_get_market_allticker() worked")
    print(list(raw2.get("data", {}).keys())[:5])
except Exception as e:
    print("public_get_market_allticker() failed:", e)
