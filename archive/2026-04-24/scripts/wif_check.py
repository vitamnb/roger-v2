import ccxt
import pandas as pd

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

symbol = 'WIF/USDT'

print("=== WIF/USDT on KuCoin ===")
print(f"Symbol: {symbol}")
print()

# Current ticker
ticker = exchange.fetch_ticker(symbol)
print(f"Current price: ${ticker['last']:.6f}")
print(f"24h high: ${ticker['high']:.6f}")
print(f"24h low: ${ticker['low']:.6f}")
change_pct = float(ticker.get('info', {}).get('changeRate', 0) or 0) * 100
print(f"24h change: {change_pct:+.1f}%")
print(f"24h volume: ${ticker['quoteVolume']:,.0f}")
print(f"24h turnover: ${ticker['baseVolume']:,.0f} WIF")
print()

# Get 1h candles for last 7 days
ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=168)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('timestamp', inplace=True)

print("Last 7 days of 1h candles:")
print(f"{'Time':<22} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Change%':>8}")
print("-" * 75)

# Group by date
daily = df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
for idx, row in daily.iterrows():
    if pd.notna(row['close']) and row['volume'] > 0:
        change = (row['close'] / row['open'] - 1) * 100 if row['open'] > 0 else 0
        print(f"{idx.strftime('%Y-%m-%d'):<22} ${row['open']:.4f}  ${row['high']:.4f}  ${row['low']:.4f}  ${row['close']:.4f}  {change:>+7.1f}%")

print()
print("=" * 75)

# Show daily highs/lows for the period
first_price = df['close'].iloc[0]
last_price = df['close'].iloc[-1]
max_price = df['high'].max()
min_price = df['low'].min()
period_return = (last_price / first_price - 1) * 100

print(f"\nPeriod stats (7 days):")
print(f"  First price: ${first_price:.4f}")
print(f"  Last price:  ${last_price:.4f}")
print(f"  Period high: ${max_price:.4f}")
print(f"  Period low:  ${min_price:.4f}")
print(f"  Period return: {period_return:+.1f}%")
print()

# Show the move from Apr 19 to Apr 22 (the pump I cited)
apr19 = df[df.index.date.astype(str) == '2026-04-19']
apr22 = df[df.index.date.astype(str) == '2026-04-22']
if len(apr19) > 0 and len(apr22) > 0:
    apr19_close = apr19['close'].iloc[-1]
    apr22_close = apr22['close'].iloc[-1]
    apr22_high = apr22['high'].max()
    move = (apr22_high / apr19_close - 1) * 100
    print(f"Move Apr 19 close -> Apr 22 high: ${apr19_close:.4f} -> ${apr22_high:.4f} = {move:+.1f}%")
    print(f"Move Apr 19 close -> Apr 22 close: ${apr19_close:.4f} -> ${apr22_close:.4f} = {(apr22_close/apr19_close-1)*100:+.1f}%")

# Compare with CoinGecko data if available
print()
print("=" * 75)
print("Historical context:")
print("  WIF/USDT listed on KuCoin: checking market info...")

market = exchange.market(symbol)
info = market.get('info', {})
for field in ['firstOpenDate', 'tradingStartTime', 'created']:
    val = info.get(field)
    if val:
        print(f"  {field}: {val}")

# URL to KuCoin WIF page
print()
print("KuCoin WIF/USDT market page:")
print("  https://www.kucoin.com/trade/wif-usdt")
print()
print("Alternative (CoinGecko WIF page):")
print("  https://www.coingecko.com/en/coins/wif")