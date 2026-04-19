import ccxt, pandas as pd, numpy as np

ex = ccxt.kucoin({'enableRateLimit': True})
ex.load_markets()

RSI_PERIOD, MA_PERIOD, BB_WINDOW, BB_STD = 14, 20, 20, 2
ATR_PERIOD = 14

def fetch(sym, tf='1h', days=30):
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
    # Aggressive entry: also allow RSI < 40 (oversold bounce) alongside cross-above-50
    df['signal_50'] = (df['rsi'] > 50) & (df['rsi_prev'] <= 50) & (df['vs_ma'] > 0)
    df['signal_40'] = (df['rsi'] < 40) & (df['rsi_prev'] >= 40) & (df['bb_pct'] < 0.3) & (df['vol_ratio'] > 1.0)
    df['signal'] = df['signal_50'] | df['signal_40']
    return df

def backtest_aggressive(df, capital=58.0, risk_pct=5.0, rr=3.0,
                        max_positions=2, trailing_adr=0.03):
    """
    Aggressive backtest:
    - 5% risk per trade
    - 3:1 R:R take profit
    - Trailing stop once in profit (moves up as price rises)
    - Up to 2 concurrent positions
    - Aggressive entries: RSI cross above 50 OR RSI<40 bounce
    """
    trades = []
    peak = capital
    max_dd = 0.0
    positions = []  # list of active position dicts
    closed_capital = capital

    for i, (ts, row) in enumerate(df.iterrows()):

        # --- TRAILING STOP CHECK for each position ---
        for pos in positions[:]:
            if pos['profit_pct'] >= 1.0:  # in profit by 1%+ -- start trailing
                new_stop = row['c'] * (1 - trailing_adr)
                if new_stop > pos['trail_stop']:
                    pos['trail_stop'] = new_stop
                    pos['stop'] = new_stop  # lock in higher stop

            pos['profit_pct'] = (row['c'] - pos['entry']) / pos['entry'] * 100

            # Exit checks
            exit_price, exit_reason = None, None
            lo, hi = row['l'], row['h']

            if lo <= pos['stop'] <= hi:
                exit_price, exit_reason = pos['stop'], 'trail_stop'
            elif hi >= pos['tp'] >= lo:
                exit_price, exit_reason = pos['tp'], 'tp_hit'
            elif row.get('rsi', 50) > 80:
                exit_price, exit_reason = row['c'], 'rsi_overbought'
            elif row.get('vs_ma', 0) < -3:
                exit_price, exit_reason = row['c'], 'trend_broken'
            elif pos['profit_pct'] >= 15:
                exit_price, exit_reason = row['c'], 'profit_target_15'

            if exit_price:
                pnl_val = pos['units'] * (exit_price - pos['entry'])
                closed_capital += pnl_val
                dd = (peak - closed_capital) / peak * 100
                max_dd = max(max_dd, dd)
                peak = max(peak, closed_capital)
                trades.append({
                    'pair': pos['pair'],
                    'entry_time': pos['entry_time'],
                    'exit_time': ts,
                    'ret': (exit_price - pos['entry']) / pos['entry'] * 100,
                    'pnl': pnl_val,
                    'ex': exit_reason,
                    'cap_after': closed_capital,
                    'concurrent': len(positions),
                    'trailed': pos['trail_stop'] > pos['orig_stop']
                })
                positions.remove(pos)

        # --- ENTRY CHECK ---
        if len(positions) < max_positions:
            if row.get('signal') and not pd.isna(row.get('signal')):
                entry = row['c']
                bl = row['bb_lower']
                sl = row['swing_low']
                atr = row.get('atr', 0)

                if row['bb_pct'] < 0.25 and not np.isnan(bl) and bl > 0:
                    stop = bl * 0.99
                elif not np.isnan(atr) and atr > 0:
                    stop = entry - atr * 1.5
                elif not np.isnan(sl):
                    stop = sl * 0.995
                else:
                    stop = entry * 0.97  # 3% hard stop

                sp = max((entry - stop) / entry * 100, 1.0)
                tp = entry + (entry - stop) * rr
                units = closed_capital * (risk_pct / 100) / (entry * sp / 100)

                positions.append({
                    'pair': str(df.index.name),
                    'entry_time': ts,
                    'entry': entry,
                    'stop': stop,
                    'orig_stop': stop,
                    'trail_stop': stop,
                    'tp': tp,
                    'units': units,
                    'sp': sp,
                    'profit_pct': 0.0,
                })

    # Close any open positions at end
    for pos in positions:
        exit_price = df.iloc[-1]['c']
        pnl_val = pos['units'] * (exit_price - pos['entry'])
        closed_capital += pnl_val
        trades.append({
            'pair': pos['pair'],
            'entry_time': pos['entry_time'],
            'exit_time': df.index[-1],
            'ret': (exit_price - pos['entry']) / pos['entry'] * 100,
            'pnl': pnl_val,
            'ex': 'eod_close',
            'cap_after': closed_capital,
            'concurrent': len(positions),
            'trailed': False
        })

    return trades, closed_capital, peak, max_dd

pairs = ['BTC/USDT','ETH/USDT','ARB/USDT','NEAR/USDT','LINK/USDT','SOL/USDT','XRP/USDT','AVAX/USDT','ADA/USDT']

print()
print('=' * 85)
print('[AGGRESSIVE BACKTEST] -- 1h | 30 days | $58 | 5% risk | 3:1 R:R | Max 2 concurrent')
print('  Entry: RSI>50 cross + price above MA  OR  RSI<40 bounce + vol spike + BB%<0.3')
print('  Exit:   TP hit / Trail stop (3% ADR) / RSI>80 / Trend broken / +15% profit cap')
print('=' * 85)
print()
print('Pair          Trades  WinRate  AvgWin%  AvgLoss%   Ret%   MaxDD%  Expectancy  Trailed')
print('-' * 85)

results = []
for pair in pairs:
    df = fetch(pair, tf='1h', days=30)
    df = indicators(df)
    if df.empty:
        print(f'{pair:<14} No data')
        continue
    trades, cap, peak, max_dd = backtest_aggressive(df)
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
    num_trailed = sum(1 for t in trades if t.get('trailed'))
    print(f'{pair:<14} {len(trades):>6}  {wr:>6.0f}%  {avg_win:>+7.2f}%  {avg_loss:>+8.2f}%  '
          f'{ret_pct:>+7.1f}%  {max_dd:>6.1f}%  {expectancy:>+10.3f}%  {num_trailed:>3}')
    results.append({
        'pair': pair, 'trades': len(trades), 'wr': wr,
        'avg_win': avg_win, 'avg_loss': avg_loss,
        'ret': ret_pct, 'max_dd': max_dd, 'expectancy': expectancy,
        'trailed': num_trailed, 'final_cap': cap
    })

# Aggressive approach: compound winner pairs
good = [r for r in results if r['expectancy'] > 0.5]
if good:
    combined_ret = np.mean([r['ret'] for r in good])
    avg_wr = np.mean([r['wr'] for r in good])
    avg_dd = np.mean([r['max_dd'] for r in good])
    avg_exp = np.mean([r['expectancy'] for r in good])
    print()
    print(f"Average (expectancy > 0.5 pairs): {len(good)} pairs")
    print(f"  Avg Win Rate:    {avg_wr:.0f}%")
    print(f"  Avg Return:     {combined_ret:+.1f}%")
    print(f"  Avg Max DD:      {avg_dd:.1f}%")
    print(f"  Avg Expectancy:  {avg_exp:+.3f}%")
    print()
    print(f"  If you had $58 x {len(good)} separate strategies running simultaneously:")
    total = sum(r['final_cap'] for r in good)
    print(f"  Combined capital: ${total:.2f}  (started at ${58*len(good):.0f})")
