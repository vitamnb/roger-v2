import pandas as pd
import pyarrow.feather as feather
from pathlib import Path

data_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\data\kucoin")

print("=== Checking downloaded feather files ===")
files = list(data_dir.glob("*.feather"))
print(f"Files found: {len(files)}")
print()

total_rows = 0
for f in sorted(files):
    try:
        df = feather.read_table(f).to_pandas()
        if hasattr(df, 'index') and hasattr(df.index, 'tz'):
            ts_col = df.index
        elif 'timestamp' in df.columns:
            ts_col = pd.to_datetime(df['timestamp'])
        else:
            ts_col = pd.to_datetime(df.iloc[:, 0])
        start = ts_col.min()
        end = ts_col.max()
        rows = len(df)
        total_rows += rows
        print(f"{f.stem:20} {rows:5} rows  {start.strftime('%Y-%m-%d')} -> {end.strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"{f.stem:20} ERROR: {e}")

print()
print(f"Total rows: {total_rows}")
print()

# Check RSI values for BTC - see what the actual RSI range is
print("=== BTC/USDT RSI check ===")
btc_file = data_dir / "BTC_USDT-1h.feather"
if btc_file.exists():
    df = feather.read_table(btc_file).to_pandas()
    import numpy as np
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    print(f"Current RSI: {rsi.iloc[-1]:.1f}")
    print(f"RSI range (last 30): {rsi.iloc[-30:].min():.1f} - {rsi.iloc[-30:].max():.1f}")
    print(f"RSI crosses through 35 in last 30? {(rsi > 35).sum()} bars")
    print(f"RSI <= 30 then > 35? crossings = {((rsi.shift(1) <= 30) & (rsi > 35)).sum()}")
else:
    print("BTC file not found")