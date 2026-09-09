"""
Tests for multi-strategy shared contract handling and master health check endpoint.
Verifies that when multiple strategies trade the exact same option contract:
- WebSocket subscription is shared cleanly.
- When one strategy exits, reference counting prevents premature unsubscription.
- Only when all strategies holding the contract exit is the symbol unsubscribed from WebSocket.
"""
import asyncio
from datetime import datetime, date
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

from backend.app.live_engine import WebLiveEngine
from backend.app.main import app
from src.config import Config
from src.data_manager import OptionQuote
from src.strategies.base_strategy import Signal
from src.utils.options_pricing import to_fyers_symbol

IST = ZoneInfo("Asia/Kolkata")


def _make_engine() -> WebLiveEngine:
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 30, "max_concurrent_positions": 10, "max_daily_loss": 50000},
        "exit_rules": {
            "stop_loss_pct": 20,
            "take_profit_pct": 40,
            "time_exit_mins": 120,
            "trailing_stop_enabled": True,
            "expanding_dynamic_tsl_enabled": True,
            "multi_index_tsl": {
                "BANKNIFTY": {
                    "atm": {"stop_loss_pct": 20.0, "target_pts": 150.0, "cost_lock_pts": 30.0, "stage1_threshold_pts": 55.0, "trail_stage1_pts": 35.0, "stage2_threshold_pts": 110.0, "trail_stage2_pts": 45.0},
                    "itm": {"stop_loss_pct": 20.0, "target_pts": 150.0, "cost_lock_pts": 30.0, "stage1_threshold_pts": 55.0, "trail_stage1_pts": 35.0, "stage2_threshold_pts": 110.0, "trail_stage2_pts": 45.0, "min_entry_price": 200.0}
                }
            }
        },
        "polling": {"option_chain_interval_secs": 10},
        "live_mode": {"auto_approve": True},
    }
    config = Config(
        fyers_client_id="x", fyers_secret_key="x", fyers_fy_id="x", fyers_user_pin="x",
        fyers_totp_secret="x", fyers_redirect_uri="https://example.com/callback",
        telegram_bot_token="", telegram_chat_id="", force_market_open=False,
        risk_params=risk_params,
    )
    engine = WebLiveEngine(config, data_engine_enabled=True)
    engine.fyers = MagicMock()
    engine.fyers.access_token = "mock_token"
    engine.fyers.subscribe_symbols = MagicMock()
    engine.fyers.unsubscribe_symbols = MagicMock()
    return engine


@pytest.mark.asyncio
async def test_multi_strategy_contract_sharing_and_ref_counted_unsubscription():
    engine = _make_engine()
    trade_time = datetime(2026, 9, 9, 10, 0, tzinfo=IST)
    tick_time = datetime(2026, 9, 9, 10, 5, tzinfo=IST)

    # Mock DB saves
    engine._save_position_db = AsyncMock()
    engine._save_wallet_db = AsyncMock()
    engine._close_position_db = AsyncMock()

    # Pre-populate option chain with a BANKNIFTY contract
    raw_symbol = to_fyers_symbol("BANKNIFTY56300CE", date(2026, 9, 29))
    engine.data_managers["BANKNIFTY"].option_chain[raw_symbol] = OptionQuote(symbol=raw_symbol, ltp=300.0)
    engine.data_managers["BANKNIFTY"].option_chain["BANKNIFTY56300CE"] = OptionQuote(symbol="BANKNIFTY56300CE", ltp=300.0)
    engine.data_managers["BANKNIFTY"]._symbol_alias["BANKNIFTY56300CE"] = raw_symbol
    engine.data_managers["BANKNIFTY"]._symbol_alias[raw_symbol] = "BANKNIFTY56300CE"

    # Strategy 1 enters
    sig1 = Signal(
        strategy="BANKNIFTY_MACD_BULLISH_1M_ATM",
        direction="CE", action="BUY", strike="BANKNIFTY56300CE",
        confidence=0.8, rationale="macd", entry_price=300.0,
        timestamp=trade_time, underlying="BANKNIFTY",
    )
    await engine.execute_signal(sig1)

    # Strategy 2 enters the SAME contract with a different entry price
    sig2 = Signal(
        strategy="BANKNIFTY_SUPPORT_BOUNCE_1M_ATM",
        direction="CE", action="BUY", strike="BANKNIFTY56300CE",
        confidence=0.85, rationale="bounce", entry_price=320.0,
        timestamp=trade_time, underlying="BANKNIFTY",
    )
    await engine.execute_signal(sig2)

    positions = engine.paper_trader.get_positions()
    assert len(positions) == 2
    assert positions[0].symbol == "BANKNIFTY56300CE"
    assert positions[1].symbol == "BANKNIFTY56300CE"
    assert positions[0].strategy != positions[1].strategy

    # Both shared the same raw Fyers symbol
    assert raw_symbol in engine._monitored_symbols
    engine.fyers.subscribe_symbols.assert_called_with([raw_symbol])

    # Now simulate a market tick at 10:05 AM where LTP drops to 250
    # For Strategy 2 (entry 320), SL is 320 * 0.8 = 256. At 250, Strategy 2's SL is HIT!
    # For Strategy 1 (entry 300), SL is 300 * 0.8 = 240. At 250, Strategy 1 is still SAFE!
    engine.data_managers["BANKNIFTY"].option_chain["BANKNIFTY56300CE"].ltp = 250.0
    engine.data_managers["BANKNIFTY"].option_chain[raw_symbol].ltp = 250.0

    with patch("backend.app.live_engine.datetime") as mock_dt:
        mock_dt.now.return_value = tick_time
        engine.check_exits()

    # Strategy 2 should be closed, but Strategy 1 must still be OPEN
    remaining = engine.paper_trader.get_positions()
    assert len(remaining) == 1
    assert remaining[0].strategy == "BANKNIFTY_MACD_BULLISH_1M_ATM"

    # CRITICAL: Since Strategy 1 is still open on BANKNIFTY56300CE,
    # Fyers MUST NOT have unsubscribed raw_symbol!
    engine.fyers.unsubscribe_symbols.assert_not_called()
    assert raw_symbol in engine._monitored_symbols

    # Now drop price to 230, hitting Strategy 1's stop-loss
    engine.data_managers["BANKNIFTY"].option_chain["BANKNIFTY56300CE"].ltp = 230.0
    engine.data_managers["BANKNIFTY"].option_chain[raw_symbol].ltp = 230.0

    with patch("backend.app.live_engine.datetime") as mock_dt:
        mock_dt.now.return_value = tick_time
        engine.check_exits()

    # Now zero open positions remain
    assert len(engine.paper_trader.get_positions()) == 0

    # ONLY NOW should Fyers unsubscribe_symbols be called!
    engine.fyers.unsubscribe_symbols.assert_called_once_with([raw_symbol])
    assert raw_symbol not in engine._monitored_symbols


def test_master_health_endpoint():
    engine = _make_engine()
    engine.is_running = True
    app.state.live_engine = engine
    app.state.db_available = True

    client = TestClient(app)
    response = client.get("/api/health/master")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert "indices" in data
    assert "NIFTY" in data["indices"]
    assert "SENSEX" in data["indices"]
    assert "BANKNIFTY" in data["indices"]

    # Verify correct next expiry dates reported for tomorrow/next cycle
    assert data["indices"]["BANKNIFTY"]["next_expiry_date"] == "2026-09-29"
    assert data["indices"]["SENSEX"]["next_expiry_date"] == "2026-09-10"
    assert data["indices"]["NIFTY"]["next_expiry_date"] == "2026-09-15"

    assert data["strategies"]["total_active"] == 44
    assert data["strategies"]["by_index"]["BANKNIFTY"] == 15
    assert data["strategies"]["by_index"]["SENSEX"] == 15
    assert data["strategies"]["by_index"]["NIFTY"] == 14
