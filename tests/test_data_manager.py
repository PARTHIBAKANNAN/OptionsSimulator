from datetime import date, datetime, timedelta
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
    assert "stochastic_k_15m" in indicators
    assert "macd_histogram_15m" in indicators


def test_heikin_ashi_15m_present_once_enough_15min_bars_exist():
    dm = DataManager()
    for c in _synthetic_candles(1000):
        dm.replay_candle(c)

    indicators = dm.calculate_indicators()
    ha = indicators.get("heikin_ashi_15m")
    assert ha is not None
    for key in ("open", "high", "low", "close", "prev_open", "prev_close"):
        assert key in ha
    assert ha["high"] >= ha["open"]
    assert ha["high"] >= ha["close"]
    assert ha["low"] <= ha["open"]
    assert ha["low"] <= ha["close"]


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


def test_update_option_chain_stores_both_the_raw_fyers_symbol_and_the_simplified_key():
    # Regression: Fyers' real option symbols are date-coded ("NSE:NIFTY2681124600CE"), but
    # select_strike() generates the simplified "NIFTY24600CE" order.symbol actually uses
    # everywhere -- these never matched, so every live-mode price lookup (SL/TP/time-exit checks,
    # the UI's live LTP) silently missed and returned None forever. Confirmed against a real Fyers
    # optionchain response on 2026-08-06.
    dm = DataManager()
    chain_data = {"optionsChain": [
        {"symbol": "NSE:NIFTY50-INDEX", "strike_price": -1, "option_type": "", "ltp": 24627.4},
        {"symbol": "NSE:NIFTY2681124600CE", "strike_price": 24600, "option_type": "CE", "ltp": 172.1, "oi": 500},
        {"symbol": "NSE:NIFTY2681124600PE", "strike_price": 24600, "option_type": "PE", "ltp": 108.75, "oi": 300},
    ]}

    dm.update_option_chain(chain_data)
    chain = dm.get_option_chain()

    assert chain["NSE:NIFTY2681124600CE"].ltp == 172.1
    assert chain["NIFTY24600CE"].ltp == 172.1
    assert chain["NIFTY24600CE"].oi == 500
    assert chain["NIFTY24600PE"].ltp == 108.75
    assert "NSE:NIFTY50-INDEX" in chain
    assert "NIFTY-1CE" not in chain and "NIFTY-1PE" not in chain  # the index row itself, excluded


def test_window_size_trims_candles():
    dm = DataManager(window_size=50)
    for c in _synthetic_candles(200):
        dm.replay_candle(c)
    assert len(dm.candles) == 50


# ---- get_prev_close / get_today_candles: feed the NIFTY header's change/%/sparkline ----------

def test_get_prev_close_returns_the_last_candle_close_before_today():
    dm = DataManager()
    dm.replay_candle(Candle(timestamp=datetime(2026, 8, 4, 15, 29), open=24000, high=24005,
                             low=23995, close=24010, volume=1000))
    dm.replay_candle(Candle(timestamp=datetime(2026, 8, 5, 9, 15), open=24020, high=24025,
                             low=24015, close=24022, volume=1000))
    assert dm.get_prev_close(date(2026, 8, 5)) == 24010


def test_get_prev_close_none_without_any_earlier_day_data():
    dm = DataManager()
    dm.replay_candle(Candle(timestamp=datetime(2026, 8, 5, 9, 15), open=24020, high=24025,
                             low=24015, close=24022, volume=1000))
    assert dm.get_prev_close(date(2026, 8, 5)) is None


def test_get_today_candles_excludes_earlier_days_and_includes_the_forming_candle():
    dm = DataManager()
    dm.replay_candle(Candle(timestamp=datetime(2026, 8, 4, 15, 29), open=24000, high=24005,
                             low=23995, close=24010, volume=1000))
    dm.replay_candle(Candle(timestamp=datetime(2026, 8, 5, 9, 15), open=24020, high=24025,
                             low=24015, close=24022, volume=1000))
    dm.on_nifty_tick({"ltp": 24030, "volume": 50, "timestamp": datetime(2026, 8, 5, 9, 16)})

    today_candles = dm.get_today_candles(date(2026, 8, 5))

    assert len(today_candles) == 2  # the pushed 09:15 candle + the still-forming 09:16 one
    assert today_candles[0].close == 24022
    assert today_candles[1].close == 24030
