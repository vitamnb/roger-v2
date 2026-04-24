"""
Volume Profile Analysis
Calculates Point of Control (POC), Value Area (VA), High/Low Volume Nodes.
"""

import numpy as np
import pandas as pd


def calculate_volume_profile(df, num_bins=50, value_area_pct=0.70):
    """
    Calculate Volume Profile for a price series.

    Args:
        df: DataFrame with 'low', 'high', 'close', 'volume' columns
        num_bins: Number of price bins for volume distribution
        value_area_pct: Percentage of volume to include in value area (default 70%)

    Returns:
        dict with: poc, poc_volume, value_area_high, value_area_low,
                   high_volume_nodes, low_volume_nodes, profile_df
    """
    if df.empty or 'volume' not in df.columns or 'close' not in df.columns:
        return None

    # Calculate typical price per candle
    df = df.copy()
    df['typical_price'] = (df['low'] + df['high'] + df['close']) / 3.0

    # Create price bins
    min_price = df['low'].min()
    max_price = df['high'].max()
    if min_price == max_price:
        return None

    bin_edges = np.linspace(min_price, max_price, num_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Assign each candle's volume to bins based on typical price
    profile_volumes = np.zeros(num_bins)
    for i in range(len(df)):
        tp = df['typical_price'].iloc[i]
        vol = df['volume'].iloc[i]
        bin_idx = np.digitize(tp, bin_edges) - 1
        bin_idx = min(max(bin_idx, 0), num_bins - 1)
        profile_volumes[bin_idx] += vol

    profile_df = pd.DataFrame({
        'price': bin_centers,
        'volume': profile_volumes
    })

    # Point of Control = price level with highest volume
    poc_idx = profile_df['volume'].idxmax()
    poc = float(profile_df.loc[poc_idx, 'price'])
    poc_volume = float(profile_df.loc[poc_idx, 'volume'])

    # Value Area = range containing value_area_pct of total volume
    total_volume = profile_volumes.sum()
    if total_volume == 0:
        return None

    target_volume = total_volume * value_area_pct
    sorted_by_price = profile_df.sort_values('price')
    cumulative = sorted_by_price['volume'].cumsum()

    # Find the narrowest range containing target_volume
    # Simplified: sort by distance from POC and accumulate
    profile_df['dist_from_poc'] = abs(profile_df['price'] - poc)
    sorted_by_dist = profile_df.sort_values('dist_from_poc')
    cumsum = sorted_by_dist['volume'].cumsum()
    in_va = cumsum <= target_volume
    va_prices = sorted_by_dist.loc[in_va, 'price']

    if not va_prices.empty:
        va_low = float(va_prices.min())
        va_high = float(va_prices.max())
    else:
        va_low = va_high = poc

    # High/Low Volume Nodes
    avg_volume = profile_df['volume'].mean()
    hvn = profile_df[profile_df['volume'] > avg_volume * 1.5]['price'].tolist()
    lvn = profile_df[profile_df['volume'] < avg_volume * 0.5]['price'].tolist()

    return {
        'poc': poc,
        'poc_volume': poc_volume,
        'value_area_high': va_high,
        'value_area_low': va_low,
        'high_volume_nodes': hvn,
        'low_volume_nodes': lvn,
        'profile_df': profile_df,
        'total_volume': total_volume
    }


def get_nearest_volume_node(price, profile, threshold_pct=0.005):
    """
    Find nearest HVN/LVN to current price.
    Returns type ('HVN'/'LVN'/None) and distance.
    """
    if profile is None:
        return None, None

    min_dist = float('inf')
    nearest_type = None
    nearest_price = None

    for hvn_price in profile.get('high_volume_nodes', []):
        dist = abs(price - hvn_price) / price
        if dist < min_dist:
            min_dist = dist
            nearest_type = 'HVN'
            nearest_price = hvn_price

    for lvn_price in profile.get('low_volume_nodes', []):
        dist = abs(price - lvn_price) / price
        if dist < min_dist:
            min_dist = dist
            nearest_type = 'LVN'
            nearest_price = lvn_price

    if min_dist <= threshold_pct:
        return nearest_type, nearest_price
    return None, None
