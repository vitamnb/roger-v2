import ccxt

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

# Test if there are any hidden OTC or special markets via fetch_markets params
print("=== Checking for hidden Web3 markets ===")
try:
    # Try fetching SOL ecosystem tokens specifically
    r = exchange.fetch_markets({'type': 'spot'})
    sol_markets = [m for m in r if 'SOL' in m['symbol'] or 'RAY' in m['symbol'] or 'BONK' in m['symbol'] or 'JTO' in m['symbol']]
    print(f"SOL ecosystem spot markets: {len(sol_markets)}")
    for m in sol_markets:
        print(f"  {m['symbol']}: {m}")
except Exception as e:
    print(f"Error: {e}")

print()
# Check if Web3 / SPL tokens appear in recent listings
try:
    # Check new markets endpoint
    r = exchange.fetch_markets()
    usdt_markets = [m for m in r if m['quote'] == 'USDT' and m['type'] == 'spot']
    print(f"Total USDT spot pairs: {len(usdt_markets)}")
    # Check for SPL tokens
    spl_keywords = ['BONK', 'WIF', 'RAY', 'JTO', 'PYTH', 'DRIFT', 'TENSOR', 'BLZE', 'HCO', 'SAND']
    for kw in spl_keywords:
        matches = [m['symbol'] for m in usdt_markets if kw in m['symbol']]
        print(f"  {kw}: {matches}")
except Exception as e:
    print(f"Error: {e}")