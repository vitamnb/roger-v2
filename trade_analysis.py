import sys; sys.path.insert(0, r'C:\Users\vitamnb\.openclaw\freqtrade')
import ccxt
import pandas as pd
import numpy as np

RSI_PERIOD = 14
MA_SHORT, MA_MEDIUM, MA_LONG = 10, 20, 50
BB_WINDOW = 20
ATR_PERIOD = 14
ADX_PERIOD = 14
VOL_SMA_PERIOD = 20

def fetch(pair, tf='1h', days=30):
    x = ccxt.kucoin({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})
    ohlcv = x.fetch_ohlcv(pair, tf, limit=days*24)
    df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df

def add_indicators(df):
    df = df.copy()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(RSI_PERIOD).mean()
    avg_loss = loss.rolling(RSI_PERIOD).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['rsi'] = (100 - (100 / (1 + rs))).clip(0, 100)
    df['ma10'] = df['close'].rolling(MA_SHORT).mean()
    df['ma20'] = df['close'].rolling(MA_MEDIUM).mean()
    df['ma50'] = df['close'].rolling(MA_LONG).mean()
    df['vol_sma'] = df['volume'].rolling(VOL_SMA_PERIOD).mean()
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(ATR_PERIOD).mean()
    df['atr_pct'] = df['atr'] / df['close'] * 100
    plus_dm = delta.where(delta > 0, 0.0).rolling(ADX_PERIOD).mean()
    minus_dm = (-delta).where(delta < 0, 0.0).rolling(ADX_PERIOD).mean()
    adx_numerator = abs(plus_dm - minus_dm)
    adx_denominator = plus_dm + minus_dm
    adx_denominator = adx_denominator.replace(0, np.nan)
    df['adx'] = (adx_numerator / adx_denominator * 100).rolling(ADX_PERIOD).mean().clip(0, 100)
    df['swing_low'] = df['low'].rolling(5).min()
    df['swing_high'] = df['high'].rolling(5).max()
    df['bull_div'] = (df['close'] < df['close'].shift(5)) & (df['rsi'] > df['rsi'].shift(5)) & (df['rsi'] < 60)
    df['vol_spike'] = df['volume'] > df['vol_sma'] * 1.5
    df['vol_ratio'] = df['volume'] / df['vol_sma']
    return df

def regime_score(df, idx, lookback=20):
    sub = df.iloc[:idx+1]
    if len(sub) < 20:
        return 50, "CHOPPY", "LONG"
    adx = sub["adx"].iloc[-1]
    rsi = sub["rsi"].iloc[-1]
    ma10 = sub["ma10"].iloc[-1]
    ma20_val = sub["ma20"].iloc[-1]
    ma20_series = sub["ma20"]
    rsi_avg = sub["rsi"].iloc[-lookback:].mean()
    ma10_20 = (ma10 > ma20_val)
    ts = 0.0; cs = 0.0
    if adx >= 30: ts += 0.4
    elif adx >= 20: ts += 0.2; cs += 0.1
    else: cs += 0.4
    if ma10_20: ts += 0.3
    else: cs += 0.3
    tot = ts + cs
    tp = ts / tot * 100 if tot > 0 else 50
    reg = "STRONG_TREND" if tp >= 60 and adx >= 40 else "TRENDING" if tp >= 60 else "CHOPPY"
    slope = (ma20_series.iloc[-1] / ma20_series.iloc[-10] - 1) * 100 if len(sub) >= 10 else 0
    direction = "LONG" if slope > 0 else "SHORT"
    return rsi, reg, direction

def full_backtest_details(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=True):
    trades = []
    for i in range(50, len(df)):
        row = df.iloc[i]
        if pd.isna(row['rsi']) or pd.isna(row['ma20']):
            continue
        rsi, reg, direction = regime_score(df, i)
        score = 0
        if row.get('bull_div') and direction == "LONG": score += 2
        if row.get('vol_spike') and direction == "LONG": score += 1
        sig_ok = (direction == "LONG" and row['rsi'] < (75 if use_override else 999)) or \
                 (direction == "SHORT" and row['rsi'] > (25 if use_override else 0))
        if sig_ok and direction == "LONG" and score >= 2:
            risk_amount = capital * risk_pct / 100
            atr = row.get('atr_pct', 1.0)
            stop_dist = max(atr * 1.5, 0.005)
            target_dist = stop_dist * rr
            entry = row['close']
            stop = entry * (1 - stop_dist / 100)
            target = entry * (1 + target_dist / 100)
            for j in range(i+1, len(df)):
                if df.iloc[j]['low'] <= stop:
                    pnl = -risk_amount
                    trades.append({'entry_time': df.index[i], 'exit_time': df.index[j],
                                   'direction': 'LONG', 'entry': entry, 'exit': stop,
                                   'pnl': pnl, 'duration_bars': j-i, 'won': False, 'regime': reg})
                    break
                elif df.iloc[j]['high'] >= target:
                    pnl = risk_amount * rr
                    trades.append({'entry_time': df.index[i], 'exit_time': df.index[j],
                                   'direction': 'LONG', 'entry': entry, 'exit': target,
                                   'pnl': pnl, 'duration_bars': j-i, 'won': True, 'regime': reg})
                    break
            capital += pnl
        elif sig_ok and direction == "SHORT" and score >= 2:
            risk_amount = capital * risk_pct / 100
            atr = row.get('atr_pct', 1.0)
            stop_dist = max(atr * 1.5, 0.005)
            target_dist = stop_dist * rr
            entry = row['close']
            stop = entry * (1 + stop_dist / 100)
            target = entry * (1 - target_dist / 100)
            for j in range(i+1, len(df)):
                if df.iloc[j]['high'] >= stop:
                    pnl = -risk_amount
                    trades.append({'entry_time': df.index[i], 'exit_time': df.index[j],
                                   'direction': 'SHORT', 'entry': entry, 'exit': stop,
                                   'pnl': pnl, 'duration_bars': j-i, 'won': False, 'regime': reg})
                    break
                elif df.iloc[j]['low'] <= target:
                    pnl = risk_amount * rr
                    trades.append({'entry_time': df.index[i], 'exit_time': df.index[j],
                                   'direction': 'SHORT', 'entry': entry, 'exit': target,
                                   'pnl': pnl, 'duration_bars': j-i, 'won': True, 'regime': reg})
                    break
            capital += pnl
    return trades

top5 = ['BNRENSHENG/USDT', 'ZEC/USDT', 'VIRTUAL/USDT', 'WIF/USDT', 'H/USDT']
for pair in top5:
    print(f"\n{'='*60}")
    print(f"  {pair}")
    print(f"{'='*60}")
    df = fetch(pair, '1h', 30)
    df = add_indicators(df)
    trades = full_backtest_details(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=True)
    wins = [t for t in trades if t['won']]
    losses = [t for t in trades if not t['won']]
    rets = [t['pnl'] for t in trades]
    total = sum(rets)
    wr = len(wins) / len(trades) * 100 if trades else 0
    durations = [t['duration_bars'] for t in trades]
    win_durations = [t['duration_bars'] for t in wins]
    loss_durations = [t['duration_bars'] for t in losses]
    avg_win_dur = np.mean(win_durations) if win_durations else 0
    avg_loss_dur = np.mean(loss_durations) if loss_durations else 0
    max_win_dur = max(win_durations) if win_durations else 0
    max_loss_dur = max(loss_durations) if loss_durations else 0
    print(f"  Return:      {total:>+.1f}%  ({len(trades)} trades, WR={wr:.0f}%)")
    print(f"  Avg trade:   {np.mean(durations):.1f} bars  ({np.mean(durations)/24:.1f} hrs)")
    print(f"  Avg WIN:     {avg_win_dur:.1f} bars  ({avg_win_dur/24:.1f} hrs)")
    print(f"  Avg LOSS:    {avg_loss_dur:.1f} bars  ({avg_loss_dur/24:.1f} hrs)")
    print(f"  Max WIN dur: {max_win_dur} bars  ({max_win_dur/24:.1f} hrs)")
    print(f"  Max LOSS dur:{max_loss_dur} bars  ({max_loss_dur/24:.1f} hrs)")
    best_trades = sorted(trades, key=lambda x: -x['pnl'])[:5]
    print(f"\n  Top 5 trades by PnL:")
    for t in best_trades:
        hrs = t['duration_bars']/24
        print(f"    {t['entry_time'].strftime('%Y-%m-%d %H:%M')} -> {t['exit_time'].strftime('%Y-%m-%d %H:%M')}  "
              f"{'WIN' if t['won'] else 'LOSS':4}  {t['pnl']:>+.1f}%  dur={t['duration_bars']} bars ({hrs:.1f}h)  {t['regime']}")
