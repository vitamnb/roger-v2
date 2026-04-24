import ccxt
from datetime import datetime

ex = ccxt.kucoin({'options': {'defaultType': 'spot'}})

# Get daily candles going back
daily = ex.fetch_ohlcv('HOLD/USDT', '1d', limit=30)
print('=== Daily candles (30d) ===')
for c in daily:
    ts = datetime.fromtimestamp(c[0]/1000).strftime('%Y-%m-%d')
    print(f'{ts} | O:{c[1]:.6f} H:{c[2]:.6f} L:{c[3]:.6f} C:{c[4]:.6f} V:{c[5]:.0f}')

# Get 4h candles for more detail on the pump
h4 = ex.fetch_ohlcv('HOLD/USDT', '4h', limit=30)
print()
print('=== 4h candles (last 15) ===')
for c in h4[-15:]:
    ts = datetime.fromtimestamp(c[0]/1000).strftime('%Y-%m-%d %H:%M')
    print(f'{ts} | O:{c[1]:.6f} H:{c[2]:.6f} L:{c[3]:.6f} C:{c[4]:.6f} V:{c[5]:.0f}')

# Get 15m candles - look at today's activity
m15 = ex.fetch_ohlcv('HOLD/USDT', '15m', limit=100)
print()
print('=== 15m candles today ===')
for c in m15[-20:]:
    ts = datetime.fromtimestamp(c[0]/1000).strftime('%H:%M')
    print(f'{ts} | O:{c[1]:.6f} H:{c[2]:.6f} L:{c[3]:.6f} C:{c[4]:.6f} V:{c[5]:.0f}')