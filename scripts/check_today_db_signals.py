import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import asyncpg
from backend.app.config import WebConfig

async def main():
    cfg = WebConfig.load()
    if not cfg.supabase_db_url:
        print("No supabase_db_url configured")
        return
    conn = await asyncpg.connect(cfg.supabase_db_url, statement_cache_size=0)
    rows = await conn.fetch("""
        SELECT timestamp AT TIME ZONE 'Asia/Kolkata' as ts, strategy, strike, direction, status, rejection_reason
        FROM options_signals
        WHERE (timestamp AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-30'
        ORDER BY timestamp ASC
    """)
    print(f"Total signals in DB today (2026-10-30): {len(rows)}")
    for r in rows:
        ts_str = r['ts'].strftime('%H:%M:%S') if r['ts'] else 'N/A'
        print(f"  [{ts_str}] {r['strategy']} | {r['direction']} {r['strike']} | Status: {r['status']} | Reason: {r['rejection_reason']}")
        
    trades = await conn.fetch("""
        SELECT entry_time AT TIME ZONE 'Asia/Kolkata' as entry_ts, exit_time AT TIME ZONE 'Asia/Kolkata' as exit_ts,
               strategy, symbol, entry_price, exit_price, pnl, exit_reason
        FROM options_paper_trades
        WHERE (entry_time AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-30'
        ORDER BY entry_time ASC
    """)
    print(f"\nTotal trades in DB today: {len(trades)}")
    for t in trades:
        e_str = t['entry_ts'].strftime('%H:%M:%S') if t['entry_ts'] else 'N/A'
        x_str = t['exit_ts'].strftime('%H:%M:%S') if t['exit_ts'] else 'N/A'
        print(f"  [{e_str} -> {x_str}] {t['strategy']} {t['symbol']} | Entry: {t['entry_price']} Exit: {t['exit_price']} | PnL: {t['pnl']} | Reason: {t['exit_reason']}")
        
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
