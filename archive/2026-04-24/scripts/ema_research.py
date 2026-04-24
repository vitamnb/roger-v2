"""
EMA Cross Pullback Strategy Research
Entry E: 1h EMA pullback
Entry F: Multi-timeframe EMA pullback (daily bias + 4h/1h pullback)
Entry G: EMA cross only (no pullback)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import time
import warnings
warnings.filterwarnings('ignore')

PAIRS = [
    "GUN/USDT","SIREN/USDT","HIGH/USDT","TRIA/USDT","GWEI/USDT","ARIA/USDT",
    "ARB/USDT","VIRTUAL/USDT","XLM/USDT","SUI/USDT","PUMP/USDT","XMR/USDT",
    "AVAX/USDT","NIGHT/USDT","XRP/USDT","RAVE/USDT","AAVE/USDT","BTC/USDT",
    "TAO/USDT","UNI/USDT"
]

MAX_BARS      = 72
TP_PCT        = 0.05
STOP_DEFAULT  = 0.02
PULLBACK_PCT  = 0.015   # price within 1.5% of 12 EMA = pullback zone
RSI_BELOW     = 50      # RSI must be below this before crossing
RSI_CROSS_VAL = 40      # RSI crosses up through this
RESULTS_FILE  = r"C:\Users\vitamnb\.openclaw\freqtrade\ema_results_2026-04-22.txt"

# ── Indicators ─────────────────────────────────────────────────────────────
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0).ewm(alpha=1/period, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/period, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

# ── Fetch ──────────────────────────────────────────────────────────────────
def fetch_ohlcv_safe(exchange, symbol, tf, limit):
    for attempt in range(3):
        try:
            return exchange.fetch_ohlcv(symbol, tf, limit=limit)
        except Exception as e:
            print(f"    [{symbol} {tf}] attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return []

def to_df(ohlcv):
    df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def align_4h_to_1h(n_1h, n_4h):
    """Return array: for each 1h bar index, the 4h bar index it belongs to."""
    return np.array([min(j // 4, n_4h - 1) for j in range(n_1h)])

# ── Backtest ───────────────────────────────────────────────────────────────
def backtest(df1, df4, dfD, entry_type, require_green):
    trades = []
    n = len(df1)
    if n < 30:
        return trades

    close  = df1['close'].values
    low    = df1['low'].values
    high   = df1['high'].values
    ema12  = df1['ema12'].values
    ema26  = df1['ema26'].values
    rsi    = df1['rsi14'].values
    green  = df1['green_candle'].values
    rsi_prev = pd.Series(rsi).shift(1).fillna(50).values

    # Align 4h EMAs to 1h
    n4 = len(df4)
    h4_idx = align_4h_to_1h(n, n4)
    e12_4h = df4['ema12'].values if n4 else np.array([])
    e26_4h = df4['ema26'].values if n4 else np.array([])

    # Daily
    e12_D = dfD['ema12'].values if len(dfD) else np.array([])
    e26_D = dfD['ema26'].values if len(dfD) else np.array([])

    for i in range(20, n - 10):
        ep = close[i]
        tp = ep * (1 + TP_PCT)
        sp = None

        # Entry E: 1h EMA pullback
        if entry_type == 'E':
            if ema12[i] <= ema26[i]:
                continue
            if not (ema12[i] * (1 - PULLBACK_PCT) <= ep <= ema12[i] * (1 + PULLBACK_PCT)):
                continue
            # RSI crosses up through RSI_CROSS_VAL from below RSI_BELOW
            if not (rsi_prev[i] < RSI_BELOW and RSI_CROSS_VAL - 5 <= rsi[i] < 65):
                continue
            if require_green and not green[i]:
                continue
            swing_low = low[i-5:i+1].min()
            sp = min(swing_low, ep * (1 - STOP_DEFAULT))

        # Entry F: multi-timeframe pullback
        elif entry_type == 'F':
            if len(e12_D) < 5 or e12_D[-1] <= e26_D[-1]:
                continue
            h4i = int(h4_idx[i])
            if h4i >= len(e12_4h) or ep > e12_4h[h4i]:
                continue
            if ep > ema12[i]:
                continue
            if not (rsi_prev[i] < RSI_BELOW and RSI_CROSS_VAL - 5 <= rsi[i] < 65):
                continue
            if require_green and not green[i]:
                continue
            swing_low = low[i-5:i+1].min()
            sp = min(swing_low, ep * (1 - STOP_DEFAULT))

        # Entry G: EMA cross only
        elif entry_type == 'G':
            cross = any(
                i - lb >= 0 and ema12[i-lb] <= ema26[i-lb] and ema12[i] > ema26[i]
                for lb in range(1, 5)
            )
            if not cross:
                continue
            if rsi[i] >= RSI_CROSS_VAL:
                continue
            if require_green and not green[i]:
                continue
            sp = ep * (1 - STOP_DEFAULT)

        else:
            continue

        if sp is None:
            continue

        result = 'timeout'
        xp = close[min(i + MAX_BARS, n-1)]
        bars = MAX_BARS

        for b in range(1, MAX_BARS + 1):
            if i + b >= n:
                result = 'timeout'
                xp = close[n-1]
                bars = b
                break
            if low[i+b] <= sp:
                result = 'stop'
                xp = sp
                bars = b
                break
            if high[i+b] >= tp:
                result = 'tp'
                xp = tp
                bars = b
                break

        pnl = (xp - ep) / ep * 100
        trades.append({'pnl': pnl, 'result': result, 'bars': bars})

    return trades

# ── Main ───────────────────────────────────────────────────────────────────
exchange = ccxt.kucoin({'enableRateLimit': True, 'defaultType': 'spot'})

LIMITS = {'1h': 300, '4h': 100, 'daily': 60}

all_results = []

print("EMA Cross Pullback Strategy Research")
print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
print(f"TP=5% | Stop=2% default | MaxBars=72 | Pullback={PULLBACK_PCT*100}% | RSI cross below{RSI_BELOW} through~{RSI_CROSS_VAL}\n")

for sym in PAIRS:
    print(f"[{sym}]")

    raw1 = fetch_ohlcv_safe(exchange, sym, '1h', LIMITS['1h'])
    raw4 = fetch_ohlcv_safe(exchange, sym, '4h', LIMITS['4h'])
    rawD = fetch_ohlcv_safe(exchange, sym, '1d', LIMITS['daily'])

    df1 = to_df(raw1) if len(raw1) >= 20 else pd.DataFrame()
    df4 = to_df(raw4) if len(raw4) >= 10 else pd.DataFrame()
    dfD = to_df(rawD) if len(rawD) >= 10 else pd.DataFrame()

    if df1.empty:
        print("  SKIP (no 1h data)\n")
        continue

    for df, col in [(df1, '1h'), (df4, '4h'), (dfD, 'daily')]:
        if not df.empty:
            df['ema12'] = calc_ema(df['close'], 12)
            df['ema26'] = calc_ema(df['close'], 26)
            df['rsi14'] = calc_rsi(df['close'], 14)
            if col == '1h':
                df['atr14'] = calc_atr(df['high'], df['low'], df['close'], 14)
            df['green_candle'] = df['close'] > df['open']

    print(f"  1h={len(df1)}  4h={len(df4)}  daily={len(dfD)}")

    for et in ['E', 'F', 'G']:
        for green_req in [True, False]:
            trades = backtest(df1, df4, dfD, et, green_req)
            nn = len(trades)

            if nn == 0:
                tag = f"Entry {et} {'+green' if green_req else 'no-green'}"
                print(f"  {tag}: 0 signals")
                all_results.append({'pair': sym, 'entry': et, 'green': green_req,
                                    'n': 0, 'wr': None, 'exp': None, 'avg_bars': None,
                                    'tp_rate': None, 'wins': 0, 'stops': 0, 'timeouts': 0})
                continue

            wins  = sum(1 for t in trades if t['result'] == 'tp')
            stops = sum(1 for t in trades if t['result'] == 'stop')
            tos   = sum(1 for t in trades if t['result'] == 'timeout')

            wr     = wins / nn * 100
            tp_r   = wins / nn * 100

            profits = [t['pnl'] for t in trades if t['result'] == 'tp']
            losses  = [t['pnl'] for t in trades if t['result'] == 'stop']
            avg_w   = np.mean(profits) if profits else 0.0
            avg_l   = np.mean(losses)  if losses  else 0.0
            exp     = (wins/nn * avg_w) - (stops/nn * abs(avg_l)) if stops else wins/nn * avg_w
            avg_b   = np.mean([t['bars'] for t in trades])

            tag = f"Entry {et} {'+green' if green_req else 'no-green'}"
            print(f"  {tag}: n={nn}  WR={wr:.1f}%  Exp={exp:.3f}%  AvgBars={avg_b:.1f}  TP={tp_r:.1f}%  [W={wins} S={stops} T={tos}]")

            all_results.append({'pair': sym, 'entry': et, 'green': green_req,
                                'n': nn, 'wr': wr, 'exp': exp, 'avg_bars': avg_b,
                                'tp_rate': tp_r, 'wins': wins, 'stops': stops, 'timeouts': tos,
                                'avg_win': avg_w, 'avg_loss': avg_l})

    time.sleep(0.3)

# ── Summary ────────────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  AGGREGATE SUMMARY")
print("="*70)

for et in ['E', 'F', 'G']:
    for green_req in [True, False]:
        sub = [r for r in all_results if r['entry'] == et and r['green'] == green_req and r['n'] > 0]
        if not sub:
            continue
        tn  = sum(r['n']    for r in sub)
        tw  = sum(r['wins'] for r in sub)
        ts  = sum(r['stops'] for r in sub)
        tt  = sum(r['timeouts'] for r in sub)
        wr  = tw / tn * 100 if tn else 0
        exp = sum(r['exp'] * r['n'] for r in sub) / tn if tn else 0
        ab  = sum(r['avg_bars'] * r['n'] for r in sub) / tn if tn else 0
        label = f"Entry {et} ({'with green candle' if green_req else 'no green filter'})"
        print(f"\n  {label}")
        print(f"    Signals={tn}  WR={wr:.1f}%  Exp={exp:.3f}%  AvgBars={ab:.1f}")
        print(f"    Wins={tw}  Stops={ts}  Timeouts={tt}  TP%={tw/tn*100:.1f}%")

# ── Top 10 pairs ───────────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  TOP 10 PAIRS BY EXPECTANCY - Entry E + green candle")
print("="*70)

top = sorted(
    [r for r in all_results if r['entry'] == 'E' and r['green'] and r['n'] > 0],
    key=lambda x: x['exp'] if x['exp'] is not None else -999,
    reverse=True
)[:10]

if top:
    print(f"\n{'Pair':<20} {'Signals':>8} {'WR%':>8} {'Exp%':>8} {'AvgBars':>9} {'TP%':>8}")
    print("-"*62)
    for r in top:
        print(f"{r['pair']:<20} {r['n']:>8} {r['wr']:>8.1f} {r['exp']:>8.3f} {r['avg_bars']:>9.1f} {r['tp_rate']:>8.1f}")
else:
    print("\n  (no Entry E + green candle signals across any pair)")

# ── MTF filter impact ───────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  MTF FILTER EFFECTIVENESS: Entry F vs Entry E")
print("="*70)

f_sub = [r for r in all_results if r['entry'] == 'F' and r['green'] and r['n'] > 0]
e_sub = [r for r in all_results if r['entry'] == 'E' and r['green'] and r['n'] > 0]
f_n = sum(r['n'] for r in f_sub)
e_n = sum(r['n'] for r in e_sub)
f_w = sum(r['wins'] for r in f_sub)
e_w = sum(r['wins'] for r in e_sub)

print(f"\n  Entry F (MTF, +green): {f_n} signals, WR={f_w/f_n*100:.1f}%" if f_n else "\n  Entry F: no signals")
print(f"  Entry E (1h only, +green): {e_n} signals, WR={e_w/e_n*100:.1f}%" if e_n else "\n  Entry E: no signals")
if e_n > 0 and f_n > 0:
    print(f"  MTF filter reduces signals by {(1-f_n/e_n)*100:.1f}%, WR change: {(f_w/f_n*100)-(e_w/e_n*100):+.1f}%")

# ── Pullback filter impact ─────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  PULLBACK FILTER IMPACT: Entry G (no pullback) vs Entry E (pullback)")
print("="*70)

g_sub = [r for r in all_results if r['entry'] == 'G' and r['green'] and r['n'] > 0]
g_n = sum(r['n'] for r in g_sub)
g_w = sum(r['wins'] for r in g_sub)
e_n2 = sum(r['n'] for r in e_sub)
e_w2 = sum(r['wins'] for r in e_sub)

if g_n:
    print(f"\n  Entry G (cross only, +green): {g_n} signals, WR={g_w/g_n*100:.1f}%")
else:
    print("\n  Entry G: no signals")
if e_n2:
    print(f"  Entry E (with pullback, +green): {e_n2} signals, WR={e_w2/e_n2*100:.1f}%")
if g_n and e_n2:
    print(f"  Pullback requirement changes WR by {(g_w/g_n*100)-(e_w2/e_n2*100):+.1f}%")

# ── Green candle impact ───────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  GREEN CANDLE FILTER IMPACT")
print("="*70)

for et in ['E', 'F', 'G']:
    g  = [r for r in all_results if r['entry'] == et and r['green'] and r['n'] > 0]
    ng = [r for r in all_results if r['entry'] == et and not r['green'] and r['n'] > 0]
    gn  = sum(r['n']    for r in g)
    gw  = sum(r['wins'] for r in g)
    ngn = sum(r['n']    for r in ng)
    ngw = sum(r['wins'] for r in ng)
    if gn:
        print(f"  Entry {et} +green: {gn} signals, WR={gw/gn*100:.1f}%")
    if ngn:
        print(f"  Entry {et} no-green: {ngn} signals, WR={ngw/ngn*100:.1f}%")

# ── Per-pair details ───────────────────────────────────────────────────────
print("\n\n" + "="*70)
print("  PER-PAIR DETAILS")
print("="*70)

for sym in PAIRS:
    sym_r = [r for r in all_results if r['pair'] == sym and r['n'] > 0]
    if not sym_r:
        continue
    print(f"\n  {sym}")
    for r in sym_r:
        gc = "+green" if r['green'] else "no-green"
        print(f"    E{r['entry']} {gc}: n={r['n']} WR={r['wr']:.1f}% Exp={r['exp']:.3f} Bars={r['avg_bars']:.1f} TP={r['tp_rate']:.1f}%")

# ── Save to file ───────────────────────────────────────────────────────────
with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
    f.write("EMA CROSS PULLBACK STRATEGY RESEARCH RESULTS\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"TP=5pct | Stop=2pct default | MaxBars=72 | Pullback=1.5pct | RSI cross below{RSI_BELOW} through~{RSI_CROSS_VAL}\n")
    f.write("="*70 + "\n\n")

    f.write("AGGREGATE SUMMARY\n")
    f.write("-"*70 + "\n")
    for et in ['E', 'F', 'G']:
        for green_req in [True, False]:
            sub = [r for r in all_results if r['entry'] == et and r['green'] == green_req and r['n'] > 0]
            if not sub:
                continue
            tn = sum(r['n']    for r in sub)
            tw = sum(r['wins'] for r in sub)
            ts = sum(r['stops'] for r in sub)
            tt = sum(r['timeouts'] for r in sub)
            wr = tw / tn * 100 if tn else 0
            exp = sum(r['exp'] * r['n'] for r in sub) / tn if tn else 0
            ab  = sum(r['avg_bars'] * r['n'] for r in sub) / tn if tn else 0
            label = f"Entry {et} ({'with green candle' if green_req else 'no green filter'})"
            f.write(f"\n  {label}\n")
            f.write(f"    Signals={tn}  WR={wr:.1f}pct  Exp={exp:.3f}pct  AvgBars={ab:.1f}\n")
            f.write(f"    Wins={tw}  Stops={ts}  Timeouts={tt}\n\n")

    f.write("\nTOP 10 PAIRS BY EXPECTANCY (Entry E + green candle)\n")
    f.write("-"*62 + "\n")
    if top:
        f.write(f"{'Pair':<20} {'Signals':>8} {'WR%':>8} {'Exp%':>8} {'AvgBars':>9} {'TP%':>8}\n")
        for r in top:
            f.write(f"{r['pair']:<20} {r['n']:>8} {r['wr']:>8.1f} {r['exp']:>8.3f} {r['avg_bars']:>9.1f} {r['tp_rate']:>8.1f}\n")
    else:
        f.write("  (no signals)\n")

    f.write("\n\nPER-PAIR DETAILS\n")
    f.write("-"*70 + "\n")
    for sym in PAIRS:
        sym_r = [r for r in all_results if r['pair'] == sym and r['n'] > 0]
        if not sym_r:
            continue
        f.write(f"\n{sym}\n")
        for r in sym_r:
            gc = "+green" if r['green'] else "no-green"
            f.write(f"  Entry{r['entry']} {gc}: n={r['n']} WR={r['wr']:.1f}pct Exp={r['exp']:.3f}pct Bars={r['avg_bars']:.1f} TP={r['tp_rate']:.1f}pct\n")

print(f"\n\nResults saved to:\n{RESULTS_FILE}")