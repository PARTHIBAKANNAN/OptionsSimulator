"""
Isolated router tests: mounts paper_router on a bare FastAPI app with require_login overridden
and a mocked live_engine, instead of spinning up the full app (backend.app.main.app's lifespan
starts Fyers/Telegram/the DB pool/the broadcaster — unnecessary weight for testing route wiring).
"""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.paper_router import router as paper_router
from backend.app.security import require_login
from backend.app.state import shared_state


def _make_app(db_available=False, wallets=None, wallet=None):
    app = FastAPI()
    app.include_router(paper_router)
    app.dependency_overrides[require_login] = lambda: {"user_id": "test"}

    engine = MagicMock()
    engine.strategy_engine.strategies = [
        SimpleNamespace(name="MACD_BULLISH"), SimpleNamespace(name="ORB_BULLISH")]
    engine.paper_trader.get_wallet.return_value = wallet
    engine.paper_trader.get_all_wallets.return_value = wallets or {}
    app.state.live_engine = engine
    app.state.db_available = db_available
    return app, engine


def test_strategy_orders_without_db_returns_current_signal_and_wallet_but_no_closed_trades():
    app, engine = _make_app(db_available=False, wallet={
        "strategy": "MACD_BULLISH", "balance": 85000.0, "allocated_capital": 85000.0, "pnl_in_wallet": 0.0})
    shared_state.update({"strategy_status": [
        {"strategy": "MACD_BULLISH", "status": "WAITING", "entry": None, "today_pnl": 0.0}]})

    with TestClient(app) as client:
        resp = client.get("/api/paper/strategies/MACD_BULLISH/orders")

    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] == "MACD_BULLISH"
    assert body["current_signal"]["status"] == "WAITING"
    assert body["closed_trades"] == []
    assert body["wallet"]["balance"] == 85000.0


def test_strategy_orders_includes_closed_trades_when_db_available():
    app, engine = _make_app(db_available=True)
    shared_state.update({"strategy_status": []})
    fake_pool = MagicMock()
    fake_pool.fetch = AsyncMock(return_value=[{
        "order_id": "abc", "symbol": "NIFTY24500CE", "qty": 1, "entry_price": 100.0,
        "entry_time": datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc),
        "exit_price": 150.0, "exit_time": datetime(2026, 8, 4, 11, 0, tzinfo=timezone.utc),
        "exit_reason": "TAKE_PROFIT", "realized_pnl": 50.0 * 65, "entry_charges": 25.0, "exit_charges": 27.0,
    }])

    with patch("backend.app.paper_router.db.get_pool", return_value=fake_pool):
        with TestClient(app) as client:
            resp = client.get("/api/paper/strategies/MACD_BULLISH/orders")

    assert resp.status_code == 200
    trades = resp.json()["closed_trades"]
    assert len(trades) == 1
    assert trades[0]["order_id"] == "abc"
    assert "contract" in trades[0] and "NIFTY" in trades[0]["contract"]
    assert trades[0]["net_pnl"] == pytest.approx(50.0 * 65 - 25.0 - 27.0)


def test_pnl_report_returns_every_strategy_even_without_a_configured_db():
    app, engine = _make_app(db_available=False)

    with TestClient(app) as client:
        resp = client.get("/api/paper/pnl/report", params={"range": "today"})

    assert resp.status_code == 200
    body = resp.json()
    assert {s["strategy"] for s in body["strategies"]} == {"MACD_BULLISH", "ORB_BULLISH"}
    assert body["combined"]["trades"] == 0
    assert body["daily_net_pnl"] == []


def test_pnl_report_rejects_an_unknown_range():
    app, engine = _make_app()
    with TestClient(app) as client:
        resp = client.get("/api/paper/pnl/report", params={"range": "last_decade"})
    assert resp.status_code == 400


def test_pnl_report_custom_range_requires_start_and_end():
    app, engine = _make_app()
    with TestClient(app) as client:
        resp = client.get("/api/paper/pnl/report", params={"range": "custom"})
    assert resp.status_code == 400


def test_pnl_report_custom_range_accepts_explicit_dates():
    app, engine = _make_app()
    with TestClient(app) as client:
        resp = client.get("/api/paper/pnl/report",
                           params={"range": "custom", "start": "2026-08-01", "end": "2026-08-06"})
    assert resp.status_code == 200
    assert resp.json()["range"] == {"start": "2026-08-01", "end": "2026-08-06"}


def test_pnl_export_returns_an_xlsx_attachment():
    app, engine = _make_app(db_available=False)

    with TestClient(app) as client:
        resp = client.get("/api/paper/pnl/export", params={"range": "today"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp.headers["content-disposition"]
    assert len(resp.content) > 0  # a real (if mostly empty) xlsx file, not an empty body
