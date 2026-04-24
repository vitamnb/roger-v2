import ccxt

# Read-only, no credentials needed for public market data
kucoin = ccxt.kucoin()
markets = kucoin.load_markets()

if 'RAVE/USDT' in markets:
    print("RAVE/USDT FOUND:")
    print(markets['RAVE/USDT'])
else:
    print("RAVE/USDT NOT found on KuCoin")
    print("\nSearching for partial matches:")
    for m in sorted(markets.keys()):
        if 'RAVE' in m.upper():
            print(f"  {m}")