#!/usr/bin/env python3
"""
Momentum Scalping Backtest — 15m timeframe
Strategy: Buy pullback to EMA20 in uptrend (price > EMA50 on 1h), quick exits
Filter: 1h trend bullish + 15m volume spike + RSI momentum
"""

import pandas as pd
import numpy as np
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT',
         'ADA_USDT', 'LINK_USDT', 'AVAX_USDT', 'BNB_USDT']

INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001
MAX_HOLD_BARS = 16  # 4 hours on 15m

def load_data(symbol, tf='15m'):
    fp = os.path.join(DATA_DIR, f"{symbol}_{tf}.csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df.sort_values('datetime').reset_index(drop=True)

def add_indicators(df):
    df = df.copy()
    df['ema20'] = df['close'].ewm(span=20).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # ATR for stop
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # Swing low (last 10 bars)
    df['swing_low'] = df['low'].rolling(10).min().shift(1)
    
    return df

def backtest_momentum_scalp(df):
    if df is None or len(df) < 100:
        return [], 0
    
    df = add_indicators(df)
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    in_trade = False
    entry_price = 0
    entry_idx = 0
    stop_price = 0
    target_price = 0
    position_size = 0
    
    for i in range(60, len(df) - MAX_HOLD_BARS):
        if not in_trade:
            # Entry: Pullback to EMA20 in uptrend
            price = df['close'].iloc[i]
            prev_close = df['close'].iloc[i-1]
            prev_low = df['low'].iloc[i-1]
            ema20 = df['ema20'].iloc[i]
            ema50 = df['ema50'].iloc[i]
            rsi = df['rsi'].iloc[i]
            vol = df['volume'].iloc[i]
            vol_avg = df['volume_avg20'].iloc[i]
            
            # Uptrend: price above EMA50
            # Pullback: previous bar touched or went below EMA20, current bar bounces
            # Momentum: RSI > 50
            # Volume: above average
            trend_up = price > ema50
            pullback = prev_low <= ema20 * 1.005 and price > ema20
            momentum = rsi > 50
            volume_conf = vol > vol_avg * 1.0
            
            if trend_up and pullback and momentum and volume_conf:
                entry_price = price
                entry_idx = i
                in_trade = True
                
                # Stop: Below swing low or 1.5x ATR
                swing = df['swing_low'].iloc[i]
                atr_stop = entry_price - df['atr'].iloc[i] * 1.5
                stop_price = max(swing, atr_stop) if not pd.isna(swing) else atr_stop
                
                # Target: 1.5:1 R:R
                risk = entry_price - stop_price
                if risk <= 0:
                    in_trade = False
                    continue
                target_price = entry_price + risk * 1.5
                
                risk_pct = risk / entry_price
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
                
                # Check target
                if high >= target_price:
                    pnl = (target_price - entry_price) / entry_price - 2 * FEE_PCT
                    trade_pnl = position_size * entry_price * pnl
                    capital += trade_pnl
                    peak = max(peak, capital)
                    dd = (peak - capital) / peak
                    max_dd = max(max_dd, dd)
                    
                    trades.append({
                        'entry_time': df['datetime'].iloc[entry_idx],
                        'exit_time': df['datetime'].iloc[j],
                        'entry_price': entry_price,
                        'exit_price': target_price,
                        'pnl': trade_pnl,
                        'pnl_pct': pnl * 100,
                        'exit_reason': 'target',
                        'capital': capital
                    })
                    in_trade = False
                    break
                
                # Time exit
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
print("MOMENTUM SCALPING BACKTEST - 15m Timeframe")
print("Pullback to EMA20 in uptrend | RSI > 50 | 1.5:1 R:R")
print("=" * 60)

all_trades = []
by_symbol = {}

for pair in PAIRS:
    df = load_data(pair)
    trades, max_dd = backtest_momentum_scalp(df)
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
