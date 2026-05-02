#!/usr/bin/env python3
"""
Cascade-Fade Scalper Research — Public Futures Data
Uses KuCoin futures OHLCV (1m) to detect liquidation cascade overshoots
No API keys needed for market data
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

PAIRS = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']

def fetch_futures_ohlcv(symbol, minutes=2880):
    """Fetch 1m futures OHLCV from KuCoin (public, no auth)"""
    exchange = ccxt.kucoin({'enableRateLimit': True})
    print(f"Fetching {symbol} 1m futures...")
    
    all_data = []
    since = exchange.parse8601((datetime.utcnow() - timedelta(minutes=minutes)).isoformat())
    
    try:
        while since < exchange.milliseconds():
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', since=since, limit=1500)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 60000
            if len(all_data) >= minutes:
                break
    except Exception as e:
        print(f"  Error: {e}")
    
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    print(f"  Got {len(df)} rows ({len(df)/60:.1f} hours)")
    return df

def detect_cascades(df, velocity_threshold=0.003, volume_mult=3.0, lookback=5):
    """Detect liquidation cascade signals"""
    df = df.copy()
    
    # Velocity: cumulative displacement over N bars
    df['displacement'] = (df['close'] - df['close'].shift(lookback)) / df['close'].shift(lookback)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    
    # Detect rapid drops (long cascade) or rapid rises (short cascade)
    df['is_cascade_long'] = (
        (df['displacement'] < -velocity_threshold) &
        (df['volume'] > df['volume_avg20'] * volume_mult)
    )
    
    df['is_cascade_short'] = (
        (df['displacement'] > velocity_threshold) &
        (df['volume'] > df['volume_avg20'] * volume_mult)
    )
    
    return df

def backtest_cascade_fade(df, velocity_threshold=0.003, volume_mult=3.0,
                          hold_bars=5, fee=0.0006):
    """Backtest: fade the cascade overshoot"""
    df = detect_cascades(df, velocity_threshold, volume_mult)
    
    trades = []
    capital = 1000
    
    for i in range(50, len(df) - hold_bars):
        # LONG fade: cascade down, enter long, hold, exit
        if df['is_cascade_long'].iloc[i]:
            entry = df['close'].iloc[i]
            exit_price = df['close'].iloc[min(i + hold_bars, len(df) - 1)]
            
            # Calculate P&L with fees
            pnl = (exit_price - entry) / entry - 2 * fee
            trade_pnl = capital * pnl * 0.5  # 50% position size
            capital += trade_pnl
            
            trades.append({
                'time': df['datetime'].iloc[i],
                'direction': 'long',
                'entry': entry,
                'exit': exit_price,
                'pnl_pct': pnl * 100,
                'pnl_abs': trade_pnl,
                'capital': capital
            })
        
        # SHORT fade: cascade up, enter short, hold, exit
        elif df['is_cascade_short'].iloc[i]:
            entry = df['close'].iloc[i]
            exit_price = df['close'].iloc[min(i + hold_bars, len(df) - 1)]
            
            pnl = (entry - exit_price) / entry - 2 * fee
            trade_pnl = capital * pnl * 0.5
            capital += trade_pnl
            
            trades.append({
                'time': df['datetime'].iloc[i],
                'direction': 'short',
                'entry': entry,
                'exit': exit_price,
                'pnl_pct': pnl * 100,
                'pnl_abs': trade_pnl,
                'capital': capital
            })
    
    return trades, capital

def sweep_parameters(df):
    """Sweep velocity and volume thresholds"""
    results = []
    
    for vel in [0.002, 0.003, 0.005, 0.007]:
        for vol in [2.0, 3.0, 4.0]:
            for hold in [3, 5, 8]:
                trades, final = backtest_cascade_fade(df, vel, vol, hold)
                if trades:
                    wins = sum(1 for t in trades if t['pnl_abs'] > 0)
                    pf = sum(t['pnl_abs'] for t in trades if t['pnl_abs'] > 0) / abs(sum(t['pnl_abs'] for t in trades if t['pnl_abs'] <= 0)) if sum(t['pnl_abs'] for t in trades if t['pnl_abs'] <= 0) != 0 else float('inf')
                    results.append({
                        'vel': vel, 'vol': vol, 'hold': hold,
                        'trades': len(trades), 'win_rate': wins/len(trades)*100,
                        'pf': pf, 'return_pct': (final - 1000) / 10,
                        'final': final
                    })
    
    return pd.DataFrame(results)

# Main
print("=" * 60)
print("CASCADE-FADE SCALPER RESEARCH — KuCoin Futures (Public Data)")
print("=" * 60)

for pair in PAIRS:
    print()
    df = fetch_futures_ohlcv(pair, minutes=1440)  # 24 hours of 1m data
    if len(df) < 200:
        print(f"  Insufficient data for {pair}")
        continue
    
    print(f"  Backtesting {pair}...")
    results = sweep_parameters(df)
    
    if len(results) > 0:
        best = results.loc[results['pf'].idxmax()]
        print(f"  Best config: velocity={best['vel']}, volume={best['vol']}x, hold={best['hold']} bars")
        print(f"  Trades: {int(best['trades'])}, Win Rate: {best['win_rate']:.1f}%, PF: {best['pf']:.2f}")
        print(f"  Return: {best['return_pct']:.2f}%, Final: ${best['final']:.2f}")
        
        # Show top 5 configs
        print()
        print("  Top 5 by Profit Factor:")
        top5 = results.nlargest(5, 'pf')
        for _, row in top5.iterrows():
            print(f"    v={row['vel']} vol={row['vol']}x h={row['hold']} | "
                  f"T={int(row['trades'])} WR={row['win_rate']:.0f}% PF={row['pf']:.2f} "
                  f"Ret={row['return_pct']:.1f}%")
    else:
        print("  No trades generated")

print()
print("=" * 60)
print("Research complete. This is 24h snapshot only.")
print("For robust validation: need 800+ days of 1m data + walk-forward.")
print("=" * 60)
