"""
Simulated order execution — no broker calls, no real money. Tracks open positions,
applies stop-loss/take-profit/time-exit, and calculates realized + unrealized P&L.
Enforces strict Bid/Ask execution and 24-field audit logging.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time as dtime
from functools import cached_property
import logging
import time
from typing import Dict, List, Optional, Union
import uuid

from src.market_data.audit_record import AuditLogger, ExecutionAuditRecord
from src.market_data.quote_store import QuoteSnapshot
from src.utils.charges import calculate_charges

logger = logging.getLogger(__name__)


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
    canonical_id: Optional[str] = None
    fyers_symbol: Optional[str] = None
    decision_quote_version: int = 0
    execution_quote_version: int = 0

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.qty * self.lot_size

    @cached_property
    def underlying(self) -> str:
        """Derived from the symbol itself rather than a stored field/DB column -- avoids a
        migration and avoids handling NULL on pre-migration rows. See docs/ARCHITECTURE.md."""
        if "BANKNIFTY" in self.symbol:
            return "BANKNIFTY"
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
    DEFAULT_TRAILING_TIERS_PCT = [
        {"gain_pct": 10.0, "lock_pct": 0.0},
        {"gain_pct": 20.0, "lock_pct": 5.0},
        {"gain_pct": 30.0, "lock_pct": 10.0},
    ]

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        slippage_pct: float = 0.1,
        lot_size: int = 65,
        max_concurrent_positions: int = 5,
        max_daily_loss: float = 5000,
        max_trades_per_day_per_strategy: int = 2,
        trailing_stop_enabled: bool = False,
        trailing_activation_pct: float = 10.0,
        trailing_stop_pct: float = 15.0,
        trailing_tiers_pct: list = None,
        consecutive_loss_limit: int = None,
        consecutive_loss_cooldown_days: int = 1,
        max_drawdown_pct_of_capital: float = None,
        drawdown_cooldown_days: int = 3,
        drawdown_breaker_grace_trades: int = 3,
        capital_by_strategy: dict = None,
        charges_rates: dict = None,
        enable_wallets: bool = False,
        post_loss_cooldown_mins: int = 0,
        min_entry_premium: float = None,
        tiered_trailing_enabled: bool = False,
        tiered_rules: dict = None,
        expanding_dynamic_tsl_enabled: bool = False,
        multi_index_tsl: dict = None,
        logger=None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.lot_size = lot_size
        self.max_concurrent_positions = max_concurrent_positions
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day_per_strategy = max_trades_per_day_per_strategy
        self.min_entry_premium = min_entry_premium
        self.tiered_trailing_enabled = tiered_trailing_enabled
        self.tiered_rules = tiered_rules or {
            "tier1": {"max_entry_price": 200.0, "stop_loss_pct": 20.0, "cost_lock_pts": 15.0, "step_pts": 15.0, "step_lock_pts": 15.0, "target_pts": 60.0},
            "tier2": {"min_entry_price": 200.0, "max_entry_price": 600.0, "stop_loss_pct": 20.0, "cost_lock_pts": 20.0, "step_pts": 15.0, "step_lock_pts": 15.0, "target_pts": 120.0},
            "tier3": {"min_entry_price": 600.0, "stop_loss_pct": 15.0, "cost_lock_pts": 20.0, "step_pts": 15.0, "step_lock_pts": 15.0, "target_pts": 150.0},
        }
        self.expanding_dynamic_tsl_enabled = expanding_dynamic_tsl_enabled
        self.multi_index_tsl = multi_index_tsl or {
            "NIFTY": {
                "atm": {"max_entry_price": 200.0, "cost_lock_pts": 12.0, "trail_stage1_pts": 10.0, "stage1_threshold_pts": 20.0, "trail_stage2_pts": 15.0, "stage2_threshold_pts": 40.0, "target_pts": 60.0},
                "itm": {"min_entry_price": 200.0, "cost_lock_pts": 16.0, "trail_stage1_pts": 14.0, "stage1_threshold_pts": 30.0, "trail_stage2_pts": 20.0, "stage2_threshold_pts": 60.0, "target_pts": 90.0},
            },
            "BANKNIFTY": {
                "atm": {"max_entry_price": 350.0, "cost_lock_pts": 25.0, "trail_stage1_pts": 22.0, "stage1_threshold_pts": 45.0, "trail_stage2_pts": 32.0, "stage2_threshold_pts": 90.0, "target_pts": 120.0},
                "itm": {"min_entry_price": 350.0, "cost_lock_pts": 35.0, "trail_stage1_pts": 30.0, "stage1_threshold_pts": 60.0, "trail_stage2_pts": 45.0, "stage2_threshold_pts": 120.0, "target_pts": 180.0},
            },
            "SENSEX": {
                "atm": {"max_entry_price": 450.0, "cost_lock_pts": 30.0, "trail_stage1_pts": 28.0, "stage1_threshold_pts": 55.0, "trail_stage2_pts": 40.0, "stage2_threshold_pts": 110.0, "target_pts": 150.0},
                "itm": {"min_entry_price": 450.0, "cost_lock_pts": 40.0, "trail_stage1_pts": 36.0, "stage1_threshold_pts": 75.0, "trail_stage2_pts": 55.0, "stage2_threshold_pts": 150.0, "target_pts": 220.0},
            },
        }
        self.trailing_stop_enabled = trailing_stop_enabled
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_stop_pct = trailing_stop_pct
        tiers = trailing_tiers_pct if trailing_tiers_pct is not None else self.DEFAULT_TRAILING_TIERS_PCT
        self.trailing_tiers_pct = sorted(tiers, key=lambda t: t["gain_pct"], reverse=True)
        self.consecutive_loss_limit = consecutive_loss_limit
        self.consecutive_loss_cooldown_days = consecutive_loss_cooldown_days
        self.max_drawdown_pct_of_capital = max_drawdown_pct_of_capital
        self.drawdown_cooldown_days = drawdown_cooldown_days
        self.drawdown_breaker_grace_trades = drawdown_breaker_grace_trades
        self.capital_by_strategy = capital_by_strategy or {}
        self.charges_rates = charges_rates
        self.post_loss_cooldown_mins = post_loss_cooldown_mins
        self.logger = logger
        self.audit_logger = audit_logger
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

    def restore_daily_counts(
        self,
        day: date,
        trades_today: dict[str, int],
        realized_pnl_today: float = 0.0,
    ) -> None:
        self._current_day = day
        self._strategy_trades_today = dict(trades_today)
        self._realized_pnl_today = realized_pnl_today

    def has_open_position(self, strategy: str) -> bool:
        return any(o.strategy == strategy for o in self.get_positions())

    def _log_audit_record(
        self,
        event_id: str,
        strategy: Optional[str],
        canonical_id: Optional[str],
        fyers_symbol: str,
        side: str,
        qty: int,
        price: float,
        quote_snapshot: Optional[QuoteSnapshot],
        decision_ver: int,
        exec_ver: int,
        status: str,
        rejection_code: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        fill_price: Optional[float] = None,
    ) -> None:
        if not self.audit_logger:
            return

        # Parse canonical components
        underlying = "UNKNOWN"
        expiry_str = ""
        strike = 0.0
        opt_type = ""
        if canonical_id and "|" in canonical_id:
            parts = canonical_id.split("|")
            if len(parts) >= 4:
                underlying, expiry_str, strike_str, opt_type = parts[0], parts[1], parts[2], parts[3]
                try:
                    strike = float(strike_str)
                except ValueError:
                    pass
        elif "BANKNIFTY" in fyers_symbol:
            underlying = "BANKNIFTY"
        elif "SENSEX" in fyers_symbol:
            underlying = "SENSEX"
        elif "NIFTY" in fyers_symbol:
            underlying = "NIFTY"

        ltp = quote_snapshot.ltp if quote_snapshot else price
        bid = quote_snapshot.bid if quote_snapshot else 0.0
        ask = quote_snapshot.ask if quote_snapshot else 0.0
        ex_ts = quote_snapshot.exchange_timestamp if quote_snapshot else time.time()
        rx_ts = quote_snapshot.receive_epoch_timestamp if quote_snapshot else time.time()
        age_ms = quote_snapshot.age_ms() if quote_snapshot else 0.0
        now_ts = time.time()

        record = ExecutionAuditRecord(
            event_id=event_id,
            strategy_id=strategy or "UNKNOWN",
            canonical_instrument_id=canonical_id or fyers_symbol,
            underlying=underlying,
            expiry=expiry_str,
            strike=strike,
            option_type=opt_type,
            fyers_symbol=fyers_symbol,
            side=side,
            quantity=qty,
            ltp=ltp,
            bid=bid,
            ask=ask,
            decision_quote_version=decision_ver,
            execution_quote_version=exec_ver,
            exchange_timestamp=ex_ts,
            receive_timestamp=rx_ts,
            processing_timestamp=now_ts,
            execution_timestamp=now_ts,
            quote_age_ms=age_ms,
            execution_price=fill_price,
            status=status,
            rejection_code=rejection_code,
            rejection_reason=rejection_reason,
        )
        self.audit_logger.log_record(record)

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        stop_loss: float = None,
        take_profit: float = None,
        strategy: str = None,
        timestamp: datetime = None,
        lot_size: int = None,
        canonical_instrument_id: Optional[str] = None,
        fyers_symbol: Optional[str] = None,
        quote_snapshot: Optional[QuoteSnapshot] = None,
        decision_quote_version: int = 0,
        execution_quote_version: int = 0,
    ) -> Order:
        timestamp = timestamp or datetime.now()
        self._roll_day(timestamp)
        lot_size = lot_size if lot_size is not None else self.lot_size
        actual_symbol = fyers_symbol or symbol
        event_id = str(uuid.uuid4())

        def _reject(code: str, reason: str):
            self._log_audit_record(
                event_id=event_id,
                strategy=strategy,
                canonical_id=canonical_instrument_id,
                fyers_symbol=actual_symbol,
                side=side,
                qty=qty,
                price=price,
                quote_snapshot=quote_snapshot,
                decision_ver=decision_quote_version,
                exec_ver=execution_quote_version,
                status="REJECTED",
                rejection_code=code,
                rejection_reason=reason,
            )
            raise RiskLimitExceeded(reason)

        if self.max_daily_loss is not None and self._realized_pnl_today <= -abs(self.max_daily_loss):
            _reject("REJECTED_DAILY_LOSS_LIMIT", f"Daily loss limit of {self.max_daily_loss} already hit")

        if self.max_concurrent_positions is not None and len(self.get_positions()) >= self.max_concurrent_positions:
            _reject("REJECTED_MAX_CONCURRENT_POSITIONS", f"Max concurrent positions ({self.max_concurrent_positions}) reached")

        if strategy is not None and self.has_open_position(strategy):
            _reject("REJECTED_STRATEGY_POSITION_EXISTS", f"Strategy '{strategy}' already has an open position")

        if strategy is not None and self._strategy_trades_today.get(strategy, 0) >= self.max_trades_per_day_per_strategy:
            _reject(
                "REJECTED_MAX_TRADES_PER_DAY",
                f"Strategy '{strategy}' already hit its {self.max_trades_per_day_per_strategy} trades/day limit",
            )

        if strategy is not None:
            paused_until = self._strategy_paused_until.get(strategy)
            if paused_until is not None and timestamp.date() < paused_until:
                _reject(
                    "REJECTED_STRATEGY_PAUSED",
                    f"Strategy '{strategy}' is paused by a circuit breaker until {paused_until}",
                )

            if self.post_loss_cooldown_mins > 0:
                last_exit = getattr(self, "_strategy_last_exit", {}).get(strategy)
                if last_exit and last_exit.get("realized_pnl", 0) <= 0:
                    cooldown_expiry = last_exit["exit_time"] + timedelta(minutes=self.post_loss_cooldown_mins)
                    if timestamp < cooldown_expiry:
                        _reject(
                            "REJECTED_POST_LOSS_COOLDOWN",
                            f"Strategy '{strategy}' in {self.post_loss_cooldown_mins}-min post-loss cooldown until {cooldown_expiry.strftime('%H:%M:%S')}",
                        )

        if self.min_entry_premium is not None and price < self.min_entry_premium:
            _reject(
                "REJECTED_MIN_PREMIUM_FLOOR",
                f"Entry premium Rs.{price:.2f} is below minimum allowed floor Rs.{self.min_entry_premium:.2f}",
            )

        # For BUY: executable price is Ask, with optional slippage
        fill_price = price * (1 + self.slippage_pct / 100) if side == "BUY" else price * (1 - self.slippage_pct / 100)
        order_value = fill_price * qty * lot_size
        entry_charges = calculate_charges(order_value, "BUY", self.charges_rates).total

        if strategy is not None and strategy in self.wallet_balance:
            required = order_value + entry_charges
            available = self.wallet_balance[strategy]
            if required > available:
                _reject(
                    "REJECTED_INSUFFICIENT_WALLET",
                    f"Strategy '{strategy}' wallet balance (Rs.{available:,.2f}) insufficient for this order (Rs.{required:,.2f} needed)",
                )

        order = Order(
            order_id=event_id,
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
            canonical_id=canonical_instrument_id,
            fyers_symbol=actual_symbol,
            decision_quote_version=decision_quote_version,
            execution_quote_version=execution_quote_version or (quote_snapshot.version if quote_snapshot else 0),
        )
        self.orders[order.order_id] = order
        if strategy is not None:
            self._strategy_trades_today[strategy] = self._strategy_trades_today.get(strategy, 0) + 1
            if strategy in self.wallet_balance:
                self.wallet_balance[strategy] -= order_value + entry_charges

        self._log_audit_record(
            event_id=order.order_id,
            strategy=strategy,
            canonical_id=canonical_instrument_id,
            fyers_symbol=actual_symbol,
            side=side,
            qty=qty,
            price=price,
            quote_snapshot=quote_snapshot,
            decision_ver=decision_quote_version,
            exec_ver=order.execution_quote_version,
            status="FILLED",
            fill_price=fill_price,
        )

        if self.logger:
            self.logger.log_trade(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self.orders.get(order_id)
        if not order or order.status != "OPEN":
            return False
        order.status = "CANCELLED"
        return True

    def close_position(
        self,
        order_id: str,
        price: float,
        timestamp: datetime = None,
        reason: str = "MANUAL",
        quote_snapshot: Optional[QuoteSnapshot] = None,
        decision_quote_version: int = 0,
        execution_quote_version: int = 0,
    ) -> Optional[Order]:
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

        # Audit record for exit execution (SELL at Bid)
        self._log_audit_record(
            event_id=str(uuid.uuid4()),
            strategy=order.strategy,
            canonical_id=order.canonical_id,
            fyers_symbol=order.fyers_symbol or order.symbol,
            side="SELL",
            qty=order.qty,
            price=price,
            quote_snapshot=quote_snapshot,
            decision_ver=decision_quote_version or (quote_snapshot.version if quote_snapshot else 0),
            exec_ver=execution_quote_version or (quote_snapshot.version if quote_snapshot else 0),
            status="FILLED",
            fill_price=price,
        )

        if self.logger:
            self.logger.log_trade(order)
        return order

    def get_wallet(self, strategy: str) -> Optional[dict]:
        if strategy not in self.wallet_balance:
            return None
        allocated = self.capital_by_strategy.get(strategy, 0.0)
        balance = self.wallet_balance[strategy]
        return {
            "strategy": strategy,
            "balance": round(balance, 2),
            "allocated_capital": allocated,
            "pnl_in_wallet": round(balance - allocated, 2),
        }

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
                {"strategy": strategy},
            )

    def _update_circuit_breakers(self, strategy: str, realized_pnl: float, exit_date: date) -> None:
        if realized_pnl > 0:
            self._strategy_consecutive_losses[strategy] = 0
        else:
            losses = self._strategy_consecutive_losses.get(strategy, 0) + 1
            self._strategy_consecutive_losses[strategy] = losses
            if self.consecutive_loss_limit is not None and losses >= self.consecutive_loss_limit:
                self._pause_strategy(strategy, exit_date, self.consecutive_loss_cooldown_days)
                self._strategy_consecutive_losses[strategy] = 0

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

    def update_positions(
        self,
        current_prices: dict,
        timestamp: datetime = None,
        time_exit_mins: int = None,
        eod_square_off: bool = False,
    ) -> list[Order]:
        """
        current_prices: {symbol: float | QuoteSnapshot}.
        Applies SL/TP/TSL/time-exit/EOD square-off.
        Separates trigger evaluation from exit execution fill (fills strictly at Bid).
        """
        timestamp = timestamp or datetime.now()
        closed = []
        for order in self.get_positions():
            quote_val = (
                current_prices.get(order.canonical_id)
                or current_prices.get(order.fyers_symbol)
                or current_prices.get(order.symbol)
            )
            if quote_val is None:
                continue

            quote_snap: Optional[QuoteSnapshot] = None
            if isinstance(quote_val, QuoteSnapshot):
                quote_snap = quote_val
                eval_price = quote_snap.ltp
                exec_bid = quote_snap.bid
            elif isinstance(quote_val, dict):
                eval_price = float(quote_val.get("ltp", 0.0))
                exec_bid = float(quote_val.get("bid", 0.0))
            else:
                eval_price = float(quote_val)
                exec_bid = eval_price

            if eval_price <= 0:
                continue

            trailing_stop_price = None
            if self.trailing_stop_enabled and order.entry_price:
                order.peak_price = max(order.peak_price, eval_price)
                peak_gain_pts = order.peak_price - order.entry_price
                ep = order.entry_price

                if getattr(self, "expanding_dynamic_tsl_enabled", True):
                    underlying = order.underlying
                    index_rules = self.multi_index_tsl.get(underlying, self.multi_index_tsl.get("NIFTY", {}))
                    is_itm = "_ITM" in (order.strategy or "") or (ep >= index_rules.get("itm", {}).get("min_entry_price", 200.0))
                    rule = index_rules.get("itm" if is_itm else "atm", {})

                    cost_lock = rule.get("cost_lock_pts", 12.0)
                    stage1_thresh = rule.get("stage1_threshold_pts", 20.0)
                    trail1 = rule.get("trail_stage1_pts", 10.0)
                    stage2_thresh = rule.get("stage2_threshold_pts", 40.0)
                    trail2 = rule.get("trail_stage2_pts", 15.0)

                    if peak_gain_pts >= stage2_thresh:
                        order.trailing_active = True
                        trailing_stop_price = max(ep, order.peak_price - trail2)
                    elif peak_gain_pts >= stage1_thresh:
                        order.trailing_active = True
                        trailing_stop_price = max(ep, order.peak_price - trail1)
                    elif peak_gain_pts >= cost_lock:
                        order.trailing_active = True
                        trailing_stop_price = ep
                elif self.tiered_trailing_enabled:
                    if ep < 200.0:
                        if peak_gain_pts >= 45.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 30.0
                        elif peak_gain_pts >= 30.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 15.0
                        elif peak_gain_pts >= 15.0:
                            order.trailing_active = True
                            trailing_stop_price = ep
                    elif ep <= 600.0:
                        if peak_gain_pts >= 70.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 50.0
                        elif peak_gain_pts >= 50.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 30.0
                        elif peak_gain_pts >= 35.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 15.0
                        elif peak_gain_pts >= 20.0:
                            order.trailing_active = True
                            trailing_stop_price = ep
                    else:
                        if peak_gain_pts >= 75.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 50.0
                        elif peak_gain_pts >= 50.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 30.0
                        elif peak_gain_pts >= 35.0:
                            order.trailing_active = True
                            trailing_stop_price = ep + 15.0
                        elif peak_gain_pts >= 20.0:
                            order.trailing_active = True
                            trailing_stop_price = ep
                else:
                    gain_pct = (order.peak_price - order.entry_price) / order.entry_price * 100
                    stepped_price = None
                    for tier in self.trailing_tiers_pct:
                        if gain_pct >= tier["gain_pct"]:
                            order.trailing_active = True
                            stepped_price = order.entry_price * (1 + tier["lock_pct"] / 100)
                            break
                    dynamic_price = order.peak_price * (1 - self.trailing_stop_pct / 100)
                    if stepped_price is not None:
                        trailing_stop_price = max(stepped_price, dynamic_price)
                    elif order.trailing_active:
                        trailing_stop_price = max(dynamic_price, order.entry_price)

                if trailing_stop_price is not None:
                    prev_tsl = getattr(order, "_highest_trailing_stop", None)
                    if prev_tsl is not None:
                        trailing_stop_price = max(trailing_stop_price, prev_tsl)
                    order._highest_trailing_stop = trailing_stop_price

            reason = None
            if order.stop_loss is not None and eval_price <= order.stop_loss:
                reason = "STOP_LOSS"
            elif trailing_stop_price is not None and eval_price <= trailing_stop_price:
                reason = "TRAILING_STOP"
            elif order.take_profit is not None and eval_price >= order.take_profit:
                reason = "TAKE_PROFIT"
            elif time_exit_mins is not None and timestamp - order.entry_time >= timedelta(minutes=time_exit_mins):
                reason = "TIME_EXIT"
            elif eod_square_off and timestamp is not None and hasattr(timestamp, "time") and timestamp.time() >= dtime(15, 15):
                reason = "EOD_SQUARE_OFF"

            if reason:
                if isinstance(quote_val, QuoteSnapshot) and exec_bid > 0:
                    fill_price = exec_bid * (1 - self.slippage_pct / 100)
                else:
                    # Backtest / flat float price mode
                    if reason == "STOP_LOSS":
                        fill_price = order.stop_loss
                    elif reason == "TAKE_PROFIT":
                        fill_price = order.take_profit
                    elif reason == "TRAILING_STOP":
                        fill_price = trailing_stop_price if trailing_stop_price is not None else eval_price
                    else:
                        fill_price = eval_price * (1 - self.slippage_pct / 100)

                closed_order = self.close_position(
                    order.order_id,
                    fill_price,
                    timestamp,
                    reason,
                    quote_snapshot=quote_snap,
                )
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
                quote_val = (
                    current_prices.get(o.canonical_id)
                    or current_prices.get(o.fyers_symbol)
                    or current_prices.get(o.symbol)
                )
                if quote_val is not None:
                    price = quote_val.ltp if isinstance(quote_val, QuoteSnapshot) else float(quote_val)
                    unrealized += o.unrealized_pnl(price)
        return {
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": realized + unrealized,
            "realized_pnl_today": self._realized_pnl_today,
        }
