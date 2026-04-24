#!/usr/bin/env python3
"""
Hybrid Strategy Backtest - 44 Pairs
Tests Entry B + Order Block + Volume across the full watchlist.
"""

import pandas as pd
import numpy as np
import os
import sys
import ccxt
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from order_block_detector import detect_order_blocks

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'case_studies')
INITIAL_CAPITAL = 1000
RISK_PER_TRADE = 0.02
FEE_PCT = 0.001

# 44 pairs from old config
PAIRS = [
    'BNRENSHENG/USDT','VIRTUAL/USDT','WIF/USDT','H/USDT','ARKM/USDT',
    'AVAX/USDT','ENA/USDT','GWEI/USDT','BTC/USDT','ARIA/USDT',
    'SIREN/USDT','ETH/USDT','DOGE/USDT','JUP/USDT','SUI/USDT',
    'THETA/USDT','FIL/USDT','KCS/USDT','RENDER/USDT','LINK/USDT',
    'OFC/USDT','HBAR/USDT','ADA/USDT','XRP/USDT','SOL/USDT',
    'ENJ/USDT','CRV/USDT','TRX/USDT','IAG/USDT','HIGH/USDT',
    'FET/USDT','NEAR/USDT','UNI/USDT','WLD/USDT','BCH/USDT',
    'ORDI/USDT','BNB/USDT','AAVE/USDT','LIGHT/USDT','DASH/USDT',
    'ZRO/USDT','SHIB/USDT','TAO/USDT','ONDO/USDT'
]


def load_or_fetch(symbol, tf='1h'):
    """Load cached data or fetch from exchange."""
    safe = symbol.replace('/', '_')
    fp = os.path.join(DATA_DIR, f"{safe}_{tf}.csv")
    
    if os.path.exists(fp):
        df = pd.read_csv(fp)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df.sort_values('datetime').reset_index(drop=True)
    
    # Fetch from KuCoin
    print(f"  Fetching {symbol} {tf}...")
    try:
        exchange = ccxt.kucoin({'enableRateLimit': True})
        since = int((pd.Timestamp.now() - pd.Timedelta(days=180)).timestamp() * 1000)
        ohlcv = exchange.fetch_ohlcv(symbol, tf, since=since, limit=1500)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df[['datetime','open','high','low','close','volume']]
        df.to_csv(fp, index=False)
        time.sleep(0.5)
        return df
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def backtest_hybrid(df):
    """Entry B + Order Block + Volume, 2:1 R:R."""
    if df is None or len(df) < 50:
        return [], 0

    df = df.copy()
    df['rsi'] = calculate_rsi(df)
    df['rsi_prev'] = df['rsi'].shift(1)
    df['volume_avg20'] = df['volume'].rolling(20).mean()
    blocks = detect_order_blocks(df, atr_mult=2.0, lookback=5)

    trades = []
    capital = INITIAL_CAPITAL
    peak = capital
    max_dd = 0

    for i in range(15, len(df) - 20):
        # RSI signal
        if not (df['rsi_prev'].iloc[i] < 35 and df['rsi'].iloc[i] >= 35 and df['rsi_prev'].iloc[i] < 30):
            continue

        # Order block filter
        ob_zone = False
        ob_low = None
        for _, block in blocks.iterrows():
            block_idx = int(block['block_index'])
            if block_idx < i and i - block_idx <= 50:
                if block['type'] == 'bullish':
                    current_price = df['close'].iloc[i]
                    if block['price_low'] * 0.98 <= current_price <= block['price_high'] * 1.02:
                        ob_zone = True
                        ob_low = block['price_low']
                        break

        # Volume filter
        if not (ob_zone and df['volume'].iloc[i] > df['volume_avg20'].iloc[i] * 1.2):
            continue

        entry_price = df['close'].iloc[i]
        stop_price = min(ob_low * 0.995, entry_price * 0.985) if ob_low else entry_price * 0.98
        target_price = entry_price + (entry_price - stop_price) * 2.0

        risk_pct = (entry_price - stop_price) / entry_price
        if risk_pct <= 0:
            continue

        risk_amount = capital * RISK_PER_TRADE
        position_size = risk_amount / (entry_price * risk_pct)

        after = df.iloc[i+1:min(i+20, len(df))]
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
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak)

        trades.append({'net_pnl': net_pnl, 'exit_reason': exit_reason})

    return trades, max_dd


def analyze(label, trades_list, max_dd):
    all_trades = [t for sub in trades_list for t in sub]
    if not all_trades:
        print(f"{label}: No trades")
        return

    df = pd.DataFrame(all_trades)
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
    total_pnl = df['net_pnl'].sum()
    total_ret = total_pnl / INITIAL_CAPITAL * 100

    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    print(f"Pairs with trades: {len([t for t in trades_list if t])} / {len(trades_list)}")
    print(f"Total trades: {n}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg win: ${avg_win:.2f}")
    print(f"Avg loss: ${avg_loss:.2f}")
    print(f"Expectancy: ${expectancy:.2f}")
    print(f"Profit factor: {pf:.2f}")
    print(f"Total return: {total_ret:.1f}%")
    print(f"Max drawdown: {max_dd*100:.1f}%")

    by_reason = df.groupby('exit_reason')['net_pnl'].agg(['count','sum'])
    print("\nBy exit reason:")
    for reason, row in by_reason.iterrows():
        print(f"  {reason}: {int(row['count'])} trades, ${row['sum']:.2f} net")


def main():
    print("="*60)
    print("HYBRID STRATEGY - 44 PAIRS BACKTEST")
    print("="*60)
    print(f"Pairs: {len(PAIRS)}")
    print(f"Timeframe: 1h | Capital: ${INITIAL_CAPITAL}")
    print()

    os.makedirs(DATA_DIR, exist_ok=True)

    all_trades = []
    all_max_dd = []

    for symbol in PAIRS:
        print(f"Processing: {symbol}...")
        df = load_or_fetch(symbol)
        trades, max_dd = backtest_hybrid(df)
        all_trades.append(trades)
        all_max_dd.append(max_dd)
        if trades:
            print(f"  {len(trades)} trades")
        else:
            print(f"  No trades")

    analyze("HYBRID (Entry B + OB + Volume, 2:1 R:R)", all_trades, max(all_max_dd) if all_max_dd else 0)
    print("\n" + "="*60)


if __name__ == '__main__':
    main()
