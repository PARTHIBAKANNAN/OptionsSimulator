"""
Read-only backtest report viewer. Deliberately no POST /run: the 90-day backtest is CPU-heavy
(~15 min on this VM's single vCPU) and running it on demand from the web would starve live
trading on the same core. New backtests stay a manual CLI action:
    python -m src.backtester.backtest_engine
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .security import require_login

router = APIRouter(prefix="/api/backtest", dependencies=[Depends(require_login)])

REPORT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "backtest_results" / "report.json"


@router.get("/report")
async def get_report():
    if not REPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="No backtest report yet — run the CLI backtester first")
    return json.loads(REPORT_PATH.read_text())
