import ccxt

# Try standard international KuCoin
print("=== Standard KuCoin (kucoin.com) ===")
kucoin_int = ccxt.kucoin()
markets_int = kucoin_int.load_markets()
rave_in_int = 'RAVE/USDT' in markets_int
print(f"RAVE/USDT available: {rave_in_int}")
if rave_in_int:
    print(f"  Info: {markets_int['RAVE/USDT']}")

# Try Australia-specific endpoint
print("\n=== KuCoin Australia (kucoin.com.au) ===")
try:
    kucoin_au = ccxt.kucoin({'options': {'domain': 'https://www.kucoin.com.au'}})
    markets_au = kucoin_au.load_markets()
    rave_in_au = 'RAVE/USDT' in markets_au
    print(f"RAVE/USDT available: {rave_in_au}")
    if rave_in_au:
        print(f"  Info: {markets_au['RAVE/USDT']}")
except Exception as e:
    print(f"Error: {e}")