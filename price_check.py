#!/usr/bin/env python
"""
price_check.py
Checks current price of open Freqtrade trades and alerts if SL or TP is hit.
Run via cron: python price_check.py
"""
import subprocess
import json
import requests


def get_open_trades():
    cmd = [
        "curl", "-s", "-X", "GET",
        "http://127.0.0.1:8080/api/v1/status",
        "-u", "roger:RogerDryRun2026!"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        trades = json.loads(result.stdout)
        return [t for t in trades if t.get("is_open")]
    except json.JSONDecodeError:
        return []


def get_price(pair):
    """Fetch current price from KuCoin public API."""
    symbol = pair.replace("/", "-")
    try:
        r = requests.get(
            f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}",
            timeout=5
        )
        data = r.json().get("data", {})
        return float(data.get("price", 0))
    except Exception:
        return None


def check_trades():
    trades = get_open_trades()
    if not trades:
        print("NO_REPLY")
        return

    alerts = []
    for t in trades:
        pair = t["pair"]
        entry = float(t["open_rate"])
        stop = float(t["stop_loss_abs"])
        tp = round(entry * 1.07, 4)
        size = t["amount"]
        stake = t["stake_amount"]
        current = get_price(pair)

        if current is None:
            continue

        pct_pnl = ((current - entry) / entry) * 100

        # Check TP hit (price >= TP)
        if current >= tp:
            alerts.append(
                f"TP HIT! {pair}\n"
                f"  Entry:  ${entry:.4f}\n"
                f"  TP:     ${tp:.4f} (target hit @ ${current:.4f})\n"
                f"  Return: +{pct_pnl:.2f}%"
            )
        # Check SL hit (price <= stop)
        elif current <= stop:
            alerts.append(
                f"SL HIT! {pair}\n"
                f"  Entry:  ${entry:.4f}\n"
                f"  Stop:   ${stop:.4f} (stop triggered @ ${current:.4f})\n"
                f"  Loss:   {pct_pnl:.2f}%"
            )

    if alerts:
        for a in alerts:
            print(a)
    else:
        # Trade still open, no alert needed
        # Print brief status for the log
        t = trades[0]
        entry = float(t["open_rate"])
        stop = float(t["stop_loss_abs"])
        tp = round(entry * 1.07, 4)
        current = get_price(t["pair"])
        if current:
            pct = ((current - entry) / entry) * 100
            print(
                f"STILL OPEN: {t['pair']}\n"
                f"  Entry:  ${entry:.4f} | Stop: ${stop:.4f} | TP: ${tp:.4f}\n"
                f"  Current: ${current:.4f} ({pct:+.2f}%)"
            )
        else:
            print("NO_REPLY")


if __name__ == "__main__":
    check_trades()
