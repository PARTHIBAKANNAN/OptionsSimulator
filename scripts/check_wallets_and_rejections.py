import asyncio
import asyncpg
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def check():
    from backend.app.config import WebConfig
    config = WebConfig.load()
    url = config.supabase_db_url
    if not url:
        print("No supabase_db_url configured.")
        return
    conn = await asyncpg.connect(url, statement_cache_size=0)
    
    # Query candle history
    candles = await conn.fetch("""
        SELECT underlying, bucket_minute, open, high, low, close, volume
        FROM options_candle_history
        WHERE bucket_date = '2026-10-28'
        ORDER BY bucket_minute ASC
    """)
    print(f"\n--- CANDLE HISTORY TODAY ({len(candles)} candles) ---")
    
    # Let's inspect candles around key trade times:
    # 09:25 to 10:40
    # 13:00 to 14:40
    def min_to_hhmm(m):
        return f"{m // 60:02d}:{m % 60:02d}"

    print("\n--- NIFTY CANDLES (12:50 to 14:40) ---")
    nifty_midday = [c for c in candles if c['underlying'] == 'NIFTY' and (12*60+50) <= c['bucket_minute'] <= (14*60+45)]
    for c in nifty_midday[::5]: # every 5 mins
        hhmm = min_to_hhmm(c['bucket_minute'])
        print(f"  {hhmm} | O:{c['open']:.1f} H:{c['high']:.1f} L:{c['low']:.1f} C:{c['close']:.1f} | Vol:{c['volume']}")

    print("\n--- SENSEX CANDLES (13:15 to 13:35) ---")
    sensex_midday = [c for c in candles if c['underlying'] == 'SENSEX' and (13*60+15) <= c['bucket_minute'] <= (13*60+35)]
    for c in sensex_midday:
        hhmm = min_to_hhmm(c['bucket_minute'])
        print(f"  {hhmm} | O:{c['open']:.1f} H:{c['high']:.1f} L:{c['low']:.1f} C:{c['close']:.1f} | Vol:{c['volume']}")
    
    # Query options_wallets
    wallets = await conn.fetch("SELECT * FROM options_wallets ORDER BY balance ASC")
    print(f"\n--- OPTIONS_WALLETS ({len(wallets)} rows) ---")
    for w in wallets:
        bal = float(w['balance'] or 0.0)
        alloc = float(w.get('allocated_capital') or 50000.0)
        print(f"  {w['strategy']:<35} | Balance: Rs.{bal:,.2f} | Allocated: Rs.{alloc:,.2f}")

    # Check distinct status in options_signals for today
    sigs = await conn.fetch("""
        SELECT status, count(*) 
        FROM options_signals 
        WHERE (timestamp AT TIME ZONE 'Asia/Kolkata')::date = '2026-10-28'
        GROUP BY status
    """)
    print("\n--- TODAY'S SIGNAL STATUS COUNTS ---")
    for s in sigs:
        print(f"  Status: {s['status']} | Count: {s['count']}")
        
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
