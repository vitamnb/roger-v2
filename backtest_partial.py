"""
backtest_partial.py
Backtest Entry E with and without partial exit (RogerLayer2).
Compares:
  - Baseline: all exits at +7% (minimal_roi only)
  - Partial:  50% at +3.5% -> SL=breakeven, remaining 50% at +7%

Usage:
  python backtest_partial.py [pair] [days]
"""
import sys
import pandas as pd
import numpy as np
import ccxt

PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "AVAX/USDT", "BNB/USDT", "THETA/USDT", "ENA/USDT", "GWEI/USDT",
    "DASH/USDT", "UNI/USDT", "LINK/USDT", "BCH/USDT", "VIRTUAL/USDT",
    "WIF/USDT", "ARKM/USDT", "ZRO/USDT", "ORDI/USDT", "ONDO/USDT",
]
DAYS = 30
TP_FULL = 0.07      # 7% full exit
TP_PARTIAL = 0.035  # 3.5% partial exit
ATR_MULT = 1.5
ATR_MAX = 0.04


def fetch_ohlcv(pair, days=DAYS, tf="1h"):
    ex = ccxt.kucoin({"options": {"defaultType": "spot"}})
    ex.loadMarkets()
    ohlcv = ex.fetch_ohlcv(pair, tf, limit=days * 24 * 30)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms")
    df["rsi"] = ta_rsi(df["close"], 14)
    df["atr"] = ta_atr(df["high"], df["low"], df["close"], 14)
    df["ema12"] = ta_ema(df["close"], 12)
    df["ema26"] = ta_ema(df["close"], 26)
    df["ema12_dist_pct"] = (df["close"] - df["ema12"]) / df["ema12"] * 100
    df["rsi_prev"] = df["rsi"].shift(1)
    df["green_prev"] = (df["close"] > df["open"]).shift(1)
    return df


def ta_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def ta_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def ta_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def check_entry(row, prev_row):
    """Entry E signal for a single row."""
    return (
        -1.5 <= row["ema12_dist_pct"] <= 1.5 and
        row["rsi"] >= 40 and
        prev_row["rsi"] < 50 and
        prev_row["green_prev"]  # prev_row.green_prev means previous candle was green
    )


def run_backtest(df, partial=True):
    """
    Walk df candle by candle. One position at a time.
    Returns list of trade dicts.
    """
    trades = []
    in_trade = False
    entry_price = 0.0
    entry_idx = 0
    stop_price = 0.0
    tp_partial_price = 0.0
    tp_full_price = 0.0
    half_exited = False

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if not in_trade:
            # ---- entry ----
            if (
                -1.5 <= row["ema12_dist_pct"] <= 1.5 and
                row["rsi"] >= 40 and
                prev["rsi"] < 50 and
                prev["close"] > prev["open"]  # previous candle green
            ):
                in_trade = True
                entry_price = row["close"]
                entry_idx = i
                atr = row["atr"]
                stop_pct = min((atr / entry_price) * ATR_MULT, ATR_MAX)
                stop_price = entry_price * (1 - stop_pct)
                tp_partial_price = entry_price * (1 + TP_PARTIAL)
                tp_full_price = entry_price * (1 + TP_FULL)
                half_exited = False
        else:
            # ---- partial exit at +3.5% ----
            if partial and not half_exited and row["close"] >= tp_partial_price:
                pnl_pct = TP_PARTIAL * 100
                stop_price = entry_price  # lock remaining to breakeven
                half_exited = True
                trades.append({
                    "pair": row.get("pair", "UNKNOWN"),
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry": entry_price,
                    "exit": row["close"],
                    "pnl_pct": pnl_pct,
                    "partial": True,
                    "exit_reason": "partial_3p5",
                })
                # Position still open but half gone, keep going

            # ---- stop loss ----
            if row["low"] <= stop_price:
                if half_exited:
                    # remaining half closed at stop
                    remaining_pnl_pct = ((stop_price - entry_price) / entry_price) * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": stop_price,
                        "pnl_pct": remaining_pnl_pct,
                        "partial": False,
                        "exit_reason": "stop_after_partial",
                    })
                else:
                    pnl_pct = ((stop_price - entry_price) / entry_price) * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": stop_price,
                        "pnl_pct": pnl_pct,
                        "partial": False,
                        "exit_reason": "stop",
                    })
                in_trade = False

            # ---- full TP at +7% ----
            elif row["close"] >= tp_full_price:
                if half_exited:
                    remaining_pnl_pct = TP_FULL * 100 - TP_PARTIAL * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": tp_full_price,
                        "pnl_pct": remaining_pnl_pct,
                        "partial": False,
                        "exit_reason": "tp_after_partial",
                    })
                else:
                    pnl_pct = TP_FULL * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": tp_full_price,
                        "pnl_pct": pnl_pct,
                        "partial": False,
                        "exit_reason": "tp_full",
                    })
                in_trade = False

            # ---- EMA breakdown exit ----
            elif row["close"] < row["ema12"]:
                if half_exited:
                    remaining_pnl_pct = ((row["close"] - entry_price) / entry_price) * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": row["close"],
                        "pnl_pct": remaining_pnl_pct,
                        "partial": False,
                        "exit_reason": "ema_after_partial",
                    })
                else:
                    pnl_pct = ((row["close"] - entry_price) / entry_price) * 100
                    trades.append({
                        "pair": row.get("pair", "UNKNOWN"),
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "entry": entry_price,
                        "exit": row["close"],
                        "pnl_pct": pnl_pct,
                        "partial": False,
                        "exit_reason": "ema",
                    })
                in_trade = False

    return trades


def summary(trades, label):
    if not trades:
        return {"label": label, "trades": 0, "return": 0.0, "wr": 0.0, "avg": 0.0}
    df = pd.DataFrame(trades)
    wins = df[df["pnl_pct"] > 0]
    total_return = df["pnl_pct"].sum()
    wr = len(wins) / len(df) * 100
    avg = df["pnl_pct"].mean()
    return {
        "label": label,
        "trades": len(df),
        "return": total_return,
        "wr": wr,
        "avg": avg,
    }


if __name__ == "__main__":
    pair_arg = sys.argv[1] if len(sys.argv) > 1 else None
    days_arg = int(sys.argv[2]) if len(sys.argv) > 2 else DAYS
    pairs_to_test = [pair_arg] if pair_arg else PAIRS

    print(f"==========================================================================================")
    print(f"PARTIAL EXIT BACKTEST — Entry E — {days_arg}d 1h — KuCoin Spot")
    print(f"Partial: 50% at +3.5% -> SL=breakeven, rest at +7%")
    print(f"Baseline: all at +7% (no partial)")
    print(f"==========================================================================================")
    print()

    results = []
    for pair in pairs_to_test:
        try:
            df = fetch_ohlcv(pair, days_arg)
            df["pair"] = pair
        except Exception as e:
            print(f"  [SKIP] {pair} — {e}")
            continue

        t_base = run_backtest(df, partial=False)
        t_part = run_backtest(df, partial=True)

        s_base = summary(t_base, "baseline")
        s_part = summary(t_part, "partial")
        results.append((pair, s_base, s_part))

        print(f"{pair}:")
        print(f"  BASELINE  | trades={s_base['trades']} | return={s_base['return']:+.1f}% | WR={s_base['wr']:.1f}% | avg={s_base['avg']:+.3f}%/trade")
        print(f"  PARTIAL   | trades={s_part['trades']} | return={s_part['return']:+.1f}% | WR={s_part['wr']:.1f}% | avg={s_part['avg']:+.3f}%/trade")
        print()

    if results:
        print("==========================================================================================")
        print("AGGREGATE TOTALS")
        print("==========================================================================================")
        n = len(results)
        tot_b = sum(r[1]["return"] for r in results)
        tot_p = sum(r[2]["return"] for r in results)
        print(f"Pairs tested: {n}")
        print(f"Baseline sum-return: {tot_b:+.1f}%")
        print(f"Partial   sum-return: {tot_p:+.1f}%")
        print(f"Delta:               {tot_p - tot_b:+.1f}%")
        print()
        print(f"{'Pair':<20} {'Baseline':>10} {'Partial':>10} {'diff':>8}")
        print("-" * 50)
        for pair, s_base, s_part in results:
            diff = s_part["return"] - s_base["return"]
            print(f"{pair:<20} {s_base['return']:>+10.1f}% {s_part['return']:>+10.1f}% {diff:>+7.1f}%")
