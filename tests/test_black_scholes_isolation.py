"""
Unit tests for Black-Scholes isolation in live trading.
"""
from datetime import datetime
import pytest

from src.data_manager import OptionQuote
from src.market_data.quote_store import QuoteSnapshot
from src.strategies.base_strategy import BaseStrategy


class DummyStrategy(BaseStrategy):
    def evaluate(self, data_state: dict):
        return None


def test_black_scholes_isolated_in_live_mode():
    strat = DummyStrategy(name="TEST_STRAT", direction="CE", strike_step=50, underlying="NIFTY")

    # 1. In backtest mode (is_live = False), missing quote falls back to theoretical BS price
    backtest_state = {
        "is_live": False,
        "spot_price": 24000.0,
        "option_chain": {},
        "timestamp": datetime(2026, 9, 21, 10, 0),
    }
    bs_price = strat.get_option_price(
        symbol="NIFTY24000CE",
        strike=24000.0,
        spot_price=24000.0,
        option_type="CE",
        data_state=backtest_state,
    )
    assert bs_price is not None
    assert bs_price > 0.0

    # 2. In live mode (is_live = True), missing quote strictly returns None (ZERO synthetic fill)
    live_state_missing = {
        "is_live": True,
        "spot_price": 24000.0,
        "option_chain": {},
        "timestamp": datetime(2026, 9, 21, 10, 0),
    }
    live_price_missing = strat.get_option_price(
        symbol="NIFTY24000CE",
        strike=24000.0,
        spot_price=24000.0,
        option_type="CE",
        data_state=live_state_missing,
    )
    assert live_price_missing is None

    # 3. In live mode with real quote present, returns real LTP
    quote = OptionQuote(symbol="NIFTY24000CE", ltp=185.50, bid=185.0, ask=186.0)
    live_state_present = {
        "is_live": True,
        "spot_price": 24000.0,
        "option_chain": {"NIFTY24000CE": quote},
        "timestamp": datetime(2026, 9, 21, 10, 0),
    }
    live_price_present = strat.get_option_price(
        symbol="NIFTY24000CE",
        strike=24000.0,
        spot_price=24000.0,
        option_type="CE",
        data_state=live_state_present,
    )
    assert live_price_present == 185.50
