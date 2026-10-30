from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pytest

from src.data_manager import DataManager, Candle
from src.market_data.contract_master import ContractMaster
from src.strategies.base_strategy import BaseStrategy


def test_contract_master_futures_indexing():
    cm = ContractMaster()
    cm.load_contracts()

    # Verify active futures are loaded for all 3 indices
    for und in ("NIFTY", "BANKNIFTY", "SENSEX"):
        fut = cm.get_active_future(und)
        assert fut is not None, f"Active future missing for {und}"
        assert fut.option_type == "FUT"
        assert fut.strike == 0.0
        assert fut.expiry >= datetime.now(ZoneInfo("Asia/Kolkata")).date()
        # Test reverse lookup
        assert cm.get_underlying_for_future_token(fut.token) == und


def test_data_manager_future_tick_accumulation():
    dm = DataManager(underlying="NIFTY")
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 10, 30, 9, 30, tzinfo=ist)

    # 1. Spot tick arrives with 0 volume (standard Alice Blue index feed)
    dm.on_tick(price=23000.0, volume=0, timestamp=now)
    assert dm.candles == []
    assert dm._current is not None
    assert dm._current.close == 23000.0
    assert dm._current.volume == 0

    # 2. Future tick arrives with cumulative volume 50000
    dm.on_future_tick(ltp=23050.0, volume=50000, timestamp=now + timedelta(seconds=5))
    # First tick establishes baseline; delta is 0
    assert dm._current.volume == 0

    # 3. Subsequent future tick arrives with cumulative volume 52500 (volume surge +2500)
    dm.on_future_tick(ltp=23055.0, volume=52500, timestamp=now + timedelta(seconds=15))
    assert dm._current.volume == 2500
    assert dm._current.delta == 2500.0  # Uptick from 23050 to 23055

    # 4. Another future tick arrives on downtick (23055 -> 23052, +1000 lots)
    dm.on_future_tick(ltp=23052.0, volume=53500, timestamp=now + timedelta(seconds=30))
    assert dm._current.volume == 3500
    assert dm._current.delta == 1500.0  # 2500 - 1000 = 1500


def test_macd_hist_keys_and_vwap_generation():
    dm = DataManager(underlying="NIFTY")
    ist = ZoneInfo("Asia/Kolkata")
    base_time = datetime(2026, 10, 30, 9, 15, tzinfo=ist)

    # Populate 30 closed 1-minute bars with futures volume
    for i in range(30):
        t = base_time + timedelta(minutes=i)
        price = 23000.0 + i * 2.0
        c = Candle(timestamp=t, open=price - 1, high=price + 2, low=price - 2, close=price,
                   volume=1000 + i * 50, delta=200.0)
        dm.candles.append(c)

    # Set live candle
    dm._current = Candle(timestamp=base_time + timedelta(minutes=30), open=23060, high=23065, low=23058, close=23062, volume=1500)
    dm._future_live_ltp = 23080.0
    dm._future_volume_today = 85000

    state = dm.get_state()
    indicators = state["indicators"]

    # Verify both macd_hist_5m and macd_histogram_5m exist and match
    assert "macd_hist_5m" in indicators
    assert "macd_histogram_5m" in indicators
    assert indicators["macd_hist_5m"] == indicators["macd_histogram_5m"]

    # Verify true VWAP was computed with volume
    assert "vwap_5m" in indicators
    assert indicators["vwap_5m"] > 23000.0
    assert "future_ltp" in indicators
    assert indicators["future_ltp"] == 23080.0


def test_dynamic_regime_and_1m_scalp_filters():
    # 1. 1M Scalp confirmed when aligned with 5M trend
    bullish_state = {
        "nifty_price": 23100.0,
        "indicators": {
            "supertrend_10_3_direction": 1.0,  # Bullish
            "ema_20_5m": 23050.0,
        }
    }
    assert BaseStrategy.is_scalp_1m_confirmed(bullish_state, "CE") is True
    assert BaseStrategy.is_scalp_1m_confirmed(bullish_state, "PE") is False

    bearish_state = {
        "nifty_price": 23000.0,
        "indicators": {
            "supertrend_10_3_direction": -1.0,  # Bearish
            "ema_20_5m": 23050.0,
        }
    }
    assert BaseStrategy.is_scalp_1m_confirmed(bearish_state, "PE") is True
    assert BaseStrategy.is_scalp_1m_confirmed(bearish_state, "CE") is False

    # 2. Chop free rejects low ADX
    choppy_state = {
        "indicators": {"adx_14_5m": 16.5}
    }
    now = datetime(2026, 10, 30, 13, 0)
    assert BaseStrategy.is_chop_free(choppy_state, now) is False

    trending_state = {
        "indicators": {"adx_14_5m": 28.0},
        "candles": [Candle(timestamp=now, open=23000, high=23050, low=22995, close=23045, volume=5000)]
    }
    assert BaseStrategy.is_chop_free(trending_state, now) is True

