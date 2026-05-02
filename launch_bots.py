#!/usr/bin/env python3
"""Launch 6 paper trading bots with proper working directory and paths."""

import subprocess
import os
import time
import sys

FREQTRADE_DIR = r"C:\Users\vitamnb\.openclaw\freqtrade"
PYTHON_PATH = r"C:\Users\vitamnb\AppData\Local\Programs\Python\Python311\python.exe"

BOTS = [
    {"name": "Roger_v3_Sniper", "strategy": "RogerHybrid_v3", "port": 8083},
    {"name": "Roger_v2_Quality", "strategy": "RogerHybrid_v2", "port": 8084},
    {"name": "Roger_v4_Vol2x", "strategy": "RogerHybrid_v4", "port": 8085},
    {"name": "Roger_v5_Frequency", "strategy": "RogerHybrid_v5", "port": 8086},
    {"name": "Roger_v6_Workhorse", "strategy": "RogerHybrid_v6", "port": 8087},
    {"name": "Roger_v7_Conservative", "strategy": "RogerHybrid_v7", "port": 8088},
]

def launch_bot(bot):
    """Launch a single bot."""
    config_path = os.path.join(FREQTRADE_DIR, "user_data", f"config_{bot['name']}.json")
    db_path = os.path.join(FREQTRADE_DIR, "user_data", f"{bot['name']}.sqlite")
    log_path = os.path.join(FREQTRADE_DIR, "user_data", "logs", f"{bot['name']}.log")
    
    cmd = [
        PYTHON_PATH, "-m", "freqtrade", "trade",
        "--config", config_path,
        "--strategy", bot["strategy"],
        "--db-url", f"sqlite:///{db_path}",
        "--logfile", log_path,
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHON_PATH
    
    p = subprocess.Popen(
        cmd,
        cwd=FREQTRADE_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    return p

def main():
    print("=" * 50)
    print("Launching 6 Paper Trading Bots")
    print("=" * 50)
    print(f"Capital: $900 (leaving $100 reserve)")
    print(f"Pairs: BTC, ETH, SOL, XRP, ATOM, ADA, LINK, AVAX, BNB")
    print(f"Timeframe: 1h")
    print()
    
    processes = []
    for bot in BOTS:
        print(f"Starting {bot['name']} on port {bot['port']}...")
        p = launch_bot(bot)
        processes.append((bot, p))
        time.sleep(3)
    
    print()
    print("All bots launched!")
    print()
    print("Dashboard URLs:")
    for bot, p in processes:
        print(f"  {bot['name']}: http://127.0.0.1:{bot['port']} (PID: {p.pid})")
    print()
    print("Press Ctrl+C to stop all bots")
    print("Note: First trade may take 1-4 hours (waiting for 1h candle close)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down bots...")
        for bot, p in processes:
            print(f"  Stopping {bot['name']}...")
            p.terminate()
            p.wait(timeout=10)
        print("All bots stopped.")

if __name__ == "__main__":
    main()
