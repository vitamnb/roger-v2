import ccxt, pandas as pd, numpy as np

ex = ccxt.kucoin({'enableRateLimit': True})
ex.load_markets()

RSI_PERIOD = 14
MA_SHORT = 10
MA_MEDIUM = 20
MA_LONG = 50
BB_WINDOW = 20
ATR_PERIOD = 14
ADX_PERIOD = 14

sym = 'SHIB/USDT'

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
    d = df['c'].diff()
    g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
    l = (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df['rsi'] = 100-(100/(1+g/l.replace(0,np.nan)))
    df['ma10'] = df['c'].rolling(MA_SHORT).mean()
    df['ma20'] = df['c'].rolling(MA_MEDIUM).mean()
    df['ma50'] = df['c'].rolling(MA_LONG).mean() if len(df)>=MA_LONG else df['ma20']
    df['vol_sma'] = df['v'].rolling(20).mean()
    df['vol_ratio'] = df['v']/df['vol_sma']
    bb_std = df['c'].rolling(BB_WINDOW).std()
    df['bb_mid'] = df['c'].rolling(BB_WINDOW).mean()
    df['bb_upper'] = df['bb_mid']+2*bb_std
    df['bb_lower'] = df['bb_mid']-2*bb_std
    df['bb_range'] = df['bb_upper']-df['bb_lower']
    df['bb_pct'] = (df['c']-df['bb_lower'])/df['bb_range'].replace(0,np.nan)
    df['vs_ma20'] = (df['c']-df['ma20'])/df['ma20']*100
    df['vs_ma50'] = (df['c']-df['ma50'])/df['ma50']*100 if 'ma50' in df.columns else 0
    tr1 = df['h']-df['l']
    tr2 = (df['h']-df['c'].shift(1)).abs()
    tr3 = (df['l']-df['c'].shift(1)).abs()
    df['atr'] = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1).rolling(ATR_PERIOD).mean()
    df['swing_low'] = df['l'].rolling(5).min()
    df['swing_high'] = df['h'].rolling(5).max()
    df['rsi_prev'] = df['rsi'].shift(1)
    plus_dm = df['h'].diff()
    minus_dm = -df['l'].diff()
    plus_dm[plus_dm<0] = 0
    minus_dm[minus_dm<0] = 0
    tr = pd.concat([tr1,tr2,tr3],axis=1).max(axis=1)
    atr_tr = tr.rolling(ADX_PERIOD).mean()
    plus_di = 100*(plus_dm.rolling(ADX_PERIOD).mean()/atr_tr)
    minus_di = 100*(minus_dm.rolling(ADX_PERIOD).mean()/atr_tr)
    dx = 100*(plus_di-minus_di).abs()/(plus_di+minus_di)
    df['adx'] = dx.rolling(ADX_PERIOD).mean()
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    return df

def regime(df, lookback=30):
    if df.empty:
        return None
    close = df['c']
    ma10 = df['ma10']
    ma20 = df['ma20']
    rsi = df['rsi'].iloc[-1]
    rsi_avg = df['rsi'].iloc[-lookback:].mean()
    rsi_range = df['rsi'].iloc[-lookback:].max()-df['rsi'].iloc[-lookback:].min()
    adx = df['adx'].iloc[-1]
    ma10_above_20 = (ma10>ma20).iloc[-lookback:].mean()
    oscillates = min(abs(((close-ma20)/ma20>0).iloc[-lookback:].mean()-0.5)*2,1)
    ma_crosses = int(((ma10>ma20)!=(ma10.shift(1)>ma20.shift(1))).iloc[-lookback:].sum())
    trend_s, chop_s = 0.0, 0.0
    if adx>=30: trend_s+=0.4
    elif adx>=20: trend_s+=0.2; chop_s+=0.1
    else: chop_s+=0.4
    if ma10_above_20>0.8: trend_s+=0.3
    elif ma10_above_20<0.3: chop_s+=0.3
    if oscillates<0.3: trend_s+=0.2
    elif oscillates>0.6: chop_s+=0.2
    if ma_crosses<=3: trend_s+=0.2
    elif ma_crosses>=8: chop_s+=0.3
    if rsi_range<15: chop_s+=0.3
    elif rsi_avg>58 or rsi_avg<42: trend_s+=0.2
    total = trend_s+chop_s
    tp = trend_s/total*100 if total>0 else 50
    cp = chop_s/total*100 if total>0 else 50
    reg = 'STRONG_TREND' if tp>=60 and adx>=40 else 'TRENDING' if tp>=60 else 'CHOPPY' if cp>=60 else 'RANGE_BOUND'
    ma20_slope = (ma20.iloc[-1]/ma20.iloc[-10]-1)*100 if len(df)>=10 else 0
    direction = 'LONG' if ma20_slope>0 else 'SHORT' if reg in('STRONG_TREND','TRENDING') else 'NEUTRAL'
    return {'regime':reg,'direction':direction,'adx':round(adx,1),'rsi':round(rsi,1),
            'rsi_avg':round(rsi_avg,1),'trend_pct':round(tp,1),'chop_pct':round(cp,1),
            'ma_crosses':ma_crosses,'ma_slope':round(ma20_slope,2)}

def sup_res(df):
    highs = df['swing_high'].dropna()
    lows = df['swing_low'].dropna()
    if len(highs) < 5:
        return None, None
    return lows.iloc[-1], highs.iloc[-1]

df1h = fetch(sym, '1h', 30)
df1h = indicators(df1h)
df4h = fetch(sym, '4h', 90)
df4h = indicators(df4h)
df15m = fetch(sym, '15m', 7)
df15m = indicators(df15m)

r1h = regime(df1h, 30)
r4h = regime(df4h, 30)
r15m = regime(df15m, 20)
sl_4h, sr_4h = sup_res(df4h)
sl_1h, sr_1h = sup_res(df1h)

price = float(df1h['c'].iloc[-1])
atr_1h = float(df1h['atr'].iloc[-1])
atr_4h = float(df4h['atr'].iloc[-1])
vol_r = float(df1h['vol_ratio'].iloc[-1])

# SHIB-specific trade levels (conservative 3% stop)
entry = price
stop_default = entry * 0.97
tp_2r = entry + (entry - stop_default)*2
tp_3r = entry + (entry - stop_default)*3
stop_atr = entry - atr_1h
atr_stop_pct = atr_1h/entry*100

vol_24h = float(df1h['v'].iloc[-24:].sum()) if len(df1h)>=24 else 0

print('SHIB/USDT FULL ANALYSIS')
print('='*60)
print()
print('CURRENT PRICE (1h): ' + ('$'+'{:.8f}'.format(price)))
print('24h VOLUME: {:,.0f} SHIB'.format(vol_24h))
print()
print('REGIME BY TIMEFRAME:')
print('  Timeframe  Regime         Dir     ADX   RSI  RSI(avg)  Trend%  Chop%  MAxs  Slope')
print('  ' + '-'*75)
for label, r in [('15m',r15m),('1h',r1h),('4h',r4h)]:
    if r:
        print('  {:<8}  {:<13} {:<7} {:>5.1f} {:>5.1f} {:>7.1f} {:>6.1f}% {:>5.1f}% {:>4} {:>6.2f}%'.format(
            label, r['regime'], r['direction'], r['adx'], r['rsi'],
            r['rsi_avg'], r['trend_pct'], r['chop_pct'], r['ma_crosses'], r['ma_slope']))
print()
print('SUPPORT / RESISTANCE (1h):')
if sl_1h:
    print('  Support:   $' + '{:.8f}'.format(sl_1h) + '  (' + '{:.2f}%'.format((price-sl_1h)/price*100) + ' below)')
if sr_1h:
    print('  Resistance:$' + '{:.8f}'.format(sr_1h) + '  (' + '{:.2f}%'.format((sr_1h-price)/price*100) + ' above)')
print()
print('SUPPORT / RESISTANCE (4h):')
if sl_4h:
    print('  Support:   $' + '{:.8f}'.format(sl_4h) + '  (' + '{:.2f}%'.format((price-sl_4h)/price*100) + ' below)')
if sr_4h:
    print('  Resistance:$' + '{:.8f}'.format(sr_4h) + '  (' + '{:.2f}%'.format((sr_4h-price)/price*100) + ' above)')
print()
print('VOLATILITY:')
print('  ATR (1h):  $' + '{:.8f}'.format(atr_1h) + '  (' + '{:.3f}%'.format(atr_1h/price*100) + ' of price)')
print('  ATR (4h):  $' + '{:.8f}'.format(atr_4h) + '  (' + '{:.2f}%'.format(atr_4h/price*100) + ' of price)')
print('  Volume:    ' + '{:.2f}x'.format(vol_r) + ' 20-period avg')
print()
print('SHADOW MODE TRADE LEVELS (aggressive):')
print('  Entry:     $' + '{:.8f}'.format(entry))
print('  Stop (3%): $' + '{:.8f}'.format(stop_default) + '  (-3.0%)')
print('  TP 2:1:   $' + '{:.8f}'.format(tp_2r) + '  (+6.0%)')
print('  TP 3:1:   $' + '{:.8f}'.format(tp_3r) + '  (+9.0%)')
print()
print('LAST 20 RSI READINGS (1h):')
print('  Time       RSI    Price           Volx   vsMA20')
print('  ' + '-'*55)
for i, (ts, row) in enumerate(df1h[['rsi','c','vol_ratio','vs_ma20']].tail(20).iterrows()):
    marker = ' <<' if i==19 else ''
    rsi_s = '{:5.1f}'.format(row['rsi'])
    vol_s = '{:5.2f}x'.format(row['vol_ratio'])
    vsma = '{:>+6.2f}%'.format(row['vs_ma20'])
    price_s = '{:.8f}'.format(row['c'])
    print('  {}  {}  {}  {}  {}{}'.format(str(ts)[-14:-5], rsi_s, price_s, vol_s, vsma, marker))
