"""
Black-Scholes estimate used only when a real option price isn't available yet
(mainly backtesting, since Fyers only provides historical candles for the index,
not individual option strikes — see FYERS_FEASIBILITY_REPORT.md). Live trading
should always prefer the actual LTP from the option chain over this estimate.
"""
import math
import re
from datetime import datetime

RISK_FREE_RATE = 0.07
DEFAULT_IV = 0.14

SYMBOL_RE = re.compile(r"NIFTY(\d+)(CE|PE)$")


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
    """NIFTY weekly options expire Thursday. Falls back to 7 days if already Thursday post-close."""
    days_ahead = (3 - from_date.weekday()) % 7  # Thursday = 3
    if days_ahead == 0:
        days_ahead = 7
    return float(days_ahead)
