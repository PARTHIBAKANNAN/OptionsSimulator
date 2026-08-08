"""
Black-Scholes estimate used only when a real option price isn't available yet
(mainly backtesting, since Fyers only provides historical candles for the index,
not individual option strikes — see FYERS_FEASIBILITY_REPORT.md). Live trading
should always prefer the actual LTP from the option chain over this estimate.
"""
import math
import re
from datetime import date, datetime, timedelta
from datetime import time as dtime

RISK_FREE_RATE = 0.07
DEFAULT_IV = 0.14

SYMBOL_RE = re.compile(r"(?:NIFTY|SENSEX)(\d+)(CE|PE)$")

# Each index's weekly-expiry weekday, as a chronological list of (effective_from, weekday) --
# weekday 0=Monday .. 6=Sunday. The applicable regime for a given date is the last entry whose
# effective_from is <= that date.
#
# NIFTY: NSE moved weekly index expiry from Thursday to Tuesday effective 2025-09-01 (a
# SEBI-mandated exchange-wide swap). Contracts expiring on/before 2025-08-31 were the last
# Thursday-expiry ones; the first Tuesday expiry was 2025-09-02.
#
# SENSEX: BSE weekly options launched with a Friday expiry effective 2023-05-15, moved to Tuesday
# for an interim phase effective 2025-01-01, then to Thursday (current) effective 2025-09-01 --
# confirmed by user.
INDEX_EXPIRY_RULES = {
    "NIFTY": [
        (date.min, 3),          # Thursday, since inception
        (date(2025, 9, 1), 1),  # Tuesday, current
    ],
    "SENSEX": [
        (date(2023, 5, 15), 4),  # Friday, since weekly options launched
        (date(2025, 1, 1), 1),   # Tuesday, interim phase
        (date(2025, 9, 1), 3),   # Thursday, current
    ],
}


def _expiry_weekday(for_date: date, index: str = "NIFTY") -> int:
    regimes = INDEX_EXPIRY_RULES[index]
    weekday = regimes[0][1]
    for effective_from, wd in regimes:
        if for_date >= effective_from:
            weekday = wd
        else:
            break
    return weekday


def parse_option_symbol(symbol: str):
    """'NIFTY24500CE' -> (24500.0, 'CE'); 'SENSEX81500PE' -> (81500.0, 'PE'); (None, None) if it
    doesn't match."""
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


def next_weekly_expiry_days(from_date: datetime, index: str = "NIFTY") -> float:
    """Weekly options expire on the applicable weekday for this index (see INDEX_EXPIRY_RULES) at
    market close (15:30 IST). On the expiry day itself this returns the fractional day remaining
    until that close (heavy same-day theta decay), not a flat 7 — treating any expiry weekday as
    "next week" would overprice every option traded on the actual expiry day."""
    expiry_weekday = _expiry_weekday(from_date.date(), index)
    days_ahead = (expiry_weekday - from_date.weekday()) % 7
    if days_ahead != 0:
        return float(days_ahead)

    market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
    if from_date >= market_close:
        return 7.0  # today's expiry already closed — next one is a week out
    return max((market_close - from_date).total_seconds() / 86400.0, 0.0)


def is_expiry_day(from_date: datetime, index: str = "NIFTY") -> bool:
    """True on the applicable expiry weekday for this index before the 15:30 IST close — the
    window an expiry-day strategy can act in."""
    return (from_date.weekday() == _expiry_weekday(from_date.date(), index)
            and from_date.time() < dtime(15, 30))


def next_weekly_expiry_date(from_date: datetime, index: str = "NIFTY") -> date:
    """Calendar date of the applicable weekly expiry — same weekday-selection rule as
    next_weekly_expiry_days, but returning the actual date instead of a day-count (for display)."""
    expiry_weekday = _expiry_weekday(from_date.date(), index)
    days_ahead = (expiry_weekday - from_date.weekday()) % 7
    if days_ahead != 0:
        return from_date.date() + timedelta(days=days_ahead)

    market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
    if from_date >= market_close:
        return from_date.date() + timedelta(days=7)
    return from_date.date()


def format_display_symbol(symbol: str, expiry: date) -> str:
    """'NIFTY24600CE' + 2026-08-11 -> 'NIFTY11Aug202624600CE'. Display-only: the bare
    strike+type symbol is ambiguous about which week's contract it is, but this is never used as
    a lookup key — order.symbol / option-chain quote keys are untouched everywhere else."""
    strike, option_type = parse_option_symbol(symbol)
    if strike is None:
        return symbol
    prefix = "SENSEX" if symbol.startswith("SENSEX") else "NIFTY"
    return f"{prefix}{expiry.day:02d}{expiry.strftime('%b')}{expiry.year}{int(strike)}{option_type}"
