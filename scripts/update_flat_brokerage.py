import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg
from src.utils.charges import calculate_charges

async def main():
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    rows = await conn.fetch("SELECT order_id, symbol, qty, lot_size, entry_price, exit_price FROM options_positions WHERE status = 'CLOSED' AND exit_time::date = '2026-08-24'")
    
    tot_charges = 0.0
    for r in rows:
        oid = r['order_id']
        entry_val = float(r['entry_price']) * r['qty'] * r['lot_size']
        exit_val = float(r['exit_price']) * r['qty'] * r['lot_size'] if r['exit_price'] else 0.0
        
        c_buy = calculate_charges(entry_val, 'BUY')
        c_sell = calculate_charges(exit_val, 'SELL') if r['exit_price'] else None
        
        chg_buy = c_buy.total
        chg_sell = c_sell.total if c_sell else 0.0
        tot_charges += (chg_buy + chg_sell)
        
        query = "UPDATE options_positions SET entry_charges = $1, exit_charges = $2 WHERE order_id = $3"
        await conn.execute(query, chg_buy, chg_sell, oid)
    
    print(f"[update_flat_brokerage] Successfully updated {len(rows)} trades in Supabase! Total Deductions = Rs.{tot_charges:.2f}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
