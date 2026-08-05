from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from src.data_manager import Candle, DataManager

IST = ZoneInfo("Asia/Kolkata")


def _synthetic_candles(n=200, start_price=24000.0):
    base = datetime(2026, 1, 1, 9, 15)
    candles = []
    price = start_price
    for i in range(n):
        price += 1 if i % 2 == 0 else -0.5
        candles.append(Candle(
            timestamp=base + timedelta(minutes=i),
            open=price, high=price + 2, low=price - 2, close=price,
            volume=1000 + (i % 5) * 100,
        ))
    return candles


def test_candle_built_from_ticks():
    dm = DataManager()
    ts = datetime(2026, 1, 1, 9, 15, 5)
    dm.on_nifty_tick({"ltp": 24000, "volume": 100, "timestamp": ts})
    dm.on_nifty_tick({"ltp": 24010, "volume": 50, "timestamp": ts + timedelta(seconds=10)})

    current = dm.get_current_candle()
    assert current.open == 24000
    assert current.high == 24010
    assert current.close == 24010
    assert current.volume == 150


def test_new_minute_pushes_previous_candle():
    dm = DataManager()
    ts = datetime(2026, 1, 1, 9, 15, 5)
    dm.on_nifty_tick({"ltp": 24000, "volume": 100, "timestamp": ts})
    dm.on_nifty_tick({"ltp": 24020, "volume": 100, "timestamp": ts + timedelta(minutes=1)})

    assert len(dm.candles) == 1
    assert dm.candles[0].close == 24000
    assert dm.get_current_candle().open == 24020


def test_indicators_calculated():
    dm = DataManager()
    for c in _synthetic_candles(1000):  # ~16.7 hours -> enough 1H bars for RSI(14)/EMA(50)/MACD(26)
        dm.replay_candle(c)

    indicators = dm.calculate_indicators()
    assert "rsi_1h" in indicators
    assert 0 <= indicators["rsi_1h"] <= 100
    assert "ema_20_1h" in indicators
    assert "macd_histogram_1h" in indicators


def test_indicators_survive_mixing_seeded_historical_and_live_tick_candles():
    # Regression: LiveTrader._seed_historical_candles() loads Fyers historical candles (pandas
    # Timestamps, tz-converted in FyersAPIClient.get_historical_data) and then on_tick() appends
    # live candles (plain datetime, tz from src.trader.IST) into the SAME DataManager.candles
    # list. If those two use different tz implementations (e.g. pandas' string-based tz_convert,
    # which resolves via pytz, vs on_tick's zoneinfo.ZoneInfo), pandas silently builds an
    # object-dtype Timestamp column instead of datetime64[ns, tz] once both are combined, and
    # .resample() then raises "Only valid with DatetimeIndex..." on every single tick -- breaking
    # every strategy's indicators for the rest of the session. See docs/ARCHITECTURE.md.
    dm = DataManager()
    base = pd.Timestamp(datetime(2026, 1, 1, 9, 15), tz=IST)
    historical_df = pd.DataFrame([
        {"Timestamp": base + timedelta(minutes=i), "Open": 24000 + i, "High": 24002 + i,
         "Low": 23998 + i, "Close": 24000.0 + i, "Volume": 1000}
        for i in range(999)
    ])
    dm.load_historical(historical_df)

    live_ts = datetime(2026, 1, 1, 9, 15, tzinfo=IST) + timedelta(minutes=999)
    dm.on_nifty_tick({"ltp": 25000, "volume": 500, "timestamp": live_ts})
    dm.on_nifty_tick({"ltp": 25010, "volume": 500, "timestamp": live_ts + timedelta(minutes=1)})

    indicators = dm.calculate_indicators()  # must not raise
    assert "rsi_1h" in indicators


def test_vol_regime_ratio_calculated_with_enough_history():
    dm = DataManager()
    for c in _synthetic_candles(2400):  # ~40 hours -> enough 1H bars for ATR(14) + its 20-bar average
        dm.replay_candle(c)

    indicators = dm.calculate_indicators()
    assert "vol_regime_ratio" in indicators
    assert indicators["vol_regime_ratio"] > 0


def test_vol_regime_ratio_absent_without_enough_history():
    dm = DataManager()
    for c in _synthetic_candles(1000):  # ~16.7 hours -> not enough for the 35-bar ATR warmup
        dm.replay_candle(c)

    indicators = dm.calculate_indicators()
    assert "vol_regime_ratio" not in indicators


def test_option_chain_tracks_quotes():
    dm = DataManager()
    dm.on_option_tick("NIFTY24500CE", {"ltp": 65.5, "bid": 65, "ask": 66, "oi": 1000})
    chain = dm.get_option_chain()
    assert chain["NIFTY24500CE"].ltp == 65.5
    assert chain["NIFTY24500CE"].oi == 1000


def test_window_size_trims_candles():
    dm = DataManager(window_size=50)
    for c in _synthetic_candles(200):
        dm.replay_candle(c)
    assert len(dm.candles) == 50
