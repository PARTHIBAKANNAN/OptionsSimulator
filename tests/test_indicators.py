import pandas as pd
import pytest

from src.utils.indicators import heikin_ashi


def test_heikin_ashi_first_candle_seeds_open_from_its_own_open_and_close():
    df = pd.DataFrame({"Open": [100.0], "High": [105.0], "Low": [98.0], "Close": [104.0]})
    ha = heikin_ashi(df)

    assert ha["ha_close"].iloc[0] == pytest.approx((100 + 105 + 98 + 104) / 4)
    assert ha["ha_open"].iloc[0] == pytest.approx((100 + 104) / 2)
    assert ha["ha_high"].iloc[0] == 105.0  # real high still dominates
    assert ha["ha_low"].iloc[0] == 98.0


def test_heikin_ashi_second_candle_open_averages_previous_ha_open_and_close():
    df = pd.DataFrame({
        "Open": [100.0, 104.0], "High": [105.0, 110.0], "Low": [98.0, 103.0], "Close": [104.0, 109.0],
    })
    ha = heikin_ashi(df)

    prev_ha_open, prev_ha_close = ha["ha_open"].iloc[0], ha["ha_close"].iloc[0]
    assert ha["ha_open"].iloc[1] == pytest.approx((prev_ha_open + prev_ha_close) / 2)
    assert ha["ha_close"].iloc[1] == pytest.approx((104 + 110 + 103 + 109) / 4)


def test_heikin_ashi_high_low_take_the_synthetic_open_close_into_account():
    # A gap-down open below both HA open/close should still be captured by ha_low, and vice versa
    # for ha_high — ha_high/ha_low are max/min over {real H/L, ha_open, ha_close}, not just real H/L.
    df = pd.DataFrame({
        "Open": [100.0, 90.0], "High": [105.0, 95.0], "Low": [98.0, 88.0], "Close": [104.0, 92.0],
    })
    ha = heikin_ashi(df)
    assert ha["ha_high"].iloc[1] >= ha["ha_open"].iloc[1]
    assert ha["ha_high"].iloc[1] >= ha["ha_close"].iloc[1]
    assert ha["ha_low"].iloc[1] <= ha["ha_open"].iloc[1]
    assert ha["ha_low"].iloc[1] <= ha["ha_close"].iloc[1]


def test_heikin_ashi_strong_uptrend_produces_little_to_no_lower_wick():
    # The textbook HA property this whole indicator exists for: in a clean, strong uptrend, each
    # HA candle's open sits at (or very near) its low, since ha_open trails behind the rising
    # ha_close from the prior bar.
    rows = []
    price = 100.0
    for _ in range(10):
        o = price
        price += 5.0
        rows.append({"Open": o, "High": price + 0.5, "Low": o - 0.1, "Close": price})
    df = pd.DataFrame(rows)
    ha = heikin_ashi(df)

    last_lower_wick = ha["ha_open"].iloc[-1] - ha["ha_low"].iloc[-1]
    last_body = ha["ha_close"].iloc[-1] - ha["ha_open"].iloc[-1]
    assert last_body > 0
    assert last_lower_wick == pytest.approx(0.0, abs=0.15)


def test_heikin_ashi_returns_expected_columns_and_row_count():
    df = pd.DataFrame({"Open": [1, 2, 3], "High": [2, 3, 4], "Low": [0, 1, 2], "Close": [1.5, 2.5, 3.5]})
    ha = heikin_ashi(df)
    assert list(ha.columns) == ["ha_open", "ha_high", "ha_low", "ha_close"]
    assert len(ha) == 3
