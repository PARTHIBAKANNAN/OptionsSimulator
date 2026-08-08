from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.strategies.base_strategy import Signal
from src.trader import IST, LiveTrader, NIFTY_SYMBOL, SENSEX_SYMBOL, is_market_open


def _make_config(extra_risk_params: dict = None) -> Config:
    risk_params = {
        "position_sizing": {"qty_per_signal": 1, "lot_size": 65, "max_concurrent_positions": 5, "max_daily_loss": 5000},
        "exit_rules": {"stop_loss_pct": 20, "take_profit_pts": 150, "time_exit_mins": 120},
        "polling": {"option_chain_interval_secs": 10},
    }
    if extra_risk_params:
        risk_params.update(extra_risk_params)
    return Config(
        fyers_client_id="x", fyers_secret_key="x", fyers_fy_id="x", fyers_user_pin="x",
        fyers_totp_secret="x", fyers_redirect_uri="https://example.com/callback",
        telegram_bot_token="", telegram_chat_id="", force_market_open=False,
        risk_params=risk_params,
    )


def test_auto_mode_defaults_to_true_when_unconfigured():
    trader = LiveTrader(_make_config())
    assert trader.auto_mode is True


def test_auto_mode_can_be_disabled():
    trader = LiveTrader(_make_config({"live_mode": {"auto_approve": False}}))
    assert trader.auto_mode is False


def test_circuit_breaker_config_wired_into_paper_trader():
    trader = LiveTrader(_make_config({
        "circuit_breaker": {
            "consecutive_loss_limit": 3, "consecutive_loss_cooldown_days": 1,
            "max_drawdown_pct_of_capital": 25, "drawdown_cooldown_days": 3,
            "drawdown_breaker_grace_trades": 3,
        },
    }))
    assert trader.paper_trader.consecutive_loss_limit == 3
    assert trader.paper_trader.max_drawdown_pct_of_capital == 25
    assert trader.paper_trader.drawdown_breaker_grace_trades == 3


def test_circuit_breaker_disabled_without_config_section():
    trader = LiveTrader(_make_config())
    assert trader.paper_trader.consecutive_loss_limit is None
    assert trader.paper_trader.max_drawdown_pct_of_capital is None


@pytest.mark.asyncio
async def test_execute_signal_auto_approves_without_telegram_wait():
    # No telegram configured (empty token) either way, but this confirms the auto_mode path
    # doesn't require a telegram approval decision at all -- it places the order directly.
    trader = LiveTrader(_make_config())
    signal = Signal(
        strategy="TEST", direction="CE", action="BUY", strike="NIFTY24500CE",
        confidence=0.75, rationale="test", entry_price=100.0, timestamp=datetime(2026, 5, 8, 10, 0),
    )
    await trader.execute_signal(signal)
    assert len(trader.paper_trader.get_positions()) == 1


def test_is_market_open_requires_ist_aware_datetime():
    # 2026-08-04 is a Tuesday. Regression coverage for the real bug: the deploy VM's system
    # clock runs UTC, so callers must build `now` via datetime.now(IST), never bare
    # datetime.now() -- a naive "09:15" is only correct if it actually represents IST.
    risk_params = {"market_hours": {"start": "09:15", "end": "15:30"}}
    assert is_market_open(datetime(2026, 8, 4, 9, 15, tzinfo=IST), risk_params) is True
    assert is_market_open(datetime(2026, 8, 4, 12, 0, tzinfo=IST), risk_params) is True
    assert is_market_open(datetime(2026, 8, 4, 15, 30, tzinfo=IST), risk_params) is True
    assert is_market_open(datetime(2026, 8, 4, 9, 14, tzinfo=IST), risk_params) is False
    assert is_market_open(datetime(2026, 8, 4, 15, 31, tzinfo=IST), risk_params) is False


def test_is_market_open_false_on_weekend():
    risk_params = {"market_hours": {"start": "09:15", "end": "15:30"}}
    saturday = datetime(2026, 8, 8, 10, 0, tzinfo=IST)  # 2026-08-08 is a Saturday
    assert is_market_open(saturday, risk_params) is False


def _make_trader_with_mock_fyers(extra_risk_params: dict = None) -> LiveTrader:
    trader = LiveTrader(_make_config(extra_risk_params))
    trader.fyers = MagicMock()
    trader.fyers.access_token = None
    trader.fyers.refresh_access_token.return_value = True
    trader.fyers.get_historical_data.return_value = []
    return trader


def test_ensure_connection_state_does_not_login_before_daily_login_time():
    trader = _make_trader_with_mock_fyers()
    early = datetime(2026, 8, 4, 8, 30, tzinfo=IST)  # Tuesday, before 08:50
    market_open = trader.ensure_connection_state(early)
    assert market_open is False
    trader.fyers.refresh_access_token.assert_not_called()
    assert trader._connected is False


def test_ensure_connection_state_logs_in_at_daily_login_time_but_market_still_closed():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token-after-refresh"
    just_after_login_time = datetime(2026, 8, 4, 8, 55, tzinfo=IST)
    market_open = trader.ensure_connection_state(just_after_login_time)
    assert market_open is False
    trader.fyers.refresh_access_token.assert_called_once()
    # Logged in, but market isn't open yet -- must not connect the websocket this early.
    trader.fyers.start_websocket.assert_not_called()
    assert trader._connected is False


def test_ensure_connection_state_connects_once_market_opens():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token"
    trader._last_login_date = datetime(2026, 8, 4, tzinfo=IST).date()  # already logged in today

    market_open = trader.ensure_connection_state(datetime(2026, 8, 4, 9, 15, tzinfo=IST))

    assert market_open is True
    trader.fyers.start_websocket.assert_called_once()
    trader.fyers.subscribe_symbols.assert_called_once()
    assert trader._connected is True


def test_ensure_connection_state_disconnects_after_market_close():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token"
    trader._last_login_date = datetime(2026, 8, 4, tzinfo=IST).date()
    trader._connected = True

    market_open = trader.ensure_connection_state(datetime(2026, 8, 4, 15, 35, tzinfo=IST))

    assert market_open is False
    trader.fyers.stop_websocket.assert_called_once()
    assert trader._connected is False


def test_ensure_connection_state_only_logs_in_once_per_day():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token"
    trader.ensure_connection_state(datetime(2026, 8, 4, 8, 55, tzinfo=IST))
    trader.ensure_connection_state(datetime(2026, 8, 4, 9, 30, tzinfo=IST))
    trader.ensure_connection_state(datetime(2026, 8, 4, 14, 0, tzinfo=IST))
    assert trader.fyers.refresh_access_token.call_count == 1


def test_ensure_connection_state_retries_login_after_a_failure():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.refresh_access_token.return_value = False  # simulate a failed login attempt

    trader.ensure_connection_state(datetime(2026, 8, 4, 8, 55, tzinfo=IST))
    assert trader._last_login_date is None  # not marked done, so it will retry
    trader.ensure_connection_state(datetime(2026, 8, 4, 8, 56, tzinfo=IST))

    assert trader.fyers.refresh_access_token.call_count == 2
    trader.fyers.start_websocket.assert_not_called()  # never got a token, never connects


def test_ensure_connection_state_force_market_open_bypasses_the_wall_clock():
    trader = _make_trader_with_mock_fyers({"live_mode": {"auto_approve": True}})
    trader.config.force_market_open = True
    trader.fyers.access_token = "token"

    saturday_predawn = datetime(2026, 8, 8, 3, 0, tzinfo=IST)
    market_open = trader.ensure_connection_state(saturday_predawn)

    assert market_open is True
    trader.fyers.refresh_access_token.assert_called_once()
    trader.fyers.start_websocket.assert_called_once()


def test_ensure_connection_state_seeds_historical_candles_before_market_opens():
    # Regression: the dashboard had nothing to show (no NIFTY price at all) outside market hours
    # because historical seeding only ever ran once the websocket connected at market-open.
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token-after-refresh"  # already logged in, market still shut

    market_open = trader.ensure_connection_state(datetime(2026, 8, 4, 8, 55, tzinfo=IST))

    assert market_open is False
    assert trader.fyers.get_historical_data.call_count == 2  # once each for NIFTY and SENSEX
    trader.fyers.start_websocket.assert_not_called()  # still shouldn't connect the live stream


def test_ensure_connection_state_only_seeds_historical_candles_once_per_day():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.access_token = "token"

    trader.ensure_connection_state(datetime(2026, 8, 4, 8, 55, tzinfo=IST))
    trader.ensure_connection_state(datetime(2026, 8, 4, 9, 15, tzinfo=IST))
    trader.ensure_connection_state(datetime(2026, 8, 4, 14, 0, tzinfo=IST))

    assert trader.fyers.get_historical_data.call_count == 2  # once each for NIFTY and SENSEX, not re-triggered


def test_on_tick_routes_index_ticks_to_the_matching_data_manager():
    trader = LiveTrader(_make_config())
    trader.on_tick({"symbol": NIFTY_SYMBOL, "ltp": 24500.0, "vol_traded_today": 1000})
    trader.on_tick({"symbol": SENSEX_SYMBOL, "ltp": 81500.0, "vol_traded_today": 500})

    assert trader.data_managers["NIFTY"].get_state()["nifty_price"] == 24500.0
    assert trader.data_managers["SENSEX"].get_state()["nifty_price"] == 81500.0


def test_on_tick_routes_option_ticks_by_exchange_prefix():
    trader = LiveTrader(_make_config())
    trader.on_tick({"symbol": "NSE:NIFTY2681124600CE", "ltp": 172.1})
    trader.on_tick({"symbol": "BSE:SENSEX2681181500CE", "ltp": 250.0})

    assert trader.data_managers["NIFTY"].get_option_chain()["NSE:NIFTY2681124600CE"].ltp == 172.1
    assert trader.data_managers["SENSEX"].get_option_chain()["BSE:SENSEX2681181500CE"].ltp == 250.0


def test_on_tick_drops_a_tick_with_an_unrecognized_exchange_prefix():
    trader = LiveTrader(_make_config())
    trader.on_tick({"symbol": "XYZ:SOMETHING24500CE", "ltp": 100.0})  # must not raise

    assert trader.data_managers["NIFTY"].get_option_chain() == {}
    assert trader.data_managers["SENSEX"].get_option_chain() == {}


def test_on_market_closed_tick_is_a_noop_on_the_base_cli_trader():
    trader = _make_trader_with_mock_fyers()
    trader._on_market_closed_tick()  # must not raise


@pytest.mark.asyncio
async def test_poll_option_chain_only_subscribes_to_real_fyers_symbols():
    # Regression: update_option_chain() now stores both the raw Fyers symbol and a simplified
    # "NIFTY24600CE" key (see DataManager) -- only the raw one is ever valid to hand to Fyers'
    # own subscribe_symbols(); passing the simplified key would try to subscribe to a symbol
    # that doesn't exist on the exchange at all.
    trader = _make_trader_with_mock_fyers()
    trader.fyers.get_option_chain.return_value = {"optionsChain": [
        {"symbol": "NSE:NIFTY2681124600CE", "strike_price": 24600, "option_type": "CE", "ltp": 172.1},
    ]}

    await trader.poll_option_chain()

    trader.fyers.subscribe_symbols.assert_called_once()
    subscribed = trader.fyers.subscribe_symbols.call_args.args[0]
    assert subscribed == ["NSE:NIFTY2681124600CE"]


@pytest.mark.asyncio
async def test_poll_option_chain_does_not_resubscribe_already_monitored_symbols():
    trader = _make_trader_with_mock_fyers()
    trader.fyers.get_option_chain.return_value = {"optionsChain": [
        {"symbol": "NSE:NIFTY2681124600CE", "strike_price": 24600, "option_type": "CE", "ltp": 172.1},
    ]}

    await trader.poll_option_chain()
    trader.fyers.subscribe_symbols.reset_mock()
    await trader.poll_option_chain()

    trader.fyers.subscribe_symbols.assert_not_called()
