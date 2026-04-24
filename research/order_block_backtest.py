#!/usr/bin/env python3
"""
Order Block Strategy Backtest — with Expectancy
Tests full entry/exit P&L on the 5 majors.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks

# --- Config ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT']
TIMEFRAME = '4h'
INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001


def load_data(symbol, tf='4h'):
    fp = os.path.join(DATA_DIR, f"{symbol}_{tf}.csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df.sort_values('datetime').reset_index(drop=True)


def backtest_pair(symbol, df):
    if df is None or len(df) < 50:
        return None, 0

    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    if blocks.empty:
        return None, 0

    trades = []
    capital = INITIAL_CAPITAL
    peak_capital = capital
    max_drawdown = 0

    for _, block in blocks.iterrows():
        idx = int(block['block_index'])
        if idx >= len(df) - 1:
            continue

        block_type = block['type']
        block_high = block['price_high']
        block_low = block['price_low']

        # Only trade bullish blocks (spot only)
        if block_type != 'bullish':
            continue

        test_slice = df.iloc[idx+1:min(idx+21, len(df))]

        # Look for price to enter block zone
        in_zone = test_slice[
            (test_slice['low'] <= block_high) &
            (test_slice['high'] >= block_low)
        ]
        if in_zone.empty:
            continue

        entry_idx = in_zone.index[0]
        entry_price = in_zone.iloc[0]['close']

        # Stop below block low
        stop_price = block_low * 0.998
        if stop_price >= entry_price:
            continue

        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:
            continue

        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)

        # Target 2:1 R:R
        target_price = entry_price + (entry_price - stop_price) * 2

        # Simulate
        after = df.iloc[entry_idx:min(entry_idx+20, len(df))]
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
        if capital > peak_capital:
            peak_capital = capital
        dd = (peak_capital - capital) / peak_capital
        max_drawdown = max(max_drawdown, dd)

        trades.append({
            'symbol': symbol,
            'entry_time': df.iloc[entry_idx]['datetime'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'position_size': position_size,
            'gross_pnl': gross_pnl,
            'fees': fees,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'capital_after': capital
        })

    return pd.DataFrame(trades), max_drawdown


def analyze_results(all_trades, max_dd):
    if all_trades.empty:
        print("No trades found.")
        return None, None, None, None

    wins = all_trades[all_trades['net_pnl'] > 0]
    losses = all_trades[all_trades['net_pnl'] <= 0]

    total_trades = len(all_trades)
    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
    avg_win = wins['net_pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['net_pnl'].mean() if len(losses) > 0 else 0

    win_pct = len(wins) / total_trades if total_trades > 0 else 0
    loss_pct = len(losses) / total_trades if total_trades > 0 else 0
    expectancy = (win_pct * avg_win) - (loss_pct * abs(avg_loss))

    gross_profit = wins['net_pnl'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['net_pnl'].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    final_capital = all_trades.iloc[-1]['capital_after']
    total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    print("\n" + "="*60)
    print("ORDER BLOCK STRATEGY BACKTEST RESULTS")
    print("="*60)
    print(f"Total trades: {total_trades}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg win: ${avg_win:.2f}")
    print(f"Avg loss: ${avg_loss:.2f}")
    print(f"Expectancy per trade: ${expectancy:.2f}")
    print(f"Profit factor: {profit_factor:.2f}")
    print(f"Total return: {total_return:.1f}%")
    print(f"Final capital: ${final_capital:.2f}")
    print(f"Max drawdown: {max_dd*100:.1f}%")
    print("="*60)

    print("\nPer-symbol:")
    for symbol in all_trades['symbol'].unique():
        sym = all_trades[all_trades['symbol'] == symbol]
        sym_wins = len(sym[sym['net_pnl'] > 0])
        print(f"  {symbol}: {len(sym)} trades, {sym_wins/len(sym)*100:.1f}% win, ${sym['net_pnl'].sum():.2f} net")

    return expectancy, profit_factor, total_return, max_dd


def main():
    print("="*60)
    print("Order Block Strategy - Full Expectancy Backtest")
    print("="*60)
    print(f"Capital: ${INITIAL_CAPITAL} | Risk/trade: {RISK_PER_TRADE*100}% | Fee: {FEE_PCT*100}%")
    print()

    all_trades = []
    all_max_dd = []

    for symbol in PAIRS:
        print(f"Backtesting: {symbol}...")
        df = load_data(symbol)
        trades, max_dd = backtest_pair(symbol, df)
        if trades is not None and not trades.empty:
            all_trades.append(trades)
            all_max_dd.append(max_dd)
            print(f"  {len(trades)} trades")
        else:
            print(f"  No trades")

    if all_trades:
        combined = pd.concat(all_trades, ignore_index=True)
        max_dd_overall = max(all_max_dd) if all_max_dd else 0
        analyze_results(combined, max_dd_overall)
    else:
        print("No trades across all pairs.")


if __name__ == '__main__':
    main()
