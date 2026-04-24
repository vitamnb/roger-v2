import ccxt, time
exchange = ccxt.kucoin({'enableRateLimit': True})
for pair in ['LTC/USDT', 'ATOM/USDT', 'XRP/USDT', 'BTC/USDT', 'ETH/USDT', 'DOT/USDT']:
    try:
        ticker = exchange.fetch_ticker(pair)
        print(f"{pair}: {ticker['last']}")
    except Exception as e:
        print(f"{pair}: error - {e}")
    time.sleep(0.1)
