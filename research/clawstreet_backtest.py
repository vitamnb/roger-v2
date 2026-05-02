#!/usr/bin/env python3
"""
Backtest ClawStreet logic on freqtrade whitelist
Entry: RSI(14) < 40 (between 15-40)
Stop: -2%
Target: +7%
No volume, no OB, no engulfing
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

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

def backtest_clawstreet(df):
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    
    for i in range(20, len(df) - 20):
        # Entry: RSI between 15 and 40
        if not (15 < df['rsi'].iloc[i] < 40):
            continue
        
        entry_price = df['close'].iloc[i]
        stop_price = entry_price * 0.98
        target_price = entry_price * 1.07
        
        risk_pct = 0.02
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        
        exited = False
        for j in range(i + 1, min(i + 50, len(df))):
            high = df['high'].iloc[j]
            low = df['low'].iloc[j]
            
            if low <= stop_price:
                pnl = (stop_price - entry_price) / entry_price - 2 * FEE_PCT
                exited = True
                exit_reason = 'stop'
                exit_price = stop_price
                break
            elif high >= target_price:
                pnl = (target_price - entry_price) / entry_price - 2 * FEE_PCT
                exited = True
                exit_reason = 'target'
                exit_price = target_price
                break
        
        if not exited:
            exit_price = df['close'].iloc[min(i + 49, len(df) - 1)]
            pnl = (exit_price - entry_price) / entry_price - 2 * FEE_PCT
            exit_reason = 'timeout'
        
        trade_pnl = position_size * entry_price * pnl
        capital += trade_pnl
        peak = max(peak, capital)
        dd = (peak - capital) / peak
        max_dd = max(max_dd, dd)
        
        trades.append({
            'entry_time': df['datetime'].iloc[i],
            'exit_time': df['datetime'].iloc[min(i + 49, len(df) - 1)] if not exited else df['datetime'].iloc[j],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': trade_pnl,
            'pnl_pct': pnl * 100,
            'exit_reason': exit_reason,
            'capital': capital
        })
    
    return trades, max_dd

print("=" * 60)
print("CLAWSTREET LOGIC BACKTEST ON 9-PAIR WHITELIST")
print("Entry: RSI(14) 15-40 | Stop: -2% | Target: +7%")
print("No volume, no OB, no engulfing")
print("=" * 60)

all_trades = []
by_symbol = {}

for pair in PAIRS:
    df = load_data(pair)
    trades, max_dd = backtest_clawstreet(df)
    by_symbol[pair] = {
        'trades': len(trades),
        'win': sum(1 for t in trades if t['pnl'] > 0),
        'net': sum(t['pnl'] for t in trades),
        'max_dd': max_dd
    }
    all_trades.extend(trades)
    print(f"  {pair}: {len(trades)} trades")

if all_trades:
    wins = [t['pnl'] for t in all_trades if t['pnl'] > 0]
    losses = [t['pnl'] for t in all_trades if t['pnl'] <= 0]
    win_rate = len(wins) / len(all_trades) * 100
    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0
    total_pnl = sum(t['pnl'] for t in all_trades)
    expectancy = total_pnl / len(all_trades)
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    pf = gross_profit / abs(gross_loss) if gross_loss else float('inf')
    max_dd = max(by_symbol[s]['max_dd'] for s in by_symbol)
    
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total trades: {len(all_trades)}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg win: ${avg_win:.2f}")
    print(f"Avg loss: ${avg_loss:.2f}")
    print(f"Expectancy: ${expectancy:.2f}")
    print(f"Profit factor: {pf:.2f}")
    print(f"Total return: {total_pnl:.2f}%")
    print(f"Final capital: ${1000 + total_pnl:.2f}")
    print(f"Max drawdown: {max_dd:.1%}")
    print()
    print("By symbol:")
    for pair, stats in by_symbol.items():
        wr = stats['win'] / stats['trades'] * 100 if stats['trades'] else 0
        print(f"  {pair}: {stats['trades']} trades, {wr:.1f}% win, ${stats['net']:.2f} net")
    
    print()
    print("By exit reason:")
    for reason in ['stop', 'target', 'timeout']:
        rt = [t for t in all_trades if t['exit_reason'] == reason]
        if rt:
            rw = sum(1 for t in rt if t['pnl'] > 0)
            print(f"  {reason}: {len(rt)} trades, {rw/len(rt)*100:.1f}% win")
else:
    print("No trades generated.")
