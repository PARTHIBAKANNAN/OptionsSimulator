import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import DataManager, Candle
from src.strategies.engine import create_all_strategies

def main():
    print("=====================================================================================")
    print("                     DEEP ENGINE AUDIT: 5-MINUTE STRATEGY EVALUATION                  ")
    print("=====================================================================================")

    # Create DataManager
    dm = DataManager(window_size=3000, underlying="NIFTY")
    strategies = create_all_strategies()
    five_min_strategies = [s for s in strategies if "_5M_" in s.name]
    
    print(f"\nTotal Registered Strategies: {len(strategies)}")
    print(f"5-Minute (5M ITM) Strategies Count: {len(five_min_strategies)}")
    for s in five_min_strategies:
        print(f" - {s.name} (Underlying: {s.underlying})")

    # Load recent NIFTY historical CSV to simulate 1000 candles
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"\nData file {nifty_csv} not found.")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df_slice = df.tail(1000).reset_index(drop=True)

    print(f"\nSimulating {len(df_slice)} 1-minute candles from {df_slice['Timestamp'].iloc[0]} to {df_slice['Timestamp'].iloc[-1]}...")

    five_m_signals = []
    indicator_snapshots = []

    for row in df_slice.itertuples(index=False):
        candle = Candle(
            timestamp=row.Timestamp,
            open=row.Open,
            high=row.High,
            low=row.Low,
            close=row.Close,
            volume=int(row.Volume)
        )
        dm.replay_candle(candle)
        state = dm.get_state()
        indicators = state.get("indicators", {})

        # Track 5M indicator availability
        if len(indicator_snapshots) < 10 or row.Timestamp.minute % 5 == 0:
            five_m_keys = {k: v for k, v in indicators.items() if "5m" in k or "5M" in k}
            if len(indicator_snapshots) < 5:
                indicator_snapshots.append((row.Timestamp, five_m_keys))

        # Evaluate 5M strategies
        for s in five_min_strategies:
            if s.underlying != "NIFTY":
                continue
            sig = s.evaluate(state)
            if sig:
                five_m_signals.append((row.Timestamp, s.name, sig))

    print(f"\n--- 5M INDICATOR KEYS IN DATA_STATE ---")
    if indicator_snapshots:
        sample_ts, sample_keys = indicator_snapshots[-1]
        print(f"Sample at {sample_ts}:")
        for k, v in sample_keys.items():
            print(f"   {k}: {v}")

    print(f"\n--- 5M STRATEGY SIGNALS GENERATED ---")
    print(f"Total 5M Signals Generated: {len(five_m_signals)}")
    for ts, name, sig in five_m_signals:
        print(f" [{ts}] {name} -> {sig.strike} @ Rs.{sig.entry_price:.2f} ({sig.rationale})")

if __name__ == '__main__':
    main()
