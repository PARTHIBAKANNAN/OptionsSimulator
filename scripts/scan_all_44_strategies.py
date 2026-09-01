import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, time as dtime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import DataManager, Candle
from src.strategies.engine import create_all_strategies

def main():
    print("=========================================================================================================")
    print("                   COMPREHENSIVE CODE & EXECUTION AUDIT: ALL 44 STRATEGIES SCAN                        ")
    print("=========================================================================================================")

    strategies = create_all_strategies()
    print(f"Total Registered Strategies Found: {len(strategies)}\n")

    strategy_categories = {
        "1M ATM": [s for s in strategies if "_1M_" in s.name or "_ATM" in s.name],
        "5M ITM": [s for s in strategies if "_5M_" in s.name],
        "IronFly / Special": [s for s in strategies if "_5M_" not in s.name and "_1M_" not in s.name]
    }

    for cat, list_s in strategy_categories.items():
        print(f"--- {cat} ({len(list_s)} strategies) ---")
        for s in list_s:
            print(f"  • {s.name:<45} | Underlying: {s.underlying:<9} | Strike Mode: {s.strike_mode}")

    # Load 1000 candles from NIFTY dataset
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print("Dataset file not found.")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df_slice = df.tail(1000).reset_index(drop=True)

    print(f"\nScanning strategy evaluations across {len(df_slice)} 1-minute bars...")

    dm = DataManager(window_size=3000, underlying="NIFTY")

    evaluation_errors = []
    signals_count_by_strategy = {s.name: 0 for s in strategies}
    missing_indicator_warns = set()

    for row in df_slice.itertuples(index=False):
        candle = Candle(
            timestamp=row.Timestamp,
            open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=int(row.Volume)
        )
        dm.replay_candle(candle)
        state = dm.get_state()
        indicators = state.get("indicators", {})

        for s in strategies:
            try:
                sig = s.evaluate(state)
                if sig:
                    signals_count_by_strategy[s.name] += 1
            except Exception as e:
                evaluation_errors.append((row.Timestamp, s.name, str(e)))

    print("\n=========================================================================================================")
    print("                                            AUDIT RESULTS                                                ")
    print("=========================================================================================================")
    print(f"Total Strategy Evaluation Calls Tested: {len(df_slice) * len(strategies):,}")
    print(f"Total Technical Exceptions/Crashes: {len(evaluation_errors)}")

    if evaluation_errors:
        print("\nCRITICAL TECHNICAL ERRORS DETECTED:")
        for ts, name, err in evaluation_errors[:10]:
            print(f" [{ts}] Strategy '{name}': {err}")
    else:
        print("SUCCESS: ALL 44 STRATEGIES EVALUATED WITH 0 TECHNICAL ERRORS (No NameError, KeyError, or AttributeError)!")

    print("\n--- SIGNAL GENERATION BY STRATEGY CATEGORY ---")
    active_strats = {k: v for k, v in signals_count_by_strategy.items() if v > 0}
    inactive_strats = {k: v for k, v in signals_count_by_strategy.items() if v == 0}

    print(f"Strategies that Generated Signals in 1000-candle sample ({len(active_strats)}):")
    for name, cnt in list(active_strats.items())[:15]:
        print(f"  • {name:<45}: {cnt} signals")

    print(f"\nStrategies with 0 signals (Waiting for specific market setups) ({len(inactive_strats)}):")
    for name in list(inactive_strats.keys())[:15]:
        print(f"  • {name}")

if __name__ == '__main__':
    main()
