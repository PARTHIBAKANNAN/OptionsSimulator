import asyncio
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncpg

IST = ZoneInfo("Asia/Kolkata")

async def main():
    from backend.app.config import WebConfig
    config = WebConfig.load()
    url = config.supabase_db_url
    if not url:
        print("No supabase_db_url configured.")
        return
    conn = await asyncpg.connect(url, statement_cache_size=0)

    rows = await conn.fetch("""
        SELECT *
        FROM options_positions
        WHERE (entry_time AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-28'
           OR (exit_time AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-28'
        ORDER BY entry_time ASC
    """)

    print(f"=========================================================================================")
    print(f"                      TODAY'S (2026-10-28) LIVE TRADES AUDIT ({len(rows)} Trades)")
    print(f"=========================================================================================\n")

    tot_gross = 0.0
    tot_chg = 0.0
    wins = 0
    losses = 0
    sl_hits = 0
    tsl_exits = 0
    tp_hits = 0
    manual_exits = 0
    other_exits = 0

    for i, r in enumerate(rows, 1):
        pnl = float(r['realized_pnl'] or 0.0)
        chg = float(r['entry_charges'] or 0.0) + float(r['exit_charges'] or 0.0)
        net = pnl - chg
        tot_gross += pnl
        tot_chg += chg

        reason = r['exit_reason'] or 'OPEN'
        if reason == 'STOP_LOSS':
            sl_hits += 1
            losses += 1
        elif reason == 'TRAILING_STOP':
            tsl_exits += 1
            if net > 0:
                wins += 1
            else:
                losses += 1
        elif reason == 'TAKE_PROFIT':
            tp_hits += 1
            wins += 1
        elif 'MANUAL' in reason:
            manual_exits += 1
            if net > 0: wins += 1
            else: losses += 1
        else:
            other_exits += 1
            if net > 0: wins += 1
            else: losses += 1

        ent_ist = r['entry_time'].astimezone(IST).strftime('%H:%M:%S') if r['entry_time'] else 'N/A'
        ext_ist = r['exit_time'].astimezone(IST).strftime('%H:%M:%S') if r['exit_time'] else 'OPEN'
        peak = float(r['peak_price']) if ('peak_price' in r and r['peak_price'] is not None) else 0.0
        ep = float(r['entry_price'] or 0.0)
        xp = float(r['exit_price'] or 0.0)
        pts_diff = xp - ep

        print(f"[{i:02d}] {r['order_id'][:8]} | {r['strategy']:<35} | {r['symbol']:<18}")
        print(f"     Time: In {ent_ist} -> Out {ext_ist} | Reason: {reason}")
        print(f"     Price: Entry Rs.{ep:.2f} -> Exit Rs.{xp:.2f} (Pts: {pts_diff:+.2f}) | Peak: Rs.{peak:.2f} (+{peak - ep:.2f} pts)")
        print(f"     P&L: Gross Rs.{pnl:+.2f} | Chg Rs.{chg:.2f} | Net Rs.{net:+.2f}\n")

    print(f"-----------------------------------------------------------------------------------------")
    print(f"SUMMARY METRICS:")
    print(f"Total Trades: {len(rows)}")
    print(f"Exit Breakdown: SL Hits: {sl_hits} | TSL Exits: {tsl_exits} | TP Hits: {tp_hits} | Manual: {manual_exits} | Other: {other_exits}")
    print(f"Win/Loss: Wins: {wins} | Losses: {losses} | Win Rate: {(wins/len(rows)*100) if rows else 0:.1f}%")
    print(f"Financials: Gross P&L: Rs.{tot_gross:+.2f} | Total Charges: Rs.{tot_chg:.2f} | Net Realized P&L: Rs.{tot_gross - tot_chg:+.2f}")
    print(f"-----------------------------------------------------------------------------------------")

    # Also inspect options_signals
    signals = await conn.fetch("""
        SELECT *
        FROM options_signals
        WHERE (timestamp AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-28'
        ORDER BY timestamp ASC
    """)
    print(f"\n=========================================================================================")
    print(f"                      TODAY'S SIGNALS GENERATION LOG ({len(signals)} Signals)")
    print(f"=========================================================================================")
    for s in signals:
        ts = s['timestamp'].astimezone(IST).strftime('%H:%M:%S') if s['timestamp'] else 'N/A'
        rej = s.get('rejection_reason') or ''
        status = s['status']
        print(f"[{ts}] {s['strategy']:<35} | {s['strike']:<18} | Status: {status:<10} | {rej}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
