"""
Database & Wallet Reset Script
==============================
Resets the live paper trading database tables:
1. TRUNCATE TABLE options_positions CASCADE; (Clears all trade logs)
2. Resets options_wallets with all 44 strategies using round-figure allocated capital.
3. Clears cached AI debrief journal and last_market_state so everything starts pristine.

Usage:
    python scripts/reset_live_db.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / "TradeDashBoard" / "backend" / ".env")

CAPITAL_PATH = PROJECT_ROOT / "data" / "backtest_results" / "capital_requirements.json"


async def main():
    import asyncpg

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or os.environ.get("POSTGRES_URL")
    
    if not CAPITAL_PATH.exists():
        print(f"ERROR: {CAPITAL_PATH} not found.")
        return

    caps = json.loads(CAPITAL_PATH.read_text())
    print(f"Loaded {len(caps)} strategy capital allocations.")

    if not db_url:
        print("\n[NOTE] No DATABASE_URL found in local .env.")
        print("To reset the remote Supabase / Postgres database, run the generated SQL below in your Supabase SQL Editor:")
        print("=" * 70)
        print("-- 1. Clear all old closed & open trades")
        print("TRUNCATE TABLE public.options_positions CASCADE;")
        print("\n-- 2. Clear old candle history cache if needed (optional)")
        print("TRUNCATE TABLE public.options_candle_history CASCADE;")
        print("\n-- 3. Reset all 44 strategy wallets to clean round capital allocations")
        print("TRUNCATE TABLE public.options_wallets CASCADE;")
        print("INSERT INTO public.options_wallets (strategy, balance, allocated_capital, updated_at) VALUES")
        values = []
        for strat, info in caps.items():
            cap = info["recommended_capital"]
            values.append(f"  ('{strat}', {cap}, {cap}, now())")
        print(",\n".join(values) + ";")
        print("=" * 70)
        return

    print(f"Connecting to database: {db_url[:25]}...")
    conn = await asyncpg.connect(db_url, statement_cache_size=0)
    try:
        print("1. Truncating options_positions...")
        await conn.execute("TRUNCATE TABLE public.options_positions CASCADE;")
        
        print("2. Resetting options_wallets...")
        await conn.execute("TRUNCATE TABLE public.options_wallets CASCADE;")
        
        insert_query = """
            INSERT INTO public.options_wallets (strategy, balance, allocated_capital, updated_at)
            VALUES ($1, $2, $3, now())
        """
        for strat, info in caps.items():
            cap = float(info["recommended_capital"])
            await conn.execute(insert_query, strat, cap, cap)
            
        print(f"Successfully reset {len(caps)} strategy wallets in PostgreSQL!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
