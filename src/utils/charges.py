"""
Realistic Indian F&O trading-cost model, applied per executed leg (entry and exit are each one
"order") so paper P&L reflects what a real account would actually net, not just the raw price
difference. Rates default to a standard discount-broker schedule but are fully overridable via
config/risk_params.json's "charges" section — see DEFAULT_RATES for every key.
"""
from dataclasses import dataclass

DEFAULT_RATES = {
    "brokerage_flat": 20.0,        # Rs. per executed order, or brokerage_pct of order value if lower
    "brokerage_pct": 0.03,
    "stt_sell_pct": 0.1,           # Securities Transaction Tax — sell-side premium only
    "exchange_txn_pct": 0.03503,   # NSE F&O transaction charge, both sides
    "sebi_fee_pct": 0.0001,        # SEBI turnover fee (Rs. 10 per crore), both sides
    "stamp_duty_buy_pct": 0.003,   # Stamp duty — buy-side only
    "gst_pct": 18.0,               # GST on (brokerage + exchange txn charges), both sides
}


@dataclass
class ChargeBreakdown:
    brokerage: float
    stt: float
    exchange_txn: float
    sebi_fee: float
    stamp_duty: float
    gst: float

    @property
    def total(self) -> float:
        return round(
            self.brokerage + self.stt + self.exchange_txn + self.sebi_fee + self.stamp_duty + self.gst, 2)


def calculate_charges(order_value: float, side: str, rates: dict = None) -> ChargeBreakdown:
    """order_value: qty * lot_size * price for this leg. side: 'BUY' (entry) or 'SELL' (exit) —
    options are only ever bought then sold in this system (see PaperTrader), so BUY always means
    entry and SELL always means exit; STT applies only on the sell side, stamp duty only on buy."""
    r = {**DEFAULT_RATES, **(rates or {})}
    order_value = abs(order_value)

    brokerage = min(r["brokerage_flat"], r["brokerage_pct"] / 100 * order_value)
    exchange_txn = r["exchange_txn_pct"] / 100 * order_value
    sebi_fee = r["sebi_fee_pct"] / 100 * order_value
    stt = r["stt_sell_pct"] / 100 * order_value if side == "SELL" else 0.0
    stamp_duty = r["stamp_duty_buy_pct"] / 100 * order_value if side == "BUY" else 0.0
    gst = r["gst_pct"] / 100 * (brokerage + exchange_txn)

    return ChargeBreakdown(
        brokerage=round(brokerage, 2), stt=round(stt, 2), exchange_txn=round(exchange_txn, 2),
        sebi_fee=round(sebi_fee, 2), stamp_duty=round(stamp_duty, 2), gst=round(gst, 2))


def calculate_trade_roundtrip_charges(buy_value: float, sell_value: float, rates: dict = None) -> dict:
    """Returns combined itemized regulatory tax breakdown for both entry and exit legs."""
    buy_chg = calculate_charges(buy_value, "BUY", rates)
    sell_chg = calculate_charges(sell_value, "SELL", rates)

    return {
        "brokerage": round(buy_chg.brokerage + sell_chg.brokerage, 2),
        "stt": round(buy_chg.stt + sell_chg.stt, 2),
        "exchange_txn": round(buy_chg.exchange_txn + sell_chg.exchange_txn, 2),
        "gst": round(buy_chg.gst + sell_chg.gst, 2),
        "stamp_duty": round(buy_chg.stamp_duty + sell_chg.stamp_duty, 2),
        "sebi_fee": round(buy_chg.sebi_fee + sell_chg.sebi_fee, 2),
        "total_charges": round(buy_chg.total + sell_chg.total, 2),
    }
