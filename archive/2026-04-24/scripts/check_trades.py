import requests

try:
    r = requests.get('http://127.0.0.1:8080/api/v1/trades', auth=('roger','RogerDryRun2026!'), timeout=10)
    print('Status:', r.status_code)
    data = r.json()
    print('Type:', type(data))
    
    if isinstance(data, list):
        print('Total trades:', len(data))
        closed = [t for t in data if not t.get('is_open', True)]
        print('Closed trades:', len(closed))
        
        if closed:
            print('\nRecent closed trades:')
            for t in closed[-10:]:
                pair = t.get('pair', '?')
                profit = t.get('profit_ratio', 0) * 100
                reason = t.get('close_reason', 'unknown')
                print(f'  {pair}: {profit:+.2f}% | {reason}')
    else:
        print('Unexpected response type')
        
except Exception as e:
    print(f'Error: {e}')
