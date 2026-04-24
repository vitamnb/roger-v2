"""
Order Block Detector
Identifies order blocks (last opposing candle before a significant move).
"""

import numpy as np
import pandas as pd


def calculate_atr(df, period=14):
    """Calculate Average True Range."""
    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr


def detect_order_blocks(df, atr_mult=2.0, lookback=5, volume_confirm=True):
    """
    Detect order blocks in price data.

    Args:
        df: DataFrame with OHLCV columns
        atr_mult: Multiple of ATR to define 'significant move'
        lookback: How many candles forward to check for significant move
        volume_confirm: Require volume spike during block formation

    Returns:
        DataFrame with order blocks: [index, type, price_high, price_low,
                                      volume, move_size, tested, test_result]
    """
    if len(df) < 20:
        return pd.DataFrame()

    df = df.copy().reset_index(drop=True)
    atr = calculate_atr(df)
    atr_mean = atr.mean()

    blocks = []

    for i in range(len(df) - lookback - 1):
        if pd.isna(atr.iloc[i]) or atr.iloc[i] == 0:
            continue

        # Current candle
        candle = df.iloc[i]
        next_candles = df.iloc[i+1:i+1+lookback]

        # Determine if this is a potential block
        # A bullish block = last bearish/neutral candle before big up move
        # A bearish block = last bullish/neutral candle before big down move

        is_bearish = candle['close'] < candle['open']
        is_bullish = candle['close'] > candle['open']

        # Check for significant move after this candle
        if is_bearish:
            # Check for big up move (bullish block)
            move_size = (next_candles['high'].max() - candle['close']) / candle['close']
            if move_size > (atr.iloc[i] * atr_mult) / candle['close']:
                # Volume confirmation
                avg_vol = df['volume'].iloc[max(0,i-5):i].mean()
                vol_spike = candle['volume'] > avg_vol * 1.3 if volume_confirm else True

                if vol_spike:
                    blocks.append({
                        'block_index': i,
                        'type': 'bullish',
                        'price_high': float(candle['high']),
                        'price_low': float(candle['low']),
                        'price_close': float(candle['close']),
                        'price_open': float(candle['open']),
                        'volume': float(candle['volume']),
                        'move_size_pct': float(move_size * 100),
                        'atr_at_block': float(atr.iloc[i])
                    })

        elif is_bullish:
            # Check for big down move (bearish block)
            move_size = (candle['close'] - next_candles['low'].min()) / candle['close']
            if move_size > (atr.iloc[i] * atr_mult) / candle['close']:
                avg_vol = df['volume'].iloc[max(0,i-5):i].mean()
                vol_spike = candle['volume'] > avg_vol * 1.3 if volume_confirm else True

                if vol_spike:
                    blocks.append({
                        'block_index': i,
                        'type': 'bearish',
                        'price_high': float(candle['high']),
                        'price_low': float(candle['low']),
                        'price_close': float(candle['close']),
                        'price_open': float(candle['open']),
                        'volume': float(candle['volume']),
                        'move_size_pct': float(move_size * 100),
                        'atr_at_block': float(atr.iloc[i])
                    })

    blocks_df = pd.DataFrame(blocks)
    return blocks_df


def test_order_block_retest(df, blocks_df, test_lookforward=20):
    """
    Test whether price retests order blocks and respects them.

    Args:
        df: Full price DataFrame
        blocks_df: Order blocks from detect_order_blocks()
        test_lookforward: How many candles to look for retest

    Returns:
        blocks_df with 'tested', 'test_result', 'test_price', 'test_index' columns
    """
    if blocks_df.empty:
        return blocks_df

    results = blocks_df.copy()
    results['tested'] = False
    results['test_result'] = None
    results['test_price'] = None
    results['test_index'] = None

    for idx, block in results.iterrows():
        block_high = block['price_high']
        block_low = block['price_low']
        block_type = block['type']
        start_idx = int(block['block_index']) + 1
        end_idx = min(start_idx + test_lookforward, len(df))

        if start_idx >= len(df):
            continue

        test_slice = df.iloc[start_idx:end_idx]

        # Bullish block: price returns to block zone, then bounces up
        if block_type == 'bullish':
            enters_zone = test_slice[
                (test_slice['low'] <= block_high) &
                (test_slice['high'] >= block_low)
            ]
            if not enters_zone.empty:
                results.at[idx, 'tested'] = True
                entry_idx = enters_zone.index[0]
                # Check if price moves up after entering zone
                after_entry = df.iloc[entry_idx:min(entry_idx+5, len(df))]
                if len(after_entry) > 1:
                    max_up = (after_entry['high'].max() - enters_zone.iloc[0]['close']) / enters_zone.iloc[0]['close']
                    min_down = (enters_zone.iloc[0]['close'] - after_entry['low'].min()) / enters_zone.iloc[0]['close']

                    if max_up > min_down * 1.5:  # More up than down
                        results.at[idx, 'test_result'] = 'bounce'
                    else:
                        results.at[idx, 'test_result'] = 'break'
                    results.at[idx, 'test_price'] = float(enters_zone.iloc[0]['close'])
                    results.at[idx, 'test_index'] = int(entry_idx)

        # Bearish block: price returns to block zone, then drops
        elif block_type == 'bearish':
            enters_zone = test_slice[
                (test_slice['low'] <= block_high) &
                (test_slice['high'] >= block_low)
            ]
            if not enters_zone.empty:
                results.at[idx, 'tested'] = True
                entry_idx = enters_zone.index[0]
                after_entry = df.iloc[entry_idx:min(entry_idx+5, len(df))]
                if len(after_entry) > 1:
                    max_up = (after_entry['high'].max() - enters_zone.iloc[0]['close']) / enters_zone.iloc[0]['close']
                    min_down = (enters_zone.iloc[0]['close'] - after_entry['low'].min()) / enters_zone.iloc[0]['close']

                    if min_down > max_up * 1.5:  # More down than up
                        results.at[idx, 'test_result'] = 'bounce'
                    else:
                        results.at[idx, 'test_result'] = 'break'
                    results.at[idx, 'test_price'] = float(enters_zone.iloc[0]['close'])
                    results.at[idx, 'test_index'] = int(entry_idx)

    return results
