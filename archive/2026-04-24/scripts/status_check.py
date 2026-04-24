import sqlite3
conn = sqlite3.connect(r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite")
c = conn.cursor()
c.execute("SELECT pair, open_rate, close_rate, is_open, exit_reason, close_profit FROM trades ORDER BY is_open DESC, open_date")
rows = c.fetchall()
conn.close()
for r in rows:
    pair, open_rate, close_rate, is_open, exit_reason, close_profit = r
    open_val = float(open_rate) if open_rate else 0
    close_val = float(close_rate) if close_rate else 0
    pnl = float(close_profit) if close_profit else 0
    status = "OPEN" if is_open else "CLOSED"
    exit_s = exit_reason if exit_reason else "—"
    print(f"{pair:<12} {status:<7} entry=${open_val:.5f}  close=${close_val:.5f}  pnl={pnl:+.2f}%  exit={exit_s}")
