import pytest

from src.utils.charges import calculate_charges


def test_buy_side_applies_stamp_duty_not_stt():
    charges = calculate_charges(order_value=13000.0, side="BUY")
    assert charges.stamp_duty > 0
    assert charges.stt == 0.0


def test_sell_side_applies_stt_not_stamp_duty():
    charges = calculate_charges(order_value=13000.0, side="SELL")
    assert charges.stt > 0
    assert charges.stamp_duty == 0.0


def test_brokerage_is_capped_at_flat_fee_for_large_orders():
    # order_value large enough that 0.03% would exceed the Rs. 20 flat fee
    charges = calculate_charges(order_value=1_000_000.0, side="BUY")
    assert charges.brokerage == 20.0


def test_brokerage_is_flat_twenty_for_options_orders():
    # Options orders use flat Rs. 20.0 per order leg
    charges = calculate_charges(order_value=10_000.0, side="BUY")
    assert charges.brokerage == 20.0


def test_gst_applies_to_brokerage_and_exchange_txn_only():
    charges = calculate_charges(order_value=10_000.0, side="BUY")
    expected_gst = round(0.18 * (charges.brokerage + charges.exchange_txn), 2)
    assert charges.gst == pytest.approx(expected_gst)


def test_total_sums_every_component():
    charges = calculate_charges(order_value=13000.0, side="SELL")
    expected = round(
        charges.brokerage + charges.stt + charges.exchange_txn + charges.sebi_fee
        + charges.stamp_duty + charges.gst, 2)
    assert charges.total == expected


def test_custom_rates_override_defaults():
    charges = calculate_charges(order_value=10_000.0, side="BUY", rates={"stamp_duty_buy_pct": 1.0})
    assert charges.stamp_duty == pytest.approx(100.0)


def test_negative_order_value_is_treated_as_magnitude():
    positive = calculate_charges(order_value=10_000.0, side="BUY")
    negative = calculate_charges(order_value=-10_000.0, side="BUY")
    assert negative.total == positive.total
