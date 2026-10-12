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


def test_aliceblue_session_date_rollover_rejection(tmp_path):
    import json
    import base64
    import time
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

    cache_file = tmp_path / "aliceblue_token.json"
    yesterday = datetime.now(IST) - timedelta(days=1)
    
    # Create fake JWT with iat from yesterday but exp in future
    header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
    payload = base64.b64encode(json.dumps({
        "userId": "2628887",
        "iat": int(yesterday.timestamp()),
        "exp": int(time.time() + 3600),
    }).encode()).decode()
    fake_token = f"{header}.{payload}.signature"

    cache_file.write_text(json.dumps({
        "user_session": fake_token,
        "date": yesterday.date().isoformat(),
        "updated_at": yesterday.isoformat(),
    }), encoding="utf-8")

    client = AliceBlueClient(
        user_id="2628887",
        token_cache_path=cache_file,
    )
    # Must reject yesterday's cached token
    assert client._restore_session() is False
    assert client.is_authenticated is False


def test_aliceblue_session_same_day_restore(tmp_path):
    import json
    import base64
    import time
    from datetime import datetime
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

    cache_file = tmp_path / "aliceblue_token.json"
    today = datetime.now(IST)
    
    header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
    payload = base64.b64encode(json.dumps({
        "userId": "2628887",
        "iat": int(today.timestamp()),
        "exp": int(time.time() + 3600),
    }).encode()).decode()
    fake_token = f"{header}.{payload}.signature"

    cache_file.write_text(json.dumps({
        "user_session": fake_token,
        "date": today.date().isoformat(),
        "updated_at": today.isoformat(),
    }), encoding="utf-8")

    client = AliceBlueClient(
        user_id="2628887",
        token_cache_path=cache_file,
    )
    # Must restore today's cached token
    assert client._restore_session() is True
    assert client.is_authenticated is True


def test_aliceblue_auto_login_flow_with_totp_key(tmp_path, monkeypatch):
    import base64
    import time
    from unittest.mock import MagicMock
    import pyotp

    # Generate test TOTP key
    test_totp_key = pyotp.random_base32()
    client = AliceBlueClient(
        user_id="2628887",
        password="MySecretPassword123",
        totp_key=test_totp_key,
        token_cache_path=tmp_path / "aliceblue_token.json",
    )

    # Mock requests.Session
    mock_session = MagicMock()
    
    # Step 1: verify/user response
    r1 = MagicMock(status_code=200)
    r1.json.return_value = {"status": "success"}

    # Step 2: enckey response
    r2 = MagicMock(status_code=200)
    r2.json.return_value = {"result": [{"encKey": "mock_encryption_key_12345"}]}

    # Step 3: pwd/validate response
    r3 = MagicMock(status_code=200)
    r3.json.return_value = {"result": [{"token": "step3_web_token_abc"}]}

    from datetime import datetime
    from zoneinfo import ZoneInfo
    import json
    today = datetime.now(ZoneInfo("Asia/Kolkata"))
    header = base64.b64encode(b'{"alg":"HS256"}').decode()
    payload = base64.b64encode(json.dumps({"userId": "2628887", "iat": int(today.timestamp()), "exp": int(time.time() + 86400)}).encode()).decode()
    access_token = f"{header}.{payload}.signature"

    r4 = MagicMock(status_code=200)
    r4.json.return_value = {"result": [{"accessToken": access_token}]}

    mock_session.post.side_effect = [r1, r2, r3, r4]
    monkeypatch.setattr("requests.Session", lambda: mock_session)

    # Auto-login with totp=None should auto-generate TOTP code and succeed
    success = client.authenticate(totp=None)
    assert success is True
    assert client.is_authenticated is True
    assert client._user_session == access_token
    assert (tmp_path / "aliceblue_token.json").exists()


def test_aliceblue_auto_login_failure_falls_back_to_unauthenticated(tmp_path):
    client = AliceBlueClient(
        user_id="2628887",
        password="MySecretPassword123",
        totp_key="",  # No TOTP key configured
        token_cache_path=tmp_path / "aliceblue_token.json",
    )
    # When auto-login runs without TOTP key, it should fail gracefully
    success = client.authenticate(totp=None)
    assert success is False
    assert client.is_authenticated is False
