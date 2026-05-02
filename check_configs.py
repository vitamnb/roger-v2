import json

for bot in ['Roger_v3_Sniper', 'Roger_v2_Quality']:
    with open(f'C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot}.json') as f:
        c = json.load(f)
    print(f'{bot}:')
    print(f'  pair_whitelist: {pair_whitelist in c}')
    print(f'  pairlists: {pairlists in c}')
    print(f'  keys: {list(c.keys())}')
