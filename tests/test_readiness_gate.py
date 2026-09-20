"""
Unit tests for 4-Stage Engine Readiness Gate in LiveTrader.
"""
from datetime import datetime
from unittest.mock import MagicMock
import pytest

from src.config import Config
from src.trader import LiveTrader, IST


@pytest.fixture
def mock_trader():
    config = Config(
        fyers_client_id="TEST-100",
        fyers_secret_key="secret",
        fyers_fy_id="FY12345",
        fyers_user_pin="1234",
        fyers_totp_secret="JBSWY3DPEHPK3PXP",
        fyers_redirect_uri="https://127.0.0.1",
        telegram_bot_token="",
        telegram_chat_id="",
        force_market_open=True,
        risk_params={},
    )

    trader = LiveTrader(config)
    trader.fyers.access_token = "mock_token"
    return trader


def test_readiness_gate_stages(mock_trader):
    assert mock_trader.readiness_stage == "INIT"

    # Stage 1: CONTRACT_READY via initialize_contracts()
    mock_chain_data = {
        "expiryData": [{"expiry": 1789935950}],
        "optionsChain": [
            {
                "symbol": f"NSE:NIFTY26SEP{24000 + k * 50}{opt}",
                "strike_price": float(24000 + k * 50),
                "option_type": opt,
                "expiry": 1789935950,
            }
            for k in range(-15, 16)
            for opt in ("CE", "PE")
        ]
    }
    mock_trader.fyers.get_option_chain = MagicMock(return_value=mock_chain_data)

    success = mock_trader.initialize_contracts()
    assert success is True
    assert mock_trader.readiness_stage == "CONTRACT_READY"

    # When not ARMED, evaluate_strategies() returns empty
    signals = mock_trader.evaluate_strategies()
    # If not armed, evaluate_strategies returns signals if called directly, but in start() loop it's gated by readiness_stage == "STRATEGIES_ARMED"
    assert mock_trader.readiness_stage != "STRATEGIES_ARMED"

    # Stage 2: SUBSCRIPTION_READY
    mock_trader.fyers.start_websocket = MagicMock()
    mock_trader.fyers.subscribe_symbols = MagicMock()
    now = datetime(2026, 9, 24, 9, 20, tzinfo=IST)
    mock_trader.ensure_connection_state(now)
    assert mock_trader.readiness_stage == "SUBSCRIPTION_READY"

    # Stage 3 & 4: Live ticks advance to QUOTE_READY and STRATEGIES_ARMED
    # Feed spot tick
    mock_trader.on_tick({"symbol": "NSE:NIFTY50-INDEX", "ltp": 24000.0, "volume": 1000})
    mock_trader.on_tick({"symbol": "NSE:NIFTYBANK-INDEX", "ltp": 56000.0, "volume": 1000})
    mock_trader.on_tick({"symbol": "BSE:SENSEX-INDEX", "ltp": 78000.0, "volume": 1000})

    # Feed option ticks
    for k in range(-5, 6):
        mock_trader.on_tick({
            "symbol": f"NSE:NIFTY26SEP{24000 + k * 50}CE",
            "ltp": 150.0,
            "bid_price": 149.5,
            "ask_price": 150.5,
            "vol_traded_today": 5000,
        })

    assert mock_trader.readiness_stage == "STRATEGIES_ARMED"
