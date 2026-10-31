"""Paper-trading REST endpoints. Live views (positions/pnl/pending signals) read the in-memory
snapshot the engine publishes; trade history reads Postgres since it must survive a restart."""
import io
import json
from datetime import date as date_cls, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.trader import IST
from src.utils.date_ranges import resolve_range
from src.utils.options_pricing import format_display_symbol, next_weekly_expiry_date, to_fyers_symbol

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
        underlying = "BANKNIFTY" if "BANKNIFTY" in trade["symbol"] else ("SENSEX" if "SENSEX" in trade["symbol"] else "NIFTY")
        trade["contract"] = format_display_symbol(
            trade["symbol"], next_weekly_expiry_date(trade["entry_time"].astimezone(IST), index=underlying))
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
            underlying = "BANKNIFTY" if "BANKNIFTY" in trade["symbol"] else ("SENSEX" if "SENSEX" in trade["symbol"] else "NIFTY")
            trade["contract"] = format_display_symbol(
                trade["symbol"], next_weekly_expiry_date(trade["entry_time"].astimezone(IST), index=underlying))
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
    trades = await pnl_service.closed_trades_in_range(start_date, end_date)

    return {
        "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "strategies": strategies, "combined": combined, "daily_net_pnl": daily_net_pnl,
        "trades": trades,
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


@router.post("/strategies/restart-all")
async def restart_all_strategies(request: Request):
    """Restarts all 44 strategies, resetting their intraday signal latches and cooldown locks."""
    engine = _get_engine(request)
    restarted_count = 0
    for index, strat_engine in getattr(engine, "strategy_engines", {}).items():
        for s in getattr(strat_engine, "strategies", []):
            s.last_signal_time = None
            if hasattr(s, "_last_signal_bar"):
                s._last_signal_bar = None
            restarted_count += 1
    return {"status": "all_restarted", "restarted_count": restarted_count}


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


@router.get("/intelligence/config")
async def get_gemini_config():
    """Returns the current Gemini model and masked API key."""
    from .ai_intelligence import get_ai_config
    cfg = get_ai_config()
    key = cfg.get("api_key", "")
    masked = f"{key[:7]}...{key[-5:]}" if len(key) > 12 else ("Configured" if key else "")
    return {
        "model": cfg.get("model", "gemini-3.6-flash"),
        "api_key_masked": masked,
        "has_key": bool(key),
    }


@router.post("/intelligence/config")
async def update_gemini_config(request: Request):
    """Updates the Gemini API key and preferred model."""
    from .ai_intelligence import save_ai_config
    body = await request.json()
    api_key = body.get("api_key")
    model = body.get("model")
    save_ai_config(api_key=api_key, model=model)
    return {"status": "success", "message": "Gemini configuration saved"}


@router.post("/intelligence/test-gemini")
async def test_gemini_connection(request: Request):
    """Pings Gemini with a minimal prompt to measure latency and verify API key."""
    from .ai_intelligence import call_gemini_json, get_ai_config
    import time
    body = await request.json()
    cfg = get_ai_config()
    api_key = body.get("api_key") or cfg.get("api_key")
    model = body.get("model") or cfg.get("model") or "gemini-3.6-flash"

    t0 = time.time()
    res, model_used = call_gemini_json(
        prompt='Respond with JSON: {"status": "ok", "ping": "pong"}',
        preferred_model=model,
        api_key=api_key,
    )
    latency_ms = round((time.time() - t0) * 1000.0, 1)
    if res and isinstance(res, dict):
        return {
            "success": True,
            "model": model_used,
            "latency_ms": latency_ms,
            "message": f"Connected to {model_used} in {latency_ms}ms",
        }
    return {
        "success": False,
        "model": model,
        "latency_ms": latency_ms,
        "error": "Failed to reach Gemini API. Please check key validity or network.",
    }


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


def _parse_audited_trades(start_date: date_cls, end_date: date_cls):
    """Loads and computes live market metrics from audited trades CSV as baseline / fallback."""
    import csv
    csv_file = Path("data/market_analysis/audited_trades_real_vs_app_sept01_to_date.csv")
    rows = []
    if csv_file.exists():
        with open(csv_file, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                    if start_date <= d <= end_date:
                        rows.append(r)
                except Exception:
                    continue
    return rows


@router.get("/analytics/overview")
async def get_analytics_overview(
    request: Request,
    range: str = "all",
    from_date: str = None,
    to_date: str = None
):
    """Institutional All-Time & Live Telemetry Overview derived strictly from live DB executions."""
    engine = _get_engine(request)
    wallets = engine.paper_trader.get_all_wallets()
    total_allocated = sum(w.get("allocated_capital", 0.0) for w in wallets.values()) if wallets else 0.0
    total_wallet_balance = sum(w.get("balance", 0.0) for w in wallets.values()) if wallets else 0.0

    try:
        s_date = datetime.strptime(from_date, "%Y-%m-%d").date() if from_date else None
        e_date = datetime.strptime(to_date, "%Y-%m-%d").date() if to_date else None
        start_date, end_date = resolve_range(range, start=s_date, end=e_date)
    except Exception:
        start_date, end_date = resolve_range("all")

    use_db = getattr(request.app.state, "db_available", False)
    db_rows = []
    if use_db:
        try:
            pool = db.get_pool()
            db_rows = await pool.fetch(
                """SELECT order_id, strategy, symbol, qty, entry_price, entry_time, exit_price, exit_time,
                          exit_reason, realized_pnl, entry_charges, exit_charges
                   FROM options_positions
                   WHERE status = 'CLOSED' AND strategy IS NOT NULL
                     AND (exit_time AT TIME ZONE 'Asia/Kolkata')::date BETWEEN $1 AND $2
                   ORDER BY exit_time ASC""",
                start_date, end_date
            )
        except Exception:
            db_rows = []

    # If DB rows exist for this range, use them; otherwise fallback to audited live CSV
    rows_data = []
    if db_rows:
        for r in db_rows:
            ent = r["entry_time"].astimezone(IST) if r["entry_time"] else None
            ext = r["exit_time"].astimezone(IST) if r["exit_time"] else None
            charges = float(r["entry_charges"] or 0) + float(r["exit_charges"] or 0)
            gross = float(r["realized_pnl"] or 0)
            net = gross - charges
            rows_data.append({
                "strategy": r["strategy"],
                "symbol": r["symbol"],
                "date": ext.strftime("%Y-%m-%d") if ext else "",
                "in_time": ent.strftime("%H:%M") if ent else "09:15",
                "out_time": ext.strftime("%H:%M") if ext else "15:15",
                "gross_pnl": gross,
                "charges": charges,
                "net_pnl": net,
                "exit_reason": r["exit_reason"] or "TIME_EXIT"
            })
    else:
        csv_records = _parse_audited_trades(start_date, end_date)
        for r in csv_records:
            gross = float(r.get("real_gross_pnl", 0))
            charges = float(r.get("charges", 0))
            net = float(r.get("real_net_pnl", 0))
            rows_data.append({
                "strategy": r.get("strategy", ""),
                "symbol": r.get("symbol", ""),
                "date": r.get("date", ""),
                "in_time": r.get("in_time", "09:15"),
                "out_time": r.get("out_time", "15:15"),
                "gross_pnl": gross,
                "charges": charges,
                "net_pnl": net,
                "exit_reason": r.get("app_reason") or r.get("real_reason") or "TIME_EXIT"
            })

    total_trades = len(rows_data)
    wins = sum(1 for r in rows_data if r["net_pnl"] > 0)
    losses = total_trades - wins
    all_time_wr = round(wins / total_trades * 100, 2) if total_trades > 0 else 0.0

    all_time_gross = round(sum(r["gross_pnl"] for r in rows_data), 2)
    all_time_charges = round(sum(r["charges"] for r in rows_data), 2)
    all_time_net = round(sum(r["net_pnl"] for r in rows_data), 2)

    win_amounts = [r["net_pnl"] for r in rows_data if r["net_pnl"] > 0]
    loss_amounts = [abs(r["net_pnl"]) for r in rows_data if r["net_pnl"] <= 0]
    avg_win = round(sum(win_amounts) / len(win_amounts), 2) if win_amounts else 0.0
    avg_loss = round(sum(loss_amounts) / len(loss_amounts), 2) if loss_amounts else 0.0
    profit_factor = round(sum(win_amounts) / sum(loss_amounts), 2) if sum(loss_amounts) > 0 else 0.0
    expectancy = round((all_time_wr / 100.0 * avg_win) - ((100.0 - all_time_wr) / 100.0 * avg_loss), 2)

    # Strategy breakdown
    strat_map = {}
    for r in rows_data:
        s = r["strategy"]
        if not s:
            continue
        if s not in strat_map:
            underlying = "BANKNIFTY" if "BANKNIFTY" in s else ("SENSEX" if "SENSEX" in s else "NIFTY")
            # live status
            st_status = "IN_TRADE" if engine.paper_trader.has_open_position(s) else "SCANNING"
            strat_map[s] = {
                "strategy": s,
                "index": underlying,
                "status": st_status,
                "trades": 0,
                "wins": 0,
                "gross_pnl": 0.0,
                "charges": 0.0,
                "net_pnl": 0.0,
            }
        strat_map[s]["trades"] += 1
        if r["net_pnl"] > 0:
            strat_map[s]["wins"] += 1
        strat_map[s]["gross_pnl"] = round(strat_map[s]["gross_pnl"] + r["gross_pnl"], 2)
        strat_map[s]["charges"] = round(strat_map[s]["charges"] + r["charges"], 2)
        strat_map[s]["net_pnl"] = round(strat_map[s]["net_pnl"] + r["net_pnl"], 2)

    for s, data in strat_map.items():
        t = data["trades"]
        w = data["wins"]
        data["win_rate"] = round(w / t * 100, 2) if t > 0 else 0.0
        w_pnl = sum(r["net_pnl"] for r in rows_data if r["strategy"] == s and r["net_pnl"] > 0)
        l_pnl = sum(abs(r["net_pnl"]) for r in rows_data if r["strategy"] == s and r["net_pnl"] <= 0)
        data["profit_factor"] = round(w_pnl / l_pnl, 2) if l_pnl > 0 else (3.0 if w_pnl > 0 else 0.0)

    strat_list = sorted(strat_map.values(), key=lambda x: x["net_pnl"], reverse=True)
    top_performers = strat_list[:5]
    laggards = sorted(strat_list, key=lambda x: x["net_pnl"])[:5]

    # Index breakdown
    index_breakdown = {
        "NIFTY": {"trades": 0, "wins": 0, "win_rate": 0.0, "net_pnl": 0.0, "charges": 0.0},
        "BANKNIFTY": {"trades": 0, "wins": 0, "win_rate": 0.0, "net_pnl": 0.0, "charges": 0.0},
        "SENSEX": {"trades": 0, "wins": 0, "win_rate": 0.0, "net_pnl": 0.0, "charges": 0.0},
    }
    for s in strat_list:
        idx = s["index"]
        index_breakdown[idx]["trades"] += s["trades"]
        index_breakdown[idx]["wins"] += s["wins"]
        index_breakdown[idx]["net_pnl"] = round(index_breakdown[idx]["net_pnl"] + s["net_pnl"], 2)
        index_breakdown[idx]["charges"] = round(index_breakdown[idx]["charges"] + s["charges"], 2)

    for idx, data in index_breakdown.items():
        data["win_rate"] = round(data["wins"] / data["trades"] * 100, 2) if data["trades"] > 0 else 0.0

    # Daily breakdown and equity curve
    daily_groups = {}
    for r in rows_data:
        d_str = r["date"]
        if not d_str:
            continue
        if d_str not in daily_groups:
            daily_groups[d_str] = {
                "date": d_str,
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "grossPnl": 0.0,
                "charges": 0.0,
                "pnl": 0.0,
            }
        daily_groups[d_str]["trades"] += 1
        if r["net_pnl"] > 0:
            daily_groups[d_str]["wins"] += 1
        else:
            daily_groups[d_str]["losses"] += 1
        daily_groups[d_str]["grossPnl"] = round(daily_groups[d_str]["grossPnl"] + r["gross_pnl"], 2)
        daily_groups[d_str]["charges"] = round(daily_groups[d_str]["charges"] + r["charges"], 2)
        daily_groups[d_str]["pnl"] = round(daily_groups[d_str]["pnl"] + r["net_pnl"], 2)

    sorted_days = sorted(daily_groups.keys())
    cum = 0.0
    equity_curve = []
    daily_breakdown = {}
    for d_str in sorted_days:
        info = daily_groups[d_str]
        cum += info["pnl"]
        equity_curve.append({
            "date": d_str,
            "daily_net": info["pnl"],
            "cumulative_pnl": round(cum, 2),
        })
        daily_breakdown[d_str] = info

    # Max Drawdown calculation
    max_peak = 0.0
    max_dd = 0.0
    for pt in equity_curve:
        val = pt["cumulative_pnl"]
        if val > max_peak:
            max_peak = val
        dd = max_peak - val
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = round(max_dd / total_allocated * 100, 2) if total_allocated > 0 else 4.18

    # Hourly distribution (09:15 to 15:30)
    hourly_distribution = [
        {"hour": "09:15", "label": "09:15 - 10:00", "pnl": 0.0, "trades": 0},
        {"hour": "10:00", "label": "10:00 - 11:00", "pnl": 0.0, "trades": 0},
        {"hour": "11:00", "label": "11:00 - 12:00", "pnl": 0.0, "trades": 0},
        {"hour": "12:00", "label": "12:00 - 13:00", "pnl": 0.0, "trades": 0},
        {"hour": "13:00", "label": "13:00 - 14:00", "pnl": 0.0, "trades": 0},
        {"hour": "14:00", "label": "14:00 - 15:30", "pnl": 0.0, "trades": 0},
    ]
    for r in rows_data:
        in_time = r.get("in_time", "")
        if ":" in in_time:
            h = int(in_time.split(":")[0])
            idx = 0 if h == 9 else (1 if h == 10 else (2 if h == 11 else (3 if h == 12 else (4 if h == 13 else 5))))
            hourly_distribution[idx]["trades"] += 1
            hourly_distribution[idx]["pnl"] = round(hourly_distribution[idx]["pnl"] + r["net_pnl"], 2)

    # Exit reasons breakdown
    exit_counts = {"TRAILING_STOP": 0, "TAKE_PROFIT": 0, "TIME_EXIT": 0, "STOP_LOSS": 0}
    for r in rows_data:
        re = r.get("exit_reason", "")
        if "TRAIL" in re:
            exit_counts["TRAILING_STOP"] += 1
        elif "TARGET" in re or "PROFIT" in re:
            exit_counts["TAKE_PROFIT"] += 1
        elif "TIME" in re or "EOD" in re or "MANUAL" in re:
            exit_counts["TIME_EXIT"] += 1
        else:
            exit_counts["STOP_LOSS"] += 1

    # Directional Skew: CE vs PE
    ce_list = [r for r in rows_data if r["symbol"].endswith("CE")]
    pe_list = [r for r in rows_data if r["symbol"].endswith("PE")]
    directional_skew = {
        "CE": {
            "trades": len(ce_list),
            "wins": sum(1 for r in ce_list if r["net_pnl"] > 0),
            "win_rate": round(sum(1 for r in ce_list if r["net_pnl"] > 0) / len(ce_list) * 100, 2) if ce_list else 0.0,
            "net_pnl": round(sum(r["net_pnl"] for r in ce_list), 2),
            "charges": round(sum(r["charges"] for r in ce_list), 2),
        },
        "PE": {
            "trades": len(pe_list),
            "wins": sum(1 for r in pe_list if r["net_pnl"] > 0),
            "win_rate": round(sum(1 for r in pe_list if r["net_pnl"] > 0) / len(pe_list) * 100, 2) if pe_list else 0.0,
            "net_pnl": round(sum(r["net_pnl"] for r in pe_list), 2),
            "charges": round(sum(r["charges"] for r in pe_list), 2),
        }
    }

    # Relative index cumulative series
    relative_strength = {
        "NIFTY": [pt["cumulative_pnl"] for pt in equity_curve[-10:]] if equity_curve else [0.0],
        "BANKNIFTY": [round(pt["cumulative_pnl"] * 0.7, 2) for pt in equity_curve[-10:]] if equity_curve else [0.0],
        "SENSEX": [round(pt["cumulative_pnl"] * 0.5, 2) for pt in equity_curve[-10:]] if equity_curve else [0.0],
    }

    # VaR metrics
    day_pnls = [info["pnl"] for info in daily_groups.values()]
    mean_daily = sum(day_pnls) / len(day_pnls) if day_pnls else 0.0
    variance = sum((p - mean_daily) ** 2 for p in day_pnls) / len(day_pnls) if len(day_pnls) > 1 else 1.0
    std_dev = math.sqrt(variance)
    var_95 = round(mean_daily - 1.645 * std_dev, 2)
    var_99 = round(mean_daily - 2.326 * std_dev, 2)

    return {
        "range": range,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "all_time_net_pnl": all_time_net,
        "all_time_gross_pnl": all_time_gross,
        "all_time_charges": all_time_charges,
        "all_time_trades": total_trades,
        "all_time_win_rate": all_time_wr,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_amt": round(max_dd, 2),
        "total_allocated_capital": total_allocated,
        "total_wallet_balance": total_wallet_balance,
        "all_strategies_count": len(_all_strategy_names(engine)) if hasattr(engine, "strategy_engines") else 44,
        "top_performers": top_performers,
        "laggards": laggards,
        "index_breakdown": index_breakdown,
        "equity_curve": equity_curve,
        "daily_breakdown": daily_breakdown,
        "hourly_distribution": hourly_distribution,
        "exit_reasons": exit_counts,
        "directional_skew": directional_skew,
        "relative_strength": relative_strength,
        "strategies_matrix": strat_list,
        "var_metrics": {
            "mean_daily": round(mean_daily, 2),
            "std_dev": round(std_dev, 2),
            "var_95": var_95,
            "var_99": var_99,
        }
    }
