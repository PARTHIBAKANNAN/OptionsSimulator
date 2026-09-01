import sys
from pathlib import Path
import pandas as pd
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import DataManager, Candle
from src.strategies.engine import create_all_strategies

def main():
    print("=========================================================================================================")
    print("                      TODAY'S (2026-09-01) LIVE TRADE & 5M STRATEGY RE-AUDIT                             ")
    print("=========================================================================================================")

    # 1. Fetch today's executed trades from Supabase if DB available
    try:
        from backend.app.config import WebConfig
        import asyncpg, asyncio
        config = WebConfig.load()
        if config.supabase_db_url:
            async def get_trades():
                conn = await asyncpg.connect(config.supabase_db_url, statement_cache_size=0)
                signals = await conn.fetch("SELECT * FROM options_signals WHERE timestamp >= '2026-09-01' ORDER BY timestamp ASC")
                await conn.close()
                return signals
            trades = asyncio.run(get_trades())
            print(f"\n--- TODAY'S EXECUTION LOG IN SUPABASE DB ({len(trades)} trades) ---")
            for t in trades:
                print(f"[{str(t['timestamp'])[:16]}] {t['strategy']:<35} | {t['strike']:<15} | Status: {t['status']:<10} | Entry: {t.get('entry_price')}")
        else:
            print("Supabase DB URL not set locally.")
    except Exception as e:
        print(f"Error fetching DB: {e}")

    # 2. Test 5M strategy generation on today's candle dataset
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # Take recent 375 candles (1 day slice)
    today_df = df.tail(375).reset_index(drop=True)
    print(f"\nSimulating 5M strategy triggers across {len(today_df)} candles ({today_df['Timestamp'].iloc[0]} to {today_df['Timestamp'].iloc[-1]})...")

    dm = DataManager(window_size=3000, underlying="NIFTY")
    strategies = create_all_strategies()
    five_m_strategies = [s for s in strategies if "_5M_" in s.name]

    signals_fired = []
    for row in today_df.itertuples(index=False):
        candle = Candle(
            timestamp=row.Timestamp,
            open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=int(row.Volume)
        )
        dm.replay_candle(candle)
        state = dm.get_state()
        if state.get("nifty_price") is None:
            continue

        for s in five_m_strategies:
            if s.underlying != "NIFTY":
                continue
            sig = s.evaluate(state)
            if sig:
                signals_fired.append(sig)

    print(f"\n--- 5M SIGNALS FIRED ({len(signals_fired)}) ---")
    for idx, sig in enumerate(signals_fired, 1):
        print(f"{idx:<2}. [{str(sig.timestamp)[:16]}] {sig.strategy:<35} -> {sig.strike} @ Rs.{sig.entry_price:.2f} ({sig.rationale})")

if __name__ == '__main__':
    main()
