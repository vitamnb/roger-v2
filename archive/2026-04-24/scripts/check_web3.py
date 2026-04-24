import ccxt

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

print("=== KuCoin API Capabilities ===")
print()

# Check available markets
try:
    markets = exchange.load_markets()
    print(f"Spot markets loaded: {len(markets)}")
    print(f"Types available: {exchange.has}")
    print()
    
    # Check if there are any Web3/DEX-type markets
    print("=== Checking market types ===")
    for sym in ['SOL/USDT', 'RAY/USDT', 'BONK/USDT', 'WIF/USDT']:
        if sym in markets:
            m = markets[sym]
            print(f"{sym}: type={m['type']}, exchange={m['exchange']}, spot={m.get('spot', False)}")
except Exception as e:
    print(f"Error: {e}")

# Check OTC/decentralized endpoints
print()
print("=== Testing Web3 market endpoint ===")
try:
    # Try to access any /api/v1/market/* endpoints
    r = exchange.fetch2(path='api/v1/market/config', params={})
    print(r)
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")