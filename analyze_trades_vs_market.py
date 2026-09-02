"""
Clean IST conversion of the 23 paper trades + cross-reference against real
1-min index candles to see what the underlying was actually doing at each
entry/exit timestamp.
"""
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data" / "market_analysis"
IST = ZoneInfo("Asia/Kolkata")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 60)


def load_trades() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "trades_raw.csv")
    df["entry_time_utc"] = pd.to_datetime(df["entry_time"], utc=True)
    df["exit_time_utc"] = pd.to_datetime(df["exit_time"], utc=True)
    df["entry_time_ist"] = df["entry_time_utc"].dt.tz_convert(IST)
    df["exit_time_ist"] = df["exit_time_utc"].dt.tz_convert(IST)
    df["trade_date"] = df["entry_time_ist"].dt.date
    df["index"] = df["symbol"].apply(
        lambda s: "BANKNIFTY" if s.startswith("BANKNIFTY") else ("SENSEX" if s.startswith("SENSEX") else "NIFTY")
    )
    df["direction"] = df["symbol"].apply(lambda s: "CE" if s.endswith("CE") else "PE")
    df["hold_min"] = (df["exit_time_utc"] - df["entry_time_utc"]).dt.total_seconds() / 60.0
    df["is_win"] = df["realized_pnl"] > 0
    return df.sort_values("entry_time_ist").reset_index(drop=True)


def load_candles(index_name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{index_name}_week_candles.csv")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True).dt.tz_convert(IST)
    return df.sort_values("Timestamp").reset_index(drop=True)


def spot_at(candles: pd.DataFrame, ts) -> float | None:
    """Nearest candle close at or before ts."""
    sub = candles[candles["Timestamp"] <= ts]
    if len(sub) == 0:
        return None
    return float(sub.iloc[-1]["Close"])


def main():
    trades = load_trades()
    candles = {idx: load_candles(idx) for idx in ["NIFTY", "SENSEX", "BANKNIFTY"]}

    # Attach spot price at entry and exit, and spot move during the hold
    entry_spot, exit_spot = [], []
    for _, row in trades.iterrows():
        c = candles[row["index"]]
        entry_spot.append(spot_at(c, row["entry_time_ist"]))
        exit_spot.append(spot_at(c, row["exit_time_ist"]))
    trades["spot_entry"] = entry_spot
    trades["spot_exit"] = exit_spot
    trades["spot_move"] = trades["spot_exit"] - trades["spot_entry"]
    trades["spot_move_pct"] = (trades["spot_move"] / trades["spot_entry"] * 100).round(3)
    trades["premium_move_pct"] = ((trades["exit_price"] - trades["entry_price"]) / trades["entry_price"] * 100).round(2)

    # Directionally-correct check: for a PE, spot going DOWN should mean premium UP
    def direction_correct(row):
        if row["direction"] == "PE":
            return row["spot_move"] < 0  # spot fell -> PE should gain
        return row["spot_move"] > 0  # CE -> spot should rise

    trades["market_moved_favorably"] = trades.apply(direction_correct, axis=1)

    out_cols = [
        "trade_date", "entry_time_ist", "exit_time_ist", "hold_min", "index", "direction", "strategy",
        "entry_price", "exit_price", "premium_move_pct", "spot_entry", "spot_exit", "spot_move_pct",
        "market_moved_favorably", "exit_reason", "realized_pnl", "is_win",
    ]
    clean = trades[out_cols].copy()
    clean.to_csv(DATA_DIR / "trades_clean_ist.csv", index=False)

    print("=" * 130)
    print("CLEAN TRADE LOG (IST) WITH SPOT CROSS-REFERENCE")
    print("=" * 130)
    for _, r in clean.iterrows():
        print(
            f"{r['trade_date']} {str(r['entry_time_ist'])[11:19]}-{str(r['exit_time_ist'])[11:19]} "
            f"| {r['index']:9s} {r['direction']} | {r['strategy']:35s} | "
            f"prem {r['entry_price']:7.2f}->{r['exit_price']:7.2f} ({r['premium_move_pct']:+6.2f}%) | "
            f"spot {r['spot_entry']:9.2f}->{r['spot_exit']:9.2f} ({r['spot_move_pct']:+.3f}%) | "
            f"fav={str(r['market_moved_favorably']):5s} | {r['exit_reason']:14s} | pnl={r['realized_pnl']:9.2f}"
        )

    print("\n" + "=" * 130)
    print("SUMMARY: Did the underlying move in the trade's favor?")
    print("=" * 130)
    fav = clean.groupby("market_moved_favorably")["realized_pnl"].agg(["count", "sum", "mean"])
    print(fav)

    print("\nWins where market moved favorably:", len(clean[(clean["is_win"]) & (clean["market_moved_favorably"])]))
    print("Wins where market moved AGAINST:   ", len(clean[(clean["is_win"]) & (~clean["market_moved_favorably"])]))
    print("Losses where market moved favorably (delta was right, still lost):",
          len(clean[(~clean["is_win"]) & (clean["market_moved_favorably"])]))
    print("Losses where market moved against (delta was wrong):",
          len(clean[(~clean["is_win"]) & (~clean["market_moved_favorably"])]))

    print("\n" + "=" * 130)
    print("BY STRATEGY")
    print("=" * 130)
    by_strat = clean.groupby("strategy").agg(
        trades=("realized_pnl", "count"),
        wins=("is_win", "sum"),
        pnl=("realized_pnl", "sum"),
    )
    by_strat["win_rate_%"] = (by_strat["wins"] / by_strat["trades"] * 100).round(1)
    print(by_strat.sort_values("pnl"))

    print("\n" + "=" * 130)
    print("BY DIRECTION / TIMEFRAME (from strategy name)")
    print("=" * 130)
    clean["timeframe"] = clean["strategy"].apply(lambda s: "5M_ITM" if "5M_ITM" in s else ("1M_ATM" if "1M_ATM" in s else "OTHER"))
    print(clean.groupby(["direction", "timeframe"])["realized_pnl"].agg(["count", "sum"]))

    print("\n" + "=" * 130)
    print("BY DAY")
    print("=" * 130)
    print(clean.groupby("trade_date")["realized_pnl"].agg(["count", "sum", "mean"]))

    print(f"\nSaved clean IST trade log to: {DATA_DIR / 'trades_clean_ist.csv'}")


if __name__ == "__main__":
    main()
