import pandas as pd
import sys
sys.path.insert(0, r'C:\Users\vitamnb\.openclaw\freqtrade\research')
from order_block_detector import detect_order_blocks

df = pd.read_csv(r'C:\Users\vitamnb\.openclaw\freqtrade\data\timeframe_test\ETH_USDT_1d.csv')
df['datetime'] = pd.to_datetime(df['datetime'])

# RSI
delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()
rs = avg_gain / avg_loss
df['rsi'] = 100 - (100 / (1 + rs))
df['rsi_prev'] = df['rsi'].shift(1)
df['volume_avg20'] = df['volume'].rolling(20).mean()

blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)

# Find the signal
for i in range(20, len(df) - 20):
    if df['rsi_prev'].iloc[i] < 35 and df['rsi'].iloc[i] >= 35 and df['rsi_prev'].iloc[i] < 30:
        for _, block in blocks.iterrows():
            if int(block['block_index']) < i and i - int(block['block_index']) <= 50:
                if block['type'] == 'bullish':
                    price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= price <= block['price_high'] * 1.02:
                        if df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * 1.2:
                            print(f"Signal found at: {df['datetime'].iloc[i]}")
                            print(f"Price: {price:.2f}")
                            print(f"RSI: {df['rsi'].iloc[i]:.1f}")
                            print(f"Volume: {df['volume'].iloc[i]:.0f} vs avg {df['volume_avg20'].iloc[i]:.0f}")
                            print(f"Block: low={block['price_low']:.2f} high={block['price_high']:.2f}")
                            
                            # Simulate trade
                            entry_price = price
                            stop_price = block['price_low'] * 0.995
                            target_price = entry_price + (entry_price - stop_price) * 2.0
                            after = df.iloc[i+1:min(i+20, len(df))]
                            low_after = after['low'].min()
                            high_after = after['high'].max()
                            
                            if low_after <= stop_price:
                                print("Result: STOP hit")
                            elif high_after >= target_price:
                                print("Result: TARGET hit")
                            else:
                                print(f"Result: TIMEOUT at {after.iloc[-1]['close']:.2f}")
                            break
