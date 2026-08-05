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

REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "backtest_results" / "report.json"


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
