#!/usr/bin/env python3
"""
Optimization Tests - Baseline Strategy
Tests trailing stops, session filtering, ADX filter, partial exits, consecutive loss limits.
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


def calculate_adx(df, period=14):
    """Calculate ADX for trend strength."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    return adx


def is_bullish_engulfing(df, idx):
    if idx < 1 or idx >= len(df):
        return False
    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]
    return (prev['close'] < prev['open'] and
            curr['close'] > curr['open'] and
            curr['close'] > prev['open'] and
            curr['open'] <= prev['close'])


def backtest_baseline(df):
    """Baseline: RSI35/30, vol1.2, RR2.0, age50, no engulf."""
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
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
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


def backtest_trailing_stop(df, trail_pct=0.5):
    """Trailing stop: moves up as price moves up, locks in profit."""
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
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
        if not (ob_zone and df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * 1.2):
            continue
        
        entry_price = df['close'].iloc[i]
        initial_stop = min(ob_low * 0.995, entry_price * 0.985) if ob_low else entry_price * 0.98
        target_price = entry_price + (entry_price - initial_stop) * 2.0
        
        risk_pct = (entry_price - initial_stop) / entry_price
        if risk_pct <= 0:
            continue
        
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        
        after = df.iloc[i+1:min(i+20, len(df))]
        if len(after) < 2:
            continue
        
        exit_price = None
        exit_reason = None
        current_stop = initial_stop
        highest_price = entry_price
        
        for j in range(len(after)):
            price = after.iloc[j]
            
            # Update trailing stop
            if price['close'] > highest_price:
                highest_price = price['close']
                # Move stop up by trail_pct of the profit
                new_stop = initial_stop + (highest_price - entry_price) * (trail_pct / 100)
                current_stop = max(current_stop, new_stop)
            
            if price['low'] <= current_stop:
                exit_price = current_stop
                exit_reason = 'trailing_stop'
                break
            elif price['high'] >= target_price:
                exit_price = target_price
                exit_reason = 'target'
                break
        
        if exit_price is None:
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


def backtest_session_filter(df):
    """Only trade during UTC 14:00-22:00 (US market open overlap)."""
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['hour_utc'] = df['datetime'].dt.hour
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    
    for i in range(20, len(df) - 20):
        # Session filter
        if not (14 <= df['hour_utc'].iloc[i] <= 22):
            continue
        
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
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


def backtest_adx_filter(df, adx_threshold=25):
    """Only trade when ADX < threshold (ranging market)."""
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    df['adx'] = calculate_adx(df)
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    
    for i in range(20, len(df) - 20):
        # ADX filter - only in ranging markets
        if pd.notna(df['adx'].iloc[i]) and df['adx'].iloc[i] >= adx_threshold:
            continue
        
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
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


def backtest_partial_exit(df):
    """Close 50% at 1:1, let rest run to 2:1."""
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
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
        if not (ob_zone and df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * 1.2):
            continue
        
        entry_price = df['close'].iloc[i]
        stop_price = min(ob_low * 0.995, entry_price * 0.985) if ob_low else entry_price * 0.98
        risk = entry_price - stop_price
        target_1_1 = entry_price + risk * 1.0  # 50% exit here
        target_2_1 = entry_price + risk * 2.0  # Rest exits here
        
        risk_pct = risk / entry_price
        if risk_pct <= 0:
            continue
        
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        
        after = df.iloc[i+1:min(i+20, len(df))]
        if len(after) < 2:
            continue
        
        pnl = 0
        exit_reason = 'timeout'
        hit_1_1 = False
        
        for j in range(len(after)):
            price = after.iloc[j]
            
            if not hit_1_1 and price['high'] >= target_1_1:
                # Exit 50% at 1:1
                half_size = position_size / 2
                pnl += (target_1_1 - entry_price) / entry_price * half_size * entry_price
                pnl -= half_size * entry_price * FEE_PCT
                hit_1_1 = True
                exit_reason = 'partial_1_1'
                # Move stop to breakeven for remaining
                stop_price = entry_price
            
            if hit_1_1 and price['high'] >= target_2_1:
                # Exit rest at 2:1
                half_size = position_size / 2
                pnl += (target_2_1 - entry_price) / entry_price * half_size * entry_price
                pnl -= half_size * entry_price * FEE_PCT
                exit_reason = 'partial_2_1'
                break
            
            if price['low'] <= stop_price:
                if hit_1_1:
                    # Remaining half stopped out at breakeven or lower
                    half_size = position_size / 2
                    pnl += (stop_price - entry_price) / entry_price * half_size * entry_price
                    pnl -= half_size * entry_price * FEE_PCT
                    exit_reason = 'partial_stop'
                else:
                    # Full position stopped
                    pnl += (stop_price - entry_price) / entry_price * position_size * entry_price
                    pnl -= position_size * entry_price * FEE_PCT * 2
                    exit_reason = 'stop'
                break
        
        if exit_reason == 'timeout':
            # Close remaining at timeout
            if hit_1_1:
                half_size = position_size / 2
                pnl += (after.iloc[-1]['close'] - entry_price) / entry_price * half_size * entry_price
                pnl -= half_size * entry_price * FEE_PCT
            else:
                pnl += (after.iloc[-1]['close'] - entry_price) / entry_price * position_size * entry_price
                pnl -= position_size * entry_price * FEE_PCT * 2
        
        capital += pnl
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak)
        
        trades.append({'net_pnl': pnl, 'exit_reason': exit_reason})
    
    return trades, max_dd


def backtest_consecutive_loss_limit(df, max_consecutive=3):
    """Stop trading after N consecutive losses, resume next day."""
    if df is None or len(df) < 50:
        return [], 0
    
    df = df.copy()
    df['date'] = df['datetime'].dt.date
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    
    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0
    consecutive_losses = 0
    current_date = None
    
    for i in range(20, len(df) - 20):
        trade_date = df['date'].iloc[i]
        
        # Reset on new day
        if current_date != trade_date:
            current_date = trade_date
            consecutive_losses = 0
        
        # Skip if too many consecutive losses
        if consecutive_losses >= max_consecutive:
            continue
        
        if not (df['rsi_prev'].iloc[i] < 35 and
                df['rsi'].iloc[i] >= 35 and
                df['rsi_prev'].iloc[i] < 30):
            continue
        
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break
        
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
        
        if net_pnl < 0:
            consecutive_losses += 1
        else:
            consecutive_losses = 0
        
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
    print("OPTIMIZATION TESTS - BASELINE STRATEGY")
    print("=" * 90)
    
    data = {}
    for symbol in PAIRS:
        df = load_data(symbol)
        if df is not None:
            data[symbol] = df
            print(f"Loaded: {symbol} ({len(df)} candles)")
    
    print()
    
    configs = [
        ("1. Baseline (no optimization)", backtest_baseline),
        ("2. Trailing stop (0.5%)", lambda df: backtest_trailing_stop(df, 0.5)),
        ("3. Trailing stop (1.0%)", lambda df: backtest_trailing_stop(df, 1.0)),
        ("4. Session filter (UTC 14-22)", backtest_session_filter),
        ("5. ADX filter (<25, ranging only)", lambda df: backtest_adx_filter(df, 25)),
        ("6. ADX filter (<20, very ranging)", lambda df: backtest_adx_filter(df, 20)),
        ("7. Partial exit (50% @ 1:1, rest @ 2:1)", backtest_partial_exit),
        ("8. Consecutive loss limit (3/day)", lambda df: backtest_consecutive_loss_limit(df, 3)),
    ]
    
    results = []
    
    for label, func in configs:
        print(f"Testing: {label}...")
        all_trades = []
        all_max_dd = []
        
        for symbol, df in data.items():
            trades, max_dd = func(df)
            all_trades.append(trades)
            all_max_dd.append(max_dd)
        
        res = analyze(label, all_trades, max(all_max_dd) if all_max_dd else 0)
        if res:
            results.append(res)
            print(f"  -> {res['trades']} trades, {res['win_rate']:.1f}% win, ${res['expectancy']:.2f} exp, {res['total_return']:.1f}% return")
        else:
            print(f"  -> No trades")
    
    # Sort by expectancy
    results.sort(key=lambda x: x['expectancy'], reverse=True)
    
    print(f"\n{'='*90}")
    print("OPTIMIZATION RESULTS RANKED BY EXPECTANCY")
    print(f"{'='*90}")
    print(f"{'Config':<50} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['label']:<50} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f}")
    
    print("=" * 90)


if __name__ == '__main__':
    main()
