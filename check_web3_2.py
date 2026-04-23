import ccxt

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

markets = exchange.load_markets()

# Search for potential Web3/SPL/DeFi pairs
keywords = ['WEB3', 'W3', 'DEX', 'SOL', 'RAY', 'BONK', 'WIF', 'JTO', 'PYTH', 'DRIFT', 'TENSOR']
print("=== Searching for potential Web3/SOL ecosystem pairs ===")
found = []
for sym in markets:
    for kw in keywords:
        if kw in sym:
            found.append(sym)
found = sorted(set(found))
print(f"Found {len(found)} pairs:")
for f in found[:30]:
    print(f"  {f}")

print()
print("=== Market types breakdown ===")
types = {}
for m in markets.values():
    t = m.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, c in types.items():
    print(f"  {t}: {c}")

# Check if there's a specific Web3 market type
print()
print("=== Checking Web3/SPL pairs specifically ===")
sol_pairs = [s for s in markets if 'SOL' in s or 'RAY' in s or 'BONK' in s or 'WIF' in s]
for s in sorted(sol_pairs)[:20]:
    m = markets[s]
    print(f"{s}: type={m['type']}, linear={m.get('linear')}, inverse={m.get('inverse')}")