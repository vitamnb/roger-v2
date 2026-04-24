import pandas as pd
import pyarrow.feather as feather
import numpy as np
from pathlib import Path

data_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\data\kucoin")

def calc_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    return 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

def check_btc_signals():
    df = feather.read_table(data_dir / "BTC_USDT-1h.feather").to_pandas()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    elif df.index.name and 'time' in df.index.name.lower():
        pass  # already indexed
    else:
        # try first column as datetime
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        df.set_index(df.columns[0], inplace=True)
    
    # Indicators
    df['rsi'] = calc_rsi(df['close'])
    df['rsi_prev'] = df['rsi'].shift(1)
    df['ema12'] = df['close'].ewm(span=12).mean()
    df['ema26'] = df['close'].ewm(span=26).mean()
    df['ema12_dist_pct'] = (df['close'] - df['ema12']) / df['ema12'] * 100
    df['green'] = df['close'] > df['open']
    df['green_prev'] = df['green'].shift(1)
    
    # Strategy conditions
    cond1 = df['ema12'] > df['ema26']  # EMA bull
    cond2 = df['ema12_dist_pct'] <= 0.5  # Price at EMA pullback
    cond3 = (df['rsi'] > 35) & (df['rsi_prev'] <= 30)  # RSI cross through 35 from below 30
    cond4 = df['green_prev'] == True  # Previous candle green
    
    # Each condition separately
    print("=== BTC/USDT — condition coverage (last 100 bars) ===")
    df_recent = df.iloc[-100:]
    c1 = (df_recent['ema12'] > df_recent['ema26'])
    c2 = (df_recent['ema12_dist_pct'] <= 0.5)
    c3 = (df_recent['rsi'] > 35) & (df_recent['rsi_prev'] <= 30)
    c4 = df_recent['green_prev'] == True
    
    print(f"Condition 1 (EMA bull):       {c1.sum():3d} bars ({c1.sum()}%)")
    print(f"Condition 2 (at EMA):         {c2.sum():3d} bars ({c2.sum()}%)")
    print(f"Condition 3 (RSI cross 35):   {c3.sum():3d} bars ({c3.sum()}%)")
    print(f"Condition 4 (prev green):     {c4.sum():3d} bars ({c4.sum()}%)")
    
    # All 4 conditions
    all4 = cond1 & cond2 & cond3 & cond4
    print(f"\nAll 4 conditions (last 100): {all4.sum()} bars")
    all4_full = (df['ema12'] > df['ema26']) & (df['ema12_dist_pct'] <= 0.5) & ((df['rsi'] > 35) & (df['rsi_prev'] <= 30)) & (df['green'].shift(1) == True)
    print(f"All 4 conditions (full):      {all4_full.sum()} bars")
    
    # Where are RSI crosses happening?
    crosses = (df['rsi'] > 35) & (df['rsi_prev'] <= 30)
    print(f"\nTotal RSI crosses through 35 in dataset: {crosses.sum()}")
    
    # When RSI crosses, is EMA bull?
    cross_ema_bull = (c1[c3.values[c1[c3].values]]).sum() if c3.sum() > 0 else 0
    print(f"RSI crosses with EMA bull (last 100): {cross_ema_bull}")
    
    # Show last 10 RSI crosses
    cross_idx = df[crosses].index[-10:]
    print("\nLast 10 RSI crosses through 35:")
    for idx in cross_idx:
        row = df.loc[idx]
        print(f"  {idx.strftime('%Y-%m-%d %H:%M')} | RSI={row['rsi']:.1f} prev={row['rsi_prev']:.1f} | EMA12>{row['ema12']:.0f} EMA26>{row['ema26']:.0f} dist={row['ema12_dist_pct']:+.2f}% green_prev={row['green']}")

check_btc_signals()