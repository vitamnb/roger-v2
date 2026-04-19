import ccxt, pandas as pd
ex = ccxt.kucoin({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
ex.loadMarkets()
tickers = ex.fetch_tickers()
pairs = []
for sym, t in tickers.items():
    if '/USDT' in sym and t.get('quoteVolume', 0):
        vol = float(t.get('quoteVolume', 0) or 0)
        price = float(t.get('last', 0) or 0)
        if vol > 0:
            pairs.append((sym, vol, price))
pairs.sort(key=lambda x: x[1], reverse=True)
print(f'Total USDT pairs on KuCoin: {len(pairs)}')
print()
for i, (s, v, p) in enumerate(pairs[:60]):
    print(f'{i+1:3}. {s:<20} vol=${v:>14,.0f}  price={p}')
