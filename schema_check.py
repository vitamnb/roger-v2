import sqlite3
conn = sqlite3.connect(r"C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite")
cur = conn.execute("PRAGMA table_info(trades)")
cols = [r[1] for r in cur.fetchall()]
print("Columns:", cols)
