#!/usr/bin/env python3
"""
9-Variant Backtest - All configs side by side on 9 pairs
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


def backtest_variant(df, rsi_entry, rsi_oversold, volume_mult, rr_ratio, block_age, use_engulfing, rsi70_exit):
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

        if use_engulfing and not is_bullish_engulfing(df, i):
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
            price = after.iloc[j]

            if price['low'] <= stop_price:
                exit_price = stop_price
                exit_reason = 'stop'
                break
            elif price['high'] >= target_price:
                exit_price = target_price
                exit_reason = 'target'
                break
            elif rsi70_exit and j > 0:
                # Check RSI of forward slice
                slice_df = after.iloc[:j+1].copy()
                rsi_fwd = calculate_rsi(slice_df)
                if len(rsi_fwd) > 0 and pd.notna(rsi_fwd.iloc[-1]) and rsi_fwd.iloc[-1] > 70:
                    exit_price = price['close']
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
    print("=" * 110)
    print("9-VARIANT HYBRID STRATEGY BACKTEST - 9 PAIRS")
    print("=" * 110)

    data = {}
    for symbol in PAIRS:
        df = load_data(symbol)
        if df is not None:
            data[symbol] = df
            print(f"Loaded: {symbol} ({len(df)} candles)")
        else:
            print(f"Missing: {symbol}")

    variants = [
        ("v1 BASELINE: RSI35/30, vol1.2, RR2.0, age50", 35, 30, 1.2, 2.0, 50, False, False),
        ("v2 + ENGULFING: RSI35/30, vol1.2, RR2.0, age50", 35, 30, 1.2, 2.0, 50, True, False),
        ("v3 ENGULF+VOL1.5: RSI35/30, vol1.5, RR2.0, age50", 35, 30, 1.5, 2.0, 50, True, False),
        ("v4 VOL2.0x: RSI35/30, vol2.0, RR2.0, age50", 35, 30, 2.0, 2.0, 50, False, False),
        ("v5 RSI40: RSI40/30, vol1.2, RR2.0, age50", 40, 30, 1.2, 2.0, 50, False, False),
        ("v6 AGE30: RSI35/30, vol1.2, RR2.0, age30", 35, 30, 1.2, 2.0, 30, False, False),
        ("v7 RR1.5: RSI35/30, vol1.2, RR1.5, age50", 35, 30, 1.2, 1.5, 50, False, False),
        ("v8 RSI70EXIT: RSI35/30, vol1.2, RR2.0, age50, RSI70", 35, 30, 1.2, 2.0, 50, False, True),
        ("v9 VOL1.5: RSI35/30, vol1.5, RR2.0, age50", 35, 30, 1.5, 2.0, 50, False, False),
    ]

    results = []

    for label, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit in variants:
        print(f"\nTesting: {label}...")
        all_trades = []
        all_max_dd = []

        for symbol, df in data.items():
            trades, max_dd = backtest_variant(df, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit)
            all_trades.append(trades)
            all_max_dd.append(max_dd)
            if trades:
                print(f"  {symbol}: {len(trades)} trades")

        res = analyze(label, all_trades, max(all_max_dd) if all_max_dd else 0)
        if res:
            results.append(res)
            print(f"  -> {res['trades']} total trades, {res['win_rate']:.1f}% win, ${res['expectancy']:.2f} exp, {res['total_return']:.1f}% ret")

    # Sort by expectancy
    results.sort(key=lambda x: x['expectancy'], reverse=True)

    print(f"\n{'='*110}")
    print("FINAL RESULTS - RANKED BY EXPECTANCY")
    print(f"{'='*110}")
    print(f"{'Variant':<55} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7}")
    print("-" * 110)

    for r in results:
        print(f"{r['label']:<55} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f}")

    print("=" * 110)

    # Exit reason breakdown for top 3
    print(f"\n\n{'='*110}")
    print("EXIT REASON BREAKDOWN (Top 3 Variants)")
    print(f"{'='*110}")

    for rank, r in enumerate(results[:3], 1):
        label = r['label']
        # Find the trades for this variant
        # Re-run to get trades with exit reasons
        rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit = variants[results.index(r)][1:]
        all_trades = []
        for symbol, df in data.items():
            trades, _ = backtest_variant(df, rsi_entry, rsi_oversold, volume_mult, rr, block_age, engulfing, rsi70_exit)
            all_trades.extend(trades)

        df_trades = pd.DataFrame(all_trades)
        by_reason = df_trades.groupby('exit_reason')['net_pnl'].agg(['count', 'sum'])

        print(f"\n#{rank}: {label}")
        for reason, row in by_reason.iterrows():
            print(f"  {reason}: {int(row['count'])} trades, ${row['sum']:.2f} net")

    print("=" * 110)


if __name__ == '__main__':
    main()
