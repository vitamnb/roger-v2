import requests

r = requests.get('http://127.0.0.1:8080/api/v1/performance', auth=('roger','RogerDryRun2026!'), timeout=10)
print('HTTP:', r.status_code)

if r.status_code == 200:
    data = r.json()
    print('Performance entries:', len(data))
    
    # Sort by most recent (profit_ratio has timestamp)
    for p in data:
        pair = p.get('pair', '?')
        profit = p.get('profit_pct', 0)
        count = p.get('count', 0)
        wins = p.get('wins', 0)
        losses = p.get('losses', 0)
        print(f'  {pair}: {profit:+.2f}% | {wins}W/{losses}L ({count} trades)')
