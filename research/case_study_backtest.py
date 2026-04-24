#!/usr/bin/env python3
"""
Structure + Volume Profile Backtest
Tests The Chart Guys methodology on 5 major pairs.
"""

import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from volume_profile import calculate_volume_profile, get_nearest_volume_node
from order_block_detector import detect_order_blocks, test_order_block_retest
from structure_tracker import find_swing_points, detect_break_of_structure, get_current_structure_bias

# --- Config ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
PAIRS = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'ATOM_USDT']
TIMEFRAMES = ['1h', '4h', '1d']


def load_data(symbol, timeframe):
    """Load CSV data for a symbol/timeframe."""
    filepath = os.path.join(DATA_DIR, f"{symbol}_{timeframe}.csv")
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    return df


def backtest_order_blocks(df):
    """Backtest order block retest performance."""
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)
    if blocks.empty:
        return None, 0, 0

    results = test_order_block_retest(df, blocks, test_lookforward=20)
    tested = results[results['tested'] == True]

    if tested.empty:
        return results, 0, 0

    bounces = len(tested[tested['test_result'] == 'bounce'])
    breaks = len(tested[tested['test_result'] == 'break'])
    total = len(tested)

    return results, bounces, total


def backtest_structure_breaks(df):
    """Backtest break of structure retest performance."""
    swings = find_swing_points(df, left_bars=3, right_bars=3)
    if swings.empty or len(swings) < 2:
        return None, 0, 0

    breaks = detect_break_of_structure(df, swings)
    if breaks.empty:
        return breaks, 0, 0

    # Test retest of break levels
    wins = 0
    total = 0

    for _, break_event in breaks.iterrows():
        idx = int(break_event['index'])
        if idx >= len(df) - 1:
            continue

        retest_high = break_event['retest_zone_high']
        retest_low = break_event['retest_zone_low']
        direction = break_event['direction']

        # Look for retest in next 20 candles
        test_slice = df.iloc[idx+1:min(idx+21, len(df))]
        in_zone = test_slice[
            (test_slice['low'] <= retest_high) &
            (test_slice['high'] >= retest_low)
        ]

        if not in_zone.empty:
            total += 1
            entry_idx = in_zone.index[0]
            after = df.iloc[entry_idx:min(entry_idx+5, len(df))]

            if len(after) > 1:
                entry_price = in_zone.iloc[0]['close']
                if direction == 'up':
                    # In uptrend, retest should hold and price goes up
                    max_up = (after['high'].max() - entry_price) / entry_price
                    max_down = (entry_price - after['low'].min()) / entry_price
                    if max_up > max_down * 1.5:
                        wins += 1
                else:
                    max_down = (entry_price - after['low'].min()) / entry_price
                    max_up = (after['high'].max() - entry_price) / entry_price
                    if max_down > max_up * 1.5:
                        wins += 1

    return breaks, wins, total


def analyze_volume_profile(df, lookback=50):
    """Analyze how price interacts with volume profile."""
    if len(df) < lookback * 2:
        return None

    interactions = []
    for i in range(lookback, len(df)):
        slice_df = df.iloc[i-lookback:i]
        profile = calculate_volume_profile(slice_df)

        if profile:
            current_price = df.iloc[i]['close']
            node_type, node_price = get_nearest_volume_node(current_price, profile)

            if node_type:
                # Check what happens next
                future = df.iloc[i:min(i+5, len(df))]
                if len(future) > 1:
                    change = (future.iloc[-1]['close'] - current_price) / current_price
                    interactions.append({
                        'datetime': df.iloc[i]['datetime'],
                        'price': current_price,
                        'node_type': node_type,
                        'node_price': node_price,
                        'poc': profile['poc'],
                        'va_high': profile['value_area_high'],
                        'va_low': profile['value_area_low'],
                        'next_5_change_pct': change * 100
                    })

    return pd.DataFrame(interactions)


def run_case_study(symbol, timeframe):
    """Run full case study analysis on one symbol/timeframe."""
    print(f"\n{'='*60}")
    print(f"Case Study: {symbol} | {timeframe}")
    print(f"{'='*60}")

    df = load_data(symbol, timeframe)
    if df is None:
        print(f"  No data found. Run case_study_fetcher.py first.")
        return

    print(f"  Candles: {len(df)}")
    print(f"  Date range: {df['datetime'].min()} to {df['datetime'].max()}")

    # 1. Order Block Analysis
    print(f"\n  --- Order Block Analysis ---")
    ob_results, ob_bounces, ob_total = backtest_order_blocks(df)
    if ob_results is not None and not ob_results.empty:
        print(f"  Total blocks found: {len(ob_results)}")
        print(f"  Blocks tested: {ob_total}")
        if ob_total > 0:
            print(f"  Bounces (respect): {ob_bounces} ({ob_bounces/ob_total*100:.1f}%)")
            print(f"  Breaks (fail): {ob_total - ob_bounces} ({(ob_total-ob_bounces)/ob_total*100:.1f}%)")
            print(f"  Edge: {'POSITIVE' if ob_bounces > ob_total/2 else 'NEGATIVE/NEUTRAL'}")
    else:
        print(f"  No order blocks found")

    # 2. Structure Analysis
    print(f"\n  --- Break of Structure Analysis ---")
    st_results, st_wins, st_total = backtest_structure_breaks(df)
    if st_results is not None and not st_results.empty:
        print(f"  Total breaks found: {len(st_results)}")
        print(f"  Retests tested: {st_total}")
        if st_total > 0:
            print(f"  Wins (retest holds): {st_wins} ({st_wins/st_total*100:.1f}%)")
            print(f"  Fails: {st_total - st_wins} ({(st_total-st_wins)/st_total*100:.1f}%)")
            print(f"  Edge: {'POSITIVE' if st_wins > st_total/2 else 'NEGATIVE/NEUTRAL'}")
    else:
        print(f"  No structure breaks found")

    # 3. Volume Profile Analysis
    print(f"\n  --- Volume Profile Analysis ---")
    vp_df = analyze_volume_profile(df, lookback=50)
    if vp_df is not None and not vp_df.empty:
        hvn = vp_df[vp_df['node_type'] == 'HVN']
        lvn = vp_df[vp_df['node_type'] == 'LVN']

        if not hvn.empty:
            hvn_up = len(hvn[hvn['next_5_change_pct'] > 0])
            print(f"  HVN interactions: {len(hvn)} | Price up after: {hvn_up} ({hvn_up/len(hvn)*100:.1f}%)")

        if not lvn.empty:
            lvn_down = len(lvn[lvn['next_5_change_pct'] < 0])
            print(f"  LVN interactions: {len(lvn)} | Price down after: {lvn_down} ({lvn_down/len(lvn)*100:.1f}%)")

        # POC approach
        near_poc = vp_df[abs(vp_df['price'] - vp_df['poc']) / vp_df['price'] < 0.005]
        if not near_poc.empty:
            poc_bullish = len(near_poc[near_poc['next_5_change_pct'] > 0.5])
            print(f"  Near POC interactions: {len(near_poc)} | Strong moves (>0.5%): {poc_bullish}")
    else:
        print(f"  No volume profile interactions found")


def main():
    print("=" * 60)
    print("Structure + Volume Profile Case Study Backtest")
    print("=" * 60)
    print(f"Pairs: {', '.join(PAIRS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print()

    for symbol in PAIRS:
        for tf in TIMEFRAMES:
            run_case_study(symbol, tf)

    print("\n" + "=" * 60)
    print("Case Study Complete")
    print("=" * 60)


if __name__ == '__main__':
    main()
