import requests

r = requests.get('http://127.0.0.1:8080/api/v1/status', auth=('roger','RogerDryRun2026!'), timeout=10)
data = r.json()

if isinstance(data, list):
    print(f"Total trades in database: {len(data)}")
    
    for t in data:
        pair = t.get('pair')
        is_open = t.get('is_open')
        profit = t.get('profit_ratio', 0) * 100
        profit_abs = t.get('profit_abs', 0)
        entry = t.get('open_rate', 0)
        current = t.get('current_rate', entry)
        reason = t.get('close_reason', 'open')
        date = t.get('open_date', '?')
        
        status = "OPEN" if is_open else "CLOSED"
        print(f"\n{pair} [{status}]")
        print(f"  Date: {date}")
        print(f"  Entry: ${entry:.4f} | Current: ${current:.4f}")
        print(f"  PnL: {profit:+.2f}% (${profit_abs:+.2f})")
        if not is_open:
            print(f"  Reason: {reason}")
