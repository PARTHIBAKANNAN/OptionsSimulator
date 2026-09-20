"""
Unit tests for InstrumentRegistry and Instrument dataclass.
"""
from datetime import date
import pytest

from src.market_data.instrument_registry import Instrument, InstrumentRegistry


@pytest.fixture
def fyers_chain_fixture():
    return {
        "s": "ok",
        "code": 200,
        "message": "success",
        "data": {
            "expiryData": [
                {"date": "24-Sep-2026", "expiry": 1789935950},
                {"date": "01-Oct-2026", "expiry": 1790540750},
            ],
            "optionsChain": [
                {
                    "symbol": "NSE:BANKNIFTY26SEP56000CE",
                    "strike_price": 56000.0,
                    "option_type": "CE",
                    "expiry": 1789935950,
                    "ltp": 320.45,
                    "bid": 320.20,
                    "ask": 320.60,
                    "volume": 254100,
                    "oi": 128450,
                },
                {
                    "symbol": "NSE:BANKNIFTY26SEP56000PE",
                    "strike_price": 56000.0,
                    "option_type": "PE",
                    "expiry": 1789935950,
                    "ltp": 285.10,
                    "bid": 284.85,
                    "ask": 285.30,
                    "volume": 312000,
                    "oi": 154200,
                },
                {
                    "symbol": "NSE:BANKNIFTY26SEP56100CE",
                    "strike_price": 56100.0,
                    "option_type": "CE",
                    "expiry": 1789935950,
                    "ltp": 260.00,
                    "bid": 259.50,
                    "ask": 260.50,
                    "volume": 150000,
                    "oi": 90000,
                },
                {
                    "symbol": "NSE:BANKNIFTY26SEP56100PE",
                    "strike_price": 56100.0,
                    "option_type": "PE",
                    "expiry": 1789935950,
                    "ltp": 340.00,
                    "bid": 339.50,
                    "ask": 340.50,
                    "volume": 180000,
                    "oi": 110000,
                },
            ],
        },
    }


def test_instrument_canonical_id():
    inst = Instrument(
        underlying="BANKNIFTY",
        expiry=date(2026, 9, 24),
        strike=56000.0,
        option_type="CE",
        exchange="NSE",
        fyers_symbol="NSE:BANKNIFTY26SEP56000CE",
        lot_size=30,
    )
    assert inst.canonical_id == "BANKNIFTY|2026-09-24|56000|CE"
    assert inst.clean_alias == "BANKNIFTY56000CE"


def test_register_from_fyers_chain(fyers_chain_fixture):
    registry = InstrumentRegistry()
    registered = registry.register_from_fyers_chain(
        underlying="BANKNIFTY",
        exchange="NSE",
        chain_data=fyers_chain_fixture["data"],
        lot_size=30,
    )
    assert len(registered) == 4
    assert registry.get_active_expiry("BANKNIFTY") == date(2026, 9, 21)

    # Resolution checks
    inst_ce = registry.resolve_by_clean_alias("BANKNIFTY56000CE")
    assert inst_ce is not None
    assert inst_ce.canonical_id == "BANKNIFTY|2026-09-21|56000|CE"
    assert inst_ce.fyers_symbol == "NSE:BANKNIFTY26SEP56000CE"

    inst_sym = registry.resolve_by_symbol("NSE:BANKNIFTY26SEP56000PE")
    assert inst_sym is not None
    assert inst_sym.option_type == "PE"


def test_strike_coverage_verification():
    registry = InstrumentRegistry()
    # Build 31 strikes around 56000 (depth=15 => 54500 to 57500)
    options = []
    for k in range(-15, 16):
        strike = 56000 + k * 100
        options.append({
            "symbol": f"NSE:BANKNIFTY26SEP{strike}CE",
            "strike_price": float(strike),
            "option_type": "CE",
            "expiry": 1789935950,
        })
        options.append({
            "symbol": f"NSE:BANKNIFTY26SEP{strike}PE",
            "strike_price": float(strike),
            "option_type": "PE",
            "expiry": 1789935950,
        })

    registry.register_from_fyers_chain(
        underlying="BANKNIFTY",
        exchange="NSE",
        chain_data={"optionsChain": options, "expiryData": [{"expiry": 1789935950}]},
        lot_size=30,
    )

    is_covered, missing_ce, missing_pe = registry.verify_strategy_coverage(
        underlying="BANKNIFTY",
        spot_price=56020.0,
        strike_step=100,
        depth=15,
    )
    assert is_covered is True
    assert len(missing_ce) == 0
    assert len(missing_pe) == 0

    # Test missing strike coverage detection
    is_covered_deep, missing_ce_deep, _ = registry.verify_strategy_coverage(
        underlying="BANKNIFTY",
        spot_price=56020.0,
        strike_step=100,
        depth=20,  # exceeds registered 15
    )
    assert is_covered_deep is False
    assert len(missing_ce_deep) > 0
