import pytest
from unittest.mock import MagicMock
from datetime import datetime, date
from zoneinfo import ZoneInfo

from src.config import Config
from src.trader import LiveTrader, IST
from src.simulator.paper_trader import Order

IST = ZoneInfo("Asia/Kolkata")


def test_multi_strategy_symbol_sharing_ref_count():
    """Validates that:
    1. Multiple strategies trading the same contract share Socket 2 subscription.
    2. Closing position for Strategy A does NOT unsubscribe if Strategy B still holds it.
    3. Only when ALL positions in that symbol close across all strategies is it unsubscribed.
    4. Re-entry by any strategy re-subscribes seamlessly.
    """
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
    trader = LiveTrader(config)
    trader.fyers = MagicMock()

    # Initial state
    assert len(trader._active_trade_symbols) == 0

    sym = "NSE:NIFTY26SEP22850PE"

    # Strategy 1 buys sym
    order1 = trader.paper_trader.place_order(
        symbol="NIFTY22850PE",
        side="BUY",
        qty=1,
        price=100.0,
        strategy="STRATEGY_MOMENTUM",
        timestamp=datetime.now(IST),
        lot_size=65,
        canonical_instrument_id="NIFTY_2026-09-29_22850_PE",
        fyers_symbol=sym,
    )
    trader._reconcile_active_trade_symbols()

    # Must be subscribed on Socket 2 with ref_count = 1
    assert trader._active_trade_symbols[sym] == 1
    trader.fyers.subscribe_trades_symbols.assert_called_once_with([sym])

    # Strategy 2 buys the EXACT same contract
    trader.fyers.reset_mock()
    order2 = trader.paper_trader.place_order(
        symbol="NIFTY22850PE",
        side="BUY",
        qty=1,
        price=102.0,
        strategy="STRATEGY_TREND_FOLLOW",
        timestamp=datetime.now(IST),
        lot_size=65,
        canonical_instrument_id="NIFTY_2026-09-29_22850_PE",
        fyers_symbol=sym,
    )
    trader._reconcile_active_trade_symbols()

    # ref_count should now be 2; no duplicate subscription needed
    assert trader._active_trade_symbols[sym] == 2
    trader.fyers.subscribe_trades_symbols.assert_not_called()

    # Strategy 1 exits its trade
    trader.fyers.reset_mock()
    trader.paper_trader.close_position(order1.order_id, price=110.0, timestamp=datetime.now(IST))
    trader._reconcile_active_trade_symbols()

    # CRITICAL: Strategy 2 is still holding it! Must NOT unsubscribe!
    assert trader._active_trade_symbols[sym] == 1
    trader.fyers.unsubscribe_trades_symbols.assert_not_called()

    # Strategy 2 now also exits its trade
    trader.paper_trader.close_position(order2.order_id, price=115.0, timestamp=datetime.now(IST))
    trader._reconcile_active_trade_symbols()

    # Now that all positions are closed, it should be unsubscribed
    assert sym not in trader._active_trade_symbols
    trader.fyers.unsubscribe_trades_symbols.assert_called_once_with([sym])

    # Re-entry: Strategy 1 re-enters the contract
    trader.fyers.reset_mock()
    order3 = trader.paper_trader.place_order(
        symbol="NIFTY22850PE",
        side="BUY",
        qty=1,
        price=120.0,
        strategy="STRATEGY_MOMENTUM",
        timestamp=datetime.now(IST),
        lot_size=65,
        canonical_instrument_id="NIFTY_2026-09-29_22850_PE",
        fyers_symbol=sym,
    )
    trader._reconcile_active_trade_symbols()

    # Should re-subscribe seamlessly
    assert trader._active_trade_symbols[sym] == 1
    trader.fyers.subscribe_trades_symbols.assert_called_once_with([sym])
