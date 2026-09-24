import asyncio
import sys
import json
from datetime import datetime
from pathlib import Path
import asyncpg

async def analyze():
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    
    rows = await conn.fetch('''
        SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time, exit_price, exit_time, status, exit_reason, realized_pnl, entry_charges, exit_charges
        FROM options_positions
        WHERE (exit_time::date = '2026-09-16' OR entry_time::date = '2026-09-16')
        ORDER BY entry_time ASC
    ''')
    
    print(f"=== TOTAL TRADES ON 2026-09-16: {len(rows)} ===")
    
    app_gross_pnl = 0.0
    for r in rows:
        pnl = float(r['realized_pnl'] or 0)
        app_gross_pnl += pnl
        entry_t = r['entry_time'].strftime('%H:%M:%S') if r['entry_time'] else 'N/A'
        exit_t = r['exit_time'].strftime('%H:%M:%S') if r['exit_time'] else 'OPEN'
        reason = r['exit_reason'] or 'N/A'
        print(f"{r['strategy']} | {r['symbol']} (lot {r['lot_size']}) | In: {entry_t} @ Rs.{r['entry_price']:.2f} | Out: {exit_t} @ Rs.{r['exit_price']:.2f} | Reason: {reason} | PnL: Rs.{pnl:.2f}")

    print(f"\nApp Total Recorded Gross PnL (Synthetic/Distorted): Rs. {app_gross_pnl:.2f}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(analyze())
