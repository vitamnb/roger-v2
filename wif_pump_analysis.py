import ccxt
import pandas as pd
import numpy as np
import talib.abstract as ta

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

symbol = 'WIF/USDT'

# Fetch 4h candles for last 7 days
print(f"=== {symbol} Pre-Pump Analysis ===")
print()

# Get 4h data
ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=42)  # 7 days of 4h
df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
df_4h.set_index('timestamp', inplace=True)

# Get 1h data  
ohlcv_1h = exchange.fetch_ohlcv(symbol, '1h', limit=168)  # 7 days of 1h
df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
df_1h.set_index('timestamp', inplace=True)

# Calculate indicators on 1h
df_1h['rsi'] = ta.RSI(df_1h['close'], timeperiod=14)
df_1h['ema12'] = ta.EMA(df_1h['close'], timeperiod=12)
df_1h['ema26'] = ta.EMA(df_1h['close'], timeperiod=26)
df_1h['volume_avg'] = df_1h['volume'].rolling(20).mean()
df_1h['vol_ratio'] = df_1h['volume'] / df_1h['volume_avg']
df_1h['atr'] = ta.ATR(df_1h['high'], df_1h['low'], df_1h['close'], timeperiod=14)
df_1h['price_pct'] = df_1h['close'].pct_change() * 100

# Calculate 4h indicators
df_4h['rsi'] = ta.RSI(df_4h['close'], timeperiod=14)
df_4h['ema12'] = ta.EMA(df_4h['close'], timeperiod=12)
df_4h['ema26'] = ta.EMA(df_4h['close'], timeperiod=26)
df_4h['volume_avg'] = df_4h['volume'].rolling(10).mean()
df_4h['vol_ratio'] = df_4h['volume'] / df_4h['volume_avg']

print("Last 72 hours on 1H chart:")
print("-" * 100)

recent_1h = df_1h.tail(72).copy()
for idx, row in recent_1h.iterrows():
    rsi = row['rsi']
    ema12 = row['ema12']
    ema26 = row['ema26']
    vol_r = row['vol_ratio']
    price_pct = row['price_pct']
    
    # Flag early warning signs
    flags = []
    if rsi < 35: flags.append("RSI_OVERSOLD")
    elif rsi < 45: flags.append("RSI_COOL")
    if ema12 > ema26: flags.append("EMA_BULL")
    if vol_r > 1.5: flags.append(f"VOL_SPIKE({vol_r:.1f}x)")
    if price_pct > 3: flags.append(f"+{price_pct:.1f}%")
    
    flag_str = " | ".join(flags) if flags else "---"
    print(f"{idx.strftime('%m-%d %H:%M')} | ${row['close']:.4f} | RSI:{rsi:5.1f} | Vol:{vol_r:.1f}x | {flag_str}")

print()
print("=== Pre-Pump Signals ===")
print()

# Find the pump start point
pump_start_idx = df_1h['price_pct'].idxmax()
pump_candles = df_1h.loc[pump_start_idx:].head(24)

# Look backwards - what happened before the pump?
print("24h BEFORE pump started:")
print("-" * 80)
before_pump = df_1h.drop(pump_start_idx).tail(24)
for idx, row in before_pump.iterrows():
    rsi = row['rsi'] if not pd.isna(row['rsi']) else 0
    vol_r = row['vol_ratio'] if not pd.isna(row['vol_ratio']) else 0
    ema12 = row['ema12'] if not pd.isna(row['ema12']) else 0
    ema26 = row['ema26'] if not pd.isna(row['ema26']) else 0
    
    # Scan for our trigger conditions
    triggers = []
    if ema12 > ema26: triggers.append("EMA_BULL")
    if rsi < 40: triggers.append(f"RSI_LOW({rsi:.0f})")
    if rsi > 60: triggers.append(f"RSI_HIGH({rsi:.0f})")
    if vol_r > 1.3: triggers.append(f"VOL({vol_r:.1f}x)")
    
    trigger_str = " | ".join(triggers) if triggers else ""
    
    print(f"{idx.strftime('%m-%d %H:%M')} | ${row['close']:.4f} | RSI:{rsi:5.1f} | Vol:{vol_r:.1f}x | EMA:{ema12:.4f}>{ema26:.4f} {trigger_str}")

# Also check 4h for bigger picture
print()
print("=== 4H View (broader context) ===")
print("-" * 80)
recent_4h = df_4h.tail(20)
for idx, row in recent_4h.iterrows():
    rsi = row['rsi'] if not pd.isna(row['rsi']) else 0
    vol_r = row['vol_ratio'] if not pd.isna(row['vol_ratio']) else 0
    ema12 = row['ema12'] if not pd.isna(row['ema12']) else 0
    ema26 = row['ema26'] if not pd.isna(row['ema26']) else 0
    
    flags = []
    if rsi < 40: flags.append(f"RSI_LOW({rsi:.0f})")
    if rsi > 60: flags.append(f"RSI_HIGH({rsi:.0f})")
    if ema12 > ema26: flags.append("EMA_BULL")
    if vol_r > 1.5: flags.append(f"VOL({vol_r:.1f}x)")
    
    print(f"{idx.strftime('%m-%d %H:%M')} | ${row['close']:.4f} | RSI:{rsi:5.1f} | Vol:{vol_r:.1f}x | {', '.join(flags) if flags else '---'}")