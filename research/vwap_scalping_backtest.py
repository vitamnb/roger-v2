#!/usr/bin/env python3
"""
VWAP Range Scalping Backtest — 15m timeframe
Strategy: Buy lower band (VWAP - 1.5x ATR) + RSI < 45, sell at VWAP
Filter: ADX < 25 (range regime)
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT',
         'ADA_USDT', 'LINK_USDT', 'AVAX_USDT', 'BNB_USDT']

INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001
ATR_BAND_MULT = 1.5
ADX_THRESHOLD = 25
RSI_ENTRY_MAX = 45
MAX_HOLD_BARS = 20

def load_data(symbol):
    fp = os.path.join(DATA_DIR, f"{symbol}_15m.csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df.sort_values('datetime').reset_index(drop=True)

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_adx(df, period=14):
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    atr = calculate_atr(df, period)
    plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
    minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    return adx, plus_di, minus_di

def calculate_vwap(df):
    """Standard VWAP calculation"""
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def backtest_vwap_scalping(df):
    if df is None or len(df) < 100:
        return [], 0
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])
    df['atr'] = calculate_atr(df)
    df['vwap'] = calculate_vwap(df)
    df['adx'], _, _ = calculate_adx(df)
    
    # Reset VWAP daily (approximate using 96 bars = 1 day at 15m)
    df['day'] = df.index // 96
    df['vwap'] = df.groupby('day').apply(
        lambda x: ((x['high'] + x['low'] + x['close']) / 3 * x['volume']).cumsum() / x['volume'].cumsum()
    ).reset_index(level=0, drop=True)
    
    df['lower_band'] = df['vwap'] - df['atr'] * ATR_BAND_MULT
    df['upper_band'] = df['vwap'] + df['atr'] * ATR_BAND_MULT
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    in_trade = False
    entry_price = 0
    entry_idx = 0
    
    for i in range(50, len(df) - MAX_HOLD_BARS):
        if not in_trade:
            # Entry signal
            price = df['close'].iloc[i]
            lower = df['lower_band'].iloc[i]
            rsi = df['rsi'].iloc[i]
            adx = df['adx'].iloc[i]
            
            if price <= lower and rsi < RSI_ENTRY_MAX and adx < ADX_THRESHOLD:
                # Long entry
                entry_price = price
                entry_idx = i
                in_trade = True
                
                stop_price = entry_price * 0.99  # 1% hard stop
                target_price = df['vwap'].iloc[i]  # VWAP as target
                
                risk_pct = (entry_price - stop_price) / entry_price
                if risk_pct <= 0:
                    in_trade = False
                    continue
                
                risk_amount = capital * RISK_PER_TRADE
                position_size = risk_amount / (entry_price * risk_pct)
        
        else:
            # Manage trade
            for j in range(i, min(i + MAX_HOLD_BARS, len(df))):
                high = df['high'].iloc[j]
                low = df['low'].iloc[j]
                close = df['close'].iloc[j]
                
                # Check stop
                if low <= stop_price:
                    pnl = (stop_price - entry_price) / entry_price - 2 * FEE_PCT
                    trade_pnl = position_size * entry_price * pnl
                    capital += trade_pnl
                    peak = max(peak, capital)
                    dd = (peak - capital) / peak
                    max_dd = max(max_dd, dd)
                    
                    trades.append({
                        'entry_time': df['datetime'].iloc[entry_idx],
                        'exit_time': df['datetime'].iloc[j],
                        'entry_price': entry_price,
                        'exit_price': stop_price,
                        'pnl': trade_pnl,
                        'pnl_pct': pnl * 100,
                        'exit_reason': 'stop',
                        'capital': capital
                    })
                    in_trade = False
                    break
                
                # Check target (price crosses above VWAP)
                if close >= df['vwap'].iloc[j]:
                    pnl = (df['vwap'].iloc[j] - entry_price) / entry_price - 2 * FEE_PCT
                    trade_pnl = position_size * entry_price * pnl
                    capital += trade_pnl
                    peak = max(peak, capital)
                    dd = (peak - capital) / peak
                    max_dd = max(max_dd, dd)
                    
                    trades.append({
                        'entry_time': df['datetime'].iloc[entry_idx],
                        'exit_time': df['datetime'].iloc[j],
                        'entry_price': entry_price,
                        'exit_price': df['vwap'].iloc[j],
                        'pnl': trade_pnl,
                        'pnl_pct': pnl * 100,
                        'exit_reason': 'target',
                        'capital': capital
                    })
                    in_trade = False
                    break
                
                # Time-based exit
                if j - entry_idx >= MAX_HOLD_BARS - 1:
                    pnl = (close - entry_price) / entry_price - 2 * FEE_PCT
                    trade_pnl = position_size * entry_price * pnl
                    capital += trade_pnl
                    peak = max(peak, capital)
                    dd = (peak - capital) / peak
                    max_dd = max(max_dd, dd)
                    
                    trades.append({
                        'entry_time': df['datetime'].iloc[entry_idx],
                        'exit_time': df['datetime'].iloc[j],
                        'entry_price': entry_price,
                        'exit_price': close,
                        'pnl': trade_pnl,
                        'pnl_pct': pnl * 100,
                        'exit_reason': 'timeout',
                        'capital': capital
                    })
                    in_trade = False
                    break
    
    return trades, max_dd

# Run backtest
print("=" * 60)
print("VWAP RANGE SCALPING BACKTEST — 15m Timeframe")
print(f"ADX < {ADX_THRESHOLD} | RSI < {RSI_ENTRY_MAX} | VWAP bands {ATR_BAND_MULT}x ATR")
print("=" * 60)

all_trades = []
by_symbol = {}

for pair in PAIRS:
    df = load_data(pair)
    trades, max_dd = backtest_vwap_scalping(df)
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
