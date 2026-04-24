"""
trade_journal.py — Extracts closed trades from Freqtrade DB and logs them
with market context for pattern analysis.
Run: python trade_journal.py
Output: trades_journal.csv
"""
import sqlite3
import pandas as pd
import csv
import os
from datetime import datetime

DB_PATH = r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite"
OUTPUT_PATH = r"C:\Users\vitamnb\.openclaw\freqtrade\trades_journal.csv"

def load_trades():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            t.id,
            t.pair,
            t.open_rate,
            t.close_rate,
            t.close_profit_abs,
            t.realized_profit,
            t.exit_reason,
            t.open_date,
            t.close_date,
            t.strategy,
            t.timeframe,
            t.stake_amount,
            t.amount,
            t.fee_open,
            t.fee_close,
            t.trading_mode,
            t.is_short,
            t.stop_loss_pct,
            t.initial_stop_loss_pct,
            t.max_rate,
            t.min_rate
        FROM trades t
        WHERE t.is_open = 0
          AND t.close_date IS NOT NULL
        ORDER BY t.close_date DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def enrich_trade(row):
    """Add derived fields for analysis."""
    try:
        open_rate = float(row['open_rate']) if row['open_rate'] else 0
        close_rate = float(row['close_rate']) if row['close_rate'] else 0
        stake = float(row['stake_amount']) if row['stake_amount'] else 0
        fee_open = float(row['fee_open']) if row['fee_open'] else 0
        fee_close = float(row['fee_close']) if row['fee_close'] else 0
        realized = float(row['realized_profit']) if row['realized_profit'] else 0

        if open_rate > 0 and close_rate > 0:
            gross_pnl = (close_rate - open_rate) / open_rate
            fees = fee_open + fee_close
            net_pnl = gross_pnl - fees
        else:
            gross_pnl = None
            net_pnl = None

        row['gross_pnl_pct'] = round(gross_pnl * 100, 4) if gross_pnl is not None else None
        row['net_pnl_pct'] = round(net_pnl * 100, 4) if net_pnl is not None else None
        row['realized_profit_abs'] = realized

        # Outcome label
        exit_reason = str(row['exit_reason']).lower() if row['exit_reason'] else ''
        if exit_reason == 'exit_signal':
            row['outcome'] = 'WIN' if (net_pnl is not None and net_pnl > 0) else 'LOSS'
        elif exit_reason == 'stop_loss':
            row['outcome'] = 'SL'
        elif exit_reason == 'roi':
            row['outcome'] = 'TP'
        elif exit_reason == 'stoploss':
            row['outcome'] = 'SL'
        elif realized == 0 and close_rate and open_rate:
            row['outcome'] = 'LOSS'
        else:
            row['outcome'] = str(row['exit_reason']) if row['exit_reason'] else 'UNKNOWN'

        # Holding duration
        if row['open_date'] and row['close_date']:
            open_dt = pd.to_datetime(row['open_date'])
            close_dt = pd.to_datetime(row['close_date'])
            duration_minutes = (close_dt - open_dt).total_seconds() / 60
            row['duration_minutes'] = round(duration_minutes, 1)
            row['duration_hours'] = round(duration_minutes / 60, 2)
        else:
            row['duration_minutes'] = None
            row['duration_hours'] = None

        # Time of entry
        if row['open_date']:
            open_dt = pd.to_datetime(row['open_date'])
            row['entry_hour'] = open_dt.hour
            row['entry_dayofweek'] = open_dt.day_name()

    except Exception as e:
        pass

    return row

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading trades from DB...")
    df = load_trades()

    if df.empty:
        print("No closed trades found.")
        return

    print(f"Found {len(df)} closed trades. Enriching...")

    enriched = df.apply(enrich_trade, axis=1)

    # Select and reorder columns for the journal
    cols = [
        'id', 'pair', 'strategy', 'timeframe',
        'open_date', 'close_date',
        'entry_hour', 'entry_dayofweek',
        'open_rate', 'close_rate',
        'stake_amount', 'amount',
        'gross_pnl_pct', 'net_pnl_pct',
        'outcome', 'exit_reason',
        'duration_minutes', 'duration_hours',
        'fee_open', 'fee_close',
        'trading_mode', 'is_short',
        'stop_loss_pct', 'max_rate', 'min_rate'
    ]
    journal = enriched[[c for c in cols if c in enriched.columns]]

    # Append to existing CSV or write new
    file_exists = os.path.exists(OUTPUT_PATH)
    if file_exists:
        existing = pd.read_csv(OUTPUT_PATH)
        # Merge: append new trades not already in file
        existing_ids = set(existing['id'].astype(str))
        new = journal[~journal['id'].astype(str).isin(existing_ids)]
        if not new.empty:
            combined = pd.concat([existing, new], ignore_index=True)
            combined.to_csv(OUTPUT_PATH, index=False)
            print(f"Appended {len(new)} new trade(s). Total: {len(combined)}")
        else:
            print("No new trades to append.")
    else:
        journal.to_csv(OUTPUT_PATH, index=False)
        print(f"Created new journal with {len(journal)} trades.")

    # Summary stats
    if len(journal) > 0:
        wins = journal[journal['outcome'] == 'WIN']
        losses = journal[journal['outcome'].isin(['LOSS', 'SL'])]
        tps = journal[journal['outcome'] == 'TP']
        print(f"\n=== Journal Summary ===")
        print(f"Total closed: {len(journal)}")
        print(f"Wins:  {len(wins)} ({len(wins)/len(journal)*100:.1f}%)")
        print(f"Losses: {len(losses)} ({len(losses)/len(journal)*100:.1f}%)")
        print(f"TPs:   {len(tps)}")
        if wins['net_pnl_pct'].notna().any():
            print(f"Avg win:  {wins['net_pnl_pct'].mean():.2f}%")
        if losses['net_pnl_pct'].notna().any():
            print(f"Avg loss: {losses['net_pnl_pct'].mean():.2f}%")

if __name__ == "__main__":
    main()
