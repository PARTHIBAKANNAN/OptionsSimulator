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
    def __init__(self, name: str, direction: str, strike_step: int = 50, underlying: str = "NIFTY",
                 strike_mode: str = "ATM", target_premium: float = 200.0, min_cooldown_mins: int = 15):
        self.name = name
        self.direction = direction  # 'CE' or 'PE'
        self.strike_step = strike_step
        self.underlying = underlying  # 'NIFTY' or 'SENSEX' -- symbol prefix and expiry-rule lookup
        self.strike_mode = strike_mode  # 'ATM' or 'ITM'
        self.target_premium = target_premium  # Target premium for ITM (e.g. Rs.200 for Nifty, Rs.600 for Sensex)
        self.min_cooldown_mins = min_cooldown_mins
        self.last_signal_time: Optional[datetime] = None
        self._last_signal_bar: Optional[datetime] = None

    def can_trigger(self, current_time: datetime) -> bool:
        """Enforces opening 09:25 AM cutoff and a minimum cooldown between signals to prevent immediate duplicate re-entries."""
        if current_time is not None:
            t = current_time.time() if hasattr(current_time, "time") else None
            if t and t < OPENING_CUTOFF_TIME:
                return False
        if self.last_signal_time is None:
            return True
        elapsed_seconds = (current_time - self.last_signal_time).total_seconds()
        return elapsed_seconds >= self.min_cooldown_mins * 60

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        raise NotImplementedError

    def select_strike(self, spot_price: float, option_type: str, timestamp: datetime = None) -> tuple[str, float]:
        """Returns (symbol, numeric_strike) for either ATM or ITM based on strike_mode."""
        atm_strike = round(spot_price / self.strike_step) * self.strike_step
        if self.strike_mode != "ITM":
            symbol = f"{self.underlying}{int(atm_strike)}{option_type}"
            return symbol, float(atm_strike)

        # ITM Strike Selection
        ts = timestamp or datetime.now()
        dte = next_weekly_expiry_days(ts, index=self.underlying)
        best_strike = atm_strike
        best_price = black_scholes_price(spot_price, atm_strike, dte, option_type)
        best_diff = abs(best_price - self.target_premium)

        for k in range(1, 15):
            strike = atm_strike - k * self.strike_step if option_type == "CE" else atm_strike + k * self.strike_step
            price = black_scholes_price(spot_price, strike, dte, option_type)
            diff = abs(price - self.target_premium)
            if diff < best_diff:
                best_diff = diff
                best_strike = strike
                best_price = price
            elif price > self.target_premium + 150:
                break

        symbol = f"{self.underlying}{int(best_strike)}{option_type}"
        return symbol, float(best_strike)

    def get_option_price(self, symbol: str, strike: float, spot_price: float,
                          option_type: str, data_state: dict) -> float:
        """Prefer the real quote from the option chain; fall back to a Black-Scholes estimate."""
        option_chain = data_state.get("option_chain", {})
        quote = option_chain.get(symbol)
        if quote is not None and getattr(quote, "ltp", 0) > 0:
            return quote.ltp

        timestamp = data_state.get("timestamp") or datetime.now()
        days_to_expiry = next_weekly_expiry_days(timestamp, index=self.underlying)
        return black_scholes_price(spot=spot_price, strike=strike, days_to_expiry=days_to_expiry,
                                    option_type=option_type)
