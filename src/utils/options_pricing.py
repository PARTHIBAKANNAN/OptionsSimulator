"""
Black-Scholes estimate used only when a real option price isn't available yet
(mainly backtesting, since Fyers only provides historical candles for the index,
not individual option strikes — see FYERS_FEASIBILITY_REPORT.md). Live trading
should always prefer the actual LTP from the option chain over this estimate.
"""
import math
import re
from datetime import date, datetime
from datetime import time as dtime

RISK_FREE_RATE = 0.07
DEFAULT_IV = 0.14

SYMBOL_RE = re.compile(r"NIFTY(\d+)(CE|PE)$")

# NSE moved NIFTY weekly index expiry from Thursday to Tuesday effective 2025-09-01 (a SEBI-mandated
# exchange-wide swap — BSE moved the other way, to Thursday). Contracts expiring on/before
# 2025-08-31 were the last Thursday-expiry ones; the first Tuesday expiry was 2025-09-02. Backtests
# spanning this date need the correct weekday on each side, not one hardcoded assumption.
EXPIRY_DAY_CHANGE_DATE = date(2025, 9, 1)
_OLD_EXPIRY_WEEKDAY = 3  # Thursday
_NEW_EXPIRY_WEEKDAY = 1  # Tuesday


def _expiry_weekday(for_date: date) -> int:
    return _OLD_EXPIRY_WEEKDAY if for_date < EXPIRY_DAY_CHANGE_DATE else _NEW_EXPIRY_WEEKDAY


def parse_option_symbol(symbol: str):
    """'NIFTY24500CE' -> (24500.0, 'CE'); (None, None) if it doesn't match."""
    match = SYMBOL_RE.search(symbol)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes_price(spot: float, strike: float, days_to_expiry: float, option_type: str,
                         iv: float = DEFAULT_IV, risk_free_rate: float = RISK_FREE_RATE) -> float:
    if days_to_expiry <= 0:
        intrinsic = max(spot - strike, 0) if option_type == "CE" else max(strike - spot, 0)
        return round(intrinsic, 2)

    t = days_to_expiry / 365.0
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv ** 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)

    if option_type == "CE":
        price = spot * _norm_cdf(d1) - strike * math.exp(-risk_free_rate * t) * _norm_cdf(d2)
    else:
        price = strike * math.exp(-risk_free_rate * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)

    return round(max(price, 0.05), 2)


def next_weekly_expiry_days(from_date: datetime) -> float:
    """NIFTY weekly options expire on the applicable weekday (see EXPIRY_DAY_CHANGE_DATE) at market
    close (15:30 IST). On the expiry day itself this returns the fractional day remaining until
    that close (heavy same-day theta decay), not a flat 7 — treating any expiry weekday as "next
    week" would overprice every option traded on the actual expiry day."""
    expiry_weekday = _expiry_weekday(from_date.date())
    days_ahead = (expiry_weekday - from_date.weekday()) % 7
    if days_ahead != 0:
        return float(days_ahead)

    market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
    if from_date >= market_close:
        return 7.0  # today's expiry already closed — next one is a week out
    return max((market_close - from_date).total_seconds() / 86400.0, 0.0)


def is_expiry_day(from_date: datetime) -> bool:
    """True on the applicable expiry weekday (Thursday before 2025-09-01, Tuesday on/after) before
    the 15:30 IST close — the window an expiry-day strategy can act in."""
    return (from_date.weekday() == _expiry_weekday(from_date.date())
            and from_date.time() < dtime(15, 30))
