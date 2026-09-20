"""
Unit tests for QuoteValidator.
"""
import time
import pytest

from src.market_data.quote_store import QuoteSnapshot
from src.market_data.quote_validator import QuoteValidator, ValidationIntent


def test_validator_rejections():
    validator = QuoteValidator(entry_max_age_ms=500.0, exit_max_age_ms=2000.0, max_spread_bps=800)

    # 1. No quote
    valid, code, price = validator.validate(None, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is False
    assert code == "REJECTED_NO_QUOTE"

    # 2. Stale quote
    stale_snap = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=150.0,
        bid=149.5,
        ask=150.5,
        open_interest=1000,
        volume=5000,
        exchange_timestamp=time.time() - 2.0,
        receive_epoch_timestamp=time.time() - 2.0,
        receive_monotonic_timestamp=time.monotonic() - 1.0,  # 1000ms old (> 500ms limit)
        version=1,
    )
    valid, code, price = validator.validate(stale_snap, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is False
    assert code == "REJECTED_STALE_QUOTE"

    # 3. Invalid / 0 LTP
    zero_ltp_snap = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=0.0,
        bid=149.5,
        ask=150.5,
        open_interest=1000,
        volume=5000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=1,
    )
    valid, code, price = validator.validate(zero_ltp_snap, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is False
    assert code == "REJECTED_INVALID_LTP"

    # 4. No Ask for BUY
    no_ask_snap = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=150.0,
        bid=149.5,
        ask=0.0,
        open_interest=1000,
        volume=5000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=1,
    )
    valid, code, price = validator.validate(no_ask_snap, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is False
    assert code == "REJECTED_NO_ASK"

    # 5. Excessive spread (> 800 bps = 8%)
    # Ask=100, Bid=90 => spread = (100-90)/100 = 10% = 1000 bps > 800 bps
    wide_spread_snap = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=95.0,
        bid=90.0,
        ask=100.0,
        open_interest=1000,
        volume=5000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=1,
    )
    valid, code, price = validator.validate(wide_spread_snap, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is False
    assert code == "REJECTED_EXCESSIVE_SPREAD"


def test_validator_success_paths():
    validator = QuoteValidator(entry_max_age_ms=500.0, exit_max_age_ms=2000.0, max_spread_bps=800)

    good_snap = QuoteSnapshot(
        canonical_id="NIFTY|2026-09-24|24500|CE",
        fyers_symbol="NSE:NIFTY26SEP24500CE",
        ltp=150.25,
        bid=150.00,
        ask=150.50,
        open_interest=10000,
        volume=50000,
        exchange_timestamp=time.time(),
        receive_epoch_timestamp=time.time(),
        receive_monotonic_timestamp=time.monotonic(),
        version=5,
    )

    # Valid BUY -> fills at Ask
    valid, code, exec_price = validator.validate(good_snap, side="BUY", intent=ValidationIntent.NEW_ENTRY)
    assert valid is True
    assert code is None
    assert exec_price == 150.50

    # Valid SELL -> fills at Bid
    valid, code, exec_price = validator.validate(good_snap, side="SELL", intent=ValidationIntent.EXIT)
    assert valid is True
    assert code is None
    assert exec_price == 150.00

    # Valid EVALUATION -> returns LTP
    valid, code, exec_price = validator.validate(good_snap, side="", intent=ValidationIntent.EVALUATION)
    assert valid is True
    assert code is None
    assert exec_price == 150.25
