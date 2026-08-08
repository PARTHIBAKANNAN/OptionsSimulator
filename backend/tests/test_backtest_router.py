"""
Regression test: a report.json containing a literal Infinity (e.g. a strategy with wins but zero
losses, from before build_report's 999.99 profit_factor sentinel existed) 500s every request to
GET /api/backtest/report, because Starlette's JSONResponse.render() calls json.dumps with
allow_nan=False even though Python's own json.loads happily parsed the non-standard literal.
"""
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import backtest_router
from backend.app.backtest_router import _sanitize, router as backtest_api_router
from backend.app.security import require_login


def _make_app():
    app = FastAPI()
    app.include_router(backtest_api_router)
    app.dependency_overrides[require_login] = lambda: {"user_id": "test"}
    return app


def test_sanitize_replaces_non_finite_floats_with_none():
    report = {
        "MACD_BULLISH": {"strategy": "MACD_BULLISH", "profit_factor": float("inf"), "total_pnl": 100.0},
        "MACD_BEARISH": {"strategy": "MACD_BEARISH", "profit_factor": float("-inf"), "win_rate": float("nan")},
    }
    sanitized = _sanitize(report)

    assert sanitized["MACD_BULLISH"]["profit_factor"] is None
    assert sanitized["MACD_BULLISH"]["total_pnl"] == 100.0
    assert sanitized["MACD_BEARISH"]["profit_factor"] is None
    assert sanitized["MACD_BEARISH"]["win_rate"] is None


def test_sanitize_leaves_finite_values_and_nested_lists_untouched():
    report = {"a": [1, 2.5, {"b": 3.0}], "c": "text", "d": None}
    assert _sanitize(report) == report


def test_daily_breakdown_returns_404_when_no_report_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(backtest_router, "DAILY_REPORT_PATH", tmp_path / "daily_report.json")
    with TestClient(_make_app()) as client:
        resp = client.get("/api/backtest/daily-breakdown")
    assert resp.status_code == 404


def test_daily_breakdown_serves_saved_per_strategy_series(tmp_path, monkeypatch):
    path = tmp_path / "daily_report.json"
    path.write_text(json.dumps({
        "MACD_BULLISH": [{"date": "2026-01-05", "trades": 2, "wins": 1, "losses": 1,
                           "win_rate": 50.0, "pnl": 120.0, "cumulative_pnl": 120.0}],
    }))
    monkeypatch.setattr(backtest_router, "DAILY_REPORT_PATH", path)

    with TestClient(_make_app()) as client:
        resp = client.get("/api/backtest/daily-breakdown")

    assert resp.status_code == 200
    assert resp.json()["MACD_BULLISH"][0]["cumulative_pnl"] == 120.0


def test_capital_requirements_returns_404_when_no_file_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(backtest_router, "CAPITAL_REQUIREMENTS_PATH", tmp_path / "capital_requirements.json")
    with TestClient(_make_app()) as client:
        resp = client.get("/api/backtest/capital-requirements")
    assert resp.status_code == 404


def test_capital_requirements_serves_saved_per_strategy_figures(tmp_path, monkeypatch):
    path = tmp_path / "capital_requirements.json"
    path.write_text(json.dumps({
        "MACD_BULLISH": {"avg_trade_risk": 8000.0, "max_historical_drawdown": 20000.0, "recommended_capital": 85000.0},
    }))
    monkeypatch.setattr(backtest_router, "CAPITAL_REQUIREMENTS_PATH", path)

    with TestClient(_make_app()) as client:
        resp = client.get("/api/backtest/capital-requirements")

    assert resp.status_code == 200
    assert resp.json()["MACD_BULLISH"]["recommended_capital"] == 85000.0
