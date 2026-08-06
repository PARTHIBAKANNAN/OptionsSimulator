"""
Backend adapter around src/trader.py's LiveTrader: persists to Postgres instead of files,
publishes state into app.state.shared_state for the Broadcaster, and lets a signal be approved
either via Telegram (unchanged) or the web (POST /api/paper/signals/{id}/approve|reject) —
whichever comes first wins (see app.state.PendingSignalRegistry).

Falls back to replaying data/historical/nifty_90days.csv on a loop when data_engine_enabled is
False (local dev, or the corporate network blocking live Fyers WebSocket access) so the UI always
has something to show.
"""
import asyncio
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.trader import IST, LiveTrader, is_market_open
from src.data_manager import Candle
from src.simulator.paper_trader import Order, RiskLimitExceeded
from src.utils.options_pricing import (
    black_scholes_price, format_display_symbol, next_weekly_expiry_date, next_weekly_expiry_days,
    parse_option_symbol,
)

from .state import shared_state, pending_signals
from . import db

HISTORICAL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "historical" / "nifty_90days.csv"
REPLAY_SECONDS_PER_CANDLE = 0.05


class WebLiveEngine(LiveTrader):
    def __init__(self, config, data_engine_enabled: bool):
        super().__init__(config)
        self.data_engine_enabled = data_engine_enabled
        self._replay_df: pd.DataFrame | None = None

    # ---- State publishing (feeds the Broadcaster) ----------------------------------

    def _publish_state(self) -> None:
        state = self.data_manager.get_state()
        current_prices = {sym: q.ltp for sym, q in self.data_manager.get_option_chain().items()}
        pnl = self.paper_trader.get_pnl(current_prices)

        now = datetime.now(IST)
        today = now.date()
        nifty_price = state["nifty_price"]
        prev_close = self.data_manager.get_prev_close(today)
        change = (nifty_price - prev_close) if (nifty_price is not None and prev_close) else None
        change_pct = (change / prev_close * 100) if (change is not None and prev_close) else None

        shared_state.update({
            "nifty_price": nifty_price,
            "nifty_prev_close": prev_close,
            "nifty_change": round(change, 2) if change is not None else None,
            "nifty_change_pct": round(change_pct, 2) if change_pct is not None else None,
            "nifty_sparkline": [c.close for c in self.data_manager.get_today_candles(today)],
            "timestamp": state["timestamp"].isoformat() if state["timestamp"] else None,
            "market_open": self.is_running,
            # Real exchange-hours state (item 3C/B) — distinct from market_open above, which is
            # actually just "is the engine process running" and stays true all day regardless of
            # trading hours. Always real wall-clock time, even in replay mode (the simulated data's
            # own clock isn't what a "market closed" pill should reflect for a local-dev fallback).
            "exchange_open": self.config.force_market_open or is_market_open(now, self.config.risk_params),
            "mode": "live" if self.data_engine_enabled else "replay",
            "signals": [self._signal_dict(s) for s in self.recent_signals],
            "pending_signals": pending_signals.list_pending(),
            "positions": [self._order_dict(o) for o in self.paper_trader.get_positions()],
            "pnl": pnl,
            "fyers_authenticated": bool(self.fyers.access_token) if self.data_engine_enabled else None,
            "strategy_status": self._strategy_status_list(current_prices),
        })

    def _strategy_status_list(self, current_prices: dict) -> list[dict]:
        """One row per registered strategy (see create_all_strategies) — quantman-style: waiting
        for a signal, the currently open position's contract/entry/LTP/trade P&L/SL/TP, or (once
        flat) the last signal closed today with the same shape, plus that strategy's own P&L for
        today (realized trades today + any open position's unrealized). last_closed_today is what
        lets the UI keep an expand affordance up after a signal closes for the day, not just while
        it's open — see docs/ARCHITECTURE.md."""
        today = datetime.now(IST).date()
        open_by_strategy: dict[str, list] = {}
        for order in self.paper_trader.get_positions():
            open_by_strategy.setdefault(order.strategy, []).append(order)

        closed_today_by_strategy: dict[str, list] = {}
        for order in self.paper_trader.get_trade_history():
            if order.exit_time and order.exit_time.astimezone(IST).date() == today:
                closed_today_by_strategy.setdefault(order.strategy, []).append(order)

        rows = []
        for strategy in self.strategy_engine.strategies:
            name = strategy.name
            opens = open_by_strategy.get(name, [])
            closed_today = closed_today_by_strategy.get(name, [])
            today_pnl = sum(o.realized_pnl for o in closed_today)

            entry = None
            last_closed = None
            if opens:
                latest = max(opens, key=lambda o: o.entry_time)
                ltp = current_prices.get(latest.symbol)
                trade_pnl = latest.unrealized_pnl(ltp) if ltp is not None else None
                if trade_pnl is not None:
                    today_pnl += trade_pnl
                entry = {
                    "contract": format_display_symbol(latest.symbol, next_weekly_expiry_date(latest.entry_time)),
                    "entry_price": latest.entry_price,
                    "entry_time": latest.entry_time.isoformat(),
                    "ltp": ltp,
                    "trade_pnl": trade_pnl,
                    "stop_loss": latest.stop_loss,
                    "take_profit": latest.take_profit,
                }
            elif closed_today:
                last = max(closed_today, key=lambda o: o.exit_time)
                last_closed = {
                    "contract": format_display_symbol(last.symbol, next_weekly_expiry_date(last.entry_time)),
                    "entry_price": last.entry_price,
                    "entry_time": last.entry_time.isoformat(),
                    "exit_price": last.exit_price,
                    "exit_time": last.exit_time.isoformat(),
                    "pnl": last.net_pnl if last.net_pnl is not None else last.realized_pnl,
                    "exit_reason": last.exit_reason,
                    "stop_loss": last.stop_loss,
                    "take_profit": last.take_profit,
                }

            rows.append({
                "strategy": name,
                "status": "SIGNAL_ENTERED" if opens else "WAITING",
                "entry": entry,
                "last_closed_today": last_closed,
                "today_pnl": round(today_pnl, 2),
            })
        return rows

    @staticmethod
    def _signal_dict(signal) -> dict:
        return {
            "strategy": signal.strategy, "direction": signal.direction, "strike": signal.strike,
            "entry_price": signal.entry_price, "confidence": signal.confidence,
            "rationale": signal.rationale, "timestamp": signal.timestamp.isoformat(),
            "contract": format_display_symbol(signal.strike, next_weekly_expiry_date(signal.timestamp)),
        }

    @staticmethod
    def _order_dict(order) -> dict:
        return {
            "order_id": order.order_id, "symbol": order.symbol, "qty": order.qty,
            "entry_price": order.entry_price, "stop_loss": order.stop_loss,
            "take_profit": order.take_profit, "strategy": order.strategy,
            "entry_time": order.entry_time.isoformat(),
            "contract": format_display_symbol(order.symbol, next_weekly_expiry_date(order.entry_time)),
        }

    # ---- Postgres persistence (replaces StateManager's files for the web path) -----
    # Best-effort: if the DB isn't configured/reachable/slow, log and continue — in-memory
    # paper-trading correctness never depends on persistence succeeding. DB_TIMEOUT_SECS is a
    # hard ceiling per call, applied via asyncio.wait_for around the WHOLE pool.execute() —
    # not asyncpg's own `timeout=` kwarg, which only bounds the query once a connection is
    # already acquired. The observed hang (one trade, then frozen forever, zero exceptions,
    # no server-side trace of the query) was in Pool.acquire() itself, which asyncpg gives no
    # default timeout at all — Pool.execute(timeout=...) never even got a chance to apply.

    DB_TIMEOUT_SECS = 5.0
    TELEGRAM_TIMEOUT_SECS = 10.0

    async def _db_execute(self, query: str, *args) -> None:
        # Replay mode is a local-dev/fallback data source (simulated historical candles fired at
        # ~50ms/candle) -- it must never write to the SAME Postgres table live trading uses. This
        # was a real incident: replay test runs on 2026-08-03 left 11 never-closed positions in
        # options_positions with entry_time values from May-July (the replayed CSV's own dates),
        # which _restore_state() then resurrected as if they were live open positions on every
        # subsequent restart -- 13 phantom "open positions" blocked every real signal from firing
        # at all once they exceeded max_concurrent_positions. See docs/ARCHITECTURE.md.
        if not self.data_engine_enabled:
            return
        try:
            pool = db.get_pool()
        except RuntimeError:
            return
        try:
            await asyncio.wait_for(pool.execute(query, *args), timeout=self.DB_TIMEOUT_SECS)
        except Exception as e:
            self.logger.log_error(f"DB write failed/timed out, continuing without it: {e}")

    async def _save_position_db(self, order) -> None:
        await self._db_execute(
            """INSERT INTO options_positions
               (order_id, symbol, side, qty, lot_size, entry_price, entry_time, status,
                stop_loss, take_profit, strategy, entry_charges)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
               ON CONFLICT (order_id) DO UPDATE SET status = EXCLUDED.status""",
            order.order_id, order.symbol, order.side, order.qty, order.lot_size,
            order.entry_price, order.entry_time, order.status, order.stop_loss,
            order.take_profit, order.strategy, order.entry_charges,
        )

    async def _close_position_db(self, order) -> None:
        await self._db_execute(
            """UPDATE options_positions SET status=$2, exit_price=$3, exit_time=$4,
               exit_reason=$5, realized_pnl=$6, exit_charges=$7 WHERE order_id=$1""",
            order.order_id, order.status, order.exit_price, order.exit_time,
            order.exit_reason, order.realized_pnl, order.exit_charges,
        )

    async def _save_wallet_db(self, strategy: str) -> None:
        wallet = self.paper_trader.get_wallet(strategy)
        if wallet is None:
            return
        await self._db_execute(
            """INSERT INTO options_wallets (strategy, balance, allocated_capital, updated_at)
               VALUES ($1, $2, $3, now())
               ON CONFLICT (strategy) DO UPDATE SET balance = EXCLUDED.balance, updated_at = now()""",
            strategy, wallet["balance"], wallet["allocated_capital"],
        )

    async def _restore_state(self) -> None:
        """Restores durable state across a restart: without this, a fresh WebLiveEngine always
        rebuilds an empty in-memory PaperTrader, silently discarding every strategy's compounded
        wallet balance and orphaning any position that was still OPEN at the moment of restart
        (this happened for real on 2026-08-05 — two live orders were never seen again). Best-effort
        like every other DB call here: if this fails, start fresh rather than block startup.

        Scoped to positions opened TODAY (IST) only — these are intraday options with a 2-hour
        time-exit, so anything still OPEN from an earlier calendar day is by definition stale data
        from a crash or (before _db_execute's data_engine_enabled guard existed) a replay test run,
        never a real position waiting to be managed. Restoring those unconditionally is exactly
        what caused 13 phantom "open positions" to block every real signal on 2026-08-06."""
        try:
            pool = db.get_pool()
        except RuntimeError:
            return

        today = datetime.now(IST).date()
        try:
            wallet_rows = await asyncio.wait_for(
                pool.fetch("SELECT strategy, balance FROM options_wallets"), timeout=self.DB_TIMEOUT_SECS)
            restored_wallets = 0
            for row in wallet_rows:
                if row["strategy"] in self.paper_trader.wallet_balance:
                    self.paper_trader.wallet_balance[row["strategy"]] = float(row["balance"])
                    restored_wallets += 1

            open_rows = await asyncio.wait_for(
                pool.fetch(
                    """SELECT order_id, symbol, side, qty, lot_size, entry_price, entry_time,
                              stop_loss, take_profit, strategy, entry_charges
                       FROM options_positions
                       WHERE status = 'OPEN' AND (entry_time AT TIME ZONE 'Asia/Kolkata')::date = $1""",
                    today),
                timeout=self.DB_TIMEOUT_SECS)
            for row in open_rows:
                entry_price = float(row["entry_price"])
                order = Order(
                    order_id=row["order_id"], symbol=row["symbol"], side=row["side"], qty=row["qty"],
                    lot_size=row["lot_size"], entry_price=entry_price, entry_time=row["entry_time"],
                    status="OPEN", stop_loss=row["stop_loss"] and float(row["stop_loss"]),
                    take_profit=row["take_profit"] and float(row["take_profit"]), strategy=row["strategy"],
                    peak_price=entry_price, entry_charges=float(row["entry_charges"] or 0.0),
                )
                self.paper_trader.orders[order.order_id] = order

            # Reconstructs today's per-strategy trade count and realized P&L too -- without this,
            # max_trades_per_day_per_strategy and the daily-loss breaker both silently reset to
            # zero on every restart. Confirmed live on 2026-08-06: 3 restarts in one trading day
            # let MACD_BULLISH place 3 entries despite its 2/day cap, since each restart's fresh
            # in-memory counter had no idea the previous run had already placed 2.
            trade_count_rows = await asyncio.wait_for(
                pool.fetch(
                    """SELECT strategy, COUNT(*) AS cnt FROM options_positions
                       WHERE strategy IS NOT NULL AND (entry_time AT TIME ZONE 'Asia/Kolkata')::date = $1
                       GROUP BY strategy""",
                    today),
                timeout=self.DB_TIMEOUT_SECS)
            trades_today = {row["strategy"]: row["cnt"] for row in trade_count_rows}

            realized_row = await asyncio.wait_for(
                pool.fetchrow(
                    """SELECT COALESCE(SUM(realized_pnl), 0) AS total FROM options_positions
                       WHERE status = 'CLOSED' AND (exit_time AT TIME ZONE 'Asia/Kolkata')::date = $1""",
                    today),
                timeout=self.DB_TIMEOUT_SECS)
            realized_pnl_today = float(realized_row["total"]) if realized_row else 0.0

            self.paper_trader.restore_daily_counts(today, trades_today, realized_pnl_today)

            if restored_wallets or open_rows:
                self.logger.log_websocket_event(
                    "state_restored", {"wallets": restored_wallets, "open_positions": len(open_rows)})
        except Exception as e:
            self.logger.log_error(f"State restore failed, starting fresh: {e}")

    async def _save_signal_db(self, signal_id: str, signal, status: str) -> None:
        await self._db_execute(
            """INSERT INTO options_signals
               (id, strategy, direction, strike, confidence, rationale, entry_price, timestamp, status)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
               ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status""",
            signal_id, signal.strategy, signal.direction, signal.strike, signal.confidence,
            signal.rationale, signal.entry_price, signal.timestamp, status,
        )

    # ---- Overrides: dual-path (web + Telegram) signal approval ----------------------

    def evaluate_strategies(self):
        signals = super().evaluate_strategies()
        self._publish_state()
        return signals

    def _on_market_closed_tick(self) -> None:
        self._publish_state()

    async def execute_signal(self, signal) -> None:
        signal_id = str(uuid.uuid4())

        # Replay mode fires signals every ~50ms (see _start_replay) — real human approval has no
        # meaning there (no one's watching a simulated 90-day replay tick by tick), and routing
        # each one through Telegram exhausts its connection pool almost immediately. Auto-approve
        # instead, so replay actually produces positions/trade history to look at.
        #
        # auto_mode (config/risk_params.json's live_mode.auto_approve) applies the same
        # auto-approve path to LIVE data too. This never places a real broker order either way —
        # it's still paper trading — so the manual-tap gate below (a self-imposed precaution
        # originally aimed at eventual real order placement, see
        # docs/planning-archive/FYERS_FEASIBILITY_REPORT.md) isn't required for it. Telegram still
        # gets a trade-execution notice once the paper order actually fills (see below), just
        # without blocking on a reply first.
        if not self.data_engine_enabled or self.auto_mode:
            await self._save_signal_db(signal_id, signal, "approve")
            decision = "approve"
        else:
            loop = asyncio.get_event_loop()
            future = pending_signals.register(signal_id, self._signal_dict(signal) | {"id": signal_id}, loop)
            await self._save_signal_db(signal_id, signal, "pending")
            self._publish_state()

            if self.telegram:
                try:
                    telegram_signal_id = await asyncio.wait_for(
                        self.telegram.send_signal_alert(signal), timeout=self.TELEGRAM_TIMEOUT_SECS)
                    asyncio.create_task(self._await_telegram_and_resolve(telegram_signal_id, signal_id))
                except Exception as e:
                    self.logger.log_error(f"Telegram alert failed, web approval still available: {e}")

            try:
                decision = await asyncio.wait_for(future, timeout=300)
            except asyncio.TimeoutError:
                pending_signals.resolve(signal_id, "timeout")
                decision = "timeout"

            await self._save_signal_db(signal_id, signal, decision)

        self._publish_state()

        if decision != "approve":
            return

        stop_loss = max(signal.entry_price * (1 - self.stop_loss_pct / 100), 0.05)
        take_profit = signal.entry_price + self.take_profit_pts
        try:
            order = self.paper_trader.place_order(
                symbol=signal.strike, side="BUY", qty=self.qty_per_signal, price=signal.entry_price,
                stop_loss=stop_loss, take_profit=take_profit, strategy=signal.strategy,
                timestamp=signal.timestamp,
            )
        except RiskLimitExceeded as e:
            self.logger.log_error(f"Signal rejected by risk limits: {e}", {"strategy": signal.strategy})
            return

        await self._save_position_db(order)
        if order.strategy:
            asyncio.create_task(self._save_wallet_db(order.strategy))
        self._publish_state()
        # Gated by data_engine_enabled, not just `if self.telegram:` — Telegram credentials are
        # configured VM-wide, so this ran unconditionally on every fill regardless of mode. Fixed
        # alongside the real freeze bug (a tz-naive/aware datetime subtraction in
        # _check_exits_replay — see there); this one and the timeout are still worth keeping so a
        # slow/down Telegram API can't block live trading either.
        if self.telegram and self.data_engine_enabled:
            try:
                await asyncio.wait_for(self.telegram.send_trade_execution(order), timeout=self.TELEGRAM_TIMEOUT_SECS)
            except Exception as e:
                self.logger.log_error(f"Telegram trade-execution notice failed: {e}")

    async def _await_telegram_and_resolve(self, telegram_signal_id: str, our_signal_id: str) -> None:
        decision = await self.telegram.await_decision(telegram_signal_id, timeout_secs=300)
        pending_signals.resolve(our_signal_id, decision)

    def approve_signal(self, signal_id: str, decision: str) -> bool:
        """Called by the REST endpoint. Returns False if the signal was already resolved/unknown."""
        return pending_signals.resolve(signal_id, decision)

    # ---- Live-mode exit checks (option-chain LTP, matches the CLI's behavior) -------

    def check_exits(self) -> None:
        # Must pass an explicit IST-aware timestamp — otherwise update_positions() defaults to
        # tz-naive datetime.now(), which raises `TypeError: Cannot subtract tz-naive and
        # tz-aware datetime-like objects` against order.entry_time (tz-aware, from on_tick's
        # datetime.now(IST)) the instant a position survives to its time-exit check. This was
        # the real-money-free repeat of the original freeze bug (see _check_exits_replay) — it
        # hit live mode the first time it ever ran with a real open position (2026-08-05).
        current_prices = {sym: q.ltp for sym, q in self.data_manager.get_option_chain().items()}
        closed = self.paper_trader.update_positions(
            current_prices, timestamp=datetime.now(IST), time_exit_mins=self.time_exit_mins)
        for order in closed:
            asyncio.create_task(self._close_position_db(order))
            if order.strategy:
                asyncio.create_task(self._save_wallet_db(order.strategy))
        self._publish_state()

    # ---- Entry point: live Fyers vs local replay -------------------------------------

    async def start(self) -> None:
        if self.data_engine_enabled:
            await self._restore_state()
            await super().start()
        else:
            await self._start_replay()

    async def stop(self) -> None:
        self.is_running = False
        if self.data_engine_enabled:
            await super().stop()

    async def _start_replay(self) -> None:
        if not HISTORICAL_PATH.exists():
            self.logger.log_error(f"Replay mode: no historical data at {HISTORICAL_PATH}")
            return
        self._replay_df = pd.read_csv(HISTORICAL_PATH, parse_dates=["Timestamp"])
        self.is_running = True

        candle_count = 0
        while self.is_running:
            for row in self._replay_df.itertuples(index=False):
                if not self.is_running:
                    break
                try:
                    candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                                     low=row.Low, close=row.Close, volume=int(row.Volume))
                    self.data_manager.replay_candle(candle)
                    state = self.data_manager.get_state()
                    if state["nifty_price"] is None:
                        continue

                    candle_count += 1
                    self._check_exits_replay()

                    for signal in self.evaluate_strategies():
                        asyncio.create_task(self.execute_signal(signal))
                except Exception:
                    # The for-loop body is otherwise all synchronous — an uncaught exception here
                    # would otherwise silently kill this whole task (asyncio's default handler for
                    # an unretrieved task exception can go missing once uvicorn reconfigures the
                    # root logger), which is exactly what caused a real freeze bug: one trade,
                    # then dead silence forever, from a tz-naive/aware datetime subtraction in
                    # _check_exits_replay. Log with the full traceback and keep going instead of
                    # dying on whatever one candle triggers this.
                    self.logger.log_error(
                        f"Unhandled exception in replay loop at candle {candle_count}:\n{traceback.format_exc()}")

                await asyncio.sleep(REPLAY_SECONDS_PER_CANDLE)

    def _check_exits_replay(self) -> None:
        """Replay has no live option-chain LTP — mark to market with the same Black-Scholes
        estimate the backtester uses."""
        state = self.data_manager.get_state()
        days_to_expiry = next_weekly_expiry_days(state["timestamp"])
        current_prices = {}
        for order in self.paper_trader.get_positions():
            strike, option_type = parse_option_symbol(order.symbol)
            if strike is not None:
                current_prices[order.symbol] = black_scholes_price(
                    spot=state["nifty_price"], strike=strike,
                    days_to_expiry=days_to_expiry, option_type=option_type,
                )
        # Must pass the simulated candle timestamp — otherwise update_positions() defaults to
        # tz-naive datetime.now() (wall-clock), which raises `TypeError: Cannot subtract tz-naive
        # and tz-aware datetime-like objects` against order.entry_time (tz-aware, from the CSV)
        # the instant there's an open position to check its time-exit condition. This was THE
        # freeze: every candle from then on hit the same exception, forever, on a position that
        # could never close (see the try/except around the caller in _start_replay).
        closed = self.paper_trader.update_positions(
            current_prices, timestamp=state["timestamp"], time_exit_mins=self.time_exit_mins)
        for order in closed:
            asyncio.create_task(self._close_position_db(order))
        self._publish_state()
