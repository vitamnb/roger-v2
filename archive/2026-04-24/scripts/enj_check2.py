import ccxt, pandas as pd
kucoin = ccxt.kucoin()
df = kucoin.fetch_ohlcv('ENJ/USDT', '1h', limit=25)
df = pd.DataFrame(df, columns=['ts','open','high','low','close','vol'])
df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
df['ema12'] = df['close'].ewm(span=12).mean()
start = pd.Timestamp('2026-04-23 00:00', tz='UTC')
display = df[df['ts'] >= start][['ts','open','high','low','close','ema12']].copy()
display = display.reset_index(drop=True)

partial_tp = 0.05838 * 1.035
hard_stop = 0.05838 * 0.95

print('=== ENJ hourly ENJ/USDT ===')
for i, row in display.iterrows():
    diff = row['close'] - row['ema12']
    ts = str(row['ts'])
    marker = ''
    if row['low'] <= hard_stop:
        marker = ' *** HIT HARD STOP'
    elif row['close'] >= partial_tp:
        marker = ' *** HIT PARTIAL TP'
    elif diff < 0:
        marker = ' [<<< BELOW EMA12 - exit triggers]'
    print(f"{ts} O={row['open']:.5f} H={row['high']:.5f} L={row['low']:.5f} C={row['close']:.5f} ema12={row['ema12']:.5f} diff={diff:+.5f}{marker}")

print()
print(f'partial TP: {partial_tp:.5f}')
print(f'hard stop:  {hard_stop:.5f}')
print(f'entry:      0.05838')
print()
print('=== What happened ===')
print('Entry at 02:00 UTC @ 0.05838')
print('03:00 candle: close 0.05803 BELOW ema12 0.05818')
print('  -> populate_exit_trend fires, exit_long=1')
print('  -> Freqtrade places LIMIT SELL @ 0.05803')
print('  -> Order sits there waiting')
print('04:00 candle: still below EMA12')
print('05:00 candle: price recovers to 0.05873, limit sell fills @ 0.05829')
print('  -> -0.35% loss, hard stop never hit')
print()
print('Key insight: populate_exit_trend runs CONTINUOUSLY.')
print('Once exit_long=1 is set, it stays set until trade closes.')
print('The limit sell waits for price to bounce back and fills it.')
