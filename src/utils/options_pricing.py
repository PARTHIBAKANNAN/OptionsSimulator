"""
Black-Scholes estimate used only when a real option price isn't available yet
(mainly backtesting, since Fyers only provides historical candles for the index,
not individual option strikes — see FYERS_FEASIBILITY_REPORT.md). Live trading
should always prefer the actual LTP from the option chain over this estimate.
"""
import calendar
import math
import re
from datetime import date, datetime, timedelta
from datetime import time as dtime

RISK_FREE_RATE = 0.07
DEFAULT_IV = 0.14

SYMBOL_RE = re.compile(r"(?:NIFTY|SENSEX|BANKNIFTY).*?(\d{4,6})(CE|PE)$")

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
#
# BANKNIFTY: Thursday prior to 2023-09-01; Wednesday (2) since 2023-09-04.
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
    "BANKNIFTY": [
        (date.min, 1),          # Tuesday expiry
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
    """'NIFTY24500CE' -> (24500.0, 'CE')
       'NSE:BANKNIFTY26SEP56300CE' -> (56300.0, 'CE')
       'NSE:NIFTY2691524600CE' -> (24600.0, 'CE')
       (None, None) if it doesn't match."""
    match = SYMBOL_RE.search(symbol)
    if not match:
        return None, None
    return float(match.group(1)), match.group(2)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes_greeks(spot: float, strike: float, days_to_expiry: float, option_type: str,
                         iv: float = DEFAULT_IV, risk_free_rate: float = RISK_FREE_RATE) -> dict:
    """Calculates Option Greeks (Delta, Gamma, Theta, Vega) via Black-Scholes."""
    if days_to_expiry <= 0 or spot <= 0 or strike <= 0 or iv <= 0:
        intrinsic = max(spot - strike, 0) if option_type == "CE" else max(strike - spot, 0)
        delta = 1.0 if (option_type == "CE" and spot > strike) else (-1.0 if (option_type == "PE" and spot < strike) else 0.0)
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "price": intrinsic}

    t = max(days_to_expiry / 365.0, 0.0001)
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * iv ** 2) * t) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    pdf_d1 = _norm_pdf(d1)
    cdf_d1 = _norm_cdf(d1)
    cdf_d2 = _norm_cdf(d2)
    cdf_minus_d1 = _norm_cdf(-d1)
    cdf_minus_d2 = _norm_cdf(-d2)

    gamma = round(pdf_d1 / (spot * iv * sqrt_t), 6)
    vega = round((spot * sqrt_t * pdf_d1) / 100.0, 4)  # 1% IV change

    if option_type == "CE":
        delta = round(cdf_d1, 4)
        theta_annual = -(spot * pdf_d1 * iv) / (2 * sqrt_t) - risk_free_rate * strike * math.exp(-risk_free_rate * t) * cdf_d2
        price = spot * cdf_d1 - strike * math.exp(-risk_free_rate * t) * cdf_d2
    else:
        delta = round(cdf_d1 - 1.0, 4)
        theta_annual = -(spot * pdf_d1 * iv) / (2 * sqrt_t) + risk_free_rate * strike * math.exp(-risk_free_rate * t) * cdf_minus_d2
        price = strike * math.exp(-risk_free_rate * t) * cdf_minus_d2 - spot * cdf_minus_d1

    theta_per_day = round(theta_annual / 365.0, 2)
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_per_day,
        "vega": vega,
        "price": round(max(price, 0.05), 2),
    }


def select_optimal_delta_strike(spot: float, option_type: str, index: str = "NIFTY",
                                target_delta: float = 0.60, days_to_expiry: float = None,
                                iv: float = DEFAULT_IV) -> float:
    """Evaluates strike candidates and selects the strike with Delta closest to target_delta (~0.60)."""
    step = 100 if index.upper() == "SENSEX" else 50
    atm = round(spot / step) * step

    if days_to_expiry is None:
        days_to_expiry = next_weekly_expiry_days(datetime.now(), index=index)

    # Generate strike ladder candidates (-3 to +3 strikes)
    if option_type.upper() == "CE":
        candidates = [atm - (i * step) for i in range(4)] + [atm + (i * step) for i in range(1, 3)]
    else:
        candidates = [atm + (i * step) for i in range(4)] + [atm - (i * step) for i in range(1, 3)]

    best_strike = candidates[0]
    best_diff = float("inf")

    for strike in candidates:
        greeks = black_scholes_greeks(spot, strike, days_to_expiry, option_type.upper(), iv=iv)
        diff = abs(abs(greeks["delta"]) - target_delta)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike

    return float(best_strike)


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



def last_tuesday_of_month(for_date: date) -> date:
    """Calculates the last Tuesday of the given month for BANKNIFTY monthly expiry."""
    last_day = calendar.monthrange(for_date.year, for_date.month)[1]
    d = date(for_date.year, for_date.month, last_day)
    while d.weekday() != 1:  # Tuesday is 1
        d -= timedelta(days=1)
    return d


def next_weekly_expiry_days(from_date: datetime, index: str = "NIFTY") -> float:
    """Calculates days to expiry for pricing:
    - BANKNIFTY: Discontinued weekly options; monthly expiry on the last Tuesday of the month.
    - SENSEX: Weekly options expire on Thursday.
    - NIFTY: Weekly options expire on Tuesday."""
    if index == "BANKNIFTY":
        expiry_dt = next_weekly_expiry_date(from_date, index="BANKNIFTY")
        diff_days = (expiry_dt - from_date.date()).days
        if diff_days > 0:
            return float(diff_days)
        market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
        if from_date >= market_close:
            next_m = next_weekly_expiry_date(from_date + timedelta(days=1), index="BANKNIFTY")
            return float((next_m - from_date.date()).days)
        return max((market_close - from_date).total_seconds() / 86400.0, 0.0)

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
    if index == "BANKNIFTY":
        expiry_date = last_tuesday_of_month(from_date.date())
        return (from_date.date() == expiry_date and from_date.time() < dtime(15, 30))
    return (from_date.weekday() == _expiry_weekday(from_date.date(), index)
            and from_date.time() < dtime(15, 30))


def next_weekly_expiry_date(from_date: datetime, index: str = "NIFTY") -> date:
    """Calendar date of the applicable expiry:
    - BANKNIFTY: Discontinued weekly options; expires monthly on the last Tuesday of the month.
    - SENSEX: Weekly options expire on Thursday.
    - NIFTY: Weekly options expire on Tuesday."""
    if index == "BANKNIFTY":
        curr_expiry = last_tuesday_of_month(from_date.date())
        market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
        if from_date.date() < curr_expiry:
            return curr_expiry
        elif from_date.date() == curr_expiry and from_date < market_close:
            return curr_expiry
        else:
            # Roll over to next month's last Tuesday
            year = from_date.year + (1 if from_date.month == 12 else 0)
            month = 1 if from_date.month == 12 else from_date.month + 1
            return last_tuesday_of_month(date(year, month, 1))

    expiry_weekday = _expiry_weekday(from_date.date(), index)
    days_ahead = (expiry_weekday - from_date.weekday()) % 7
    if days_ahead != 0:
        return from_date.date() + timedelta(days=days_ahead)

    market_close = from_date.replace(hour=15, minute=30, second=0, microsecond=0)
    if from_date >= market_close:
        return from_date.date() + timedelta(days=7)
    return from_date.date()


def format_display_symbol(symbol: str, expiry: date = None) -> str:
    """'BANKNIFTY56300CE' -> 'BANKNIFTY29Sep202656300CE'
       'SENSEX75100CE'    -> 'SENSEX10Sep202675100CE'
       'NIFTY24600CE'     -> 'NIFTY15Sep202624600CE'"""
    strike, option_type = parse_option_symbol(symbol)
    if strike is None:
        return symbol
    if "BANKNIFTY" in symbol:
        prefix = "BANKNIFTY"
    elif "SENSEX" in symbol:
        prefix = "SENSEX"
    else:
        prefix = "NIFTY"
    if expiry is None:
        expiry = next_weekly_expiry_date(datetime.now(), index=prefix)
    return f"{prefix}{expiry.day:02d}{expiry.strftime('%b')}{expiry.year}{int(strike)}{option_type}"


def format_readable_contract(symbol: str, expiry: date = None, timestamp: datetime = None) -> str:
    """'BANKNIFTY56300CE' -> 'BANKNIFTY 29-SEP-2026 56300 CE'."""
    strike, option_type = parse_option_symbol(symbol)
    if strike is None:
        return symbol
    if "BANKNIFTY" in symbol:
        prefix = "BANKNIFTY"
    elif "SENSEX" in symbol:
        prefix = "SENSEX"
    else:
        prefix = "NIFTY"
    if expiry is None:
        ts = timestamp or datetime.now()
        expiry = next_weekly_expiry_date(ts, index=prefix)
    return f"{prefix} {expiry.day:02d}-{expiry.strftime('%b').upper()}-{expiry.year} {int(strike)} {option_type}"


FYERS_MONTH_CODES = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D"
}


def to_fyers_symbol(symbol: str, expiry: date = None, is_monthly: bool = None) -> str:
    """Builds valid Fyers WebSocket option symbol:
       - Monthly expiry (e.g. BANKNIFTY): 'NSE:BANKNIFTY26SEP56300PE'
       - Weekly expiry (e.g. NIFTY, SENSEX): 'NSE:NIFTY2691524600CE' / 'BSE:SENSEX2691075100PE'"""
    strike, option_type = parse_option_symbol(symbol)
    if strike is None:
        return symbol
    if "BANKNIFTY" in symbol:
        underlying = "BANKNIFTY"
        exchange = "NSE"
    elif "SENSEX" in symbol:
        underlying = "SENSEX"
        exchange = "BSE"
    else:
        underlying = "NIFTY"
        exchange = "NSE"
    if expiry is None:
        expiry = next_weekly_expiry_date(datetime.now(), index=underlying)
    yy = f"{expiry.year % 100:02d}"

    # Under SEBI regulations, BANKNIFTY contracts expire monthly: format is {YY}{MMM}{STRIKE}{TYPE}
    if is_monthly or underlying == "BANKNIFTY":
        mmm = expiry.strftime("%b").upper()
        return f"{exchange}:{underlying}{yy}{mmm}{int(strike)}{option_type}"

    # Weekly contracts: format is {YY}{M}{DD}{STRIKE}{TYPE}
    m = FYERS_MONTH_CODES.get(expiry.month, str(expiry.month))
    dd = f"{expiry.day:02d}"
    return f"{exchange}:{underlying}{yy}{m}{dd}{int(strike)}{option_type}"

