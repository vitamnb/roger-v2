import ccxt

kucoin = ccxt.kucoin()

# Get ticker for RAVE/USDT
ticker = kucoin.fetch_ticker('RAVE/USDT')
print(f"RAVE/USDT current price: ${ticker['last']}")
print(f"24h high: ${ticker['high']}")
print(f"24h low: ${ticker['low']}")
print(f"24h volume: {ticker['baseVolume']}")
print(f"24h change: {ticker['change']*100:.2f}%")
print(f"Bid: ${ticker['bid']} | Ask: ${ticker['ask']}")

# Also check creation time / how new the market is
info = ticker.get('info', {})
created = info.get('tradingStartTime') or info.get('enableTime')
if created:
    import datetime
    ts = int(str(created)[:10]) if len(str(created)) > 10 else created
    dt = datetime.datetime.fromtimestamp(ts/1000, tz=datetime.timezone(datetime.timedelta(hours=10)))
    age_days = (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))) - dt).days
    print(f"\nMarket created: {dt.strftime('%Y-%m-%d %H:%M AEST')} ({age_days} days ago)")
else:
    print(f"\nMarket info: {info}")