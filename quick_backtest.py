import ccxt, pandas as pd, numpy as np

ex = ccxt.kucoin({'enableRateLimit': True})
ex.load_markets()

RSI_PERIOD, MA_PERIOD, BB_WINDOW, BB_STD = 14, 20, 20, 2
ATR_PERIOD = 14

def fetch(sym, tf='4h', days=90):
    since = ex.parse8601((pd.Timestamp.utcnow()-pd.Timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z'))
    cs = ex.fetch_ohlcv(sym, tf, since=since, limit=1000)
    if not cs:
        return pd.DataFrame()
    df = pd.DataFrame(cs, columns=['ts','o','h','l','c','v'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df.sort_index()

def indicators(df):
    if df.empty:
        return df
    d = df['c'].diff()
    g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
    l = (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df['rsi'] = 100 - (100 / (1 + g / l.replace(0, np.nan)))
    df['ma20'] = df['c'].rolling(MA_PERIOD).mean()
    df['vol_sma'] = df['v'].rolling(20).mean()
    df['vol_ratio'] = df['v'] / df['vol_sma']
    bb_std = df['c'].rolling(BB_WINDOW).std()
    df['bb_mid'] = df['c'].rolling(BB_WINDOW).mean()
    df['bb_upper'] = df['bb_mid'] + BB_STD * bb_std
    df['bb_lower'] = df['bb_mid'] - BB_STD * bb_std
    bb_range = df['bb_upper'] - df['bb_lower']
    df['bb_pct'] = (df['c'] - df['bb_lower']) / bb_range.replace(0, np.nan)
    df['vs_ma'] = (df['c'] - df['ma20']) / df['ma20'] * 100
    df['atr'] = pd.concat([
        df['h'] - df['l'],
        (df['h'] - df['c'].shift(1)).abs(),
        (df['l'] - df['c'].shift(1)).abs()
    ], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()
    df['swing_low'] = df['l'].rolling(5).min()
    df['rsi_prev'] = df['rsi'].shift(1)
    df['signal'] = (df['rsi'] > 50) & (df['rsi_prev'] <= 50) & (df['vs_ma'] > 0)
    return df

def backtest(df, capital=58.0, risk_pct=2.0, rr=2.0):
    trades = []
    peak = capital
    max_dd = 0.0
    pos = None

    for i, (ts, row) in enumerate(df.iterrows()):
        if pos is None:
            if row.get('signal') and not pd.isna(row.get('signal')):
                entry = row['c']
                bl = row['bb_lower']
                sl = row['swing_low']
                atr = row.get('atr', 0)
                if row['bb_pct'] < 0.3 and not np.isnan(bl) and bl > 0:
                    stop = bl * 0.995
                elif not np.isnan(sl):
                    stop = sl * 0.995
                elif not np.isnan(atr) and atr > 0:
                    stop = entry - atr
                else:
                    stop = entry * 0.98
                sp = max((entry - stop) / entry * 100, 0.5)
                tp = entry + (entry - stop) * rr
                units = capital * (risk_pct / 100) / (entry * sp / 100)
                pos = {'entry': entry, 'stop': stop, 'tp': tp, 'units': units}
        else:
            exit_price, exit_reason = None, None
            lo, hi = row['l'], row['h']
            if lo <= pos['stop'] <= hi:
                exit_price, exit_reason = pos['stop'], 'stop'
            elif hi >= pos['tp'] >= lo:
                exit_price, exit_reason = pos['tp'], 'tp'
            elif row.get('rsi', 50) > 75:
                exit_price, exit_reason = row['c'], 'rsi_overbought'
            elif row.get('vs_ma', 0) < -2:
                exit_price, exit_reason = row['c'], 'trend_broken'

            if exit_price:
                pnl_pct = (exit_price - pos['entry']) / pos['entry'] * 100
                pnl_val = pos['units'] * (exit_price - pos['entry'])
                capital += pnl_val
                dd = (peak - capital) / peak * 100
                max_dd = max(max_dd, dd)
                peak = max(peak, capital)
                trades.append({
                    'pair': str(df.index.name),
                    'ret': pnl_pct,
                    'pnl': pnl_val,
                    'ex': exit_reason,
                    'cap': capital
                })
                pos = None

    return trades, capital, peak, max_dd

pairs = ['BTC/USDT','ETH/USDT','ARB/USDT','NEAR/USDT','LINK/USDT','SOL/USDT','XRP/USDT']

print('Pair          Trades  WinRate  AvgWin%  AvgLoss%  Ret%    MaxDD%  Expectancy')
print('-' * 80)

for pair in pairs:
    df = fetch(pair)
    df = indicators(df)
    if df.empty:
        print(f'{pair:<14} No data')
        continue
    trades, cap, peak, max_dd = backtest(df)
    if not trades:
        print(f'{pair:<14} 0 trades')
        continue
    wins = [t for t in trades if t['ret'] > 0]
    losses = [t for t in trades if t['ret'] <= 0]
    wr = len(wins) / len(trades) * 100
    avg_win = np.mean([t['ret'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['ret'] for t in losses]) if losses else 0
    expectancy = np.mean([t['ret'] for t in trades])
    ret_pct = (cap / 58.0 - 1) * 100
    print(f'{pair:<14} {len(trades):>6}  {wr:>6.0f}%  {avg_win:>+7.2f}%  {avg_loss:>+8.2f}%  {ret_pct:>+6.1f}%  {max_dd:>6.1f}%  {expectancy:>+10.3f}%')

print()
print('Scanner-based signals vs actual trades completed (4h candles, 90 days, $58, 2% risk, 2:1 R:R)')
