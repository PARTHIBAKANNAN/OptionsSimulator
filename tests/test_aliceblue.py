import pytest
from datetime import date
from src.market_data.contract_master import ContractMaster
from src.market_data.instrument_registry import InstrumentRegistry
from src.market_data.quote_store import QuoteStore
from src.brokers.aliceblue_client import AliceBlueClient


def test_contract_master_corridor_generation():
    cm = ContractMaster()
    cm.load_contracts()

    # Verify active expiries are populated
    assert "NIFTY" in cm._active_expiry_by_underlying
    assert "BANKNIFTY" in cm._active_expiry_by_underlying
    assert "SENSEX" in cm._active_expiry_by_underlying

    # Test corridor generation for 15 strikes each side
    spot_prices = {"NIFTY": 22500.0, "BANKNIFTY": 55200.0, "SENSEX": 81000.0}
    corridor = cm.get_corridor_tokens(spot_prices, strikes_each_side=15)

    # 3 index spots + (31 * 2 * 3) options = ~189 tokens
    assert len(corridor) >= 180
    assert ("NSE", 26000) in corridor
    assert ("NSE", 26009) in corridor
    assert ("BSE", 1) in corridor


def test_contract_master_alias_lookup():
    cm = ContractMaster()
    cm.load_contracts()

    token = cm.get_token_by_alias("NIFTY22500CE")
    assert token is not None
    assert isinstance(token, int)

    meta = cm.get_by_token(token)
    assert meta is not None
    assert meta.underlying == "NIFTY"
    assert meta.strike == 22500.0
    assert meta.option_type == "CE"


def test_aliceblue_client_tick_dispatch():
    registry = InstrumentRegistry()
    quote_store = QuoteStore()
    client = AliceBlueClient(
        user_id="2628887",
        session_token="fake.jwt.token",
        quote_store=quote_store,
        instrument_registry=registry,
    )
    client.contract_master.load_contracts()
    client._sync_instruments_to_registry()

    token = client.contract_master.get_token_by_alias("NIFTY22500CE")
    assert token is not None

    # Simulate incoming tick for this token
    mock_tick = {
        "t": "tk",
        "tk": str(token),
        "lp": "189.20",
        "bp1": "189.15",
        "sp1": "189.25",
        "v": "5000",
        "oi": "250000",
    }
    client._on_ws_tick(mock_tick)

    # Verify snapshot reached QuoteStore
    meta = client.contract_master.get_by_token(token)
    snap = quote_store.get_snapshot(meta.canonical_id)
    assert snap is not None
    assert snap.ltp == 189.20
    assert snap.bid == 189.15
    assert snap.ask == 189.25
    assert snap.source == "ws"
