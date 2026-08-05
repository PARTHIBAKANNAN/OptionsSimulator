"""
Regression test: a report.json containing a literal Infinity (e.g. a strategy with wins but zero
losses, from before build_report's 999.99 profit_factor sentinel existed) 500s every request to
GET /api/backtest/report, because Starlette's JSONResponse.render() calls json.dumps with
allow_nan=False even though Python's own json.loads happily parsed the non-standard literal.
"""
from backend.app.backtest_router import _sanitize


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
