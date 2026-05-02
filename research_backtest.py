#!/usr/bin/env python3
"""
Research Backtest Runner
Unified backtesting tool using VectorBT for rapid strategy validation.
Compares strategies against buy & hold benchmark.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import vectorbt as vbt

# Set up paths
FREQTRADE_DIR = Path("C:/Users/vitamnb/.openclaw/freqtrade")
DATA_DIR = FREQTRADE_DIR / "user_data" / "data" / "kucoin"
RESULTS_DIR = FREQTRADE_DIR / "research_results"

# Ensure results directory exists
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def load_kucoin_data(pair: str, timeframe: str, days: int) -> pd.DataFrame:
    """
    Load historical OHLCV data from freqtrade format.
    
    Freqtrade stores data as: user_data/data/kucoin/{pair.replace('/', '_')}-{timeframe}.feather
    """
    pair_filename = pair.replace("/", "_")
    data_file = DATA_DIR / f"{pair_filename}-{timeframe}.feather"
    
    if not data_file.exists():
        print(f"ERROR: Data file not found: {data_file}")
        print(f"Please download data first using: freqtrade download-data --pairs {pair} --timeframes {timeframe}")
        sys.exit(1)
    
    # Load feather format
    df = pd.read_feather(data_file)
    
    # Ensure datetime index
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    
    # Filter to last N days
    cutoff = df.index.max() - pd.Timedelta(days=days)
    df = df[df.index >= cutoff]
    
    print(f"Loaded {len(df)} candles from {df.index.min()} to {df.index.max()}")
    
    return df


def calculate_rsi_signals(df: pd.DataFrame, period: int = 14, oversold: int = 30, overbought: int = 70) -> Tuple[pd.Series, pd.Series]:
    """
    Simple RSI mean reversion strategy.
    Buy when RSI < oversold, sell when RSI > overbought.
    """
    close = df['close']
    
    # Calculate RSI using vectorbt
    rsi = vbt.RSI.run(close, window=period).rsi
    
    # Generate signals
    entries = rsi < oversold
    exits = rsi > overbought
    
    return entries, exits


def calculate_macd_signals(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
    """
    MACD crossover strategy.
    Buy when MACD line crosses above signal line.
    """
    close = df['close']
    
    # Calculate MACD
    macd = vbt.MACD.run(close, fast=fast, slow=slow, signal=signal)
    
    # Generate signals
    entries = macd.macd_above(macd.signal)
    exits = macd.macd_below(macd.signal)
    
    return entries, exits


def run_vectorbt_backtest(
    df: pd.DataFrame,
    entries: pd.Series,
    exits: pd.Series,
    init_cash: float = 1000.0,
    fees: float = 0.001,
    slippage: float = 0.001
) -> vbt.Portfolio:
    """
    Run VectorBT backtest with given signals.
    """
    close = df['close']
    
    portfolio = vbt.Portfolio.from_signals(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=init_cash,
        fees=fees,
        slippage=slippage,
        freq='1h',  # Hourly data
        direction='longonly'
    )
    
    return portfolio


def calculate_buy_and_hold(df: pd.DataFrame, init_cash: float = 1000.0) -> Dict:
    """
    Calculate buy & hold benchmark returns.
    """
    start_price = df['close'].iloc[0]
    end_price = df['close'].iloc[-1]
    
    shares = init_cash / start_price
    final_value = shares * end_price
    
    total_return = (final_value - init_cash) / init_cash
    
    # Calculate drawdown
    cummax = df['close'].cummax()
    drawdown = (df['close'] - cummax) / cummax
    max_drawdown = drawdown.min()
    
    return {
        'total_return': total_return,
        'final_value': final_value,
        'max_drawdown': max_drawdown,
        'start_price': start_price,
        'end_price': end_price
    }


def extract_metrics(portfolio: vbt.Portfolio) -> Dict:
    """
    Extract standard metrics from VectorBT portfolio.
    """
    metrics = {
        'total_return': portfolio.total_return(),
        'sharpe_ratio': portfolio.sharpe_ratio(),
        'sortino_ratio': portfolio.sortino_ratio(),
        'max_drawdown': portfolio.max_drawdown(),
        'win_rate': portfolio.trades.win_rate() if len(portfolio.trades) > 0 else 0,
        'avg_trade_return': portfolio.trades.returns.mean() if len(portfolio.trades) > 0 else 0,
        'total_trades': len(portfolio.trades),
        'profit_factor': portfolio.trades.profit_factor() if len(portfolio.trades) > 0 else 0,
    }
    
    # Convert to Python scalars for JSON serialization
    return {k: float(v) if hasattr(v, 'item') else v for k, v in metrics.items()}


def save_results(
    strategy_name: str,
    pair: str,
    timeframe: str,
    days: int,
    metrics: Dict,
    bh_metrics: Dict,
    output_dir: Path = RESULTS_DIR
) -> Path:
    """
    Save backtest results to JSON file.
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{strategy_name}_{pair.replace('/', '_')}_{timeframe}_{days}d_{timestamp}.json"
    filepath = output_dir / filename
    
    results = {
        'metadata': {
            'strategy': strategy_name,
            'pair': pair,
            'timeframe': timeframe,
            'days': days,
            'timestamp': timestamp,
            'timestamp_iso': datetime.now().isoformat(),
        },
        'strategy_metrics': metrics,
        'buy_hold_metrics': bh_metrics,
        'comparison': {
            'outperformance_vs_bh': metrics['total_return'] - bh_metrics['total_return'],
            'sharpe_vs_bh': 'N/A',  # Would need BH Sharpe calc
        }
    }
    
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)
    
    return filepath


def print_results(strategy_name: str, metrics: Dict, bh_metrics: Dict):
    """
    Pretty print backtest results.
    """
    print("\n" + "="*60)
    print(f"BACKTEST RESULTS: {strategy_name}")
    print("="*60)
    
    print(f"\n{'Metric':<25} {'Strategy':>15} {'Buy & Hold':>15}")
    print("-"*60)
    print(f"{'Total Return':<25} {metrics['total_return']*100:>14.2f}% {bh_metrics['total_return']*100:>14.2f}%")
    print(f"{'Sharpe Ratio':<25} {metrics['sharpe_ratio']:>15.2f} {'N/A':>15}")
    print(f"{'Sortino Ratio':<25} {metrics['sortino_ratio']:>15.2f} {'N/A':>15}")
    print(f"{'Max Drawdown':<25} {metrics['max_drawdown']*100:>14.2f}% {bh_metrics['max_drawdown']*100:>14.2f}%")
    print(f"{'Win Rate':<25} {metrics['win_rate']*100:>14.2f}% {'N/A':>15}")
    print(f"{'Total Trades':<25} {metrics['total_trades']:>15} {'1':>15}")
    print(f"{'Profit Factor':<25} {metrics['profit_factor']:>15.2f} {'N/A':>15}")
    
    outperf = (metrics['total_return'] - bh_metrics['total_return']) * 100
    print(f"\n{'Outperformance vs B&H':<25} {outperf:>+.2f}%")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Research Backtest Runner')
    parser.add_argument('--strategy', type=str, default='RSI', 
                       choices=['RSI', 'MACD', 'BuyHold'],
                       help='Strategy to backtest')
    parser.add_argument('--pair', type=str, default='BTC/USDT',
                       help='Trading pair (e.g., BTC/USDT)')
    parser.add_argument('--timeframe', type=str, default='1h',
                       choices=['1h', '4h', '1d'],
                       help='Candle timeframe')
    parser.add_argument('--days', type=int, default=90,
                       help='Number of days to backtest')
    parser.add_argument('--init-cash', type=float, default=1000.0,
                       help='Initial cash amount')
    parser.add_argument('--save', action='store_true',
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    print(f"Research Backtest: {args.strategy} on {args.pair} ({args.timeframe}, last {args.days} days)")
    print(f"Data directory: {DATA_DIR}")
    print()
    
    # Load data
    try:
        df = load_kucoin_data(args.pair, args.timeframe, args.days)
    except SystemExit:
        return 1
    
    # Calculate buy & hold benchmark
    bh_metrics = calculate_buy_and_hold(df, args.init_cash)
    
    # Run strategy backtest
    if args.strategy == 'BuyHold':
        # Buy & hold: enter at start, never exit
        entries = pd.Series([True] + [False] * (len(df) - 1), index=df.index)
        exits = pd.Series([False] * len(df), index=df.index)
    elif args.strategy == 'RSI':
        entries, exits = calculate_rsi_signals(df)
    elif args.strategy == 'MACD':
        entries, exits = calculate_macd_signals(df)
    else:
        print(f"ERROR: Unknown strategy: {args.strategy}")
        return 1
    
    # Run backtest
    portfolio = run_vectorbt_backtest(df, entries, exits, args.init_cash)
    
    # Extract metrics
    metrics = extract_metrics(portfolio)
    
    # Print results
    print_results(args.strategy, metrics, bh_metrics)
    
    # Save results if requested
    if args.save:
        filepath = save_results(args.strategy, args.pair, args.timeframe, args.days, metrics, bh_metrics)
        print(f"\nResults saved to: {filepath}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
