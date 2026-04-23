import requests
from datetime import datetime

r = requests.get('http://127.0.0.1:8080/api/v1/status', auth=('roger','RogerDryRun2026!'), timeout=10)
data = r.json()

if isinstance(data, list):
    print(f"Total trades: {len(data)}")
    
    # Separate open and closed
    open_trades = [t for t in data if t.get('is_open')]
    closed_trades = [t for t in data if not t.get('is_open')]
    
    print(f"Open: {len(open_trades)} | Closed: {len(closed_trades)}")
    
    if open_trades:
        print("\n=== OPEN TRADES ===")
        for t in open_trades:
            pair = t.get('pair')
            profit = t.get('profit_ratio', 0) * 100
            entry = t.get('open_rate', 0)
            current = t.get('current_rate', entry)
            print(f"  {pair}: {profit:+.2f}% | Entry: ${entry:.4f} | Current: ${current:.4f}")
    
    if closed_trades:
        print("\n=== CLOSED TRADES ===")
        total_profit = 0
        for t in closed_trades:
            pair = t.get('pair')
            profit = t.get('profit_ratio', 0) * 100
            profit_abs = t.get('profit_abs', 0)
            reason = t.get('close_reason', 'unknown')
            total_profit += profit_abs
            print(f"  {pair}: {profit:+.2f}% (${profit_abs:+.2f}) | {reason}")
        
        print(f"\nTotal PnL: ${total_profit:+.2f}")
