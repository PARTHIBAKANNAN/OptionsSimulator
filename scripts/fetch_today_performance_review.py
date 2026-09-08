import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    print("=========================================================================================================")
    print("                             TODAY'S (2026-08-31) FULL QUANT PERFORMANCE DEBRIEF                         ")
    print("=========================================================================================================")

    # Check last market state or logs
    try:
        from backend.app.config import WebConfig
        import asyncpg
        config = WebConfig.load()
        if config.supabase_db_url:
            async def fetch_db_trades():
                conn = await asyncpg.connect(config.supabase_db_url, statement_cache_size=0)
                tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                print("Available DB tables:", [t['table_name'] for t in tables])
                signals = await conn.fetch("SELECT * FROM options_signals ORDER BY timestamp DESC LIMIT 20")
                await conn.close()
                return signals

            import asyncio
            rows = asyncio.run(fetch_db_trades())
            print(f"\nRecent Signals/Trades in Database (total {len(rows)}):\n")
            print(f"{'#':<3} | {'Entry Time':<19} | {'Strategy':<35} | {'Strike':<15} | {'Status':<12} | {'Entry':<8} | {'Exit':<8} | {'Reason':<14}")
            print("-" * 125)
            for idx, r in enumerate(rows, 1):
                entry_p = f"{r['entry_price']:.2f}" if r.get('entry_price') is not None else "—"
                exit_p = f"{r['exit_price']:.2f}" if r.get('exit_price') is not None else "—"
                reason = r.get('exit_reason') or r.get('status') or "—"
                print(f"{idx:<3} | {str(r['timestamp'])[:16]:<19} | {r['strategy']:<35} | {r['strike']:<15} | {r['status']:<12} | {entry_p:<8} | {exit_p:<8} | {reason:<14}")
    except Exception as e:
        print(f"Error fetching DB trades: {e}")

if __name__ == '__main__':
    main()
