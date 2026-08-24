"""
Data Migration Script: Recalculates today's SENSEX trades in Postgres and updates lot_size from 65 to 20.
Run via: python scripts/recalculate_sensex_trades.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
from src.utils.charges import calculate_charges


async def main():
    import asyncpg

    # Read DB connection params from .env or environment
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT.parent / "TradeDashBoard" / "backend" / ".env")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[recalculate_sensex_trades] DATABASE_URL not set in environment or .env file.")
        print("[recalculate_sensex_trades] Checking local json files...")
        pos_file = PROJECT_ROOT / "data" / "positions.json"
        if pos_file.exists():
            import json
            data = json.loads(pos_file.read_text())
            updated = 0
            for item in data:
                if str(item.get("symbol", "")).startswith("SENSEX") and item.get("lot_size") == 65:
                    item["lot_size"] = 20
                    updated += 1
            if updated:
                pos_file.write_text(json.dumps(data, indent=2))
                print(f"[recalculate_sensex_trades] Updated {updated} SENSEX records in data/positions.json")
        return

    print(f"[recalculate_sensex_trades] Connecting to Database...")
    conn = await asyncpg.connect(database_url)

    today = datetime.now(IST).date()
    print(f"[recalculate_sensex_trades] Checking today's SENSEX trades ({today})...")

    # Fetch today's SENSEX trades
    rows = await conn.fetch(
        """SELECT order_id, strategy, symbol, qty, lot_size, entry_price, entry_time,
                  exit_price, exit_time, realized_pnl, entry_charges, exit_charges
           FROM options_positions
           WHERE symbol LIKE 'SENSEX%' AND entry_time::date = $1""",
        today
    )

    if not rows:
        print("[recalculate_sensex_trades] No SENSEX trades found for today.")
        await conn.close()
        return

    print(f"[recalculate_sensex_trades] Found {len(rows)} SENSEX trades to inspect.")

    updated_count = 0
    wallet_adjustments = {}

    for row in rows:
        order_id = row["order_id"]
        strategy = row["strategy"]
        qty = row["qty"] or 1
        entry_price = float(row["entry_price"]) if row["entry_price"] is not None else 0.0
        exit_price = float(row["exit_price"]) if row["exit_price"] is not None else None

        # Re-calc for lot_size = 20
        new_lot_size = 20
        entry_val = entry_price * qty * new_lot_size
        new_entry_charges = round(calculate_charges(entry_val, "BUY").total, 2)

        new_exit_charges = 0.0
        new_realized_pnl = None

        if exit_price is not None:
            exit_val = exit_price * qty * new_lot_size
            new_exit_charges = round(calculate_charges(exit_val, "SELL").total, 2)
            new_realized_pnl = round((exit_price - entry_price) * qty * new_lot_size, 2)

        print(f"  Order {order_id[:8]}... ({strategy}): Old lot_size={row['lot_size']} -> New lot_size={new_lot_size}")
        print(f"    Old P&L={row['realized_pnl']} -> New P&L={new_realized_pnl}")

        await conn.execute(
            """UPDATE options_positions
               SET lot_size = $2,
                   entry_charges = $3,
                   exit_charges = $4,
                   realized_pnl = $5
               WHERE order_id = $1""",
            order_id, new_lot_size, new_entry_charges, new_exit_charges, new_realized_pnl
        )
        updated_count += 1

    print(f"[recalculate_sensex_trades] Successfully updated {updated_count} SENSEX trades in database.")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
