import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main():
    print("=========================================================================================================")
    print("                    TODAY'S (2026-09-01) INDIVIDUAL TRADE PERFORMANCE BREAKDOWN                           ")
    print("=========================================================================================================")

    # 1. Fetch via Supabase DB if available
    try:
        from backend.app.config import WebConfig
        import asyncpg, asyncio
        config = WebConfig.load()
        if config.supabase_db_url:
            async def fetch_db_trades():
                conn = await asyncpg.connect(config.supabase_db_url, statement_cache_size=0)
                signals = await conn.fetch("SELECT * FROM options_signals WHERE timestamp >= '2026-09-01' ORDER BY timestamp ASC")
                await conn.close()
                return signals

            rows = asyncio.run(fetch_db_trades())
            print(f"\nFound {len(rows)} trades executed in Supabase Database today:\n")
            print(f"{'#':<3} | {'Entry Time':<16} | {'Strategy Name':<35} | {'Strike':<15} | {'Entry':<7} | {'Exit':<7} | {'Exit Reason':<12} | {'Net P&L (Rs)'}")
            print("-" * 125)
            for idx, r in enumerate(rows, 1):
                pnl = r['realized_pnl'] if r.get('realized_pnl') is not None else 0.0
                entry_p = f"{r['entry_price']:.2f}" if r.get('entry_price') is not None else "—"
                exit_p = f"{r['exit_price']:.2f}" if r.get('exit_price') is not None else "—"
                reason = r.get('exit_reason') or r.get('status') or "—"
                print(f"{idx:<3} | {str(r['timestamp'])[:16]:<16} | {r['strategy']:<35} | {r['strike']:<15} | {entry_p:<7} | {exit_p:<7} | {reason:<12} | Rs.{pnl:>8,.2f}")
    except Exception as e:
        print(f"Error checking Supabase DB: {e}")

    # 2. Check local logs/trades.log for 2026-09-01
    log_file = PROJECT_ROOT / "logs" / "trades.log"
    if log_file.exists():
        lines = [line.strip() for line in log_file.read_text().splitlines() if "2026-09-01" in line]
        print(f"\nFound {len(lines)} trade log entries in logs/trades.log today:")
        for line in lines[-25:]:
            print(" ", line)

if __name__ == '__main__':
    main()
