import ccxt

ex = ccxt.kucoin({'options': {'defaultType': 'spot'}})

# Get ticker
ticker = ex.fetch_ticker('HOLD/USDT')
print('=== HOLD/USDT Ticker ===')
print(f'Price: {ticker["last"]:.6f}')
print(f'24h Change: {ticker["change"]*100:.2f}%')
print(f'24h High: {ticker["high"]:.6f}')
print(f'24h Low: {ticker["low"]:.6f}')
print(f'24h Volume: {ticker["quoteVolume"]:,.0f} USDT')
print(f'Bid: {ticker["bid"]:.6f}')
print(f'Ask: {ticker["ask"]:.6f}')
print(f'Spread: {(ticker["ask"]-ticker["bid"])/ticker["bid"]*100:.3f}%')

# Get OHLCV for 1h candles (last 48)
ohlcv = ex.fetch_ohlcv('HOLD/USDT', '1h', limit=48)
print()
print('=== Last 48 1h candles ===')
for c in ohlcv[-12:]:
    ts = c[0]/1000
    print(f'{ts} | O:{c[1]:.6f} H:{c[2]:.6f} L:{c[3]:.6f} C:{c[4]:.6f} V:{c[5]:.0f}')

# Try to get more info from markets
markets = ex.load_markets()
if 'HOLD/USDT' in markets:
    m = markets['HOLD/USDT']
    print()
    print('=== Market Info ===')
    for k, v in m.items():
        print(f'{k}: {v}')