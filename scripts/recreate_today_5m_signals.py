import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import DataManager, Candle
from src.strategies.engine import create_all_strategies

def main():
    print("=========================================================================================================")
    print("                TODAY'S (2026-08-31) 5-MINUTE STRATEGY RECREATED SIGNAL AUDIT                            ")
    print("=========================================================================================================")

    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    if not nifty_csv.exists():
        print(f"Data file {nifty_csv} not found.")
        return

    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # Filter for 2026-08-31 candles if present or recent slice
    today_df = df[df["Timestamp"].dt.date == pd.to_datetime("2026-08-20").date()].reset_index(drop=True)
    if today_df.empty:
        today_df = df.tail(375).reset_index(drop=True)  # Full 1-day candle slice (375 mins)

    print(f"Dataset window: {len(today_df)} candles ({today_df['Timestamp'].iloc[0]} to {today_df['Timestamp'].iloc[-1]})\n")

    dm = DataManager(window_size=3000, underlying="NIFTY")
    strategies = create_all_strategies()
    five_m_strategies = [s for s in strategies if "_5M_" in s.name]

    signals_fired = []

    for row in today_df.itertuples(index=False):
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
        spot = state.get("nifty_price")
        if spot is None:
            continue

        for s in five_m_strategies:
            if s.underlying != "NIFTY":
                continue
            sig = s.evaluate(state)
            if sig:
                # Check 5-min cooldown
                if not (s.last_signal_time and sig.timestamp - s.last_signal_time < pd.Timedelta(minutes=5)):
                    s.last_signal_time = sig.timestamp
                    signals_fired.append(sig)

    print("=" * 125)
    print(f"{'#':<3} | {'Signal Time (IST)':<19} | {'Strategy Name':<35} | {'Strike Symbol':<16} | {'Entry Price':<11} | {'Rationale'}")
    print("=" * 125)
    if not signals_fired:
        print("No 5-minute signals were generated for this trading session.")
    else:
        for idx, sig in enumerate(signals_fired, 1):
            t_str = sig.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(sig.timestamp, "strftime") else str(sig.timestamp)[:16]
            print(f"{idx:<3} | {t_str:<19} | {sig.strategy:<35} | {sig.strike:<16} | Rs.{sig.entry_price:<8.2f} | {sig.rationale}")
    print("=" * 125)
    print(f"TOTAL 5-MINUTE SIGNALS THAT WOULD HAVE FIRED TODAY: {len(signals_fired)}")

if __name__ == '__main__':
    main()
