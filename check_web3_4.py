import ccxt

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

# Check what Web3 / SOL ecosystem pairs we CAN access via API
pairs_to_check = [
    'BONK/USDT', 'WIF/USDT', 'RAY/USDT', 'JTO/USDT', 'PYTH/USDT',
    'DRIFT/USDT', 'SOL/USDT', 'ACTSOL/USDT', 'ARCSOL/USDT', 'SOLV/USDT',
    'RESOLV/USDT', 'PLAYSOLANA/USDT'
]

print("=== KuCoin API Access to Web3/SOL Ecosystem ===")
print()

for pair in pairs_to_check:
    try:
        ticker = exchange.fetch_ticker(pair)
        print(f"{pair}:")
        print(f"  Price: ${ticker['last']:.6f}")
        print(f"  24h Vol: ${ticker['quoteVolume']:,.0f}")
        change_pct = float(ticker.get('info', {}).get('changeRate', 0) or 0) * 100
        print(f"  24h Change: {change_pct:+.1f}%")
        print(f"  24h High: ${ticker['high']:.6f} | Low: ${ticker['low']:.6f}")
        print()
    except Exception as e:
        print(f"{pair}: ERROR — {e}")
        print()

print("=== What the KuCoin App Web3 Market Actually Is ===")
print("""
The 'Web3 Market' button in the KuCoin app is a SOL-native DEX aggregator.
It connects to your Solana wallet and routes trades through:
  - Jupiter (primary price discovery)
  - Raydium
  - Orca
  - Other Solana DEXes

This is NOT KuCoin API trading — it's on-chain execution.
You need: a Solana wallet + SOL for gas + the Web3 button in the app.

What's accessible via API:
  - All standard KuCoin spot pairs (BONK, WIF, RAY, JTO, PYTH, DRIFT, etc.)
  - These are CEX trades, settle on KuCoin, same as other pairs

What's NOT accessible via API:
  - Web3 Market / DEX trades (Solana blockchain, needs SOL wallet)
  - These require the in-app Web3 button
""")