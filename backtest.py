# backtest.py -- KuCoin strategy backtester v2
# Loosened entry conditions to match real market behaviour
# Run: python backtest.py [--symbol BTC/USDT] [--timeframe 1h] [--days 90]
#                          [--capital 58] [--risk 2] [--rr 2] [--all-pairs]
# Requirements: ccxt, pandas, numpy

import ccxt
import pandas as pd
import numpy as np
import argparse
import sys
import time
from datetime import datetime, timedelta

# -- Config ---------------------------------------------------------------------
RSI_PERIOD = 14
MA_PERIOD = 20
VOL_SMA_PERIOD = 20
ATR_PERIOD = 14
BB_WINDOW = 20
BB_STD = 2
DEFAULT_DAYS = 90
DEFAULT_TIMEFRAME = "4h"           # 4h gives 542 candles / 90 days vs 200 on 1h
DEFAULT_STARTING_CAPITAL = 100.0
DEFAULT_RISK_PCT = 2.0
DEFAULT_RR = 2.0
RATE_LIMIT_DELAY = 0.05

WATCHLIST = [
    "BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT",
    "ADA/USDT","AVAX/USDT","ARB/USDT","OP/USDT","NEAR/USDT",
    "APT/USDT","FIL/USDT","LINK/USDT","DOT/USDT","ATOM/USDT",
]
# ------------------------------------------------------------------------------

def get_kucoin():
    return ccxt.kucoin({"enableRateLimit": True, "options": {"defaultType": "spot"}})

def fetch_history(exchange, symbol, timeframe, days):
    since = exchange.parse8601(
        (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    )
    limit = 1000
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles,
                          columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df.sort_index()
    except Exception as e:
        return pd.DataFrame()

def add_indicators(df):
    if df.empty or len(df) < 30:
        return df

    # RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MA
    df["ma20"] = df["close"].rolling(MA_PERIOD).mean()

    # Volume ratio
    df["vol_sma"] = df["volume"].rolling(VOL_SMA_PERIOD).mean()
    df["vol_ratio"] = df["volume"] / df["vol_sma"]

    # Bollinger Bands
    bb_std = df["close"].rolling(BB_WINDOW).std()
    df["bb_mid"] = df["close"].rolling(BB_WINDOW).mean()
    df["bb_upper"] = df["bb_mid"] + BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - BB_STD * bb_std
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_percent"] = (df["close"] - df["bb_lower"]) / bb_range.replace(0, np.nan)

    # Price vs MA
    df["price_vs_ma"] = (df["close"] - df["ma20"]) / df["ma20"] * 100

    # ATR
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()

    # Swing low
    df["swing_low"] = df["low"].rolling(5).min()

    # Previous bar
    df["rsi_prev"] = df["rsi"].shift(1)
    df["bb_p_prev"] = df["bb_percent"].shift(1)

    # Entry signal: loosened to match choppy market reality
    # Core: RSI crosses above 50 + price above MA
    # Optional: volume > 0.8x avg, BB% < 0.3 (bonus)
    df["entry_signal"] = (
        (df["rsi"] > 50) & (df["rsi_prev"] <= 50) &
        (df["price_vs_ma"] > 0)
    )
    # Strong entry bonus flag
    df["strong_entry"] = (
        df["entry_signal"] &
        (df["vol_ratio"] > 0.8) &
        (df["bb_percent"] < 0.3)
    )

    return df

def calc_stop(df, entry_price, stop_loss_pct=2.0):
    row = df.iloc[-1]
    bb_lower = row["bb_lower"]
    swing_low = row["swing_low"]
    atr = row.get("atr", 0)

    if row["bb_percent"] < 0.3 and not np.isnan(bb_lower) and bb_lower > 0:
        stop = bb_lower * 0.995
    elif not np.isnan(swing_low):
        stop = swing_low * 0.995
    elif not np.isnan(atr) and atr > 0:
        stop = entry_price - atr
    else:
        stop = entry_price * (1 - stop_loss_pct / 100)

    stop_pct = (entry_price - stop) / entry_price * 100
    stop_pct = max(stop_pct, 0.5)
    return round(stop, 6), round(stop_pct, 2)

def run_backtest(df, starting_capital=DEFAULT_STARTING_CAPITAL,
                 risk_pct=DEFAULT_RISK_PCT, rr=DEFAULT_RR):
    trades = []
    capital = starting_capital
    peak = capital
    max_dd = 0.0
    in_pos = False
    pos = {}

    for i, (ts, row) in enumerate(df.iterrows()):
        if not in_pos:
            if row.get("entry_signal", False) and not pd.isna(row["entry_signal"]):
                entry = row["close"]
                stop_price, stop_pct = calc_stop(df, entry)
                tp_price = round(entry + (entry - stop_price) * rr, 6)
                risk_amt = capital * (risk_pct / 100)
                risk_per_unit = entry * (stop_pct / 100)
                if risk_per_unit <= 0:
                    continue
                units = risk_amt / risk_per_unit
                pos = {
                    "entry_time": ts, "entry_price": entry,
                    "stop_price": stop_price, "tp_price": tp_price,
                    "stop_pct": stop_pct, "units": units,
                    "risk_amt": risk_amt, "capital_at_entry": capital,
                    "is_strong": bool(row.get("strong_entry", False)),
                }
                in_pos = True
        else:
            exit_price, exit_reason = None, None
            if row["low"] <= pos["stop_price"] <= row["high"]:
                exit_price, exit_reason = pos["stop_price"], "stop"
            elif row["high"] >= pos["tp_price"] >= row["low"]:
                exit_price, exit_reason = pos["tp_price"], "tp"
            elif row.get("rsi", 50) > 75:
                exit_price, exit_reason = row["close"], "rsi_overbought"
            elif row.get("price_vs_ma", 0) < -2:
                exit_price, exit_reason = row["close"], "trend_broken"

            if exit_price:
                pnl_val = pos["units"] * (exit_price - pos["entry_price"])
                pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
                capital += pnl_val
                dd = (peak - capital) / peak * 100
                max_dd = max(max_dd, dd)
                peak = max(peak, capital)
                df_loc = df.index.get_loc(ts)
                entry_loc = df.index.get_loc(pos["entry_time"])
                trades.append({
                    "entry_time":   pos["entry_time"],
                    "exit_time":    ts,
                    "symbol":       str(df.index.name),
                    "entry_price":  pos["entry_price"],
                    "exit_price":   exit_price,
                    "pnl_pct":      round(pnl_pct, 3),
                    "pnl_value":    round(pnl_val, 4),
                    "exit_reason": exit_reason,
                    "stop_pct":     pos["stop_pct"],
                    "capital":      round(capital, 4),
                    "duration":     df_loc - entry_loc,
                    "is_strong":    pos["is_strong"],
                })
                in_pos = False
                pos = {}

    total_return = (capital - starting_capital) / starting_capital * 100
    return trades, {
        "starting_capital": starting_capital,
        "final_capital":    capital,
        "total_return_pct": round(total_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "num_trades":       len(trades),
    }

def print_trade_table(trades):
    if not trades:
        print("  No trades.")
        return
    print(f"\n  {'#':<4} {'Entry':<22} {'Exit':<22} {'PnL%':>7} {'$':>8}  {'Reason':<18} {'Bars':>5} {'Type':<7}")
    print(f"  {'-'*4} {'-'*22} {'-'*22} {'-'*7} {'-'*8}  {'-'*18} {'-'*5} {'-'*7}")
    for i, t in enumerate(trades, 1):
        tag = "STRONG" if t["is_strong"] else "WEAK  "
        print(f"  {i:<4} {str(t['entry_time'])[:22]:<22} {str(t['exit_time'])[:22]:<22} "
              f"{t['pnl_pct']:>+7.2f}% {t['pnl_value']:>+8.4f}  {t['exit_reason']:<18} "
              f"{t['duration']:>5} {tag:<7}")

def print_summary(summary, trades, timeframe, days):
    if not trades:
        print("\n  No trades to summarise.")
        return
    wins   = [t for t in trades if t["pnl_value"] > 0]
    losses = [t for t in trades if t["pnl_value"] <= 0]
    strong = [t for t in trades if t["is_strong"]]
    weak   = [t for t in trades if not t["is_strong"]]
    win_rate = len(wins) / len(trades) * 100
    avg_win  = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
    expectancy = np.mean([t["pnl_pct"] for t in trades])
    avg_bars = np.mean([t["duration"] for t in trades])
    strong_wr = len([t for t in strong if t["pnl_value"]>0])/len(strong)*100 if strong else 0
    weak_wr   = len([t for t in weak if t["pnl_value"]>0])/len(weak)*100 if weak else 0

    # Approx trades per day on this timeframe
    bars_per_day = {"15m": 96, "1h": 24, "4h": 6, "1d": 1}.get(timeframe, 24)
    est_days = len(trades) * (bars_per_day / (24*60/{
        "15m": 15, "1h": 60, "4h": 240, "1d": 1440
    }.get(timeframe, 60)))
    est_months = est_days / 30

    print(f"\n{'='*70}")
    print(f"[SUMMARY] -- {timeframe} | {days} days | {len(trades)} trades")
    print(f"{'='*70}")
    print(f"  Starting Capital:  ${summary['starting_capital']:.2f}")
    print(f"  Final Capital:      ${summary['final_capital']:.4f}")
    print(f"  Total Return:       {summary['total_return_pct']:+.2f}%")
    print(f"  Max Drawdown:       {summary['max_drawdown_pct']:.2f}%")
    print(f"  Win Rate:           {win_rate:.1f}%  ({len(wins)}W / {len(losses)}L)")
    print(f"  Avg Win:            {avg_win:+.2f}%")
    print(f"  Avg Loss:           {avg_loss:+.2f}%")
    print(f"  Expectancy:         {expectancy:+.3f}% per trade")
    print(f"  Avg Hold:           {avg_bars:.1f} bars")
    print(f"\n  [STRONG entries]   {len(strong)} trades, {strong_wr:.1f}% win rate")
    print(f"  [WEAK entries]      {len(weak)} trades, {weak_wr:.1f}% win rate")

    print(f"\n  Exit Reasons:")
    reasons = {}
    for t in trades:
        reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason:<22} {count:>3}x")

def main():
    parser = argparse.ArgumentParser(description="KuCoin strategy backtester v2")
    parser.add_argument("--symbol", "-s", default="BTC/USDT")
    parser.add_argument("--timeframe", "-t", default=DEFAULT_TIMEFRAME,
                        choices=["15m","1h","4h","1d"])
    parser.add_argument("--days", "-d", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--capital", type=float, default=DEFAULT_STARTING_CAPITAL)
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--rr", type=float, default=DEFAULT_RR)
    parser.add_argument("--all", dest="all_pairs", action="store_true",
                        help="Backtest all watchlist pairs")
    args = parser.parse_args()

    exchange = get_kucoin()

    print(f"\n{'='*70}")
    print(f"[BACKTEST] KuCoin Strategy Backtester v2")
    print(f"   Timeframe: {args.timeframe}  |  Period: {args.days} days")
    print(f"   Capital: ${args.capital:.2f}  |  Risk: {args.risk}%/trade  |  R:R: {args.rr}:1")
    print(f"   Entry: RSI>50 crossed from below + price above 20MA")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    pairs = WATCHLIST if args.all_pairs else [args.symbol]
    all_results = []

    for pair in pairs:
        sys.stdout.write(f"  [*] {pair:<12}")
        sys.stdout.flush()

        df = fetch_history(exchange, pair, args.timeframe, args.days)
        if df.empty:
            print(f"\r  [WARN] {pair}: no data")
            time.sleep(RATE_LIMIT_DELAY)
            continue

        df = add_indicators(df)
        df.index.name = pair

        trades, summary = run_backtest(df,
            starting_capital=args.capital,
            risk_pct=args.risk, rr=args.rr
        )
        summary["pair"] = pair
        summary["signals"] = int(df["entry_signal"].sum())
        summary["strong_signals"] = int(df["strong_entry"].sum())
        all_results.append(summary)

        status = f"  {summary['num_trades']} trades, {summary['total_return_pct']:+.2f}% ret"
        print(f"\r  [DONE] {pair:<12} {status}")

        time.sleep(RATE_LIMIT_DELAY)

    # Aggregate summary
    print(f"\n{'='*70}")
    print(f"[PORTFOLIO SUMMARY] -- All Pairs")
    print(f"{'='*70}")
    print(f"  {'Pair':<12} {'Trades':>7} {'Return%':>9} {'WinRate%':>10} {'MaxDD%':>8} "
          f"{'Signals':>8} {'Strong':>7}")
    print(f"  {'-'*12} {'-'*7} {'-'*9} {'-'*10} {'-'*8} {'-'*8} {'-'*7}")

    for r in all_results:
        wins = [t for t in [] if False]  # placeholder -- we didn't store all trades globally
        # Recompute win rate per pair from summary
        wr = "N/A"
        print(f"  {r['pair']:<12} {r['num_trades']:>7} {r['total_return_pct']:>+9.2f} "
              f"{'--':>10} {r['max_drawdown_pct']:>8.2f} "
              f"{r['signals']:>8} {r['strong_signals']:>7}")

    total_return_all = sum(r['total_return_pct'] for r in all_results)
    avg_trades = np.mean([r['num_trades'] for r in all_results])
    print(f"\n  Total pairs tested:    {len(all_results)}")
    print(f"  Avg trades/pair:      {avg_trades:.1f}")
    print(f"  Combined return:      {total_return_all:+.2f}%  "
          f"(sum of all pairs, illustrative)")
    print(f"\n  Note: Multi-pair results use independent capital pools.")
    print(f"  Real portfolio would share capital -- adjust accordingly.")
    print(f"\n{'='*70}")
    print(f"  Past performance does not guarantee future results.")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
