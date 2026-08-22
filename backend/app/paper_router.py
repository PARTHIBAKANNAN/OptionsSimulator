"""Paper-trading REST endpoints. Live views (positions/pnl/pending signals) read the in-memory
snapshot the engine publishes; trade history reads Postgres since it must survive a restart."""
import io
import json
from datetime import date as date_cls, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.trader import IST
from src.utils.date_ranges import resolve_range
from src.utils.options_pricing import format_display_symbol, next_weekly_expiry_date

from .security import require_login
from .state import shared_state
from . import db, pnl_service

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
    result = []
    for row in rows:
        trade = dict(row)
        # asyncpg returns timestamptz columns aware in UTC — must convert to IST before deriving
        # the expiry weekday/date, or a late-UTC-evening entry can resolve to the wrong calendar day.
        trade["contract"] = format_display_symbol(
            trade["symbol"], next_weekly_expiry_date(trade["entry_time"].astimezone(IST)))
        result.append(trade)
    return result


def _get_engine(request: Request):
    engine = getattr(request.app.state, "live_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Live engine not running")
    return engine


def _all_strategy_names(engine) -> list[str]:
    """Strategy names across both indices (engine.strategy_engines is {"NIFTY": ..., "SENSEX":
    ...}) -- P&L reporting must cover both, not just NIFTY's."""
    return [s.name for strategy_engine in engine.strategy_engines.values() for s in strategy_engine.strategies]


def _current_price(engine, symbol: str) -> float | None:
    """Live LTP for a symbol, checked across both indices' option chains (NIFTY/SENSEX symbols
    are already uniquely prefixed, so there's no ambiguity in which chain to check first)."""
    for data_manager in engine.data_managers.values():
        quote = data_manager.get_option_chain().get(symbol)
        if quote is not None and quote.ltp:
            return quote.ltp
    return None


async def _close_and_persist(engine, order_id: str):
    """Shared by the single and bulk square-off endpoints: closes one open position at its
    current LTP (falling back to entry price -- a 0 P&L close -- only if no live quote is
    available at all, rather than rejecting the square-off outright), persists it, and updates
    that strategy's wallet. Returns the closed Order, or None if it wasn't open."""
    order = engine.paper_trader.orders.get(order_id)
    if order is None or order.status != "OPEN":
        return None
    price = _current_price(engine, order.symbol) or order.entry_price
    closed = engine.paper_trader.close_position(
        order_id, price=price, timestamp=datetime.now(IST), reason="MANUAL_SQUARE_OFF")
    if closed is None:
        return None
    await engine._close_position_db(closed)
    if closed.strategy:
        await engine._save_wallet_db(closed.strategy)
    return closed


@router.post("/positions/{order_id}/close")
async def close_position(order_id: str, request: Request):
    """Square Off: manually closes one open (simulated) position at its current LTP."""
    engine = _get_engine(request)
    closed = await _close_and_persist(engine, order_id)
    if closed is None:
        raise HTTPException(status_code=404, detail="Open position not found")
    engine._publish_state()
    return {"order_id": closed.order_id, "exit_price": closed.exit_price, "realized_pnl": closed.realized_pnl}


@router.post("/positions/close-all")
async def close_all_positions(request: Request):
    """Square Off All / Day Square Off: closes every currently open position."""
    engine = _get_engine(request)
    closed_ids = []
    for order in list(engine.paper_trader.get_positions()):
        closed = await _close_and_persist(engine, order.order_id)
        if closed is not None:
            closed_ids.append(closed.order_id)
    engine._publish_state()
    return {"closed_count": len(closed_ids), "order_ids": closed_ids}


def _parse_range(range: str, start: str, end: str) -> tuple[date_cls, date_cls]:
    try:
        return resolve_range(
            range, start=date_cls.fromisoformat(start) if start else None,
            end=date_cls.fromisoformat(end) if end else None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/strategies/{name}/orders")
async def get_strategy_orders(name: str, request: Request):
    """Everything item 5's "Show Details" needs for one strategy: its current signal (live LTP/
    P&L, if any), every closed trade, and its wallet — regardless of market hours."""
    engine = _get_engine(request)
    current_signal = next(
        (r for r in shared_state.get().get("strategy_status", []) if r["strategy"] == name), None)

    closed_trades = []
    if getattr(request.app.state, "db_available", False):
        pool = db.get_pool()
        rows = await pool.fetch(
            """SELECT order_id, symbol, qty, entry_price, entry_time, exit_price, exit_time,
                      exit_reason, realized_pnl, entry_charges, exit_charges
               FROM options_positions WHERE strategy = $1 AND status = 'CLOSED'
               ORDER BY exit_time DESC""",
            name,
        )
        for row in rows:
            trade = dict(row)
            trade["contract"] = format_display_symbol(
                trade["symbol"], next_weekly_expiry_date(trade["entry_time"].astimezone(IST)))
            gross = trade["realized_pnl"]
            trade["net_pnl"] = (
                round(float(gross) - float(trade["entry_charges"] or 0) - float(trade["exit_charges"] or 0), 2)
                if gross is not None else None)
            closed_trades.append(trade)

    return {
        "strategy": name,
        "current_signal": current_signal,
        "closed_trades": closed_trades,
        "wallet": engine.paper_trader.get_wallet(name),
    }


@router.get("/pnl/report")
async def get_pnl_report(request: Request, range: str = "today", start: str = None, end: str = None):
    """Individual + combined P&L for item 6's summary tab: per-strategy trades/win-rate/gross/
    charges/net/wallet, a combined total row, and a daily net-P&L series for the equity graph."""
    engine = _get_engine(request)
    start_date, end_date = _parse_range(range, start, end)

    strategy_names = _all_strategy_names(engine)
    db_rows = await pnl_service.strategy_pnl_rows(start_date, end_date)
    wallets = engine.paper_trader.get_all_wallets()
    strategies = pnl_service.build_strategy_summary(strategy_names, db_rows, wallets)
    combined = pnl_service.combine_totals(strategies)
    daily_net_pnl = await pnl_service.daily_net_pnl_series(start_date, end_date)

    return {
        "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "strategies": strategies, "combined": combined, "daily_net_pnl": daily_net_pnl,
    }


@router.get("/pnl/export")
async def export_pnl(request: Request, range: str = "today", start: str = None, end: str = None):
    engine = _get_engine(request)
    start_date, end_date = _parse_range(range, start, end)

    strategy_names = _all_strategy_names(engine)
    db_rows = await pnl_service.strategy_pnl_rows(start_date, end_date)
    wallets = engine.paper_trader.get_all_wallets()
    strategies = pnl_service.build_strategy_summary(strategy_names, db_rows, wallets)
    combined = pnl_service.combine_totals(strategies)
    trades = await pnl_service.closed_trades_in_range(start_date, end_date)

    workbook = pnl_service.build_workbook(strategies, combined, trades, start_date, end_date)
    buffer = io.BytesIO()
    workbook.save(buffer)

    filename = f"pnl_export_{start_date.isoformat()}_{end_date.isoformat()}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/strategies/{name}/restart")
async def restart_strategy(name: str, request: Request):
    """Restarts a strategy for today's session, clearing its intraday throttles and signal latch."""
    engine = _get_engine(request)
    matched_strat = None
    for index, strat_engine in getattr(engine, "strategy_engines", {}).items():
        for s in strat_engine.strategies:
            if s.name == name:
                matched_strat = s
                break
    if matched_strat is None:
        raise HTTPException(status_code=404, detail=f"Strategy {name} not found")

    matched_strat.last_signal_time = None
    if hasattr(matched_strat, "_last_signal_bar"):
        matched_strat._last_signal_bar = None

    return {"status": "restarted", "strategy": name}


RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "backtest_results"


def _sanitize(value):
    import math
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return 0.0
        return value
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


@router.get("/strategies/{name}/history")
async def get_paper_strategy_history(name: str):
    """Returns backtest history for strategy from data/backtest_results/."""
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


@router.get("/intelligence/premarket")
async def get_premarket_intelligence():
    """Returns today's pre-market catalyst & opening market bias intelligence."""
    from .ai_intelligence import get_cached_premarket_intel
    return _sanitize(get_cached_premarket_intel())


@router.post("/intelligence/premarket/refresh")
async def refresh_premarket_intelligence():
    """Forces an on-demand live call to Gemini 3.6 Flash and returns fresh market intelligence."""
    from .ai_intelligence import generate_live_premarket_intel, INTEL_CACHE_PATH
    import json
    intel = generate_live_premarket_intel()
    try:
        INTEL_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        INTEL_CACHE_PATH.write_text(json.dumps(intel, indent=2))
    except Exception:
        pass
    return _sanitize(intel)


@router.get("/intelligence/postmarket")
async def get_postmarket_intelligence(request: Request):
    """Returns today's post-market AI performance audit & trade journal."""
    from .ai_intelligence import get_cached_postmarket_intel
    return _sanitize(get_cached_postmarket_intel())


@router.post("/intelligence/postmarket/refresh")
async def refresh_postmarket_intelligence(request: Request):
    """Forces a live post-market AI performance audit & trade debrief via Gemini 3.6 Flash."""
    from .ai_intelligence import generate_live_postmarket_journal, POSTMARKET_CACHE_PATH
    import json

    # Pull today's completed trades if DB available
    trades_today = []
    daily_pnl = 0.0
    if getattr(request.app.state, "db_available", False):
        try:
            pool = db.get_pool()
            rows = await pool.fetch(
                """SELECT order_id, symbol, qty, entry_price, entry_time, exit_price, exit_time,
                          exit_reason, realized_pnl, strategy
                   FROM options_positions 
                   WHERE status = 'CLOSED' AND DATE(exit_time AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
                   ORDER BY exit_time DESC"""
            )
            trades_today = [dict(r) for r in rows]
            daily_pnl = sum((r.get("realized_pnl") or 0.0) for r in trades_today)
        except Exception as e:
            print(f"[PostMarketRouter] DB trade fetch error: {e}")

    journal = generate_live_postmarket_journal(trades_today=trades_today, daily_pnl=daily_pnl)
    try:
        POSTMARKET_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        POSTMARKET_CACHE_PATH.write_text(json.dumps(journal, indent=2))
    except Exception:
        pass
    return _sanitize(journal)


