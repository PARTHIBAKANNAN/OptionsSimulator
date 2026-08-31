import os
import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.supabase_client import get_supabase_client

def main():
    sp = get_supabase_client()
    if not sp:
        print("Supabase client not configured.")
        return

    # Fetch OPEN signals/positions
    res = sp.table("options_signals").select("*").eq("status", "SIGNAL_ENTERED").execute()
    open_signals = res.data or []
    print(f"Found {len(open_signals)} OPEN signals in Supabase database:")
    for s in open_signals:
        print(f" - ID: {s['id']} | Strategy: {s['strategy']} | Strike: {s['strike']} | Entry: Rs.{s['entry_price']}")

    if not open_signals:
        print("No open signals found in DB.")
        return

    for s in open_signals:
        # Close position at market close price (479.15 as seen in live screen)
        exit_price = 479.15
        sp.table("options_signals").update({
            "status": "CLOSED",
            "exit_price": exit_price,
            "exit_reason": "EOD_SQUARE_OFF",
        }).eq("id", s["id"]).execute()
        print(f"Successfully closed signal {s['id']} in DB at Rs.{exit_price} (EOD_SQUARE_OFF).")

if __name__ == "__main__":
    main()
