#!/usr/bin/env python3
"""
Exhaustive 1h Parameter Backtest
Tests every combination of RSI threshold, volume multiplier, R:R, block age, engulfing.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT', 'ADA_USDT', 'LINK_USDT', 'AVAX_USDT', 'BNB_USDT']
INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001


def load_data(symbol, tf='1h'):
    fp = os.path.join(DATA_DIR, f"{symbol}_{tf}.csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df.sort_values('datetime').reset_index(drop=True)


def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def is_bullish_engulfing(df, idx):
    if idx < 1 or idx >= len(df):
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (prev['close'] < prev['open'] and 
            curr['close'] > curr['open'] and 
            curr['close'] > prev['open'] and 
            curr['open'] <= prev['close'])


def backtest(df, rsi_entry, rsi_oversold, volume_mult, rr_ratio, 
             block_age, require_engulfing):
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    
    for i in range(20, len(df) - 20):
        # RSI signal
        if not (df['rsi_prev'].iloc[i] < rsi_entry and 
                df['rsi'].iloc[i] >= rsi_entry and 
                df['rsi_prev'].iloc[i] < rsi_oversold):
            continue
        
        # Engulfing filter
        if require_engulfing and not is_bullish_engulfing(df, i):
            continue
        
        # Order block filter
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= block_age:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
        # Volume filter
        if not (ob_zone and df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * volume_mult):
            continue
        
        entry_price = df['close'].iloc[i]
        stop_price = min(ob_low * 0.995, entry_price * 0.985) if ob_low else entry_price * 0.98
        target_price = entry_price + (entry_price - stop_price) * rr_ratio
        
        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:
            continue
        
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        
        after = df.iloc[i+1:min(i+20, len(df))]
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
        'pairs': len([t for t in trades_list if t])
    }


def main():
    print("=" * 90)
    print("EXHAUSTIVE 1H PARAMETER BACKTEST - 9 PAIRS")
    print("=" * 90)
    
    # Load all data first
    data = {}
    for symbol in PAIRS:
        df = load_data(symbol)
        if df is not None:
            data[symbol] = df
            print(f"Loaded: {symbol} ({len(df)} candles)")
        else:
            print(f"Missing: {symbol}")
    
    print()
    
    # Parameter grid
    configs = []
    for rsi_entry in [30, 35, 40]:
        for rsi_oversold in [20, 25, 30]:
            if rsi_oversold >= rsi_entry:
                continue
            for volume_mult in [1.0, 1.2, 1.5, 2.0]:
                for rr in [1.5, 2.0, 2.5, 3.0]:
                    for block_age in [30, 50, 100]:
                        for engulfing in [False, True]:
                            label = f"RSI{rsi_entry}/{rsi_oversold},vol{volume_mult},RR{rr},age{block_age},eng{engulfing}"
                            configs.append((rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, label))
    
    print(f"Testing {len(configs)} configurations...")
    print()
    
    results = []
    
    for rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, label in configs:
        all_trades = []
        all_max_dd = []
        
        for symbol, df in data.items():
            trades, max_dd = backtest(df, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing)
            all_trades.append(trades)
            all_max_dd.append(max_dd)
        
        res = analyze(label, all_trades, max(all_max_dd) if all_max_dd else 0)
        if res and res['trades'] >= 5:  # Need minimum sample size
            results.append(res)
    
    # Sort by expectancy
    results.sort(key=lambda x: x['expectancy'], reverse=True)
    
    print(f"\n{'='*90}")
    print("TOP 20 CONFIGURATIONS (by expectancy, min 5 trades)")
    print(f"{'='*90}")
    print(f"{'Config':<50} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7} {'Pairs':<6}")
    print("-" * 90)
    
    for r in results[:20]:
        print(f"{r['label']:<50} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f} {r['pairs']:<6}")
    
    # Show bottom for comparison
    print(f"\n{'='*90}")
    print("BOTTOM 10 (for comparison)")
    print(f"{'='*90}")
    for r in results[-10:]:
        print(f"{r['label']:<50} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f} {r['pairs']:<6}")
    
    print("=" * 90)


if __name__ == '__main__':
    main()
