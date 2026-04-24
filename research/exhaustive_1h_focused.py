#!/usr/bin/env python3
"""
Focused 1h Parameter Backtest - 9 Pairs
Tests key variables that could improve edge.
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
             block_age, require_engulfing, exit_on_rsi70):
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
        if not (df['rsi_prev'].iloc[i] < rsi_entry and
                df['rsi'].iloc[i] >= rsi_entry and
                df['rsi_prev'].iloc[i] < rsi_oversold):
            continue

        if require_engulfing and not is_bullish_engulfing(df, i):
            continue

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

        exit_price = None
        exit_reason = None

        for j in range(len(after)):
            if after.iloc[j]['low'] <= stop_price:
                exit_price = stop_price
                exit_reason = 'stop'
                break
            elif after.iloc[j]['high'] >= target_price:
                exit_price = target_price
                exit_reason = 'target'
                break
            elif exit_on_rsi70 and j > 0:
                # Dynamic exit: RSI > 70
                rsi_slice = calculate_rsi(after.iloc[:j+1])
                if len(rsi_slice) > 0 and rsi_slice.iloc[-1] > 70:
                    exit_price = after.iloc[j]['close']
                    exit_reason = 'rsi70'
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
    print("FOCUSED 1H PARAMETER BACKTEST - 9 PAIRS")
    print("=" * 90)

    data = {}
    for symbol in PAIRS:
        df = load_data(symbol)
        if df is not None:
            data[symbol] = df
            print(f"Loaded: {symbol} ({len(df)} candles)")

    # Focused parameter grid - only meaningful variations
    configs = [
        # Baseline
        ("BASE: RSI35/30, vol1.2, RR2.0, age50, no engulf", 35, 30, 1.2, 2.0, 50, False, False),

        # R:R variations
        ("R:R 1.5", 35, 30, 1.2, 1.5, 50, False, False),
        ("R:R 2.5", 35, 30, 1.2, 2.5, 50, False, False),
        ("R:R 3.0", 35, 30, 1.2, 3.0, 50, False, False),

        # RSI variations
        ("RSI entry 30 (deeper oversold)", 30, 25, 1.2, 2.0, 50, False, False),
        ("RSI entry 40 (earlier entry)", 40, 30, 1.2, 2.0, 50, False, False),
        ("RSI oversold 20 (deeper)", 35, 20, 1.2, 2.0, 50, False, False),

        # Volume variations
        ("Volume 1.0x (no filter)", 35, 30, 1.0, 2.0, 50, False, False),
        ("Volume 1.5x (stricter)", 35, 30, 1.5, 2.0, 50, False, False),
        ("Volume 2.0x (very strict)", 35, 30, 2.0, 2.0, 50, False, False),

        # Block age variations
        ("Block age 30 (fresher)", 35, 30, 1.2, 2.0, 30, False, False),
        ("Block age 100 (older)", 35, 30, 1.2, 2.0, 100, False, False),

        # Engulfing
        ("+ Engulfing", 35, 30, 1.2, 2.0, 50, True, False),
        ("+ Engulfing + Volume 1.5x", 35, 30, 1.5, 2.0, 50, True, False),

        # RSI 70 exit
        ("+ RSI 70 exit (dynamic)", 35, 30, 1.2, 2.0, 50, False, True),

        # Best combinations
        ("RSI30/25, vol1.5, RR2.5", 30, 25, 1.5, 2.5, 50, False, False),
        ("RSI30/25, vol1.5, RR2.5 + engulf", 30, 25, 1.5, 2.5, 50, True, False),
    ]

    print(f"\nTesting {len(configs)} focused configurations...")
    results = []

    for label, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit in configs:
        all_trades = []
        all_max_dd = []

        for symbol, df in data.items():
            trades, max_dd = backtest(df, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit)
            all_trades.append(trades)
            all_max_dd.append(max_dd)

        res = analyze(label, all_trades, max(all_max_dd) if all_max_dd else 0)
        if res and res['trades'] >= 3:
            results.append(res)

    # Sort by expectancy
    results.sort(key=lambda x: x['expectancy'], reverse=True)

    print(f"\n{'='*90}")
    print("RESULTS RANKED BY EXPECTANCY")
    print(f"{'='*90}")
    print(f"{'Config':<55} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7}")
    print("-" * 90)

    for r in results:
        print(f"{r['label']:<55} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f}")

    print("=" * 90)


if __name__ == '__main__':
    main()
