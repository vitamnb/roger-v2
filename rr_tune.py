import sys; sys.path.insert(0, r'C:\Users\vitamnb\.openclaw\freqtrade')
import ccxt
import pandas as pd
import numpy as np

RSI_PERIOD = 14
MA_SHORT, MA_MEDIUM, MA_LONG = 10, 20, 50
ATR_PERIOD = 14
ADX_PERIOD = 14
VOL_SMA_PERIOD = 20
RATE_LIMIT_DELAY = 0.05

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
    ma10 = sub["ma10"].iloc[-1]
    ma20_val = sub["ma20"].iloc[-1]
    ma20_series = sub["ma20"]
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
    return adx, reg, direction

def full_backtest(df, capital=58.0, risk_pct=5.0, rr=3.0, use_override=True):
    trades = []
    rsi_blocked = 0
    total_sigs = 0
    for i in range(50, len(df)):
        row = df.iloc[i]
        if pd.isna(row['rsi']) or pd.isna(row['ma20']):
            continue
        adx_val, reg, direction = regime_score(df, i)
        score = 0
        if row.get('bull_div') and direction == "LONG": score += 2
        if row.get('vol_spike') and direction == "LONG": score += 1
        sig_ok_long = (direction == "LONG" and row['rsi'] < (75 if use_override else 999))
        sig_ok_short = (direction == "SHORT" and row['rsi'] > (25 if use_override else 0))
        sig_ok = sig_ok_long or sig_ok_short
        if not sig_ok:
            rsi_blocked += 1
            total_sigs += 1
            continue
        total_sigs += 1
        risk_amount = capital * risk_pct / 100
        atr = row.get('atr_pct', 1.0)
        stop_dist = max(atr * 1.5, 0.005)
        target_dist = stop_dist * rr
        entry = row['close']
        if direction == "LONG" and score >= 2:
            stop = entry * (1 - stop_dist / 100)
            target = entry * (1 + target_dist / 100)
            for j in range(i+1, len(df)):
                if df.iloc[j]['low'] <= stop:
                    capital += -risk_amount
                    trades.append(-risk_amount); break
                elif df.iloc[j]['high'] >= target:
                    capital += risk_amount * rr
                    trades.append(risk_amount * rr); break
        elif direction == "SHORT" and score >= 2:
            stop = entry * (1 + stop_dist / 100)
            target = entry * (1 - target_dist / 100)
            for j in range(i+1, len(df)):
                if df.iloc[j]['high'] >= stop:
                    capital += -risk_amount
                    trades.append(-risk_amount); break
                elif df.iloc[j]['low'] <= target:
                    capital += risk_amount * rr
                    trades.append(risk_amount * rr); break
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t < 0]
    ret = sum(trades)
    wr = len(wins) / len(trades) * 100 if trades else 0
    dd = 0.0
    peak = 58.0
    equity = 58.0
    for t in trades:
        equity += t
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 0
        if drawdown > dd:
            dd = drawdown
    return {
        'ret': ret, 'wr': wr, 'dd': dd, 'trades': len(trades),
        'wins': len(wins), 'losses': len(losses),
        'rsi_blocked': rsi_blocked, 'total_sigs': total_sigs
    }

PROFITABLE_PAIRS = [
    'BNRENSHENG/USDT','VIRTUAL/USDT','WIF/USDT','H/USDT','ARKM/USDT',
    'AVAX/USDT','ENA/USDT','GWEI/USDT','BTC/USDT','ARIA/USDT',
    'SIREN/USDT','ETH/USDT','DOGE/USDT','JUP/USDT','THETA/USDT',
    'FIL/USDT','KCS/USDT','RENDER/USDT','LINK/USDT','OFC/USDT',
    'HBAR/USDT','ADA/USDT','XRP/USDT','SOL/USDT','ENJ/USDT',
    'CRV/USDT','TRX/USDT','IAG/USDT','HIGH/USDT','FET/USDT',
    'NEAR/USDT','UNI/USDT','WLD/USDT','BCH/USDT','ORDI/USDT',
    'BNB/USDT','LIGHT/USDT','DASH/USDT','ZRO/USDT','SHIB/USDT',
    'TAO/USDT','ONDO/USDT',
]

print("Loading data for all 44 profitable pairs...")
pair_dfs = {}
for i, pair in enumerate(PROFITABLE_PAIRS):
    print(f"  [{i+1}/44] {pair}")
    df = fetch(pair, '1h', 30)
    df = add_indicators(df)
    pair_dfs[pair] = df

print("\n" + "="*70)
print("  R:R TUNING -- Aggressive 1h | 30d | 5% risk")
print("  Testing 5 R:R ratios across 44 profitable pairs")
print("="*70)

RR_VALUES = [2.0, 2.5, 3.0, 3.5, 4.0]
results_by_rr = {rr: {'total': 0, 'trades': 0, 'wins': 0, 'losses': 0} for rr in RR_VALUES}

for rr in RR_VALUES:
    print(f"\n  --- R:R = {rr}:1 ---")
    pair_results = []
    for pair, df in pair_dfs.items():
        bt = full_backtest(df.copy(), capital=58.0, risk_pct=5.0, rr=rr, use_override=True)
        pair_results.append((pair, bt))

    tot_ret = sum(r['ret'] for _, r in pair_results)
    tot_trades = sum(r['trades'] for _, r in pair_results)
    tot_w = sum(r['wins'] for _, r in pair_results)
    tot_l = sum(r['losses'] for _, r in pair_results)
    wr = tot_w / (tot_w + tot_l) * 100 if (tot_w + tot_l) > 0 else 0
    results_by_rr[rr]['total'] = tot_ret
    results_by_rr[rr]['trades'] = tot_trades
    results_by_rr[rr]['wins'] = tot_w
    results_by_rr[rr]['losses'] = tot_l
    print(f"  Combined return: {tot_ret:+.1f}%  |  WR={wr:.0f}%  |  Trades={tot_trades}  |  {tot_w}W/{tot_l}L")
    sorted_pr = sorted(pair_results, key=lambda pr: -pr[1]['ret'])
    print(f"  Top 5: " + ", ".join([f"{p} {r['ret']:+.0f}%" for p, r in sorted_pr[:5]]))
    print(f"  Bot 5: " + ", ".join([f"{p} {r['ret']:+.0f}%" for p, r in sorted_pr[-5:]]))

print("\n" + "="*70)
print("  R:R COMPARISON SUMMARY")
print("="*70)
print(f"  {'R:R':<6}  {'Return%':>9}  {'WR%':>5}  {'Trades':>7}  {'W':>5}  {'L':>5}")
print(f"  {'-'*6}  {'-'*9}  {'-'*5}  {'-'*7}  {'-'*5}  {'-'*5}")
for rr in RR_VALUES:
    r = results_by_rr[rr]
    wr = r['wins'] / (r['wins'] + r['losses']) * 100 if (r['wins'] + r['losses']) > 0 else 0
    print(f"  {rr:,.1f}:1  {r['total']:>+9.1f}%  {wr:>5.0f}%  {r['trades']:>7}  {r['wins']:>5}  {r['losses']:>5}")

best_rr = max(RR_VALUES, key=lambda rr: results_by_rr[rr]['total'])
print(f"\n  Best R:R: {best_rr}:1 ({results_by_rr[best_rr]['total']:+.1f}%)")
