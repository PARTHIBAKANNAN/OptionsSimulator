"""One-off: backtest IronFlyHedge (expiry-day-only 4-leg spread -- doesn't go through
BacktestEngine._backtest_single() like a directional BaseStrategy) against the full historical
CSV, mirroring BacktestEngine._backtest_iron_fly()."""
import json
import time
from pathlib import Path

import pandas as pd

from src.backtester.report import build_report
from src.config import Config
from src.data_manager import Candle, DataManager
from src.strategies.iron_fly_hedge import IronFlyHedge

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"


def main() -> None:
    config = Config.load()
    df = pd.read_csv(DATA_PATH, parse_dates=["Timestamp"])

    sizing = config.risk_params.get("position_sizing", {})
    iron_fly_cfg = config.risk_params.get("iron_fly", {})
    from datetime import time as dtime

    def parse_hhmm(value):
        h, m = value.split(":")
        return dtime(int(h), int(m))

    iron_fly = IronFlyHedge(
        wing_width_pts=iron_fly_cfg.get("wing_width_pts", 200),
        strike_step=iron_fly_cfg.get("strike_step", 100),
        entry_time=parse_hhmm(iron_fly_cfg.get("entry_time", "09:45")),
        force_exit_time=parse_hhmm(iron_fly_cfg.get("force_exit_time", "15:15")),
        profit_target_pct_of_credit=iron_fly_cfg.get("profit_target_pct_of_credit", 50.0),
        stop_loss_pct_of_max_loss=iron_fly_cfg.get("stop_loss_pct_of_max_loss", 50.0),
        max_vol_regime_ratio_to_enter=iron_fly_cfg.get("max_vol_regime_ratio_to_enter"),
        lot_size=sizing.get("lot_size", 65),
        qty=sizing.get("qty_per_signal", 1),
    )

    t0 = time.time()
    data_manager = DataManager(window_size=3000)
    closed = []
    for row in df.itertuples(index=False):
        candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                         low=row.Low, close=row.Close, volume=int(row.Volume))
        data_manager.replay_candle(candle)
        state = data_manager.get_state()
        if state["nifty_price"] is None:
            continue
        if iron_fly.position is None:
            iron_fly.maybe_enter(state)
        else:
            position = iron_fly.check_exit(state)
            if position is not None:
                closed.append(position)

    r = build_report("IRON_FLY_HEDGE", "HEDGE", closed, 1_000_000)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "IRON_FLY_HEDGE_history.json"
    out_path.write_text(json.dumps([
        {"entry_time": str(p.entry_time), "exit_time": str(p.exit_time),
         "realized_pnl": p.realized_pnl, "exit_reason": p.exit_reason}
        for p in closed
    ], indent=2))

    print(f"[IRON_FLY_HEDGE] ({time.time() - t0:.1f}s) trades={r.total_trades} "
          f"win_rate={r.win_rate}% profit_factor={r.profit_factor} total_pnl={r.total_pnl} "
          f"max_dd={r.max_drawdown} max_dd_pct={r.max_drawdown_pct}%", flush=True)


if __name__ == "__main__":
    main()