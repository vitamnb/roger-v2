#!/usr/bin/env python3
"""Trade watcher - polls freqtrade bot databases and reports new trades."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
import os

BASE = Path("C:/Users/vitamnb/.openclaw/freqtrade/user_data")
STATE_FILE = Path("C:/Users/vitamnb/.openclaw/freqtrade/.trade_watcher_state.json")

bots = [
    ("Roger_v3_Sniper", "v3 Sniper", "RSI35+ENGULF+VOL1.5"),
    ("Roger_v2_Quality", "v2 Quality", "RSI35+ENGULF"),
    ("Roger_v4_Vol2x", "v4 Vol2x", "RSI35+VOL2.0"),
    ("Roger_v5_Frequency", "v5 Frequency", "RSI40"),
    ("Roger_v6_Workhorse", "v6 Workhorse", "AGE30"),
    ("Roger_v7_Conservative", "v7 Conservative", "RR1.5"),
    ("CascadeFade_Futures", "CascadeFade", "CASCADE_FADE"),
]

# Load state
if STATE_FILE.exists():
    with open(STATE_FILE) as f:
        state = json.load(f)
else:
    state = {"reported_trades": []}

reported = set(state.get("reported_trades", []))

# Scan for new trades
new_trades = []
for bot_name, display, strategy in bots:
    db = BASE / f"{bot_name}.sqlite"
    if not db.exists():
        continue
    
    try:
        conn = sqlite3.connect(str(db))
        c = conn.cursor()
        c.execute('''
            SELECT id, pair, amount, open_rate, close_rate, 
                   close_profit, close_profit_abs, is_open, 
                   open_date, close_date, exit_reason
            FROM trades 
            ORDER BY id DESC LIMIT 5
        ''')
        
        for row in c.fetchall():
            trade_id = f"{bot_name}_{row[0]}"
            if trade_id not in reported:
                reported.add(trade_id)
                trade = {
                    "id": trade_id,
                    "bot": display,
                    "strategy": strategy,
                    "pair": row[1],
                    "amount": row[2],
                    "open_rate": row[3],
                    "close_rate": row[4],
                    "close_profit": row[5],
                    "close_profit_abs": row[6],
                    "is_open": row[7],
                    "open_date": row[8],
                    "close_date": row[9],
                    "exit_reason": row[10],
                }
                new_trades.append(trade)
        conn.close()
    except Exception as e:
        print(f"Error reading {bot_name}: {e}")

# Save state
state["reported_trades"] = list(reported)
with open(STATE_FILE, 'w') as f:
    json.dump(state, f)

# Output trade report
for trade in new_trades:
    if trade["is_open"]:
        # Entry alert
        stop_loss = trade["open_rate"] * 0.98  # 2% stop
        take_profit = trade["open_rate"] * 1.04  # 2:1 R:R
        print(f"ENTRY | {trade['bot']} ({trade['strategy']})")
        print(f"  Pair: {trade['pair']}")
        print(f"  Entry: {trade['open_rate']:.6f}")
        print(f"  Stop Loss: {stop_loss:.6f} (-2%)")
        print(f"  Take Profit: {take_profit:.6f} (+4%, 2:1 R:R)")
        print(f"  Amount: {trade['amount']:.2f} USDT")
        print(f"  Time: {trade['open_date']}")
    else:
        # Exit alert
        pnl_pct = trade["close_profit"] * 100 if trade["close_profit"] else 0
        pnl_usdt = trade["close_profit_abs"] if trade["close_profit_abs"] else 0
        print(f"EXIT | {trade['bot']} ({trade['strategy']})")
        print(f"  Pair: {trade['pair']}")
        print(f"  Entry: {trade['open_rate']:.6f}")
        print(f"  Exit: {trade['close_rate']:.6f}")
        print(f"  PnL: {pnl_pct:.2f}% (${pnl_usdt:.2f})")
        print(f"  Reason: {trade['exit_reason']}")
        print(f"  Duration: {trade['open_date']} -> {trade['close_date']}")
    print()

if not new_trades:
    # Silent - no output means no alert
    pass
