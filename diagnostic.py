import ccxt, pandas as pd, numpy as np

ex = ccxt.kucoin({'enableRateLimit': True})
ex.load_markets()

pairs = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT','ADA/USDT','AVAX/USDT','ARB/USDT','OP/USDT']
timeframe = '4h'
days = 90

print(f'4H HISTORY DIAGNOSTIC')
print(f'{"Pair":<12} {"Candles":>8} {"Start":>12} {"End":>12} {"AvgRSI":>8} {"MaxVol":>8} {"Strict":>8} {"Loose":>8}')
print('-'*75)

for pair in pairs:
    since = ex.parse8601((pd.Timestamp.utcnow() - pd.Timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z'))
    try:
        cs = ex.fetch_ohlcv(pair, timeframe, since=since, limit=1000)
    except Exception as e:
        print(f'{pair:<12} ERROR: {e}')
        continue
    if not cs:
        print(f'{pair:<12} No data')
        continue

    df = pd.DataFrame(cs, columns=['ts','o','h','l','c','v'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')

    delta = df['c'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['vol_ratio'] = df['v'] / df['v'].rolling(20).mean()
    df['ma20'] = df['c'].rolling(20).mean()
    bb_std = df['c'].rolling(20).std()
    df['bb_pct'] = (df['c'] - (df['ma20'] - 2*bb_std)) / (4*bb_std).replace(0, np.nan)
    df['vs_ma'] = (df['c'] - df['ma20']) / df['ma20'] * 100
    df['rsi_prev'] = df['rsi'].shift(1)

    sig_strict = ((df['rsi'] > 50) & (df['rsi_prev'] <= 50) &
                  (df['bb_pct'] < 0.5) & (df['vol_ratio'] > 1.0) & (df['vs_ma'] > 0))
    sig_loose = (df['rsi'] > 50) & (df['rsi_prev'] <= 50) & (df['vs_ma'] > 0)

    avg_rsi = df['rsi'].mean()
    max_vol = df['vol_ratio'].max()

    print(f'{pair:<12} {len(df):>8} {str(df["ts"].iloc[0].date()):>12} {str(df["ts"].iloc[-1].date()):>12} '
          f'{avg_rsi:>8.1f} {max_vol:>8.2f} {sig_strict.sum():>8} {sig_loose.sum():>8}')
