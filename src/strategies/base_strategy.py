"""Shared Signal type and strike-selection/pricing helpers all strategies build on."""
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Optional

from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days

OPENING_CUTOFF_TIME = dtime(9, 25)
EOD_CUTOFF_TIME = dtime(15, 15)
ORB_ENTRY_CUTOFF_TIME = dtime(10, 30)
MIDDAY_START_TIME = dtime(10, 30)
MIDDAY_END_TIME = dtime(13, 0)
MIDDAY_CHOP_START = dtime(12, 30)  # Afternoon false-breakout / V-reversal risk window
MIDDAY_CHOP_END = dtime(14, 30)
SCALP_1M_CUTOFF = dtime(10, 45)    # 1M Scalps strictly morning momentum only


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
        """Enforces opening 09:25 AM cutoff, 15:15 PM EOD cutoff, 1M morning window, and minimum cooldown."""
        if current_time is not None:
            t = current_time.time() if hasattr(current_time, "time") else None
            if t and (t < OPENING_CUTOFF_TIME or t >= EOD_CUTOFF_TIME):
                return False
            # Dynamic 1M Scalp check (no blanket clock cutoff)
            pass
        if self.last_signal_time is None:
            return True
        elapsed_seconds = (current_time - self.last_signal_time).total_seconds()
        return elapsed_seconds >= self.min_cooldown_mins * 60

    @staticmethod
    def is_midday(current_time: datetime) -> bool:
        """Returns True if current timestamp is within the 10:30 AM to 13:00 PM consolidation window."""
        if current_time is None:
            return False
        t = current_time.time() if hasattr(current_time, "time") else None
        return t is not None and (MIDDAY_START_TIME <= t < MIDDAY_END_TIME)

    @staticmethod
    def is_orb_allowed(current_time: datetime) -> bool:
        """ORB entries are strictly allowed only between 09:30 and 10:30 AM IST."""
        if current_time is None:
            return False
        t = current_time.time() if hasattr(current_time, "time") else None
        return t is not None and (OPENING_CUTOFF_TIME <= t < ORB_ENTRY_CUTOFF_TIME)

    @staticmethod
    def is_vwap_acceptable(spot: float, vwap_price: Optional[float], max_dist_pct: float = 0.40) -> bool:
        """Rejects chasing extended moves if spot is stretched more than max_dist_pct from VWAP."""
        if vwap_price is None or vwap_price <= 0 or spot <= 0:
            return True
        dist_pct = (abs(spot - vwap_price) / vwap_price) * 100.0
        return dist_pct <= max_dist_pct

    @staticmethod
    def is_midday_chop_zone(current_time: datetime) -> bool:
        """Returns True if current timestamp is within the 12:30 PM to 14:30 PM high-risk consolidation window."""
        if current_time is None:
            return False
        t = current_time.time() if hasattr(current_time, "time") else None
        return t is not None and (MIDDAY_CHOP_START <= t < MIDDAY_CHOP_END)

    @staticmethod
    def is_scalp_1m_allowed(current_time: datetime) -> bool:
        """1M Scalp entries are strictly allowed only during peak morning momentum (09:25 to 10:45 AM IST)."""
        if current_time is None:
            return False
        t = current_time.time() if hasattr(current_time, "time") else None
        return t is not None and (OPENING_CUTOFF_TIME <= t < SCALP_1M_CUTOFF)

    @staticmethod
    def is_volume_acceptable(volume_ratio: Optional[float], current_time: datetime,
                              min_morning: float = 1.0, min_midday: float = 1.4,
                              min_afternoon_chop: float = 1.5,
                              current_volume: Optional[float] = None,
                              avg_volume: Optional[float] = None) -> bool:
        """Requires higher volume surge during midday (10:30 - 13:00) and 1.5x during 12:30-14:30 chop zone."""
        if volume_ratio is None:
            if current_volume is not None and avg_volume is not None and avg_volume > 0:
                volume_ratio = current_volume / avg_volume
            else:
                return True
        if BaseStrategy.is_midday_chop_zone(current_time):
            return volume_ratio >= min_afternoon_chop
        if BaseStrategy.is_midday(current_time):
            return volume_ratio >= min_midday
        return volume_ratio >= min_morning

    @staticmethod
    def is_trend_confirmed(adx_val: Optional[float], min_adx: float = 20.0) -> bool:
        """Confirms market is in trending regime (ADX >= 20.0). Defaults to True if ADX not computed yet."""
        if adx_val is None:
            return True
        return adx_val >= min_adx

    @staticmethod
    def is_chop_free(data_state: dict, current_time: datetime) -> bool:
        """Triple Chop-Filter Matrix replacing the blunt 12:30-14:30 clock block.
        Checks ADX trend strength, candle body-to-range ratio, and Bollinger Band expansion."""
        indicators = data_state.get("indicators") or {}
        # 1. ADX filter: If ADX is computed and < 20, market is oscillating in flat chop
        adx = indicators.get("adx_14_5m") or indicators.get("adx") or indicators.get("adx_14_1m")
        if adx is not None and adx < 20.0:
            return False

        # 2. Candle body ratio in midday/afternoon chop zone (12:30 - 14:30)
        # Avoid thin-body dojis and rejection traps
        if BaseStrategy.is_midday_chop_zone(current_time):
            candles = data_state.get("candles", [])
            if candles:
                last_candle = candles[-1]
                rng = float(last_candle.high) - float(last_candle.low)
                body = abs(float(last_candle.close) - float(last_candle.open))
                if rng > 0 and (body / rng) < 0.45:
                    return False
        return True

    @staticmethod
    def is_scalp_1m_confirmed(data_state: dict, direction: str) -> bool:
        """Multi-Timeframe Macro Alignment for 1M Scalps (Replaces 10:45 AM clock block).
        Ensures 1M scalp entries are aligned with the 5M trend anchor."""
        indicators = data_state.get("indicators") or {}
        st_dir = indicators.get("supertrend_10_3_direction")
        ema20_5m = indicators.get("ema_20_5m")
        spot = data_state.get("nifty_price") or data_state.get("banknifty_price") or data_state.get("sensex_price")
        
        # In a 5M downtrend, do not take 1M CE scalps
        if direction == "CE":
            if st_dir == -1.0 and ema20_5m is not None and spot is not None and spot < ema20_5m:
                return False
        # In a 5M uptrend, do not take 1M PE scalps
        elif direction == "PE":
            if st_dir == 1.0 and ema20_5m is not None and spot is not None and spot > ema20_5m:
                return False
        return True


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
                          option_type: str, data_state: dict) -> Optional[float]:
        """Prefer the real quote from the option chain. In live trading, strictly refuse
        synthetic Black-Scholes prices to prevent massive tick-jump entry errors."""
        option_chain = data_state.get("option_chain", {})
        quote = option_chain.get(symbol)
        if quote is not None and getattr(quote, "ltp", 0) > 0:
            return float(quote.ltp)

        # In live trading, never enter on synthetic/theoretical Black-Scholes prices
        if data_state.get("is_live", False):
            return None

        timestamp = data_state.get("timestamp") or datetime.now()
        days_to_expiry = next_weekly_expiry_days(timestamp, index=self.underlying)
        return black_scholes_price(spot=spot_price, strike=strike, days_to_expiry=days_to_expiry,
                                    option_type=option_type)

