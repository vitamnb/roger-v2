"""
adaptive_trend_research.py
Compare Pure AdaptiveTrend vs AdaptiveTrend + Compromise
Tests momentum-based entries with dynamic trailing stops
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# -- Config -------------------------------------------------------------------
EXCHANGE_ID = 'kucoin'
TIMEFRAME = '6h'  # Research says H6 is optimal
TEST_DAYS = 180   # 6 months
MAX_BARS = 120    # Max hold: 120 * 6h = 30 days
OUTPUT_FILE = r'C:\Users\vitamnb\.openclaw\freqtrade\research\adaptive_trend_results.txt'

PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'AVAX/USDT', 'SUI/USDT', 'LINK/USDT']

# AdaptiveTrend parameters
MOM_LOOKBACK = 6  # bars (6h * 6 = 36h = 1.5 days)
MOM_THRESHOLD = 0.02  # 2% momentum required
ATR_PERIOD = 14
ATR_MULT = 2.5  # Trailing stop distance

# -- Exchange -----------------------------------------------------------------
exchange = ccxt.kucoin({
    'enableRateLimit': True,
    'defaultType': 'spot',
    'options': {'defaultType': 'spot'}
})

# -- Helpers ------------------------------------------------------------------

def fetch_ohlcv(symbol, timeframe, since, limit=500):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"  [WARN] {symbol}: {e}")
        return pd.DataFrame()


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_atr(df, period=14):
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df):
    df = df.copy()
    df['rsi'] = calc_rsi(df['close'])
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma50'] = df['close'].rolling(50).mean()
    df['vol_sma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_sma']
    df['atr'] = calc_atr(df)
    
    # Momentum (rate of change)
    df['mom'] = (df['close'] - df['close'].shift(MOM_LOOKBACK)) / df['close'].shift(MOM_LOOKBACK)
    
    # Trend structure
    df['higher_high'] = df['close'] > df['close'].shift(1).rolling(5).max()
    df['higher_low'] = df['close'] > df['close'].shift(1).rolling(5).min()
    df['uptrend_structure'] = df['higher_high'] & df['higher_low']
    
    # Support/Resistance (simple swing levels)
    df['swing_low_10'] = df['low'].rolling(10).min()
    df['swing_high_10'] = df['high'].rolling(10).max()
    df['near_support'] = (df['close'] - df['swing_low_10']) / df['close'] < 0.02  # within 2% of recent low
    df['near_resistance'] = (df['swing_high_10'] - df['close']) / df['close'] < 0.02
    
    return df


# -- Entry Detection ----------------------------------------------------------

def detect_entries_pure(df):
    """Entry F: Pure AdaptiveTrend — momentum only"""
    entries = []
    for i in range(50, len(df) - 1):
        if df['mom'].iloc[i] > MOM_THRESHOLD:
            entries.append({
                'idx': i,
                'price': df['close'].iloc[i],
                'time': df['timestamp'].iloc[i],
                'mom': df['mom'].iloc[i],
            })
    return entries


def detect_entries_compromise(df):
    """Entry G: AdaptiveTrend + Compromise confirmations"""
    entries = []
    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i-1]
        
        # Base: momentum
        if row['mom'] <= MOM_THRESHOLD:
            continue
        
        score = 0
        confirms = {}
        
        # Compromise confirmations:
        
        # 1. Price above MA20 (trend alignment)
        if row['close'] > row['ma20']:
            score += 15
            confirms['above_ma20'] = True
        
        # 2. Volume confirmation
        if row['vol_ratio'] >= 1.5:
            score += 25
            confirms['volume_spike'] = True
        elif row['vol_ratio'] >= 1.0:
            score += 10
            confirms['volume_ok'] = True
        
        # 3. Trend structure (higher highs/lows)
        if row['uptrend_structure']:
            score += 15
            confirms['uptrend_structure'] = True
        
        # 4. Not near resistance
        if not row['near_resistance']:
            score += 10
            confirms['not_at_resistance'] = True
        
        # Entry threshold: need base momentum + some confirmations
        # Minimum: momentum + (above MA20 OR volume ok)
        if len(confirms) >= 2:
            entries.append({
                'idx': i,
                'price': row['close'],
                'time': row['timestamp'],
                'mom': row['mom'],
                'score': score,
                'confirms': list(confirms.keys()),
            })
    return entries


# -- Trade Simulation (with trailing stops) -----------------------------------

def simulate_trades_trailing(entries, df, atr_mult=ATR_MULT):
    """
    Simulate trades with dynamic trailing stops (AdaptiveTrend style).
    No fixed TP — only trailing stop exit.
    """
    trades = []
    for entry in entries:
        entry_idx = entry['idx']
        entry_price = entry['price']
        
        # Initial stop: entry - ATR * mult
        atr_at_entry = df['atr'].iloc[entry_idx]
        if np.isnan(atr_at_entry) or atr_at_entry <= 0:
            continue
        
        stop_level = entry_price - atr_at_entry * atr_mult
        
        bars = df.iloc[entry_idx + 1: entry_idx + 1 + MAX_BARS + 1]
        if len(bars) == 0:
            continue
        
        exit_price = None
        hold_bars = 0
        max_dd_pct = 0
        
        for i, (_, bar) in enumerate(bars.iterrows()):
            # Update trailing stop (max of previous stop and new level)
            new_stop = bar['close'] - bar['atr'] * atr_mult
            if not np.isnan(new_stop):
                stop_level = max(stop_level, new_stop)
            
            # Track drawdown
            dd = (bar['close'] - entry_price) / entry_price * 100
            max_dd_pct = min(max_dd_pct, dd)
            
            # Check exit
            if bar['low'] <= stop_level:
                exit_price = stop_level
                hold_bars = i + 1
                break
        
        if exit_price is None:
            # Timeout — close at final bar
            exit_price = bars.iloc[-1]['close']
            hold_bars = len(bars)
        
        pnl_pct = (exit_price - entry_price) / entry_price * 100
        
        trades.append({
            'entry_time': entry['time'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl_pct': pnl_pct,
            'hold_bars': hold_bars,
            'max_dd_pct': max_dd_pct,
            'mom_at_entry': entry.get('mom', 0),
            'score': entry.get('score', 0),
            'confirms': entry.get('confirms', []),
        })
    
    return trades


def analyze_trades(trades, label):
    if not trades:
        return {'label': label, 'count': 0}
    
    df = pd.DataFrame(trades)
    wins = df[df['pnl_pct'] > 0]
    losses = df[df['pnl_pct'] <= 0]
    
    count = len(df)
    win_rate = len(wins) / count * 100
    avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl_pct'].mean() if len(losses) > 0 else 0
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
    avg_hold = df['hold_bars'].mean()
    max_dd = df['max_dd_pct'].min()
    
    return {
        'label': label,
        'count': count,
        'win_rate': round(win_rate, 1),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'expectancy': round(expectancy, 3),
        'avg_hold': round(avg_hold, 1),
        'max_dd': round(max_dd, 2),
        'profit_factor': round(abs(avg_win * len(wins) / (avg_loss * len(losses))) if avg_loss != 0 and len(losses) > 0 else 999, 2),
    }


# -- Main ----------------------------------------------------------------------

def run_research():
    since = exchange.milliseconds() - (TEST_DAYS + 30) * 24 * 60 * 60 * 1000
    
    all_results = {}
    
    print(f"Fetching {TIMEFRAME} data for {len(PAIRS)} pairs...")
    print(f"Testing {TEST_DAYS} days | Trailing stop ATR×{ATR_MULT}")
    print("=" * 70)
    
    for pair in PAIRS:
        print(f"\n-- {pair} --")
        
        df = fetch_ohlcv(pair, TIMEFRAME, since)
        if len(df) < 100:
            print(f"  [SKIP] Insufficient data ({len(df)} bars)")
            continue
        
        df = add_indicators(df)
        
        # Entry F: Pure momentum
        entries_f = detect_entries_pure(df)
        trades_f = simulate_trades_trailing(entries_f, df)
        
        # Entry G: Momentum + compromise
        entries_g = detect_entries_compromise(df)
        trades_g = simulate_trades_trailing(entries_g, df)
        
        result_f = analyze_trades(trades_f, 'Pure Momentum')
        result_g = analyze_trades(trades_g, 'Momentum + Compromise')
        
        print(f"  Pure:       {result_f['count']} trades | WR {result_f['win_rate']}% | Exp {result_f['expectancy']} | AvgHold {result_f['avg_hold']}bars")
        print(f"  Compromise: {result_g['count']} trades | WR {result_g['win_rate']}% | Exp {result_g['expectancy']} | AvgHold {result_g['avg_hold']}bars")
        
        all_results[pair] = {'pure': result_f, 'compromise': result_g}
    
    # Aggregate summary
    print("\n" + "=" * 70)
    print("AGGREGATE SUMMARY")
    print("=" * 70)
    
    pure_all = []
    comp_all = []
    for pair, data in all_results.items():
        if data['pure']['count'] > 0:
            pure_all.append(data['pure'])
        if data['compromise']['count'] > 0:
            comp_all.append(data['compromise'])
    
    def aggregate(results):
        if not results:
            return {}
        total_trades = sum(r['count'] for r in results)
        weighted_exp = sum(r['expectancy'] * r['count'] for r in results) / total_trades
        weighted_wr = sum(r['win_rate'] * r['count'] for r in results) / total_trades
        weighted_hold = sum(r['avg_hold'] * r['count'] for r in results) / total_trades
        return {
            'total_trades': total_trades,
            'avg_expectancy': round(weighted_exp, 3),
            'avg_winrate': round(weighted_wr, 1),
            'avg_hold': round(weighted_hold, 1),
            'pairs_tested': len(results),
        }
    
    pure_agg = aggregate(pure_all)
    comp_agg = aggregate(comp_all)
    
    print(f"\n{'Pure Momentum':<25} | Trades: {pure_agg.get('total_trades', 0)} | Exp: {pure_agg.get('avg_expectancy', 0)} | WR: {pure_agg.get('avg_winrate', 0)}% | Hold: {pure_agg.get('avg_hold', 0)}bars")
    print(f"{'Momentum + Compromise':<25} | Trades: {comp_agg.get('total_trades', 0)} | Exp: {comp_agg.get('avg_expectancy', 0)} | WR: {comp_agg.get('avg_winrate', 0)}% | Hold: {comp_agg.get('avg_hold', 0)}bars")
    
    # Write report
    lines = []
    lines.append("=" * 70)
    lines.append("ADAPTIVE TREND RESEARCH RESULTS")
    lines.append(f"Timeframe: {TIMEFRAME} | Test Period: {TEST_DAYS} days | ATR Mult: {ATR_MULT}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    
    for pair, data in all_results.items():
        lines.append(f"\n{pair}:")
        for key, res in [('PURE', data['pure']), ('COMPROMISE', data['compromise'])]:
            lines.append(f"  {key}: count={res['count']}, WR={res['win_rate']}%, Exp={res['expectancy']}, "
                        f"AvgWin={res['avg_win']}, AvgLoss={res['avg_loss']}, Hold={res['avg_hold']}bars, "
                        f"MaxDD={res['max_dd']}%, PF={res.get('profit_factor', 'N/A')}")
    
    lines.append("\n" + "=" * 70)
    lines.append("AGGREGATE")
    lines.append("=" * 70)
    lines.append(f"Pure:        {pure_agg}")
    lines.append(f"Compromise:  {comp_agg}")
    
    output = "\n".join(lines)
    with open(OUTPUT_FILE, 'w') as f:
        f.write(output)
    
    print(f"\nReport saved to: {OUTPUT_FILE}")
    return all_results


if __name__ == '__main__':
    run_research()
