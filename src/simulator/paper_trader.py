"""
Simulated order execution — no broker calls, no real money. Tracks open positions,
applies stop-loss/take-profit/time-exit, and calculates realized + unrealized P&L.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


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
    realized_pnl: Optional[float] = None

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.qty * self.lot_size


class RiskLimitExceeded(Exception):
    pass


class PaperTrader:
    def __init__(self, initial_capital: float = 1_000_000, slippage_pct: float = 0.1,
                 lot_size: int = 75, max_concurrent_positions: int = 5,
                 max_daily_loss: float = 5000, logger=None):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.lot_size = lot_size
        self.max_concurrent_positions = max_concurrent_positions
        self.max_daily_loss = max_daily_loss
        self.logger = logger

        self.orders: dict[str, Order] = {}
        self._realized_pnl_today = 0.0
        self._current_day = None

    def _roll_day(self, timestamp: datetime) -> None:
        day = timestamp.date()
        if self._current_day != day:
            self._current_day = day
            self._realized_pnl_today = 0.0

    def _open_positions(self) -> list[Order]:
        return [o for o in self.orders.values() if o.status == "OPEN"]

    def place_order(self, symbol: str, side: str, qty: int, price: float,
                     stop_loss: float = None, take_profit: float = None,
                     strategy: str = None, timestamp: datetime = None) -> Order:
        timestamp = timestamp or datetime.now()
        self._roll_day(timestamp)

        if self._realized_pnl_today <= -abs(self.max_daily_loss):
            raise RiskLimitExceeded(f"Daily loss limit of {self.max_daily_loss} already hit")
        if len(self._open_positions()) >= self.max_concurrent_positions:
            raise RiskLimitExceeded(f"Max concurrent positions ({self.max_concurrent_positions}) reached")

        fill_price = price * (1 + self.slippage_pct / 100) if side == "BUY" else price * (1 - self.slippage_pct / 100)

        order = Order(
            # UUID, not a sequential counter: the web backend persists orders to Postgres across
            # process restarts, where a counter that resets to 1 each time would collide with an
            # already-persisted order_id — see docs/ARCHITECTURE.md.
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            qty=qty,
            lot_size=self.lot_size,
            entry_price=fill_price,
            entry_time=timestamp,
            status="OPEN",
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
        )
        self.orders[order.order_id] = order
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
        order.status = "CLOSED"

        self._roll_day(order.exit_time)
        self._realized_pnl_today += order.realized_pnl

        if self.logger:
            self.logger.log_trade(order)
        return order

    def update_positions(self, current_prices: dict, timestamp: datetime = None,
                          time_exit_mins: int = None) -> list[Order]:
        """current_prices: {symbol: ltp}. Applies SL/TP/time-exit. Returns orders closed this call."""
        timestamp = timestamp or datetime.now()
        closed = []
        for order in self._open_positions():
            price = current_prices.get(order.symbol)
            if price is None:
                continue

            reason = None
            if order.stop_loss is not None and price <= order.stop_loss:
                reason = "STOP_LOSS"
            elif order.take_profit is not None and price >= order.take_profit:
                reason = "TAKE_PROFIT"
            elif time_exit_mins is not None and timestamp - order.entry_time >= timedelta(minutes=time_exit_mins):
                reason = "TIME_EXIT"

            if reason:
                closed_order = self.close_position(order.order_id, price, timestamp, reason)
                if closed_order:
                    closed.append(closed_order)
        return closed

    def get_positions(self) -> list[Order]:
        return self._open_positions()

    def get_trade_history(self) -> list[Order]:
        return [o for o in self.orders.values() if o.status == "CLOSED"]

    def get_pnl(self, current_prices: dict = None) -> dict:
        realized = sum(o.realized_pnl for o in self.get_trade_history())
        unrealized = 0.0
        if current_prices:
            for o in self._open_positions():
                price = current_prices.get(o.symbol)
                if price is not None:
                    unrealized += o.unrealized_pnl(price)
        return {
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": realized + unrealized,
            "realized_pnl_today": self._realized_pnl_today,
        }
