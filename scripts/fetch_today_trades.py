import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

async def main():
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    
    rows = await conn.fetch("""
        SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time, exit_price, exit_time, status, exit_reason, realized_pnl, entry_charges, exit_charges
        FROM options_positions
        WHERE exit_time::date = '2026-08-27' OR entry_time::date = '2026-08-27'
        ORDER BY entry_time ASC
    """)
    
    print(f"=== TODAY (2026-08-27) TRADES COUNT: {len(rows)} ===")
    tot_gross = 0.0
    tot_chg = 0.0
    wins = 0
    losses = 0
    breakevens = 0
    
    for r in rows:
        pnl = float(r['realized_pnl'] or 0)
        chg = float(r['entry_charges'] or 0) + float(r['exit_charges'] or 0)
        net = pnl - chg
        tot_gross += pnl
        tot_chg += chg
        
        if pnl > 10:
            wins += 1
        elif pnl < -10:
            losses += 1
        else:
            breakevens += 1
            
        entry_t = r['entry_time'].strftime('%H:%M:%S') if r['entry_time'] else 'N/A'
        exit_t = r['exit_time'].strftime('%H:%M:%S') if r['exit_time'] else 'OPEN'
        reason = r['exit_reason'] or 'N/A'
        print(f"{r['order_id'][:8]} | {r['strategy']} | {r['symbol']} (lot {r['lot_size']}) | In:{entry_t} @ {r['entry_price']:.2f} | Out:{exit_t} @ {r['exit_price']:.2f} | {reason} | Gross: Rs.{pnl:.2f} | Chg: Rs.{chg:.2f} | Net: Rs.{net:.2f}")

    print("\n--- PERFORMANCE SUMMARY ---")
    print(f"Total Trades: {len(rows)} (Wins: {wins}, Losses: {losses}, Breakevens/TSL: {breakevens})")
    print(f"Total Gross P&L: Rs. {tot_gross:.2f}")
    print(f"Total Charges: Rs. {tot_chg:.2f}")
    print(f"Total Net P&L: Rs. {tot_gross - tot_chg:.2f}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
