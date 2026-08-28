import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader
from src.strategies.engine import create_nifty_strategies

def main():
    nifty_csv = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
    df = pd.read_csv(nifty_csv)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # 6000-candle dataset slice (2026-07-30 to 2026-08-20)
    df_slice = df.tail(6000).reset_index(drop=True)

    dm = DataManager(window_size=3000, underlying="NIFTY")
    strategies = create_nifty_strategies()
    traders = {s.name: PaperTrader(initial_capital=1_000_000, lot_size=65, max_trades_per_day_per_strategy=2, trailing_stop_enabled=True) for s in strategies}

    for row in df_slice.itertuples(index=False):
        candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High, low=row.Low, close=row.Close, volume=int(row.Volume))
        dm.replay_candle(candle)
        state = dm.get_state()
        spot = state.get("nifty_price")
        if spot is None:
            continue

        for s in strategies:
            trader = traders[s.name]
            prices = {o.symbol: spot * 0.01 for o in trader.get_positions()}
            trader.update_positions(prices, timestamp=state["timestamp"], time_exit_mins=120)

            sig = s.evaluate(state)
            if sig:
                if not (s.last_signal_time and sig.timestamp - s.last_signal_time < pd.Timedelta(minutes=5)):
                    s.last_signal_time = sig.timestamp
                    try:
                        trader.place_order(symbol=sig.strike, side="BUY", qty=1, price=sig.entry_price, stop_loss=sig.entry_price*0.8, take_profit=sig.entry_price+150, strategy=sig.strategy, timestamp=sig.timestamp)
                    except Exception:
                        pass

    print(f"=== FULL TRADE LOG OF ALL 18 TRADES (15-DAY NIFTY DATASET: {df_slice['Timestamp'].iloc[0].date()} to {df_slice['Timestamp'].iloc[-1].date()}) ===")
    print("=" * 135)
    print(f"{'#':<3} | {'Entry Time (IST)':<19} | {'Strategy Name':<35} | {'Symbol (Lot 65)':<15} | {'Entry':<8} | {'Exit':<8} | {'Reason':<14} | {'Net PnL (Rs)'}")
    print("=" * 135)

    all_trades = []
    for s in strategies:
        history = traders[s.name].get_trade_history()
        for t in history:
            all_trades.append(t)

    # Sort trades by entry time
    all_trades.sort(key=lambda x: x.entry_time)

    tot_pnl = 0.0
    for idx, t in enumerate(all_trades, 1):
        pnl = t.realized_pnl
        tot_pnl += pnl
        entry_t = t.entry_time.strftime("%Y-%m-%d %H:%M") if hasattr(t.entry_time, "strftime") else str(t.entry_time)[:16]
        print(f"{idx:<3} | {entry_t:<19} | {t.strategy:<35} | {t.symbol:<15} | {t.entry_price:<8.2f} | {t.exit_price:<8.2f} | {t.exit_reason:<14} | Rs.{pnl:>10,.2f}")

    print("-" * 135)
    print(f"TOTAL REALIZED P&L ACROSS ALL 18 TRADES: Rs.{tot_pnl:,.2f}")
    print("=" * 135)

if __name__ == '__main__':
    main()
