import ccxt
import pandas as pd

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

print("=== Checking SOL and WIF 24h change values ===")
print()

for sym in ['SOL/USDT', 'WIF/USDT', 'BTC/USDT']:
    try:
        ticker = exchange.fetch_ticker(sym)
        print(f"{sym}:")
        print(f"  Last price:        ${ticker['last']:.6f}")
        print(f"  24h open:         ${ticker.get('open', 'N/A'):.6f}" if isinstance(ticker.get('open'), (int, float)) else f"  24h open:         N/A")
        change_pct = float(ticker.get('info', {}).get('changeRate', 0) or 0) * 100
        print(f"  24h change:        {change_pct:+.2f}%")
        print(f"  24h change raw:   {ticker.get('change', 0):+.6f}")
        print(f"  24h high:         ${ticker['high']:.6f}")
        print(f"  24h low:          ${ticker['low']:.6f}")
        print(f"  24h quote volume: ${ticker['quoteVolume']:,.0f}")
        print(f"  info:             {ticker.get('info', {})}")
        print()
    except Exception as e:
        print(f"{sym}: ERROR - {e}")
        print()

print("=== Historical check: WIF last 30 days ===")
ohlcv = exchange.fetch_ohlcv('WIF/USDT', '1d', limit=30)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

print(f"{'Date':<12} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Change':>8}")
print("-" * 65)
for _, row in df.iterrows():
    chg = (row['close'] / row['open'] - 1) * 100 if row['open'] > 0 else 0
    print(f"{row['timestamp'].strftime('%Y-%m-%d'):<12} ${row['open']:.4f}  ${row['high']:.4f}  ${row['low']:.4f}  ${row['close']:.4f}  {chg:>+7.1f}%")