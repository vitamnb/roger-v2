#!/usr/bin/env python3
"""
Download 15m candles for all pairs from KuCoin
"""

import ccxt
import pandas as pd
import os
from datetime import datetime

PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ATOM/USDT',
         'ADA/USDT', 'LINK/USDT', 'AVAX/USDT', 'BNB/USDT']

OUTPUT_DIR = r"C:\Users\vitamnb\.openclaw\freqtrade\data\case_studies"

def download_15m(symbol):
    exchange = ccxt.kucoin({'enableRateLimit': True})
    print(f"Downloading {symbol} 15m...")
    
    try:
        # Fetch 1000 candles of 15m data (about 10 days)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Save
        pair_name = symbol.replace('/', '_')
        path = os.path.join(OUTPUT_DIR, f"{pair_name}_15m.csv")
        df.to_csv(path, index=False)
        print(f"  Saved {len(df)} rows to {path}")
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for pair in PAIRS:
        download_15m(pair)
    
    print("\nDone!")
