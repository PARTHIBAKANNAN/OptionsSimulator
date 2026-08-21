"""
Read-only backtest report viewer. Deliberately no POST /run: the 90-day backtest is CPU-heavy
(~15 min on this VM's single vCPU) and running it on demand from the web would starve live
trading on the same core. New backtests stay a manual CLI action:
    python -m src.backtester.backtest_engine
"""
import json
import math
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .security import require_login

router = APIRouter(prefix="/api/backtest", dependencies=[Depends(require_login)])

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "backtest_results"
REPORT_PATH = RESULTS_DIR / "report.json"
DAILY_REPORT_PATH = RESULTS_DIR / "daily_report.json"
CAPITAL_REQUIREMENTS_PATH = RESULTS_DIR / "capital_requirements.json"


def _sanitize(value):
    """Python's json.loads happily parses a literal Infinity/-Infinity/NaN (non-standard but
    permitted by the stdlib decoder), but Starlette's JSONResponse.render() calls json.dumps with
    allow_nan=False -- so a report.json containing one of these (e.g. a strategy with wins but
    zero losses computing profit_factor = wins/0 on an older report generation, before
    build_report's 999.99 sentinel existed) 500s on every request, not just a stale display.
    Recursively replace non-finite floats with None so any such file can still be served."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


@router.get("/report")
async def get_report():
    if not REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="No backtest report yet — run the CLI backtester first")
    return _sanitize(json.loads(REPORT_PATH.read_text()))


@router.get("/daily-breakdown")
async def get_daily_breakdown():
    """Per-strategy {date, trades, wins, losses, win_rate, pnl, cumulative_pnl}[] -- already
    computed by build_daily_breakdown() and saved by the CLI backtester, just never routed."""
    if not DAILY_REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="No daily breakdown yet — run the CLI backtester first")
    return _sanitize(json.loads(DAILY_REPORT_PATH.read_text()))


@router.get("/capital-requirements")
async def get_capital_requirements():
    """Per-strategy {avg_trade_risk, max_historical_drawdown, recommended_capital} -- already
    computed by required_capital_per_strategy() and saved by the CLI backtester."""
    if not CAPITAL_REQUIREMENTS_PATH.exists():
        raise HTTPException(status_code=404, detail="No capital requirements yet — run the CLI backtester first")
    return _sanitize(json.loads(CAPITAL_REQUIREMENTS_PATH.read_text()))


@router.get("/strategies/{name}/history")
async def get_strategy_history(name: str):
    """Returns the 1-year backtest trade history for the requested strategy from data/backtest_results/."""
    history_file = RESULTS_DIR / f"{name}_history.json"
    if not history_file.exists():
        raise HTTPException(status_code=404, detail=f"No backtest history found for {name}")
    raw_trades = json.loads(history_file.read_text())
    trades = []
    for idx, t in enumerate(raw_trades, 1):
        trades.append({
            "order_id": f"BT-{idx:04d}",
            "symbol": t.get("symbol", name),
            "contract": t.get("symbol", name),
            "qty": 1,
            "entry_price": t.get("entry_price", 0.0),
            "entry_time": t.get("entry_time"),
            "exit_price": t.get("exit_price", 0.0),
            "exit_time": t.get("exit_time"),
            "exit_reason": t.get("exit_reason", "EXIT"),
            "realized_pnl": t.get("realized_pnl", 0.0),
            "net_pnl": t.get("realized_pnl", 0.0),
            "entry_charges": 0.0,
            "exit_charges": 0.0,
        })
    return _sanitize(trades)
