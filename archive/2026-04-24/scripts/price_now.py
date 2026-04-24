import requests, sqlite3

KUCOIN_API = "https://api.kucoin.com/api/v1"

def get_price(symbol):
    params = {"symbol": symbol.replace("/", "-")}
    r = requests.get(f"{KUCOIN_API}/market/orderbook/level1", params=params, timeout=5)
    data = r.json().get("data", {})
    return float(data.get("price", 0))

conn = sqlite3.connect(r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite")
c = conn.cursor()
c.execute("SELECT pair, open_rate FROM trades WHERE is_open = 1")
open_trades = c.fetchall()
conn.close()

print(f"\n{'='*65}")
print(f"OPEN TRADES — {len(open_trades)} active")
print(f"{'='*65}")
for pair, open_rate in open_trades:
    entry = float(open_rate)
    current = get_price(pair)
    pnl_pct = (current - entry) / entry * 100 if entry > 0 else 0
    marker = " +" if pnl_pct > 0 else (" -" if pnl_pct < -1 else "")
    print(f"  {pair:<12} entry=${entry:.5f}  now=${current:.5f}  pnl={pnl_pct:+.2f}%{marker}")
print(f"{'='*65}")
