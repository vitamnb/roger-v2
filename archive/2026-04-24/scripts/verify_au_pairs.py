import ccxt, json, time

# Get all active KuCoin markets
exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
})

print("Fetching KuCoin active markets...")
markets = exchange.fetch_markets()

# Get all USDT pairs that are active
active_usdt = set()
for m in markets:
    if m.get('quote') == 'USDT' and m.get('active', False):
        symbol = m['symbol']  # e.g. "BTC/USDT"
        active_usdt.add(symbol)

print(f"Total active USDT pairs on KuCoin: {len(active_usdt)}")

# Check current whitelist
with open(r'C:\Users\vitamnb\.openclaw\freqtrade\user_data\config.json') as f:
    config = json.load(f)
whitelist = config.get('exchange', {}).get('pair_whitelist', [])

print(f"\nWhitelist pairs: {len(whitelist)}")
print(f"Active on KuCoin: {len([p for p in whitelist if p in active_usdt])}")

not_active = [p for p in whitelist if p not in active_usdt]
if not_active:
    print(f"\nNOT ACTIVE on KuCoin ({len(not_active)}):")
    for p in not_active:
        print(f"  {p}")

# Check AU pairs file
with open(r'C:\Users\vitamnb\.openclaw\freqtrade\kucoin_au_pairs.txt') as f:
    au_bases = set(line.strip() for line in f if line.strip())

print(f"\nAU pairs file: {len(au_bases)} base symbols")

# Check which whitelist pairs are NOT in AU file
not_in_au = []
for pair in whitelist:
    base = pair.split('/')[0]
    if base not in au_bases:
        not_in_au.append(pair)

if not_in_au:
    print(f"\nNOT in AU pairs file ({len(not_in_au)}):")
    for p in not_in_au:
        print(f"  {p}")
else:
    print("\nAll whitelist pairs are in AU file")

# Cross-check: which pairs are in AU file but not active?
in_au_not_active = []
for pair in whitelist:
    base = pair.split('/')[0]
    if base in au_bases and pair not in active_usdt:
        in_au_not_active.append(pair)

if in_au_not_active:
    print(f"\nIn AU file but NOT ACTIVE on KuCoin ({len(in_au_not_active)}):")
    for p in in_au_not_active:
        print(f"  {p}")
