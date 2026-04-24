#!/usr/bin/env python3
"""
Case Study Data Fetcher
Downloads historical OHLCV data for 5 major pairs from KuCoin.
Stores data as CSVs for volume profile and order block analysis.
"""

import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timezone
import sys

# --- Config ---
PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ATOM/USDT']
TIMEFRAMES = ['1h', '4h', '1d']
DAYS_BACK = 180  # ~6 months of data
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'case_studies')


def init_kucoin():
    """Initialize KuCoin exchange (public data, no auth needed)."""
    return ccxt.kucoin({'enableRateLimit': True})


def fetch_ohlcv(exchange, symbol, timeframe, since_ms):
    """Fetch OHLCV data with pagination."""
    all_ohlcv = []
    limit = 1500  # KuCoin max
    current_since = since_ms

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=current_since,
                limit=limit
            )
            if not ohlcv or len(ohlcv) == 0:
                break
            all_ohlcv.extend(ohlcv)
            last_ts = ohlcv[-1][0]
            if last_ts == current_since or len(ohlcv) < limit:
                break
            current_since = last_ts + 1
            time.sleep(0.5)  # Rate limit respect
        except Exception as e:
            print(f"  Error fetching {symbol} {timeframe}: {e}")
            break

    return all_ohlcv


def save_to_csv(ohlcv, symbol, timeframe, output_dir):
    """Save OHLCV data as CSV."""
    if not ohlcv:
        return False

    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volume', 'timestamp']]

    safe_symbol = symbol.replace('/', '_')
    filename = f"{safe_symbol}_{timeframe}.csv"
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath, index=False)
    return True


def main():
    print("=" * 60)
    print("Case Study Data Fetcher")
    print("=" * 60)
    print(f"Pairs: {', '.join(PAIRS)}")
    print(f"Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"Days back: {DAYS_BACK}")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output: {OUTPUT_DIR}")
    print()

    exchange = init_kucoin()
    now = datetime.now(timezone.utc)
    since = int((now.timestamp() - DAYS_BACK * 24 * 3600) * 1000)

    total_candles = 0

    for symbol in PAIRS:
        print(f"\nFetching: {symbol}")
        for tf in TIMEFRAMES:
            print(f"  [{tf}] ... ", end='', flush=True)
            ohlcv = fetch_ohlcv(exchange, symbol, tf, since)
            if ohlcv:
                save_to_csv(ohlcv, symbol, tf, OUTPUT_DIR)
                print(f"{len(ohlcv)} candles saved")
                total_candles += len(ohlcv)
            else:
                print("NO DATA")

    print()
    print("=" * 60)
    print(f"Done. Total candles downloaded: {total_candles}")
    print(f"Files saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
