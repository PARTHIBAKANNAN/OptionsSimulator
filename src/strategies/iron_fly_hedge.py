"""
Iron Fly (short straddle + protective wings): sells the ATM call and put, buys further-OTM
call/put wings to cap risk, and profits from theta decay if NIFTY stays near the ATM strike
through expiry. Only makes sense on the weekly NIFTY expiry day itself (Thursday), when the
premium collected is heavily time-decayed and the position can realistically be run to a same-day
exit — see `is_expiry_day`/`next_weekly_expiry_days` in `src/utils/options_pricing.py`.

Unlike every other strategy here, this SELLS options. `PaperTrader`/`Order` model a single
BUY-only symbol per position, so this intentionally does NOT plug into that machinery or into
BaseStrategy/Signal — it's a self-contained 4-leg position with its own entry/mark/exit, driven
directly by BacktestEngine (see `_backtest_iron_fly`). Not yet wired into the live engine — see
docs/ARCHITECTURE.md for why.
"""
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dtime
from typing import Optional

from src.utils.options_pricing import black_scholes_price, is_expiry_day, next_weekly_expiry_days


@dataclass
class IronFlyLeg:
    symbol: str
    strike: float
    option_type: str  # 'CE' or 'PE'
    side: str  # 'SELL' or 'BUY'
    entry_price: float


@dataclass
class IronFlyPosition:
    entry_time: datetime
    legs: list = field(default_factory=list)  # 4 IronFlyLeg: sell ATM CE/PE, buy OTM CE/PE wings
    net_credit: float = 0.0   # premium collected upfront (max possible profit)
    max_loss: float = 0.0     # analytically defined worst case (wing_width - net_credit)
    lot_size: int = 65
    qty: int = 1
    status: str = "OPEN"
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None

    def current_value(self, prices: dict) -> float:
        """Cost to close now: buy back the short legs, sell the long legs, at current prices."""
        cost = 0.0
        for leg in self.legs:
            price = prices.get(leg.symbol, leg.entry_price)
            cost += price if leg.side == "SELL" else -price
        return cost

    def unrealized_pnl(self, prices: dict) -> float:
        return (self.net_credit - self.current_value(prices)) * self.qty * self.lot_size


class IronFlyHedge:
    def __init__(self, wing_width_pts: float = 200, strike_step: int = 100,
                 entry_time: dtime = dtime(9, 45), force_exit_time: dtime = dtime(15, 15),
                 profit_target_pct_of_credit: float = 50.0, stop_loss_pct_of_max_loss: float = 50.0,
                 max_vol_regime_ratio_to_enter: Optional[float] = None,
                 lot_size: int = 65, qty: int = 1):
        self.wing_width_pts = wing_width_pts
        self.strike_step = strike_step
        self.entry_time = entry_time
        self.force_exit_time = force_exit_time
        self.profit_target_pct_of_credit = profit_target_pct_of_credit
        self.stop_loss_pct_of_max_loss = stop_loss_pct_of_max_loss
        # This strategy's entire edge depends on a LOW-volatility expiry day (the body decaying
        # faster than the wings lose value). Entering on a morning where a big move already looks
        # likely is exactly when it blows through a wing — a volatility gate matters more here than
        # tuning wing width. None disables it. See docs/ARCHITECTURE.md.
        self.max_vol_regime_ratio_to_enter = max_vol_regime_ratio_to_enter
        self.lot_size = lot_size
        self.qty = qty

        self.position: Optional[IronFlyPosition] = None
        self._last_entry_day = None  # at most one entry per calendar day, even after an early exit

    @staticmethod
    def _price(nifty: float, strike: float, option_type: str, timestamp: datetime) -> float:
        days_to_expiry = next_weekly_expiry_days(timestamp)
        return black_scholes_price(spot=nifty, strike=strike, days_to_expiry=days_to_expiry,
                                    option_type=option_type)

    def maybe_enter(self, data_state: dict) -> Optional[IronFlyPosition]:
        """Enters once per expiry day, at self.entry_time, if nothing is already open today."""
        if self.position is not None:
            return None

        timestamp = data_state.get("timestamp")
        nifty = data_state.get("nifty_price")
        if timestamp is None or nifty is None:
            return None
        if not is_expiry_day(timestamp):
            return None
        if timestamp.time() < self.entry_time:
            return None
        if self._last_entry_day == timestamp.date():
            return None  # already ran (and possibly already exited) an Iron Fly today

        if self.max_vol_regime_ratio_to_enter is not None:
            vol_regime_ratio = data_state.get("indicators", {}).get("vol_regime_ratio")
            if vol_regime_ratio is not None and vol_regime_ratio > self.max_vol_regime_ratio_to_enter:
                # Too volatile this morning — skip the whole day rather than retry every candle
                # hoping it calms down; the entry decision is a morning-of regime call, not
                # something to keep chasing intraday.
                self._last_entry_day = timestamp.date()
                return None

        self._last_entry_day = timestamp.date()

        atm_strike = round(nifty / self.strike_step) * self.strike_step
        wing_ce_strike = atm_strike + self.wing_width_pts
        wing_pe_strike = atm_strike - self.wing_width_pts

        atm_ce_price = self._price(nifty, atm_strike, "CE", timestamp)
        atm_pe_price = self._price(nifty, atm_strike, "PE", timestamp)
        wing_ce_price = self._price(nifty, wing_ce_strike, "CE", timestamp)
        wing_pe_price = self._price(nifty, wing_pe_strike, "PE", timestamp)

        net_credit = (atm_ce_price + atm_pe_price) - (wing_ce_price + wing_pe_price)
        max_loss = max(self.wing_width_pts - net_credit, 0.01)

        legs = [
            IronFlyLeg(f"NIFTY{int(atm_strike)}CE", atm_strike, "CE", "SELL", atm_ce_price),
            IronFlyLeg(f"NIFTY{int(atm_strike)}PE", atm_strike, "PE", "SELL", atm_pe_price),
            IronFlyLeg(f"NIFTY{int(wing_ce_strike)}CE", wing_ce_strike, "CE", "BUY", wing_ce_price),
            IronFlyLeg(f"NIFTY{int(wing_pe_strike)}PE", wing_pe_strike, "PE", "BUY", wing_pe_price),
        ]
        self.position = IronFlyPosition(
            entry_time=timestamp, legs=legs, net_credit=net_credit, max_loss=max_loss,
            lot_size=self.lot_size, qty=self.qty,
        )
        return self.position

    def _leg_prices(self, data_state: dict) -> dict:
        nifty = data_state["nifty_price"]
        timestamp = data_state["timestamp"]
        return {leg.symbol: self._price(nifty, leg.strike, leg.option_type, timestamp)
                for leg in self.position.legs}

    def check_exit(self, data_state: dict) -> Optional[IronFlyPosition]:
        """Closes on profit target, stop-loss, or the force-exit time — whichever comes first."""
        if self.position is None:
            return None

        timestamp = data_state.get("timestamp")
        nifty = data_state.get("nifty_price")
        if timestamp is None or nifty is None:
            return None

        prices = self._leg_prices(data_state)
        pnl = self.position.unrealized_pnl(prices)

        reason = None
        if pnl >= self.position.net_credit * self.qty * self.lot_size * (self.profit_target_pct_of_credit / 100):
            reason = "PROFIT_TARGET"
        elif pnl <= -self.position.max_loss * self.qty * self.lot_size * (self.stop_loss_pct_of_max_loss / 100):
            reason = "STOP_LOSS"
        elif timestamp.time() >= self.force_exit_time:
            reason = "FORCE_EXIT"

        if reason is None:
            return None

        self.position.status = "CLOSED"
        self.position.exit_time = timestamp
        self.position.exit_reason = reason
        self.position.realized_pnl = pnl
        closed = self.position
        self.position = None
        return closed
