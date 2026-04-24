import ccxt

ex = ccxt.kucoin({'options':{'defaultType':'spot'}, 'enableRateLimit': True})
ex.load_markets()
tickers = ex.fetch_tickers()
usdt = {k: v for k, v in tickers.items() if '/USDT' in k and v.get('quoteVolume', 0) > 50000}
sorted_usdt = sorted(usdt.values(), key=lambda x: x.get('quoteVolume', 0), reverse=True)
pairs = [t['symbol'] for t in sorted_usdt[:20]]
print(f"Got {len(pairs)} pairs: {pairs[:5]}")

sym = pairs[0]
print(f"Trying order book for {sym}...")
try:
    book = ex.fetch_order_book(sym, limit=50)
    print(f"Bids: {len(book['bids'])} levels, Asks: {len(book['asks'])} levels")
    print(f"Top bid: {book['bids'][0]}, Top ask: {book['asks'][0]}")
except Exception as e:
    print(f"Error: {e}")
