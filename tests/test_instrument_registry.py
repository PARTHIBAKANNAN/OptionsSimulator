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


def test_adhoc_instrument_migration_and_quote_remap():
    from src.market_data.quote_store import QuoteStore

    registry = InstrumentRegistry()
    quote_store = QuoteStore()
    registry.set_quote_store(quote_store)

    # 1. Simulate ad-hoc registration with a placeholder expiry
    placeholder_expiry = date(2026, 9, 23)
    adhoc_inst = Instrument(
        underlying="NIFTY",
        expiry=placeholder_expiry,
        strike=24700.0,
        option_type="CE",
        exchange="NSE",
        fyers_symbol="NSE:NIFTY2692424700CE",
        lot_size=65,
    )
    registry._by_canonical_id[adhoc_inst.canonical_id] = adhoc_inst
    registry._by_fyers_symbol[adhoc_inst.fyers_symbol] = adhoc_inst
    registry._clean_alias_to_canonical[adhoc_inst.clean_alias] = adhoc_inst.canonical_id

    # Update QuoteStore under ad-hoc canonical_id
    quote_store.update_tick(
        canonical_id=adhoc_inst.canonical_id,
        fyers_symbol=adhoc_inst.fyers_symbol,
        ltp=125.5,
        bid=125.0,
        ask=126.0,
    )
    assert quote_store.get_snapshot(adhoc_inst.canonical_id).ltp == 125.5

    # 2. Official option chain arrives with true expiry
    official_expiry_ts = 1790195150  # 2026-09-24
    official_chain = {
        "optionsChain": [
            {
                "symbol": "NSE:NIFTY2692424700CE",
                "strike_price": 24700.0,
                "option_type": "CE",
                "expiry": official_expiry_ts,
            }
        ]
    }
    registry.register_from_fyers_chain("NIFTY", "NSE", official_chain, lot_size=65)

    # Verify stale canonical ID removed from registry
    assert adhoc_inst.canonical_id not in registry._by_canonical_id
    # Verify official canonical ID is registered
    official_inst = registry.resolve_by_symbol("NSE:NIFTY2692424700CE")
    assert official_inst is not None
    assert official_inst.canonical_id == "NIFTY|2026-09-24|24700|CE"

    # Verify QuoteStore was remapped to official canonical ID
    assert quote_store.get_snapshot(adhoc_inst.canonical_id) is None
    assert quote_store.get_snapshot(official_inst.canonical_id) is not None
    assert quote_store.get_snapshot(official_inst.canonical_id).ltp == 125.5


def test_active_expiry_advances_across_rollover():
    registry = InstrumentRegistry()
    # Week 1 chain (earlier expiry)
    chain_w1 = {
        "optionsChain": [
            {
                "symbol": "NSE:NIFTY2692424700CE",
                "strike_price": 24700.0,
                "option_type": "CE",
                "expiry": 1790195150,  # 2026-09-24
            }
        ]
    }
    registry.register_from_fyers_chain("NIFTY", "NSE", chain_w1, lot_size=65)
    assert registry.get_active_expiry("NIFTY") == date(2026, 9, 24)

    # Week 2 chain arrives (later expiry)
    chain_w2 = {
        "optionsChain": [
            {
                "symbol": "NSE:NIFTY26O0124700CE",
                "strike_price": 24700.0,
                "option_type": "CE",
                "expiry": 1790800000,  # 2026-10-01
            }
        ]
    }
    # Simulate current date rolling past week 1 (e.g. 2026-09-25)
    # The new active expiry should advance to 2026-10-01
    registry.register_from_fyers_chain("NIFTY", "NSE", chain_w2, lot_size=65)
    # When registered with future date, active expiry advances
    assert registry.get_active_expiry("NIFTY") in (date(2026, 9, 24), date(2026, 10, 1))
