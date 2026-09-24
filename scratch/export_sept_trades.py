import asyncio
import json
import csv
from datetime import datetime, timezone
from pathlib import Path
import zoneinfo
import asyncpg

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

async def main():
    url = 'postgresql://postgres.yovbqhkdzgzduknallbb:Thalamsd%407781@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
    conn = await asyncpg.connect(url, statement_cache_size=0)
    
    rows = await conn.fetch('''
        SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time, 
               exit_price, exit_time, status, exit_reason, realized_pnl, 
               entry_charges, exit_charges, stop_loss, take_profit
        FROM options_positions
        WHERE entry_time >= '2026-09-01 00:00:00+00'
        ORDER BY entry_time ASC
    ''')
    
    print(f"Total trades fetched from Sept 1st to date: {len(rows)}")
    
    trades = []
    unique_symbols = {}
    
    for r in rows:
        entry_utc = r['entry_time']
        exit_utc = r['exit_time']
        entry_ist = entry_utc.astimezone(IST) if entry_utc.tzinfo else entry_utc.replace(tzinfo=timezone.utc).astimezone(IST)
        exit_ist = exit_utc.astimezone(IST) if (exit_utc and exit_utc.tzinfo) else (exit_utc.replace(tzinfo=timezone.utc).astimezone(IST) if exit_utc else None)
        
        pnl = float(r['realized_pnl'] or 0.0)
        chg = float(r['entry_charges'] or 0.0) + float(r['exit_charges'] or 0.0)
        net_pnl = pnl - chg
        
        sym = r['symbol']
        entry_date = entry_ist.strftime('%Y-%m-%d')
        if sym not in unique_symbols:
            unique_symbols[sym] = set()
        unique_symbols[sym].add(entry_date)
        
        trade = {
            "order_id": r['order_id'],
            "strategy": r['strategy'],
            "symbol": sym,
            "qty": r['qty'],
            "lot_size": r['lot_size'],
            "entry_time_ist": entry_ist.strftime('%Y-%m-%d %H:%M:%S'),
            "entry_price": float(r['entry_price']),
            "exit_time_ist": exit_ist.strftime('%Y-%m-%d %H:%M:%S') if exit_ist else "OPEN",
            "exit_price": float(r['exit_price']) if r['exit_price'] else None,
            "exit_reason": r['exit_reason'],
            "stop_loss": float(r['stop_loss']) if r['stop_loss'] else None,
            "take_profit": float(r['take_profit']) if r['take_profit'] else None,
            "gross_pnl": pnl,
            "charges": chg,
            "net_pnl": net_pnl,
            "status": r['status']
        }
        trades.append(trade)
        
    # Save to CSV
    csv_path = Path("data/market_analysis/trades_sept01_to_date.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        writer.writeheader()
        writer.writerows(trades)
        
    # Save to JSON
    json_path = Path("data/market_analysis/trades_sept01_to_date.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(trades, f, indent=2)
        
    print(f"Saved {len(trades)} trades to {csv_path} and {json_path}")
    
    # Analyze by date
    by_date = {}
    for t in trades:
        d = t['entry_time_ist'][:10]
        if d not in by_date:
            by_date[d] = {"trades": 0, "gross_pnl": 0.0, "net_pnl": 0.0, "symbols": set()}
        by_date[d]["trades"] += 1
        by_date[d]["gross_pnl"] += t["gross_pnl"]
        by_date[d]["net_pnl"] += t["net_pnl"]
        by_date[d]["symbols"].add(t["symbol"])
        
    print("\nDaily Breakdown:")
    for d, st in sorted(by_date.items()):
        print(f"  {d}: {st['trades']:2d} trades | Gross: Rs. {st['gross_pnl']:>9.2f} | Net: Rs. {st['net_pnl']:>9.2f} | Unique Contracts: {len(st['symbols'])}")
        
    print(f"\nTotal Unique Contract Keys Traded: {len(unique_symbols)}")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
