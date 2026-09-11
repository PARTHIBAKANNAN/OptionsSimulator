import asyncio
import threading
from datetime import datetime, date
from unittest.mock import MagicMock, AsyncMock

import pytest

from src.config import Config
from src.trader import LiveTrader, IST
from src.simulator.paper_trader import Order
from src.utils.options_pricing import to_fyers_symbol
from backend.app.live_engine import WebLiveEngine
from backend.app.config import WebConfig


@pytest.mark.asyncio
async def test_websocket_thread_exit_scheduling_never_throws():
    """Simulates Fyers WebSocket background OS thread invoking on_tick() and check_exits().
    Verifies that _schedule_async safely dispatches async DB and Telegram coroutines
    without raising RuntimeError: no running event loop."""
    config = Config(
        fyers_client_id="fake_id",
        fyers_secret_key="fake_sec",
        fyers_fy_id="fake_fy",
        fyers_user_pin="1234",
        fyers_totp_secret="fake_totp",
        fyers_redirect_uri="https://localhost",
        telegram_bot_token="",
        telegram_chat_id="",
        force_market_open=True,
        risk_params={},
    )
    engine = WebLiveEngine(config, data_engine_enabled=True)
    engine._loop = asyncio.get_running_loop()
    engine.fyers = MagicMock()
    engine.telegram = MagicMock()
    engine.telegram.send_position_exit = AsyncMock()

    engine._close_position_db = AsyncMock()
    engine._save_wallet_db = AsyncMock()

    # Create an open position
    raw_symbol = to_fyers_symbol("BANKNIFTY56300CE", date(2026, 9, 29))
    order = engine.paper_trader.place_order(
        symbol="BANKNIFTY56300CE", side="BUY", qty=1, price=300.0,
        stop_loss=240.0, take_profit=420.0, strategy="BANKNIFTY_MACD_BULLISH_1M_ATM",
        timestamp=datetime.now(IST), lot_size=30,
    )
    engine._monitored_symbols.add(raw_symbol)

    # Function executed on a separate OS thread (simulating Fyers WebSocket background thread)
    thread_exceptions = []

    def websocket_worker():
        try:
            # Simulate tick message on worker thread that trips stop-loss
            msg = {
                "symbol": raw_symbol,
                "ltp": 230.0,  # Below SL 240.0
                "vol_traded_today": 1000,
            }
            engine.on_tick(msg)
        except Exception as e:
            thread_exceptions.append(e)

    t = threading.Thread(target=websocket_worker)
    t.start()
    t.join()

    # The background thread must NOT have encountered any exceptions
    assert len(thread_exceptions) == 0

    # Yield control to the main event loop to let threadsafe coroutines run
    await asyncio.sleep(0.05)

    # Verify that in-memory position closed
    assert len(engine.paper_trader.get_positions()) == 0

    # Verify that DB and wallet update tasks were scheduled and awaited on the main loop
    assert engine._close_position_db.called
    assert engine._save_wallet_db.called
    assert engine.telegram.send_position_exit.called
