#!/usr/bin/env python3
"""
Exhaustive Order Block Backtest
Tests confirmation logic, volume filters, and multiple R:R ratios.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT']
TIMEFRAMES = ['1h', '4h']
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


def run_backtest(df, blocks, require_confirmation=False, require_volume=False,
                 rr_ratio=2.0, max_hold=20, block_age_max=50):
    """Run a single backtest configuration."""
    if blocks.empty or df is None or len(df) < 50:
        return [], 0

    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0

    for _, block in blocks.iterrows():
        idx = int(block['block_index'])
        if idx >= len(df) - 1 or block['type'] != 'bullish':
            continue

        # Block age check
        if block_age_max and (len(df) - idx) > block_age_max:
            continue

        block_high = block['price_high']
        block_low = block['price_low']

        # Look for retest in next 20 candles
        test_slice = df.iloc[idx+1:min(idx+21, len(df))]

        if require_confirmation:
            # Wait for a candle to CLOSE inside the zone (not just wick through)
            in_zone = test_slice[
                (test_slice['close'] <= block_high) &
                (test_slice['close'] >= block_low)
            ]
        else:
            # First touch (wick or close)
            in_zone = test_slice[
                (test_slice['low'] <= block_high) &
                (test_slice['high'] >= block_low)
            ]

        if in_zone.empty:
            continue

        entry_idx = in_zone.index[0]
        entry_price = in_zone.iloc[0]['close']

        # Volume filter
        if require_volume:
            avg_vol = df['volume'].iloc[max(0, entry_idx-20):entry_idx].mean()
            if in_zone.iloc[0]['volume'] < avg_vol * 1.2:
                continue

        stop_price = block_low * 0.998
        if stop_price >= entry_price:
            continue

        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:
            continue

        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        target_price = entry_price + (entry_price - stop_price) * rr_ratio

        after = df.iloc[entry_idx:min(entry_idx + max_hold, len(df))]
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
        if capital > peak:
            peak = capital
        dd = (peak - capital) / peak
        max_dd = max(max_dd, dd)

        trades.append({
            'entry_price': entry_price, 'exit_price': exit_price,
            'stop_price': stop_price, 'target_price': target_price,
            'net_pnl': net_pnl, 'exit_reason': exit_reason,
            'risk_pct': risk_pct * 100
        })

    return trades, max_dd


def analyze(trades, max_dd, label):
    if not trades:
        return None

    df = pd.DataFrame(trades)
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
    final_cap = INITIAL_CAPITAL + df['net_pnl'].sum()
    total_ret = (final_cap - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    return {
        'label': label,
        'trades': n,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'expectancy': expectancy,
        'profit_factor': pf,
        'total_return': total_ret,
        'final_capital': final_cap,
        'max_dd': max_dd * 100
    }


def main():
    print("=" * 80)
    print("EXHAUSTIVE ORDER BLOCK BACKTEST")
    print("Testing both 1h and 4h timeframes")
    print("=" * 80)

    for tf in TIMEFRAMES:
        print(f"\n{'='*60}")
        print(f"TIMEFRAME: {tf}")
        print(f"{'='*60}")

        all_data = {}
        for symbol in PAIRS:
            df = load_data(symbol, tf)
            if df is not None:
                all_data[symbol] = df
                print(f"  Loaded: {symbol} ({len(df)} candles)")
            else:
                print(f"  Missing: {symbol}")

        print()

        configs = []
        for conf in [False, True]:
            for vol in [False, True]:
                for rr in [1.5, 2.0, 3.0]:
                    for age in [None, 50, 100]:
                        label = f"conf={conf}, vol={vol}, R:R={rr}, age={age}"
                        configs.append((conf, vol, rr, age, label))

        results = []

        for conf, vol, rr, age, label in configs:
            all_trades = []
            all_max_dd = []

            for symbol, df in all_data.items():
                blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
                trades, max_dd = run_backtest(
                    df, blocks,
                    require_confirmation=conf,
                    require_volume=vol,
                    rr_ratio=rr,
                    block_age_max=age
                )
                all_trades.extend(trades)
                all_max_dd.append(max_dd)

            if all_trades:
                res = analyze(all_trades, max(all_max_dd), label)
                if res:
                    results.append(res)

        results.sort(key=lambda x: x['expectancy'], reverse=True)

        print(f"\n{'='*80}")
        print(f"TOP 10 CONFIGURATIONS - {tf}")
        print(f"{'='*80}")
        print(f"{'Config':<45} {'Trades':<8} {'Win%':<7} {'Exp':<10} {'PF':<7} {'Ret%':<8} {'MDD%':<7}")
        print("-" * 80)

        for r in results[:10]:
            print(f"{r['label']:<45} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f}")

        print(f"\nBOTTOM 5 - {tf}")
        print("-" * 80)
        for r in results[-5:]:
            print(f"{r['label']:<45} {r['trades']:<8} {r['win_rate']:<7.1f} {r['expectancy']:<10.2f} {r['profit_factor']:<7.2f} {r['total_return']:<8.1f} {r['max_dd']:<7.1f}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
