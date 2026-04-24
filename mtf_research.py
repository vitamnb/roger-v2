"""
Multi-Timeframe Research Tool for KuCoin
Tests entry types, stop strategies, and take-profit levels
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# -- Config --------------------------------------------------------------------
EXCHANGE_ID = 'kucoin'
TIMEFRAMES = ['1h', '4h', '1d', '1w']
TEST_DAYS = 90
MAX_BARS = 72
OUTPUT_FILE = r'C:\Users\vitamnb\.openclaw\freqtrade\mtf_results_2026-04-24.txt'

# Session hours in AEST (UTC+10)
# London open: 21:00 UTC = 07:00 AEST
# NY open: 13:00 UTC = 23:00 AEST
AEST_OFFSET = 10

# -- 44 Quality Pairs -----------------------------------------------------------
PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT',
    'MATIC/USDT', 'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ETC/USDT',
    'XLM/USDT', 'ALGO/USDT', 'VET/USDT', 'FIL/USDT', 'ICP/USDT',
    'NEAR/USDT', 'APT/USDT', 'ARB/USDT', 'OP/USDT', 'IMX/USDT',
    'SUI/USDT', 'SEI/USDT', 'TIA/USDT', 'INJ/USDT', 'JUP/USDT',
    'WLD/USDT', 'RENDER/USDT', 'FET/USDT', 'AI16Z/USDT', 'ZEREBRO/USDT',
    'PXD/USDT', 'TRUMP/USDT', 'MELania/USDT', 'LAUNCHCOIN/USDT', 'FRED/USDT',
    'LIGHT/USDT', 'VANA/USDT', 'VOYA/USDT', 'NMT/USDT'
]

# -- Exchange Setup -------------------------------------------------------------
exchange = ccxt.kucoin({
    'enableRateLimit': True,
    'defaultType': 'spot',
    'options': {'defaultType': 'spot'}
})

# -- Indicator Functions ---------------------------------------------------------
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_bollinger_bands(series, period=20, std_dev=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    bb_percent = (series - lower) / (upper - lower)
    return bb_percent

def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def calc_ma(series, period):
    return series.rolling(period).mean()

def calc_volume_sma(volume, period=20):
    return volume.rolling(period).mean()

def add_indicators(df, tf):
    df = df.copy()
    df['rsi'] = calc_rsi(df['close'])
    df['ma10'] = calc_ma(df['close'], 10)
    df['ma20'] = calc_ma(df['close'], 20)
    df['ma50'] = calc_ma(df['close'], 50)
    df['volume_sma'] = calc_volume_sma(df['volume'])
    if tf == '1h':
        df['bb_percent'] = calc_bollinger_bands(df['close'])
        df['atr'] = calc_atr(df['high'], df['low'], df['close'])
        df['ema12'] = calc_ma(df['close'], 12)
        df['ema12_dist_pct'] = (df['close'] - df['ema12']) / df['ema12'] * 100
    df['green'] = df['close'] > df['open']
    return df

# -- Fetch Data -----------------------------------------------------------------
def fetch_ohlcv(symbol, timeframe, since, limit=500):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"  [WARN] {symbol} {timeframe}: {e}")
        return pd.DataFrame()

# -- Session Filter (AEST) -------------------------------------------------------
def is_session_open(timestamp_utc):
    """Check if time is within 2hrs of London (07:00 AEST) or NY (23:00 AEST) open"""
    utc_hour = timestamp_utc.hour
    utc_min = timestamp_utc.minute
    # London open: 21:00 UTC, NY open: 13:00 UTC
    london_start = 21 * 60  # minutes from midnight UTC
    london_end = 23 * 60
    ny_start = 13 * 60
    ny_end = 15 * 60
    current = utc_hour * 60 + utc_min
    in_london = london_start <= current <= london_end
    in_ny = ny_start <= current <= ny_end
    return in_london or in_ny

# -- Trade Simulation ------------------------------------------------------------
def simulate_trades(entries, stop_pct, tp_pct, df_1h):
    trades = []
    for entry in entries:
        entry_idx = entry['idx']
        entry_price = entry['price']
        stop_price = entry_price * (1 - stop_pct)
        tp_price = entry_price * (1 + tp_pct)
        
        # Find next 72 bars
        bars = df_1h.iloc[entry_idx + 1: entry_idx + 1 + MAX_BARS + 1]
        if len(bars) == 0:
            continue
        
        result = 'timeout'
        exit_price = bars.iloc[-1]['close']
        hold_bars = len(bars)
        
        for i, (_, bar) in enumerate(bars.iterrows()):
            if bar['low'] <= stop_price:
                result = 'stop'
                exit_price = stop_price
                hold_bars = i + 1
                break
            if bar['high'] >= tp_price:
                result = 'tp'
                exit_price = tp_price
                hold_bars = i + 1
                break
        
        pnl_pct = (exit_price - entry_price) / entry_price * 100
        
        trades.append({
            'entry_time': entry['time'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'result': result,
            'hold_bars': hold_bars,
            'stop_pct': stop_pct,
            'tp_pct': tp_pct,
        })
    
    return trades

def analyze_trades(trades):
    if not trades:
        return {'count': 0, 'win_rate': 0, 'expectancy': 0, 'avg_hold': 0, 'tp_rate': 0}
    
    df = pd.DataFrame(trades)
    wins = df[df['result'] == 'tp']
    stops = df[df['result'] == 'stop']
    timeouts = df[df['result'] == 'timeout']
    
    count = len(df)
    win_rate = len(wins) / count * 100 if count > 0 else 0
    tp_rate = len(wins) / count * 100 if count > 0 else 0
    avg_hold = df['hold_bars'].mean() if count > 0 else 0
    avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
    avg_loss = df[df['result'] != 'tp']['pnl_pct'].mean() if len(df[df['result'] != 'tp']) > 0 else 0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss) if count > 0 else 0
    
    return {
        'count': count,
        'win_rate': round(win_rate, 1),
        'expectancy': round(expectancy, 3),
        'avg_hold': round(avg_hold, 1),
        'tp_rate': round(tp_rate, 1),
    }

# -- Main Research Loop ---------------------------------------------------------
def run_research():
    since = exchange.milliseconds() - (TEST_DAYS + 60) * 24 * 60 * 60 * 1000
    
    results = {}
    all_trades = {et: [] for et in ['A', 'B', 'C', 'D', 'E']}
    
    print(f"Fetching data for {len(PAIRS)} pairs...")
    
    for pair in PAIRS:
        print(f"\n-- {pair} --")
        
        # Fetch all timeframes
        data = {}
        for tf in TIMEFRAMES:
            df = fetch_ohlcv(pair, tf, since)
            if len(df) > 60:
                data[tf] = add_indicators(df, tf)
        
        if '1h' not in data or '4h' not in data or '1d' not in data:
            print(f"  [SKIP] Missing required timeframes")
            continue
        
        df_1h = data['1h']
        df_4h = data['4h']
        df_1d = data['1d']
        df_1w = data.get('1w', pd.DataFrame())
        
        # Need lookback for RSI cross detection (prev RSI values)
        if len(df_1h) < 60:
            continue
        
        # -- Entry Detection --
        
        # Entry A: RSI < 35, BB% < 0.20, prev candle green
        entries_A = []
        for i in range(20, len(df_1h) - 1):
            if (df_1h['rsi'].iloc[i] < 35 and 
                df_1h['bb_percent'].iloc[i] < 0.20 and
                df_1h['green'].iloc[i - 1]):
                entries_A.append({'idx': i, 'price': df_1h['close'].iloc[i], 'time': df_1h['timestamp'].iloc[i]})
        
        # Entry B: RSI cross up through 35 after being below 30
        entries_B = []
        for i in range(20, len(df_1h) - 1):
            rsi_now = df_1h['rsi'].iloc[i]
            rsi_prev = df_1h['rsi'].iloc[i - 1]
            rsi_before = df_1h['rsi'].iloc[i - 2] if i >= 2 else rsi_prev
            
            if (rsi_now >= 35 > rsi_prev and rsi_before < 30):
                entries_B.append({'idx': i, 'price': df_1h['close'].iloc[i], 'time': df_1h['timestamp'].iloc[i]})
        
        # Entry C: Entry A + 4h RSI also < 45 at entry
        entries_C = []
        for i in range(20, len(df_1h) - 1):
            if (df_1h['rsi'].iloc[i] < 35 and 
                df_1h['bb_percent'].iloc[i] < 0.20 and
                df_1h['green'].iloc[i - 1]):
                # Find corresponding 4h bar
                entry_time = df_1h['timestamp'].iloc[i]
                tf4h_idx = df_4h['timestamp'].sub(entry_time).abs().idxmin() if len(df_4h) > 0 else None
                if tf4h_idx is not None and len(df_4h) > tf4h_idx:
                    if df_4h['rsi'].iloc[tf4h_idx] < 45:
                        entries_C.append({'idx': i, 'price': df_1h['close'].iloc[i], 'time': entry_time})
        
        # Entry D: Entry B + session filter
        entries_D = []
        for i in range(20, len(df_1h) - 1):
            rsi_now = df_1h['rsi'].iloc[i]
            rsi_prev = df_1h['rsi'].iloc[i - 1]
            rsi_before = df_1h['rsi'].iloc[i - 2] if i >= 2 else rsi_prev
            
            if (rsi_now >= 35 > rsi_prev and rsi_before < 30):
                entry_time = df_1h['timestamp'].iloc[i]
                if is_session_open(entry_time):
                    entries_D.append({'idx': i, 'price': df_1h['close'].iloc[i], 'time': entry_time})
        
        # Entry E: EMA pullback (within 1.5% of EMA12) + RSI cross up through 40 from below 50 + prev green
        entries_E = []
        for i in range(20, len(df_1h) - 1):
            rsi_now = df_1h['rsi'].iloc[i]
            rsi_prev = df_1h['rsi'].iloc[i - 1]
            rsi_before = df_1h['rsi'].iloc[i - 2] if i >= 2 else rsi_prev
            ema_dist = df_1h['ema12_dist_pct'].iloc[i]
            
            if (rsi_now >= 40 and rsi_prev < 50 and rsi_before < 50 and
                ema_dist >= -1.5 and ema_dist <= 1.5 and
                df_1h['green'].iloc[i - 1]):
                entries_E.append({'idx': i, 'price': df_1h['close'].iloc[i], 'time': df_1h['timestamp'].iloc[i]})
        
        # -- Weekly Bias Filter ------------------------------------------------
        # For weekly bias test: check weekly RSI < 50
        def filter_weekly_rsi(entries, df_1w):
            if len(df_1w) == 0:
                return entries
            filtered = []
            for e in entries:
                entry_time = e['time']
                # Find nearest weekly bar
                if len(df_1w) == 0:
                    continue
                idx = df_1w['timestamp'].sub(entry_time).abs().idxmin()
                if df_1w['rsi'].iloc[idx] < 50:
                    filtered.append(e)
            return filtered
        
        if len(df_1w) > 0:
            entries_A_bias = filter_weekly_rsi(entries_A, df_1w)
            entries_B_bias = filter_weekly_rsi(entries_B, df_1w)
            entries_C_bias = filter_weekly_rsi(entries_C, df_1w)
            entries_D_bias = filter_weekly_rsi(entries_D, df_1w)
            entries_E_bias = filter_weekly_rsi(entries_E, df_1w)
        else:
            entries_A_bias = entries_A
            entries_B_bias = entries_B
            entries_C_bias = entries_C
            entries_D_bias = entries_D
            entries_E_bias = entries_E
        
        pair_results = {}
        
        # -- Simulate each entry type --
        stop_strategies = [0.02, 'atr']
        tp_levels = [0.03, 0.05, 0.07]
        
        for et_name, entries, entries_bias in [
            ('A', entries_A, entries_A_bias),
            ('B', entries_B, entries_B_bias),
            ('C', entries_C, entries_C_bias),
            ('D', entries_D, entries_D_bias),
            ('E', entries_E, entries_E_bias),
        ]:
            pair_results[et_name] = {}
            
            for stop_strat in stop_strategies:
                for tp in tp_levels:
                    key_no_bias = f"stop_{'atr' if stop_strat == 'atr' else int(stop_strat*100)} tp_{int(tp*100)}"
                    key_bias = key_no_bias + "_wBias"
                    
                    # No bias filter
                    trades_nb = []
                    for e in entries:
                        if stop_strat == 'atr':
                            stop_pct = (df_1h['atr'].iloc[e['idx']] / e['price']) * 1.5
                        else:
                            stop_pct = stop_strat
                        trades_nb += simulate_trades([e], stop_pct, tp, df_1h)
                    pair_results[et_name][key_no_bias] = analyze_trades(trades_nb)
                    all_trades[et_name].extend(trades_nb)
                    
                    # With weekly bias filter
                    trades_b = []
                    for e in entries_bias:
                        if stop_strat == 'atr':
                            stop_pct = (df_1h['atr'].iloc[e['idx']] / e['price']) * 1.5
                        else:
                            stop_pct = stop_strat
                        trades_b += simulate_trades([e], stop_pct, tp, df_1h)
                    pair_results[et_name][key_bias] = analyze_trades(trades_b)
            
            total_entries = len(entries)
            print(f"  {et_name}: {total_entries} entries, bias: {len(entries_bias)}")
        
        results[pair] = pair_results
    
    # -- Aggregate Summary ------------------------------------------------------
    return results

# -- Output Formatting ----------------------------------------------------------
def format_results(results):
    lines = []
    lines.append("=" * 90)
    lines.append("MULTI-TIMEFRAME RESEARCH RESULTS - KuCoin Spot")
    lines.append(f"Test Period: {TEST_DAYS} days | Pairs: {len(results)} | Max Hold: {MAX_BARS} bars")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 90)
    
    # Per-pair results
    lines.append("\n" + "-" * 90)
    lines.append("PER-PAIR RESULTS")
    lines.append("-" * 90)
    
    for pair, pair_data in results.items():
        lines.append(f"\n{pair}:")
        for et, configs in pair_data.items():
            for cfg, stats in configs.items():
                if stats['count'] > 0:
                    lines.append(f"  {et}/{cfg}: count={stats['count']}, WR={stats['win_rate']}%, "
                                f"Exp={stats['expectancy']}, AvgHold={stats['avg_hold']}bars, TP%={stats['tp_rate']}%")
    
    # Aggregate summary
    lines.append("\n" + "=" * 90)
    lines.append("AGGREGATE SUMMARY BY ENTRY TYPE")
    lines.append("=" * 90)
    
    entry_types = ['A', 'B', 'C', 'D', 'E']
    entry_labels = {
        'A': 'A (baseline): RSI<35, BB%<0.20, prev green',
        'B': 'B (RSI cross): RSI crosses up through 35 from below 30',
        'C': 'C (4h confirm): baseline + 4h RSI<45',
        'D': 'D (session): RSI cross + within 2hr of London/NY open',
        'E': 'E (EMA pullback): price within 1.5% of EMA12 + RSI cross up through 40 from below 50 + prev green',
    }
    
    stop_labels = {'stop_2 tp_3': 'Fixed 2% stop, TP=3%', 'stop_2 tp_5': 'Fixed 2% stop, TP=5%',
                   'stop_2 tp_7': 'Fixed 2% stop, TP=7%', 'stop_atr tp_3': 'ATR stop, TP=3%',
                   'stop_atr tp_5': 'ATR stop, TP=5%', 'stop_atr tp_7': 'ATR stop, TP=7%'}
    
    for et in entry_types:
        lines.append(f"\n{'-'*80}")
        lines.append(f"ENTRY TYPE {et}: {entry_labels[et]}")
        lines.append(f"{'-'*80}")
        lines.append(f"{'Config':<35} {'Count':>6} {'WinRate':>8} {'Expectancy':>10} {'AvgHold':>8} {'TP%':>6}")
        lines.append(f"{'-'*80}")
        
        all_configs = {}
        for pair, pair_data in results.items():
            if et in pair_data:
                for cfg, stats in pair_data[et].items():
                    if cfg not in all_configs:
                        all_configs[cfg] = {'count': 0, 'wins': 0, 'expectancy_sum': 0, 'hold_sum': 0, 'tp_sum': 0}
                    c = all_configs[cfg]
                    c['count'] += stats['count']
                    c['wins'] += int(stats['count'] * stats['win_rate'] / 100)
                    c['expectancy_sum'] += stats['expectancy'] * stats['count']
                    c['hold_sum'] += stats['avg_hold'] * stats['count']
                    c['tp_sum'] += int(stats['count'] * stats['tp_rate'] / 100)
        
        for cfg, c in sorted(all_configs.items()):
            if c['count'] > 0:
                wr = c['wins'] / c['count'] * 100
                exp = c['expectancy_sum'] / c['count']
                avg_hold = c['hold_sum'] / c['count']
                tp_rate = c['tp_sum'] / c['count'] * 100
                cfg_label = stop_labels.get(cfg, cfg)
                lines.append(f"{cfg_label:<35} {c['count']:>6} {wr:>7.1f}% {exp:>10.3f} {avg_hold:>7.1f} {tp_rate:>5.1f}%")
    
    # Weekly Bias comparison
    lines.append("\n" + "=" * 90)
    lines.append("WEEKLY BIAS FILTER IMPACT (Weekly RSI < 50)")
    lines.append("=" * 90)
    lines.append(f"{'EntryType':<10} {'Config':<20} {'NoBias_WR':>10} {'Bias_WR':>10} {'Diff':>8}")
    lines.append("-" * 60)
    
    for et in entry_types:
        for cfg in ['stop_atr tp_5', 'stop_2 tp_5']:
            key_nb = f"{'stop_atr' if 'atr' in cfg else 'stop_2'} tp_5"
            key_b = key_nb + '_wBias'
            
            totals_nb = {'count': 0, 'wins': 0}
            totals_b = {'count': 0, 'wins': 0}
            
            for pair, pair_data in results.items():
                if et in pair_data:
                    if key_nb in pair_data[et]:
                        s = pair_data[et][key_nb]
                        totals_nb['count'] += s['count']
                        totals_nb['wins'] += int(s['count'] * s['win_rate'] / 100)
                    if key_b in pair_data[et]:
                        s = pair_data[et][key_b]
                        totals_b['count'] += s['count']
                        totals_b['wins'] += int(s['count'] * s['win_rate'] / 100)
            
            if totals_nb['count'] > 0 and totals_b['count'] > 0:
                wr_nb = totals_nb['wins'] / totals_nb['count'] * 100
                wr_b = totals_b['wins'] / totals_b['count'] * 100
                diff = wr_b - wr_nb
                lines.append(f"{et:<10} {key_nb:<20} {wr_nb:>9.1f}% {wr_b:>9.1f}% {diff:>+7.1f}%")
    
    # Best combinations
    lines.append("\n" + "=" * 90)
    lines.append("BEST COMBINATIONS (by Expectancy)")
    lines.append("=" * 90)
    
    all_combos = []
    for pair, pair_data in results.items():
        for et, configs in pair_data.items():
            for cfg, stats in configs.items():
                if stats['count'] >= 5:
                    all_combos.append({
                        'pair': pair,
                        'et': et,
                        'cfg': cfg,
                        'expectancy': stats['expectancy'],
                        'win_rate': stats['win_rate'],
                        'count': stats['count'],
                        'tp_rate': stats['tp_rate'],
                    })
    
    all_combos.sort(key=lambda x: x['expectancy'], reverse=True)
    
    lines.append(f"{'Pair':<15} {'ET':<3} {'Config':<25} {'Exp':>8} {'WR%':>6} {'Count':>6} {'TP%':>6}")
    lines.append("-" * 80)
    for c in all_combos[:20]:
        lines.append(f"{c['pair']:<15} {c['et']:<3} {c['cfg']:<25} {c['expectancy']:>8.3f} {c['win_rate']:>5.1f}% {c['count']:>6} {c['tp_rate']:>5.1f}%")
    
    lines.append("\n" + "=" * 90)
    lines.append("END OF REPORT")
    lines.append("=" * 90)
    
    return "\n".join(lines)

# -- Run ------------------------------------------------------------------------
if __name__ == '__main__':
    print("Starting Multi-Timeframe Research...")
    results = run_research()
    output = format_results(results)
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write(output)
    
    print(f"\nResults saved to: {OUTPUT_FILE}")
    print("\n" + output)
