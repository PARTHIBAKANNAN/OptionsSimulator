"""Shared Signal type and strike-selection/pricing helpers all strategies build on."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days


@dataclass
class Signal:
    strategy: str
    direction: str  # 'CE' or 'PE'
    action: str  # 'BUY'
    strike: str
    confidence: float
    rationale: str
    entry_price: float
    timestamp: datetime
    underlying: str = "NIFTY"  # 'NIFTY' or 'SENSEX' -- selects lot size at execution time


class BaseStrategy:
    def __init__(self, name: str, direction: str, strike_step: int = 50, underlying: str = "NIFTY"):
        self.name = name
        self.direction = direction  # 'CE' or 'PE'
        self.strike_step = strike_step
        self.underlying = underlying  # 'NIFTY' or 'SENSEX' -- symbol prefix and expiry-rule lookup
        self.last_signal_time: Optional[datetime] = None

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        raise NotImplementedError

    def select_strike(self, nifty_price: float, option_type: str) -> tuple[str, float]:
        """Returns (symbol, numeric_strike) for the ATM strike."""
        atm_strike = round(nifty_price / self.strike_step) * self.strike_step
        symbol = f"{self.underlying}{int(atm_strike)}{option_type}"
        return symbol, float(atm_strike)

    def get_option_price(self, symbol: str, strike: float, nifty_price: float,
                          option_type: str, data_state: dict) -> float:
        """Prefer the real quote from the option chain; fall back to a Black-Scholes estimate."""
        option_chain = data_state.get("option_chain", {})
        quote = option_chain.get(symbol)
        if quote is not None and getattr(quote, "ltp", 0) > 0:
            return quote.ltp

        timestamp = data_state.get("timestamp") or datetime.now()
        days_to_expiry = next_weekly_expiry_days(timestamp, index=self.underlying)
        return black_scholes_price(spot=nifty_price, strike=strike, days_to_expiry=days_to_expiry,
                                    option_type=option_type)
