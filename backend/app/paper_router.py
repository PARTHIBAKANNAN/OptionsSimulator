"""Paper-trading REST endpoints. Live views (positions/pnl/pending signals) read the in-memory
snapshot the engine publishes; trade history reads Postgres since it must survive a restart."""
from fastapi import APIRouter, Depends, HTTPException, Request

from .security import require_login
from .state import shared_state
from . import db

router = APIRouter(prefix="/api/paper", dependencies=[Depends(require_login)])


@router.get("/positions")
async def get_positions():
    return shared_state.get().get("positions", [])


@router.get("/pnl/summary")
async def get_pnl_summary():
    return shared_state.get().get("pnl", {})


@router.get("/signals/pending")
async def get_pending_signals():
    return shared_state.get().get("pending_signals", [])


@router.get("/trades/history")
async def get_trade_history(request: Request, limit: int = 100, offset: int = 0):
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database not configured — trade history unavailable")
    pool = db.get_pool()
    rows = await pool.fetch(
        """SELECT order_id, symbol, qty, entry_price, entry_time, exit_price, exit_time,
                  exit_reason, realized_pnl, strategy
           FROM options_positions WHERE status = 'CLOSED'
           ORDER BY exit_time DESC LIMIT $1 OFFSET $2""",
        limit, offset,
    )
    return [dict(row) for row in rows]


def _get_engine(request: Request):
    engine = getattr(request.app.state, "live_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Live engine not running")
    return engine


@router.post("/signals/{signal_id}/approve")
async def approve_signal(signal_id: str, request: Request):
    engine = _get_engine(request)
    if not engine.approve_signal(signal_id, "approve"):
        raise HTTPException(status_code=404, detail="Signal already resolved or not found")
    return {"status": "approved"}


@router.post("/signals/{signal_id}/reject")
async def reject_signal(signal_id: str, request: Request):
    engine = _get_engine(request)
    if not engine.approve_signal(signal_id, "reject"):
        raise HTTPException(status_code=404, detail="Signal already resolved or not found")
    return {"status": "rejected"}
