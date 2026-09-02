"""
Simulated order execution — no broker calls, no real money. Tracks open positions,
applies stop-loss/take-profit/time-exit, and calculates realized + unrealized P&L.
"""
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, time as dtime
from functools import cached_property
from typing import Optional

from src.utils.charges import calculate_charges


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str  # 'BUY' (options are only ever bought in this system)
    qty: int
    lot_size: int
    entry_price: float
    entry_time: datetime
    status: str  # 'OPEN', 'CLOSED', 'CANCELLED'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: Optional[str] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None  # gross — price difference only, unchanged meaning
    peak_price: Optional[float] = None  # high-water mark since entry, for the trailing stop
    trailing_active: bool = False
    entry_charges: float = 0.0
    exit_charges: float = 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.qty * self.lot_size

    @cached_property
    def underlying(self) -> str:
        """Derived from the symbol itself rather than a stored field/DB column -- avoids a
        migration and avoids handling NULL on pre-migration rows. See docs/ARCHITECTURE.md."""
        return "SENSEX" if self.symbol.startswith("SENSEX") else "NIFTY"

    @property
    def net_pnl(self) -> Optional[float]:
        """realized_pnl net of both legs' charges — the actual cash-flow effect on the wallet.
        None while still open (exit_charges aren't known yet)."""
        if self.realized_pnl is None:
            return None
        return round(self.realized_pnl - self.entry_charges - self.exit_charges, 2)


class RiskLimitExceeded(Exception):
    pass


class PaperTrader:
    # Default stepped trailing tiers, as % of entry premium rather than flat rupee points — see
    # update_positions() below for why. First-pass values pending validation against the re-run
    # backtest, same as take_profit_pct; not a final tuned answer.
    DEFAULT_TRAILING_TIERS_PCT = [
        {"gain_pct": 10.0, "lock_pct": 0.0},
        {"gain_pct": 20.0, "lock_pct": 5.0},
        {"gain_pct": 30.0, "lock_pct": 10.0},
    ]

    def __init__(self, initial_capital: float = 1_000_000, slippage_pct: float = 0.1,
                 lot_size: int = 65, max_concurrent_positions: int = 5,
                 max_daily_loss: float = 5000, max_trades_per_day_per_strategy: int = 2,
                 trailing_stop_enabled: bool = False, trailing_activation_pct: float = 10.0,
                 trailing_stop_pct: float = 15.0, trailing_tiers_pct: list = None,
                 consecutive_loss_limit: int = None, consecutive_loss_cooldown_days: int = 1,
                 max_drawdown_pct_of_capital: float = None, drawdown_cooldown_days: int = 3,
                 drawdown_breaker_grace_trades: int = 3,
                 capital_by_strategy: dict = None, charges_rates: dict = None,
                 enable_wallets: bool = False, post_loss_cooldown_mins: int = 0, logger=None):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.lot_size = lot_size
        self.max_concurrent_positions = max_concurrent_positions
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day_per_strategy = max_trades_per_day_per_strategy
        # Trailing stop only arms once a position is up trailing_activation_pct from entry — before
        # that it would just clamp tightly to entry-price noise and shake out trades early. Once
        # armed, it ratchets up to stay trailing_stop_pct below the peak premium seen so far,
        # locking in gains as the trade runs instead of relying solely on the fixed take_profit.
        self.trailing_stop_enabled = trailing_stop_enabled
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_stop_pct = trailing_stop_pct
        # Sorted descending by gain_pct once, here, so update_positions() can just take the first
        # tier whose threshold is met rather than re-sorting on every single price update.
        tiers = trailing_tiers_pct if trailing_tiers_pct is not None else self.DEFAULT_TRAILING_TIERS_PCT
        self.trailing_tiers_pct = sorted(tiers, key=lambda t: t["gain_pct"], reverse=True)
        # Circuit breakers: pause NEW entries for a strategy (existing open positions still get
        # managed normally) after either K losses in a row, or its cumulative drawdown from peak
        # P&L eats too much of the capital actually allocated to it. Both are None/disabled by
        # default — a strategy has to opt in with real numbers. capital_by_strategy maps strategy
        # name -> its allocated capital (e.g. from data/backtest_results/capital_requirements.json);
        # without an entry there, the drawdown breaker can't fire for that strategy. See
        # docs/ARCHITECTURE.md for why per-strategy drawdown-as-%-of-capital, not just the
        # backtest's arbitrary initial_capital baseline, is what actually matters here.
        self.consecutive_loss_limit = consecutive_loss_limit
        self.consecutive_loss_cooldown_days = consecutive_loss_cooldown_days
        self.max_drawdown_pct_of_capital = max_drawdown_pct_of_capital
        self.drawdown_cooldown_days = drawdown_cooldown_days
        # Drawdown is measured from the strategy's ALL-TIME peak P&L, which only improves on a new
        # high — so without this grace window, resuming from a pause and then closing even one
        # trade that isn't a strong enough win to set a new high would immediately re-trigger
        # another pause. A backtest showed this trap effectively locked strategies out of most of
        # their future good trades. This grants drawdown_breaker_grace_trades trades of breathing
        # room after each drawdown-triggered pause before the breaker can fire again. See
        # docs/ARCHITECTURE.md.
        self.drawdown_breaker_grace_trades = drawdown_breaker_grace_trades
        self.capital_by_strategy = capital_by_strategy or {}
        self.charges_rates = charges_rates
        self.post_loss_cooldown_mins = post_loss_cooldown_mins
        self.logger = logger
        self._strategy_last_exit: dict[str, dict] = {}

        self.wallet_balance: dict[str, float] = dict(self.capital_by_strategy) if enable_wallets else {}

        self.orders: dict[str, Order] = {}
        self._realized_pnl_today = 0.0
        self._current_day = None
        self._strategy_trades_today: dict[str, int] = {}
        self._strategy_consecutive_losses: dict[str, int] = {}
        self._strategy_cumulative_pnl: dict[str, float] = {}
        self._strategy_peak_pnl: dict[str, float] = {}
        self._strategy_paused_until: dict[str, date] = {}
        self._strategy_drawdown_grace_remaining: dict[str, int] = {}

    def _roll_day(self, timestamp: datetime) -> None:
        day = timestamp.date()
        if self._current_day != day:
            self._current_day = day
            self._realized_pnl_today = 0.0
            self._strategy_trades_today = {}
            self._strategy_last_exit = {}

    def restore_daily_counts(self, day: date, trades_today: dict[str, int],
                              realized_pnl_today: float = 0.0) -> None:
        """Reconstructs today's per-strategy trade count and realized P&L after a restart (see
        WebLiveEngine._restore_state). Without this, max_trades_per_day_per_strategy and the
        overall daily-loss breaker both silently reset to zero on every restart -- confirmed live
        on 2026-08-06, where 3 restarts in one trading day let MACD_BULLISH place 3 entries
        despite its 2/day cap, each restart's fresh in-memory counter never knowing about the
        entries the previous run had already placed. Must set _current_day too, or the very next
        place_order()/close_position() call's _roll_day() sees a mismatched day and wipes this
        right back out."""
        self._current_day = day
        self._strategy_trades_today = dict(trades_today)
        self._realized_pnl_today = realized_pnl_today

    def has_open_position(self, strategy: str) -> bool:
        return any(o.strategy == strategy for o in self.get_positions())

    def place_order(self, symbol: str, side: str, qty: int, price: float,
                     stop_loss: float = None, take_profit: float = None,
                     strategy: str = None, timestamp: datetime = None,
                     lot_size: int = None) -> Order:
        timestamp = timestamp or datetime.now()
        self._roll_day(timestamp)
        # Per-order override so one shared PaperTrader can size NIFTY (65) and SENSEX (20) orders
        # correctly -- falls back to the instance default when a caller doesn't pass one, so any
        # code path that forgets stays on today's single-index behavior instead of crashing.
        lot_size = lot_size if lot_size is not None else self.lot_size

        if self.max_daily_loss is not None and self._realized_pnl_today <= -abs(self.max_daily_loss):
            raise RiskLimitExceeded(f"Daily loss limit of {self.max_daily_loss} already hit")
        if self.max_concurrent_positions is not None and len(self.get_positions()) >= self.max_concurrent_positions:
            raise RiskLimitExceeded(f"Max concurrent positions ({self.max_concurrent_positions}) reached")
        if strategy is not None and self.has_open_position(strategy):
            raise RiskLimitExceeded(f"Strategy '{strategy}' already has an open position")
        if strategy is not None and self._strategy_trades_today.get(strategy, 0) >= self.max_trades_per_day_per_strategy:
            raise RiskLimitExceeded(
                f"Strategy '{strategy}' already hit its {self.max_trades_per_day_per_strategy} trades/day limit")
        if strategy is not None:
            paused_until = self._strategy_paused_until.get(strategy)
            if paused_until is not None and timestamp.date() < paused_until:
                raise RiskLimitExceeded(
                    f"Strategy '{strategy}' is paused by a circuit breaker until {paused_until}")

            # Sequential entry rule: if previous trade on this strategy was a LOSS, enforce cooldown
            if self.post_loss_cooldown_mins > 0:
                last_exit = getattr(self, "_strategy_last_exit", {}).get(strategy)
                if last_exit and last_exit.get("realized_pnl", 0) <= 0:
                    cooldown_expiry = last_exit["exit_time"] + timedelta(minutes=self.post_loss_cooldown_mins)
                    if timestamp < cooldown_expiry:
                        raise RiskLimitExceeded(
                            f"Strategy '{strategy}' in {self.post_loss_cooldown_mins}-min post-loss cooldown until {cooldown_expiry.strftime('%H:%M:%S')}")

        fill_price = price * (1 + self.slippage_pct / 100) if side == "BUY" else price * (1 - self.slippage_pct / 100)
        order_value = fill_price * qty * lot_size
        entry_charges = calculate_charges(order_value, "BUY", self.charges_rates).total

        if strategy is not None and strategy in self.wallet_balance:
            required = order_value + entry_charges
            available = self.wallet_balance[strategy]
            if required > available:
                raise RiskLimitExceeded(
                    f"Strategy '{strategy}' wallet balance (Rs.{available:,.2f}) insufficient "
                    f"for this order (Rs.{required:,.2f} needed)")

        order = Order(
            # UUID, not a sequential counter: the web backend persists orders to Postgres across
            # process restarts, where a counter that resets to 1 each time would collide with an
            # already-persisted order_id — see docs/ARCHITECTURE.md.
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            qty=qty,
            lot_size=lot_size,
            entry_price=fill_price,
            entry_time=timestamp,
            status="OPEN",
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            peak_price=fill_price,
            entry_charges=round(entry_charges, 2),
        )
        self.orders[order.order_id] = order
        if strategy is not None:
            self._strategy_trades_today[strategy] = self._strategy_trades_today.get(strategy, 0) + 1
            if strategy in self.wallet_balance:
                self.wallet_balance[strategy] -= order_value + entry_charges
        if self.logger:
            self.logger.log_trade(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order or order.status != "OPEN":
            return False
        order.status = "CANCELLED"
        return True

    def close_position(self, order_id: str, price: float, timestamp: datetime = None,
                        reason: str = "MANUAL") -> Optional[Order]:
        order = self.orders.get(order_id)
        if not order or order.status != "OPEN":
            return None

        order.exit_price = price
        order.exit_time = timestamp or datetime.now()
        order.exit_reason = reason
        order.realized_pnl = (order.exit_price - order.entry_price) * order.qty * order.lot_size
        exit_value = order.exit_price * order.qty * order.lot_size
        order.exit_charges = round(calculate_charges(exit_value, "SELL", self.charges_rates).total, 2)
        order.status = "CLOSED"

        self._roll_day(order.exit_time)
        self._realized_pnl_today += order.realized_pnl
        if order.strategy is not None:
            if not hasattr(self, "_strategy_last_exit"):
                self._strategy_last_exit = {}
            self._strategy_last_exit[order.strategy] = {
                "exit_time": order.exit_time,
                "realized_pnl": order.realized_pnl,
                "reason": reason,
            }
            self._update_circuit_breakers(order.strategy, order.realized_pnl, order.exit_time.date())
            if order.strategy in self.wallet_balance:
                self.wallet_balance[order.strategy] += exit_value - order.exit_charges

        if self.logger:
            self.logger.log_trade(order)
        return order

    def get_wallet(self, strategy: str) -> Optional[dict]:
        if strategy not in self.wallet_balance:
            return None
        allocated = self.capital_by_strategy.get(strategy, 0.0)
        balance = self.wallet_balance[strategy]
        return {"strategy": strategy, "balance": round(balance, 2), "allocated_capital": allocated,
                "pnl_in_wallet": round(balance - allocated, 2)}

    def get_all_wallets(self) -> dict[str, dict]:
        return {s: self.get_wallet(s) for s in self.wallet_balance}

    def _pause_strategy(self, strategy: str, from_date: date, cooldown_days: int) -> None:
        resume_date = from_date + timedelta(days=cooldown_days)
        current = self._strategy_paused_until.get(strategy)
        if current is None or resume_date > current:
            self._strategy_paused_until[strategy] = resume_date
        if self.logger:
            self.logger.log_error(
                f"Circuit breaker: strategy '{strategy}' paused until {resume_date}",
                {"strategy": strategy})

    def _update_circuit_breakers(self, strategy: str, realized_pnl: float, exit_date: date) -> None:
        if realized_pnl > 0:
            self._strategy_consecutive_losses[strategy] = 0
        else:
            losses = self._strategy_consecutive_losses.get(strategy, 0) + 1
            self._strategy_consecutive_losses[strategy] = losses
            if self.consecutive_loss_limit is not None and losses >= self.consecutive_loss_limit:
                self._pause_strategy(strategy, exit_date, self.consecutive_loss_cooldown_days)
                self._strategy_consecutive_losses[strategy] = 0  # fresh count once it resumes

        cumulative = self._strategy_cumulative_pnl.get(strategy, 0.0) + realized_pnl
        self._strategy_cumulative_pnl[strategy] = cumulative
        peak = max(self._strategy_peak_pnl.get(strategy, 0.0), cumulative)
        self._strategy_peak_pnl[strategy] = peak

        allocated_capital = self.capital_by_strategy.get(strategy)
        if self.max_drawdown_pct_of_capital is not None and allocated_capital:
            grace_remaining = self._strategy_drawdown_grace_remaining.get(strategy, 0)
            if grace_remaining > 0:
                self._strategy_drawdown_grace_remaining[strategy] = grace_remaining - 1
            else:
                drawdown = peak - cumulative
                if drawdown >= allocated_capital * (self.max_drawdown_pct_of_capital / 100):
                    self._pause_strategy(strategy, exit_date, self.drawdown_cooldown_days)
                    self._strategy_drawdown_grace_remaining[strategy] = self.drawdown_breaker_grace_trades

    def update_positions(self, current_prices: dict, timestamp: datetime = None,
                          time_exit_mins: int = None, eod_square_off: bool = False) -> list[Order]:
        """current_prices: {symbol: ltp}. Applies SL/TP/time-exit/EOD square-off. Returns orders closed this call."""
        timestamp = timestamp or datetime.now()
        closed = []
        for order in self.get_positions():
            price = current_prices.get(order.symbol)
            if price is None:
                continue

            trailing_stop_price = None
            if self.trailing_stop_enabled and order.entry_price:
                order.peak_price = max(order.peak_price, price)
                gain_pct = (order.peak_price - order.entry_price) / order.entry_price * 100
                dynamic_price = order.peak_price * (1 - self.trailing_stop_pct / 100)

                # Stepped trailing stop-loss, as % of entry premium (see DEFAULT_TRAILING_TIERS_PCT
                # and its comment) rather than flat rupee points — a 20-point gain is a completely
                # different fraction of premium on a Rs.30 NIFTY 1M-ATM contract vs a Rs.600 ITM
                # BankNifty one, so flat points meant this ratchet was effectively disabled for
                # low-premium contracts and hair-triggered for high-premium ones. Tiers are
                # pre-sorted descending by gain_pct in __init__, so the first match is the highest
                # tier reached.
                stepped_price = None
                for tier in self.trailing_tiers_pct:
                    if gain_pct >= tier["gain_pct"]:
                        order.trailing_active = True
                        stepped_price = order.entry_price * (1 + tier["lock_pct"] / 100)
                        break

                if stepped_price is not None:
                    trailing_stop_price = max(stepped_price, dynamic_price)
                elif not order.trailing_active and order.peak_price >= order.entry_price * (
                        1 + self.trailing_activation_pct / 100):
                    order.trailing_active = True

                if order.trailing_active and trailing_stop_price is None:
                    trailing_stop_price = max(dynamic_price, order.entry_price)

            reason = None
            fill_price = price
            if order.stop_loss is not None and price <= order.stop_loss:
                reason = "STOP_LOSS"
                fill_price = order.stop_loss
            elif trailing_stop_price is not None and price <= trailing_stop_price:
                reason = "TRAILING_STOP"
                fill_price = trailing_stop_price
            elif order.take_profit is not None and price >= order.take_profit:
                reason = "TAKE_PROFIT"
                fill_price = order.take_profit
            elif time_exit_mins is not None and timestamp - order.entry_time >= timedelta(minutes=time_exit_mins):
                reason = "TIME_EXIT"
            elif eod_square_off and timestamp is not None and hasattr(timestamp, "time") and timestamp.time() >= dtime(15, 15):
                reason = "EOD_SQUARE_OFF"

            if reason:
                closed_order = self.close_position(order.order_id, fill_price, timestamp, reason)
                if closed_order:
                    closed.append(closed_order)
        return closed

    def get_positions(self) -> list[Order]:
        return [o for o in self.orders.values() if o.status == "OPEN"]

    def get_trade_history(self) -> list[Order]:
        return [o for o in self.orders.values() if o.status == "CLOSED"]

    def get_pnl(self, current_prices: dict = None) -> dict:
        realized = sum(o.realized_pnl for o in self.get_trade_history())
        unrealized = 0.0
        if current_prices:
            for o in self.get_positions():
                price = current_prices.get(o.symbol)
                if price is not None:
                    unrealized += o.unrealized_pnl(price)
        return {
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": realized + unrealized,
            "realized_pnl_today": self._realized_pnl_today,
        }
