#!/usr/bin/env python
# check_trade.py — Query open trade from Freqtrade API and print alert
import json
import subprocess
import sys
import re

def get_open_trades():
    cmd = [
        "curl", "-s", "-X", "GET",
        "http://127.0.0.1:8080/api/v1/status",
        "-H", "Content-Type: application/json",
        "-u", "roger:RogerDryRun2026!"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        trades = json.loads(result.stdout)
        return [t for t in trades if t.get("is_open")]
    except json.JSONDecodeError:
        return None

def fmt_price(p):
    return f"${p:.4f}" if p >= 1 else f"${p:.6f}"

def main():
    trades = get_open_trades()

    if not trades:
        print("NO_REPLY")
        return

    for t in trades:
        pair = t["pair"]
        entry = t["open_rate"]
        stop = t["stop_loss_abs"]
        # minimal_roi for RogerStrategy: 0->7%, 60min->8%, 180min->10%
        # TP1 = 7% for RogerStrategy (immediate ROI)
        tp = round(entry * 1.07, 6)
        current = t.get("current_rate", entry)
        pnl_pct = t.get("profit_pct", 0)
        pnl_abs = t.get("profit_abs", 0)
        amount = t["amount"]
        stake = t["stake_amount"]
        direction = "LONG" if not t.get("is_short") else "SHORT"

        print(
            f"[TRADE] {direction} {pair}\n"
            f"   Entry:   {fmt_price(entry)}\n"
            f"   Stop:    {fmt_price(stop)} (-2%)\n"
            f"   TP:      {fmt_price(tp)} (+7%)\n"
            f"   Current: {fmt_price(current)} ({pnl_pct:+.2f}% | {pnl_abs:+.4f} USDT)\n"
            f"   Size:    {amount} (~{fmt_price(stake)})"
        )

if __name__ == "__main__":
    main()
