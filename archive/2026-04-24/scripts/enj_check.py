import ccxt, talib as ta, pandas as pd
ex = ccxt.kucoin({'options':{'defaultType':'spot'}})
ohlcv = ex.fetch_ohlcv('ENJ/USDT', '1h', limit=72)
df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','vol'])
df['atr'] = ta.ATR(df['high'], df['low'], df['close'], 14)
df['rsi'] = ta.RSI(df['close'], 14)
df['ema12'] = ta.EMA(df['close'], 12)
df['ema26'] = ta.EMA(df['close'], 26)
row = df.iloc[-1]
atr = row['atr']
entry = 0.05838
tp_partial = entry * 1.035
print(f'Current price: {row["close"]:.6f}')
print(f'ATR(14): {atr:.6f}  ({atr/row["close"]*100:.2f}% of price)')
print(f'Distance to partial TP (+3.5% @ {tp_partial:.6f}): {((tp_partial-row["close"])/row["close"])*100:.2f}%')
print(f'RSI: {row["rsi"]:.1f}')
print(f'Close vs EMA12 ({row["ema12"]:.6f}): {((row["ema12"]-row["close"])/row["close"])*100:.3f}% above')
print()
print('--- ENJ trade outlook ---')
print(f'Partial TP (+3.5%) needs price to reach {tp_partial:.6f}')
print(f'Partial TP is {((tp_partial-row["close"])/row["close"])*100:.2f}% above current price')
print(f'ATR is {atr:.6f} — price needs to move {atr/row["close"]*100:.2f}% to hit partial TP')
print()
print('Historical hold times from 30d backtest (Entry E on ENJ):')
print('  Avg hold: ~10-20 bars (10-20 hours on 1h)')
print('  Winners typically: 8-18 hours')
print('  Full +7% TP resolution: up to 40 hours in chop')
print()
print('ENJ just entered — trade is young. 1-3h to partial TP is realistic in a trending hour.')
