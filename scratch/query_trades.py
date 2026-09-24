import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/optionssimulator-app/data/trading_platform.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

cursor.execute("SELECT count(*) FROM trades")
print("Total trades in DB:", cursor.fetchone()[0])

cursor.execute("SELECT order_id, symbol, entry_price, exit_price, exit_reason, realized_pnl, entry_time, exit_time FROM trades ORDER BY rowid DESC LIMIT 35")
rows = cursor.fetchall()
print(f"Showing last {len(rows)} trades:")
for r in rows:
    print(r)

conn.close()
