"""
Structure Tracker
Identifies swing highs/lows and break of structure events.
"""

import numpy as np
import pandas as pd


def find_swing_points(df, left_bars=3, right_bars=3):
    """
    Find swing highs and lows.

    A swing high: high is highest in [left_bars] before and [right_bars] after
    A swing low: low is lowest in [left_bars] before and [right_bars] after

    Returns:
        DataFrame with columns: index, type (high/low), price
    """
    if len(df) < left_bars + right_bars + 1:
        return pd.DataFrame()

    swings = []
    highs = df['high'].values
    lows = df['low'].values

    for i in range(left_bars, len(df) - right_bars):
        # Swing high check
        is_swing_high = True
        for j in range(1, left_bars + 1):
            if highs[i] < highs[i - j]:
                is_swing_high = False
                break
        if is_swing_high:
            for j in range(1, right_bars + 1):
                if highs[i] <= highs[i + j]:
                    is_swing_high = False
                    break

        if is_swing_high:
            swings.append({
                'index': i,
                'type': 'high',
                'price': float(highs[i]),
                'datetime': df.index[i] if hasattr(df.index, 'freq') else df.iloc[i].get('datetime', i)
            })
            continue

        # Swing low check
        is_swing_low = True
        for j in range(1, left_bars + 1):
            if lows[i] > lows[i - j]:
                is_swing_low = False
                break
        if is_swing_low:
            for j in range(1, right_bars + 1):
                if lows[i] >= lows[i + j]:
                    is_swing_low = False
                    break

        if is_swing_low:
            swings.append({
                'index': i,
                'type': 'low',
                'price': float(lows[i]),
                'datetime': df.index[i] if hasattr(df.index, 'freq') else df.iloc[i].get('datetime', i)
            })

    return pd.DataFrame(swings)


def detect_break_of_structure(df, swings_df, confirmation_bars=2):
    """
    Detect break of structure events.

    In an uptrend: break of structure = close above prior swing high
    In a downtrend: break of structure = close below prior swing low

    Also tracks: change of character (break of internal structure indicating reversal)

    Returns:
        DataFrame with breaks: [index, type, broken_level, direction,
                                structure_state, retest_zone_high, retest_zone_low]
    """
    if swings_df.empty or len(swings_df) < 2:
        return pd.DataFrame()

    breaks = []
    structure_state = 'unknown'  # 'uptrend', 'downtrend', 'ranging'
    last_major_high = None
    last_major_low = None

    # Use iloc-safe indexing
    swings_list = swings_df.to_dict('records')

    for i, swing in enumerate(swings_list):
        idx = int(swing['index'])
        if idx >= len(df):
            continue

        if structure_state == 'unknown':
            # Use first two swings to establish initial state
            if i >= 1:
                prev = swings_list[i - 1]
                if swing['type'] == 'high' and prev['type'] == 'low':
                    if swing['price'] > prev['price']:
                        structure_state = 'uptrend'
                        last_major_high = swing['price']
                        last_major_low = prev['price']
                elif swing['type'] == 'low' and prev['type'] == 'high':
                    if swing['price'] < prev['price']:
                        structure_state = 'downtrend'
                        last_major_low = swing['price']
                        last_major_high = prev['price']

        elif structure_state == 'uptrend':
            # Check for higher high (continuation)
            if swing['type'] == 'high':
                if last_major_high and swing['price'] > last_major_high:
                    breaks.append({
                        'index': idx,
                        'type': 'break_of_structure',
                        'direction': 'up',
                        'broken_level': last_major_high,
                        'new_level': swing['price'],
                        'structure_state': 'uptrend_continuation',
                        'retest_zone_high': last_major_high,
                        'retest_zone_low': last_major_low if last_major_low else swing['price'] * 0.98
                    })
                    last_major_high = swing['price']

            # Check for lower low (potential reversal)
            elif swing['type'] == 'low':
                if last_major_low and swing['price'] < last_major_low:
                    breaks.append({
                        'index': idx,
                        'type': 'change_of_character',
                        'direction': 'down',
                        'broken_level': last_major_low,
                        'new_level': swing['price'],
                        'structure_state': 'potential_downtrend',
                        'retest_zone_high': last_major_high if last_major_high else swing['price'] * 1.02,
                        'retest_zone_low': swing['price']
                    })
                    structure_state = 'downtrend'
                    last_major_low = swing['price']

        elif structure_state == 'downtrend':
            # Check for lower low (continuation)
            if swing['type'] == 'low':
                if last_major_low and swing['price'] < last_major_low:
                    breaks.append({
                        'index': idx,
                        'type': 'break_of_structure',
                        'direction': 'down',
                        'broken_level': last_major_low,
                        'new_level': swing['price'],
                        'structure_state': 'downtrend_continuation',
                        'retest_zone_high': last_major_high if last_major_high else swing['price'] * 1.02,
                        'retest_zone_low': last_major_low
                    })
                    last_major_low = swing['price']

            # Check for higher high (potential reversal)
            elif swing['type'] == 'high':
                if last_major_high and swing['price'] > last_major_high:
                    breaks.append({
                        'index': idx,
                        'type': 'change_of_character',
                        'direction': 'up',
                        'broken_level': last_major_high,
                        'new_level': swing['price'],
                        'structure_state': 'potential_uptrend',
                        'retest_zone_high': swing['price'],
                        'retest_zone_low': last_major_low if last_major_low else swing['price'] * 0.98
                    })
                    structure_state = 'uptrend'
                    last_major_high = swing['price']

    breaks_df = pd.DataFrame(breaks)
    return breaks_df


def get_current_structure_bias(swings_df):
    """
    Get current market structure bias from recent swings.

    Returns: 'bullish', 'bearish', or 'neutral'
    """
    if swings_df.empty or len(swings_df) < 3:
        return 'neutral'

    recent = swings_df.tail(4)
    highs = recent[recent['type'] == 'high']['price'].tolist()
    lows = recent[recent['type'] == 'low']['price'].tolist()

    if len(highs) >= 2 and len(lows) >= 2:
        # Higher highs and higher lows = bullish
        if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
            return 'bullish'
        # Lower highs and lower lows = bearish
        if highs[-1] < highs[-2] and lows[-1] < lows[-2]:
            return 'bearish'

    return 'neutral'
