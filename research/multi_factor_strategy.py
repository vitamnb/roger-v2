#!/usr/bin/env python3
"""
Multi-Factor Strategy Backtest
Combines: Daily structure + 4h order blocks + 1h RSI/volume/candlestick triggers
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks
from structure_tracker import find_swing_points, get_current_structure_bias

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT']
INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001


def load_data(symbol, tf):
    fp = os.path.join(DATA_DIR, f"{symbol}_{tf}.csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df.sort_values('datetime').reset_index(drop=True)


def calculate_rsi(df, period=14):
    """Calculate RSI."""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_rsi_divergence(df, lookback=20):
    """Detect bullish RSI divergence (price lower low, RSI higher low)."""
    highs = df['high'].values
    lows = df['low'].values
    rsi_vals = df['rsi'].values
    divergences = []

    for i in range(lookback, len(df) - 1):
        # Find swing low in lookback period
        recent_lows = lows[i-lookback:i]
        recent_rsi = rsi_vals[i-lookback:i]

        if len(recent_lows) < 2:
            continue

        min_price_idx = np.argmin(recent_lows)
        min_price = recent_lows[min_price_idx]

        # Compare with current
        if lows[i] < min_price and not np.isnan(rsi_vals[i]):
            # Price made lower low
            rsi_at_old_low = recent_rsi[min_price_idx]
            if not np.isnan(rsi_at_old_low) and rsi_vals[i] > rsi_at_old_low:
                # RSI made higher low = bullish divergence
                divergences.append(i)

    return divergences


def is_bullish_engulfing(df, idx):
    """Check if candle at idx is a bullish engulfing."""
    if idx < 1 or idx >= len(df):
        return False

    prev = df.iloc[idx - 1]
    curr = df.iloc[idx]

    prev_bearish = prev['close'] < prev['open']
    curr_bullish = curr['close'] > curr['open']
    engulfs = curr['close'] > prev['open'] and curr['open'] <= prev['close']

    return prev_bearish and curr_bullish and engulfs


def find_nearest_order_block(blocks_df, price, direction='bullish', max_age=50):
    """Find nearest fresh order block to price."""
    if blocks_df.empty:
        return None

    fresh = blocks_df[blocks_df['type'] == direction]
    if fresh.empty:
        return None

    # Calculate distance
    fresh = fresh.copy()
    fresh['mid'] = (fresh['price_high'] + fresh['price_low']) / 2
    fresh['dist'] = abs(fresh['mid'] - price) / price

    nearest = fresh.loc[fresh['dist'].idxmin()]
    if nearest['dist'] <= 0.02:  # Within 2%
        return nearest
    return None


def backtest_multi_factor(symbol, daily_df, h4_df, h1_df,
                          require_engulfing=False,
                          require_rsi_divergence=False,
                          require_volume_spike=False,
                          rr_ratio=1.5,
                          block_max_age=50):
    """Run multi-factor backtest."""
    if daily_df is None or h4_df is None or h1_df is None:
        return None, 0

    # Daily structure for bias
    daily_swings = find_swing_points(daily_df, left_bars=2, right_bars=2)
    daily_bias = get_current_structure_bias(daily_swings)

    if daily_bias != 'bullish':
        return None, 0  # Only trade with daily bullish bias

    # 4h order blocks
    h4_blocks = detect_order_blocks(h4_df, atr_mult=2.0, lookback=5)

    # 1h RSI
    h1_df = h1_df.copy()
    h1_df['rsi'] = calculate_rsi(h1_df)
    h1_df['volume_avg20'] = h1_df['volume'].rolling(20).mean()

    # RSI divergences
    divergences = detect_rsi_divergence(h1_df) if require_rsi_divergence else []

    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0

    for i in range(50, len(h1_df) - 20):
        # Filter 1: RSI oversold
        rsi = h1_df['rsi'].iloc[i]
        if pd.isna(rsi) or rsi > 40:
            continue

        # Filter 2: Near fresh 4h order block
        current_price = h1_df['close'].iloc[i]
        block = find_nearest_order_block(h4_blocks, current_price, 'bullish', block_max_age)
        if block is None:
            continue

        # Filter 3: Inside or near block zone
        if not (block['price_low'] * 0.995 <= current_price <= block['price_high'] * 1.005):
            continue

        # Filter 4: Bullish engulfing
        if require_engulfing and not is_bullish_engulfing(h1_df, i):
            continue

        # Filter 5: RSI divergence
        if require_rsi_divergence and i not in divergences:
            continue

        # Filter 6: Volume spike
        if require_volume_spike:
            vol_avg = h1_df['volume_avg20'].iloc[i]
            if pd.isna(vol_avg) or h1_df['volume'].iloc[i] < vol_avg * 1.3:
                continue

        # Entry logic
        entry_price = h1_df['close'].iloc[i]
        # Stop below the block low, with minimum 0.5% buffer
        stop_price = min(block['price_low'] * 0.995, entry_price * 0.985)

        if stop_price >= entry_price:
            continue
        
        # Ensure target is above entry
        target_price = entry_price + (entry_price - stop_price) * rr_ratio
        if target_price <= entry_price:
            continue

        risk_pct = (entry_price - stop_price) / entry_price
        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)
        target_price = entry_price + (entry_price - stop_price) * rr_ratio

        # Simulate
        after = h1_df.iloc[i+1:min(i+20, len(h1_df))]
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
            'symbol': symbol,
            'entry_time': h1_df['datetime'].iloc[i],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'rsi': rsi,
            'net_pnl': net_pnl,
            'exit_reason': exit_reason,
            'capital_after': capital
        })

    return pd.DataFrame(trades), max_dd


def analyze(results):
    if not results:
        print("No results.")
        return

    df = pd.concat(results, ignore_index=True)
    if df.empty:
        print("No trades.")
        return

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
    final_cap = df.iloc[-1]['capital_after']
    total_ret = (final_cap - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    print(f"\n{'='*60}")
    print("MULTI-FACTOR STRATEGY RESULTS")
    print(f"{'='*60}")
    print(f"Total trades: {n}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg win: ${avg_win:.2f}")
    print(f"Avg loss: ${avg_loss:.2f}")
    print(f"Expectancy: ${expectancy:.2f}")
    print(f"Profit factor: {pf:.2f}")
    print(f"Total return: {total_ret:.1f}%")
    print(f"Final capital: ${final_cap:.2f}")
    print("="*60)

    print("\nBy symbol:")
    for sym in df['symbol'].unique():
        s = df[df['symbol'] == sym]
        sw = s[s['net_pnl'] > 0]
        print(f"  {sym}: {len(s)} trades, {len(sw)/len(s)*100:.1f}% win, ${s['net_pnl'].sum():.2f} net")

    print("\nBy exit reason:")
    for reason in df['exit_reason'].unique():
        r = df[df['exit_reason'] == reason]
        rw = r[r['net_pnl'] > 0]
        print(f"  {reason}: {len(r)} trades, {len(rw)/len(r)*100:.1f}% win")


def run_config(label, engulfing, divergence, volume, rr):
    print(f"\n{'='*60}")
    print(f"CONFIG: {label}")
    print(f"{'='*60}")

    all_results = []
    all_max_dd = []

    for symbol in PAIRS:
        daily = load_data(symbol, '1d')
        h4 = load_data(symbol, '4h')
        h1 = load_data(symbol, '1h')

        trades, max_dd = backtest_multi_factor(
            symbol, daily, h4, h1,
            require_engulfing=engulfing,
            require_rsi_divergence=divergence,
            require_volume_spike=volume,
            rr_ratio=rr
        )

        if trades is not None and not trades.empty:
            all_results.append(trades)
            all_max_dd.append(max_dd)
            print(f"  {symbol}: {len(trades)} trades")
        else:
            print(f"  {symbol}: No trades")

    if all_results:
        analyze(all_results)
        max_dd_overall = max(all_max_dd) if all_max_dd else 0
        print(f"Max drawdown: {max_dd_overall*100:.1f}%")
    else:
        print("No trades across all pairs.")


def main():
    print("="*60)
    print("MULTI-FACTOR STRATEGY BACKTEST")
    print("Daily bias + 4h blocks + 1h RSI/candlestick/volume")
    print("="*60)

    # Test configurations
    configs = [
        ("Base (RSI<40 + block zone, 1.5:1)", False, False, False, 1.5),
        ("+ Engulfing, 1.5:1", True, False, False, 1.5),
        ("+ Engulfing + Volume, 1.5:1", True, False, True, 1.5),
        ("+ Divergence, 1.5:1", False, True, False, 1.5),
        ("+ All filters, 1.5:1", True, True, True, 1.5),
        ("Base, 2.0:1", False, False, False, 2.0),
        ("+ Engulfing, 2.0:1", True, False, False, 2.0),
    ]

    for label, engulfing, divergence, volume, rr in configs:
        run_config(label, engulfing, divergence, volume, rr)

    print("\n" + "="*60)
    print("Complete")
    print("="*60)


if __name__ == '__main__':
    main()
