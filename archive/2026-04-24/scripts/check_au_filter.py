import requests, json

# Check IAG specifically on KuCoin global API
r = requests.get('https://api.kucoin.com/api/v1/symbols', timeout=10)
if r.status_code == 200:
    symbols = r.json().get('data', [])
    iag = [s for s in symbols if s.get('symbol') == 'IAG-USDT']
    print('IAG-USDT on KuCoin GLOBAL:', len(iag) > 0)
    if iag:
        print('  Tradeable:', iag[0].get('enableTrading'))
        print('  Fee:', iag[0].get('feeCategory'))

# Check AU pairs
with open(r'C:\Users\vitamnb\.openclaw\freqtrade\kucoin_au_pairs.txt') as f:
    au_pairs = set(line.strip() for line in f if line.strip())

print('\nIAG in AU pairs file:', 'IAG' in au_pairs)
print('IAG/USDT in AU pairs:', 'IAG/USDT' in au_pairs)

# Check all current whitelist pairs
with open(r'C:\Users\vitamnb\.openclaw\freqtrade\user_data\config.json') as f:
    config = json.load(f)
whitelist = config.get('exchange', {}).get('pair_whitelist', [])

print(f'\nWhitelist: {len(whitelist)} pairs')

# Check which are NOT in AU pairs
not_au = []
for pair in whitelist:
    base = pair.split('/')[0]
    if base not in au_pairs:
        not_au.append(pair)

print(f'NOT in AU pairs: {len(not_au)}')
if not_au:
    for p in not_au:
        print(f'  {p}')
