#!/usr/bin/env python3
"""
Exhaustive Timeframe Backtest
Tests Entry B + OB + Volume hybrid strategy across multiple timeframes.
"""

import pandas as pd
import numpy as np
import os
import sys
import ccxt
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'timeframe_test')
PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ATOM/USDT']
TIMEFRAMES = ['15m', '30m', '1h', '4h', '1d', '3d', '1w', '1M']
INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001


def fetch_data(symbol, tf, days_back=180):
    """Fetch OHLCV data for a symbol/timeframe."""
    safe = symbol.replace('/', '_')
    fp = os.path.join(DATA_DIR, f"{safe}_{tf}.csv")
    
    if os.path.exists(fp):
        df = pd.read_csv(fp)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df.sort_values('datetime').reset_index(drop=True)
    
    print(f"    Fetching {symbol} {tf}...")
    try:
        exchange = ccxt.kucoin({'enableRateLimit': True})
        since = int((pd.Timestamp.now() - pd.Timedelta(days=days_back)).timestamp() * 1000)
        
        all_ohlcv = []
        current_since = since
        max_loops = 20
        loops = 0
        
        while loops < max_loops:
            ohlcv = exchange.fetch_ohlcv(symbol, tf, since=current_since, limit=1500)
            if not ohlcv or len(ohlcv) == 0:
                break
            all_ohlcv.extend(ohlcv)
            last_ts = ohlcv[-1][0]
            if last_ts == current_since or len(ohlcv) < 1500:
                break
            current_since = last_ts + 1
            time.sleep(0.3)
            loops += 1
        
        if not all_ohlcv:
            return None
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df[['datetime','open','high','low','close','volume']]
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(fp, index=False)
        return df
    except Exception as e:
        print(f"    ERROR fetching {symbol} {tf}: {e}")
        return None


def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def backtest_hybrid(df):
    """Entry B + Order Block + Volume, 2:1 R:R."""
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    
    # Use fewer candles for lookback on higher timeframes
    lookback = min(5, max(2, len(df) // 100))
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=lookback)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    
    for i in range(20, len(df) - 20):
        # RSI signal
        if not (df['rsi_prev'].iloc[i] < 35 and df['rsi'].iloc[i] >= 35 and df['rsi_prev'].iloc[i] < 30):
            continue
        
        # Order block filter
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= min(50, len(df) // 4):
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
        # Volume filter
        if not (ob_zone and df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * 1.2):
            continue
        
        entry_price = df['close'].iloc[i]
        stop_price = min(ob_low * 0.995, entry_price * 0.985) if ob_low else entry_price * 0.98
        target_price = entry_price + (entry_price - stop_price) * 2.0
        
        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:
            continue
        
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        
        # Simulate forward
        hold_bars = min(20, max(5, len(df) // 20))
        after = df.iloc[i+1:min(i + hold_bars, len(df))]
        if len(after) < 2:
            continue
        
        low_after = after['low'].min()
        high_after = after['high'].max()
        
        if low_after <= stop_price:
            exit_price = stop_price
            exit_reason = 'stop'
        elif high_after >= target_price:
            exit_price = target_price
            exit_reason = 'target'
        else:
            exit_price = after.iloc[-1]['close']
            exit_reason = 'timeout'
        
        gross_pnl = (exit_price - entry_price) / entry_price * position_size * entry_price
        fees = position_size * entry_price * FEE_PCT * 2
        net_pnl = gross_pnl - fees
        
        capital += net_pnl
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak)
        
        trades.append({'net_pnl': net_pnl, 'exit_reason': exit_reason})
    
    return trades, max_dd


def analyze(label, trades_list, max_dd):
    all_trades = [t for sub in trades_list for t in sub]
    if not all_trades:
        return None
    
    df = pd.DataFrame(all_trades)
    wins = df[df['net_pnl'] > 0]
    losses = df[df['net_pnl'] <= 0]
    n = len(df)
    
    win_rate = len(wins) / n * 100
    avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['net_pnl'].mean() if len(losses) > 0 else 0
    gross_profit = wins['net_pnl'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['net_pnl'].sum()) if len(losses) > 0 else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    expectancy = (len(wins)/n * avg_win) - (len(losses)/n * abs(avg_loss))
    total_pnl = df['net_pnl'].sum()
    total_ret = total_pnl / INITIAL_CAPITAL * 100
    
    return {
        'label': label,
        'trades': n,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'expectancy': expectancy,
        'profit_factor': pf,
        'total_return': total_ret,
        'max_dd': max_dd * 100,
        'pairs_with_trades': len([t for t in trades_list if t])
    }


def main():
    print("=" * 80)
    print("EXHAUSTIVE TIMEFRAME BACKTEST")
    print("=" * 80)
    print(f"Pairs: {', '.join(PAIRS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print()
    
    results = []
    
    for tf in TIMEFRAMES:
        print(f"\n{'='*60}")
        print(f"TIMEFRAME: {tf}")
        print(f"{'='*60}")
        
        all_trades = []
        all_max_dd = []
        
        for symbol in PAIRS:
            print(f"  Processing: {symbol}...")
            df = fetch_data(symbol, tf)
            trades, max_dd = backtest_hybrid(df)
            all_trades.append(trades)
            all_max_dd.append(max_dd)
            if trades:
                print(f"    {len(trades)} trades")
            else:
                print(f"    No trades")
        
        res = analyze(f"{tf}", all_trades, max(all_max_dd) if all_max_dd else 0)
        if res:
            results.append(res)
    
    # Sort by expectancy
    results.sort(key=lambda x: x['expectancy'], reverse=True)
    
    print(f"\n{'='*80}")
    print("RESULTS RANKED BY EXPECTANCY")
    print(f"{'='*80}")
    print(f"{'Timeframe':<12} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7} {'Pairs':<7}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['label']:<12} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f} {r['pairs_with_trades']:<7}")
    
    print("=" * 80)


if __name__ == '__main__':
    main()
