"""One-off: aggregates every data/backtest_results/{NAME}_history.json (written independently by
backtest_one_strategy.py / backtest_sensex.py, one process per strategy) into report.json and
daily_report.json -- the two files backtest_router.py actually serves to the UI. Needed because
neither of those per-strategy scripts calls save_report()/save_daily_report() itself (only
`python main.py`'s single-process NIFTY run does, and it has no SENSEX equivalent), so report.json
silently goes stale every time strategies are re-backtested individually.

Each history.json entry only has entry_time/exit_time/realized_pnl/exit_reason (not the full Order
object with entry_price/qty/lot_size), which is all build_report()/build_daily_breakdown() need --
so this does NOT touch capital_requirements.json (required_capital_per_strategy() needs the fields
this thin format doesn't have; that file is produced by a full backtest run instead).

Usage: python regenerate_backtest_report.py
"""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.backtester.report import build_report, save_daily_report, save_report

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"
REPORT_PATH = RESULTS_DIR / "report.json"
DAILY_REPORT_PATH = RESULTS_DIR / "daily_report.json"


@dataclass
class ThinOrder:
    realized_pnl: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str


def _direction_of(strategy_name: str) -> str:
    if "HEDGE" in strategy_name:
        return "HEDGE"
    if "BULLISH" in strategy_name:
        return "CE"
    if "BEARISH" in strategy_name:
        return "PE"
    raise ValueError(f"Can't infer direction for {strategy_name!r} from its name")


def load_history(path: Path) -> list[ThinOrder]:
    raw = json.loads(path.read_text())
    return [
        ThinOrder(
            realized_pnl=t["realized_pnl"],
            entry_time=datetime.fromisoformat(t["entry_time"]),
            exit_time=datetime.fromisoformat(t["exit_time"]),
            exit_reason=t["exit_reason"],
        )
        for t in raw
    ]


def main() -> None:
    reports = {}
    trade_histories = {}

    for path in sorted(RESULTS_DIR.glob("*_history.json")):
        name = path.stem.removesuffix("_history")
        orders = load_history(path)
        trade_histories[name] = orders
        reports[name] = build_report(name, _direction_of(name), orders, initial_capital=1_000_000)
        print(f"[{name}] trades={reports[name].total_trades} win_rate={reports[name].win_rate}% "
              f"profit_factor={reports[name].profit_factor} total_pnl={reports[name].total_pnl}")

    save_report(reports, REPORT_PATH)
    save_daily_report(trade_histories, DAILY_REPORT_PATH)
    print(f"\n{len(reports)} strategies written to {REPORT_PATH} and {DAILY_REPORT_PATH}")


if __name__ == "__main__":
    main()
