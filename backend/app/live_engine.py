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
from datetime import datetime, timedelta
from datetime import time as dtime
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

import json

HISTORICAL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "historical" / "nifty_90days.csv"
SENSEX_HISTORICAL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "historical" / "sensex_1year.csv"
LAST_MARKET_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "last_market_state.json"
REPLAY_SECONDS_PER_CANDLE = 0.05


class WebLiveEngine(LiveTrader):
    def __init__(self, config, data_engine_enabled: bool):
        super().__init__(config)
        self.data_engine_enabled = data_engine_enabled
        self._replay_df: pd.DataFrame | None = None
        # Timestamp of the last 1-min candle already written to options_candle_history, per
        # index -- lets _maybe_persist_new_candles() persist only what's new each cycle instead
        # of re-scanning/re-inserting the whole in-memory window every time.
        self._last_persisted_candle_ts: dict[str, datetime] = {}
        self._cached_market_state: dict = {}
        if LAST_MARKET_STATE_PATH.exists():
            try:
                self._cached_market_state = json.loads(LAST_MARKET_STATE_PATH.read_text())
            except Exception:
                pass

    # ---- State publishing (feeds the Broadcaster) ----------------------------------

    def _publish_state(self) -> None:
        state = self.data_manager.get_state()
        current_prices = {}
        for data_manager in self.data_managers.values():
            current_prices.update({sym: q.ltp for sym, q in data_manager.get_option_chain().items()})
        pnl = self.paper_trader.get_pnl(current_prices)

        now = datetime.now(IST)
        today = now.date()
        nifty_price = state["nifty_price"]
        prev_close = self.data_manager.get_prev_close(today)
        change = (nifty_price - prev_close) if (nifty_price is not None and prev_close) else None
        change_pct = (change / prev_close * 100) if (change is not None and prev_close) else None

        sensex_state = self.data_managers["SENSEX"].get_state()
        sensex_price = sensex_state["nifty_price"]
        sensex_prev_close = self.data_managers["SENSEX"].get_prev_close(today)
        sensex_change = (
            (sensex_price - sensex_prev_close) if (sensex_price is not None and sensex_prev_close) else None)
        sensex_change_pct = (
            (sensex_change / sensex_prev_close * 100) if (sensex_change is not None and sensex_prev_close) else None)

        # Fallback to cached market state after hours or on weekends
        if nifty_price is not None:
            self._cached_market_state["nifty_price"] = nifty_price
            self._cached_market_state["nifty_prev_close"] = prev_close
            self._cached_market_state["nifty_change"] = round(change, 2) if change is not None else None
            self._cached_market_state["nifty_change_pct"] = round(change_pct, 2) if change_pct is not None else None
            self._cached_market_state["last_updated"] = now.isoformat()
            try:
                LAST_MARKET_STATE_PATH.write_text(json.dumps(self._cached_market_state, indent=2))
            except Exception:
                pass
        else:
            nifty_price = self._cached_market_state.get("nifty_price", 24252.00)
            prev_close = self._cached_market_state.get("nifty_prev_close", 24231.85)
            change = self._cached_market_state.get("nifty_change", 20.15)
            change_pct = self._cached_market_state.get("nifty_change_pct", 0.08)

        if sensex_price is not None:
            self._cached_market_state["sensex_price"] = sensex_price
            self._cached_market_state["sensex_prev_close"] = sensex_prev_close
            self._cached_market_state["sensex_change"] = round(sensex_change, 2) if sensex_change is not None else None
            self._cached_market_state["sensex_change_pct"] = round(sensex_change_pct, 2) if sensex_change_pct is not None else None
        else:
            sensex_price = self._cached_market_state.get("sensex_price", 77540.83)
            sensex_prev_close = self._cached_market_state.get("sensex_prev_close", 77537.72)
            sensex_change = self._cached_market_state.get("sensex_change", 3.11)
            sensex_change_pct = self._cached_market_state.get("sensex_change_pct", 0.00)

        nifty_candles_5m = self.data_manager.get_candles_5m_with_delta(today)
        sensex_candles_5m = self.data_managers["SENSEX"].get_candles_5m_with_delta(today)

        shared_state.update({
            "nifty_price": nifty_price,
            "nifty_prev_close": prev_close,
            "nifty_change": round(change, 2) if change is not None else None,
            "nifty_change_pct": round(change_pct, 2) if change_pct is not None else None,
            "nifty_sparkline": [c.close for c in self.data_manager.get_today_candles(today)],
            "nifty_candles_5m": nifty_candles_5m,
            "sensex_price": sensex_price,
            "sensex_prev_close": sensex_prev_close,
            "sensex_change": round(sensex_change, 2) if sensex_change is not None else None,
            "sensex_change_pct": round(sensex_change_pct, 2) if sensex_change_pct is not None else None,
            "sensex_candles_5m": sensex_candles_5m,
            "timestamp": state["timestamp"].isoformat() if state["timestamp"] else now.isoformat(),
            "market_open": self.is_running,
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
        flat) the strategy's most recent closed trade with the same shape, plus that strategy's
        own P&L for today (realized trades today + any open position's unrealized). last_closed
        is scoped to "most recent ever", not "today" — a strategy that last traded on Friday still
        has something to expand on Monday morning, not just on the day it happened, which is the
        only thing that keeps the expand affordance from disappearing entirely over a weekend or
        any other gap between trades. today_pnl is still computed from today's closes only."""
        today = datetime.now(IST).date()
        open_by_strategy: dict[str, list] = {}
        for order in self.paper_trader.get_positions():
            open_by_strategy.setdefault(order.strategy, []).append(order)

        closed_today_by_strategy: dict[str, list] = {}
        last_closed_by_strategy: dict[str, object] = {}
        for order in self.paper_trader.get_trade_history():
            if not order.exit_time:
                continue
            if order.exit_time.astimezone(IST).date() == today:
                closed_today_by_strategy.setdefault(order.strategy, []).append(order)
            current_latest = last_closed_by_strategy.get(order.strategy)
            if current_latest is None or order.exit_time > current_latest.exit_time:
                last_closed_by_strategy[order.strategy] = order

        rows = []
        all_strategies = [s for engine in self.strategy_engines.values() for s in engine.strategies]
        for strategy in all_strategies:
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
                    "order_id": latest.order_id,
                    "contract": format_display_symbol(latest.symbol, next_weekly_expiry_date(latest.entry_time)),
                    "qty": latest.qty,
                    "entry_price": latest.entry_price,
                    "entry_time": latest.entry_time.isoformat(),
                    "ltp": ltp,
                    "trade_pnl": trade_pnl,
                    "stop_loss": latest.stop_loss,
                    "take_profit": latest.take_profit,
                }
            else:
                last = last_closed_by_strategy.get(name)
                if last is not None:
                    last_closed = {
                        "contract": format_display_symbol(last.symbol, next_weekly_expiry_date(last.entry_time)),
                        "qty": last.qty,
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
                "last_closed": last_closed,
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

        # Separate try/except: a candle-history restore failure shouldn't be treated as if
        # wallets/positions also failed to restore (they're independent DB reads).
        try:
            await self._restore_candle_history(pool, today)
        except Exception as e:
            self.logger.log_error(f"Candle history restore failed, starting with an empty chart: {e}")

    async def _restore_candle_history(self, pool, today) -> None:
        """Restores today's already-persisted 1-min candles (OHLCV + tick-rule delta) per index,
        run BEFORE _seed_historical_candles() (called later, inside the main loop's first tick)
        -- DataManager.load_historical() preserves delta on any timestamp that already has a
        candle in memory, so seeding fresh REST OHLCV afterwards can't wipe out the real delta
        history restored here. Without this, the chart's cumulative-delta view resets to empty on
        every backend restart, even though the underlying data was never actually lost."""
        for index, data_manager in self.data_managers.items():
            rows = await asyncio.wait_for(
                pool.fetch(
                    """SELECT bucket_minute, open, high, low, close, volume, delta
                       FROM options_candle_history WHERE underlying=$1 AND bucket_date=$2
                       ORDER BY bucket_minute""",
                    index, today),
                timeout=self.DB_TIMEOUT_SECS)
            if not rows:
                continue
            midnight = datetime.combine(today, dtime(0, 0), tzinfo=IST)
            restored = [
                Candle(
                    timestamp=midnight + timedelta(minutes=row["bucket_minute"]),
                    open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                    close=float(row["close"]), volume=int(row["volume"] or 0), delta=float(row["delta"] or 0),
                )
                for row in rows
            ]
            data_manager.candles = restored
            self._last_persisted_candle_ts[index] = restored[-1].timestamp
        self.logger.log_websocket_event(
            "candle_history_restored", {index: len(dm.candles) for index, dm in self.data_managers.items()})

    def _maybe_persist_new_candles(self) -> None:
        """Detects and queues persistence of any 1-min candles that completed since the last
        check, for both indices -- lets today's chart/CVD history survive a restart instead of
        resetting to empty (only available from live ticks, never re-derivable from Fyers'
        historical REST data). Fire-and-forget, same pattern as _save_wallet_db elsewhere here;
        the sync/async split lets this run from evaluate_strategies() (not itself async) while
        still doing the actual DB write asynchronously."""
        for index, data_manager in self.data_managers.items():
            last_ts = self._last_persisted_candle_ts.get(index)
            new_candles = [c for c in data_manager.candles if last_ts is None or c.timestamp > last_ts]
            if not new_candles:
                continue
            self._last_persisted_candle_ts[index] = new_candles[-1].timestamp
            asyncio.create_task(self._persist_candles_db(index, new_candles))

    async def _persist_candles_db(self, index: str, candles: list) -> None:
        for candle in candles:
            midnight = candle.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            bucket_minute = int((candle.timestamp - midnight).total_seconds() // 60)
            await self._db_execute(
                """INSERT INTO options_candle_history
                   (underlying, bucket_date, bucket_minute, open, high, low, close, volume, delta)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                   ON CONFLICT (underlying, bucket_date, bucket_minute) DO NOTHING""",
                index, candle.timestamp.date(), bucket_minute,
                candle.open, candle.high, candle.low, candle.close, candle.volume, candle.delta,
            )

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
        self._maybe_persist_new_candles()
        return signals

    def _on_market_closed_tick(self) -> None:
        # Flushes the day's last still-forming candle once (idempotent -- a no-op on every
        # subsequent closed-tick, see DataManager.flush_current_candle) so it isn't lost/left
        # unpersisted, mirroring TradeDashBoard's end-of-day flush_all().
        for data_manager in self.data_managers.values():
            data_manager.flush_current_candle()
        self._maybe_persist_new_candles()
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
        #
        # Merging both indices' option chains is safe (no key collisions): NIFTY and SENSEX
        # symbols are already uniquely prefixed by select_strike().
        current_prices = {}
        for data_manager in self.data_managers.values():
            current_prices.update({sym: q.ltp for sym, q in data_manager.get_option_chain().items()})
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
        # Merges both indices' historical CSVs by timestamp so SENSEX strategies aren't blind
        # whenever replay mode triggers (local dev, or the corporate network blocking live
        # Fyers) -- without this they'd evaluate against permanently-empty state, and any signal
        # that DID fire on stale data would risk the same class of orphaned-position bug already
        # fixed once for NIFTY-only replay. Falls back to NIFTY-only if the SENSEX CSV is
        # missing, rather than failing replay mode entirely.
        frames = []
        if HISTORICAL_PATH.exists():
            nifty_df = pd.read_csv(HISTORICAL_PATH, parse_dates=["Timestamp"])
            nifty_df["underlying"] = "NIFTY"
            frames.append(nifty_df)
        else:
            self.logger.log_error(f"Replay mode: no historical data at {HISTORICAL_PATH}")
        if SENSEX_HISTORICAL_PATH.exists():
            sensex_df = pd.read_csv(SENSEX_HISTORICAL_PATH, parse_dates=["Timestamp"])
            sensex_df["underlying"] = "SENSEX"
            frames.append(sensex_df)
        else:
            self.logger.log_error(f"Replay mode: no SENSEX historical data at {SENSEX_HISTORICAL_PATH} "
                                   f"-- continuing NIFTY-only")
        if not frames:
            return
        self._replay_df = pd.concat(frames, ignore_index=True).sort_values("Timestamp")
        self.is_running = True

        candle_count = 0
        while self.is_running:
            for row in self._replay_df.itertuples(index=False):
                if not self.is_running:
                    break
                try:
                    candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                                     low=row.Low, close=row.Close, volume=int(row.Volume))
                    data_manager = self.data_managers[row.underlying]
                    data_manager.replay_candle(candle)
                    state = data_manager.get_state()
                    if state["nifty_price"] is None:
                        continue

                    candle_count += 1
                    self._check_exits_replay(now=state["timestamp"])

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

    def _check_exits_replay(self, now: datetime = None) -> None:
        """Replay has no live option-chain LTP — mark to market with the same Black-Scholes
        estimate the backtester uses. `now` is the just-replayed candle's own timestamp (the
        simulated "current time" driving this exit check); defaults to the NIFTY DataManager's
        latest state for back-compat with direct (NIFTY-only) callers/tests."""
        if now is None:
            now = self.data_manager.get_state()["timestamp"]
        current_prices = {}
        for order in self.paper_trader.get_positions():
            data_manager = self.data_managers.get(order.underlying, self.data_manager)
            spot = data_manager.get_state()["nifty_price"]
            if spot is None:
                continue
            days_to_expiry = next_weekly_expiry_days(now, index=order.underlying)
            strike, option_type = parse_option_symbol(order.symbol)
            if strike is not None:
                current_prices[order.symbol] = black_scholes_price(
                    spot=spot, strike=strike,
                    days_to_expiry=days_to_expiry, option_type=option_type,
                )
        # Must pass the simulated candle timestamp — otherwise update_positions() defaults to
        # tz-naive datetime.now() (wall-clock), which raises `TypeError: Cannot subtract tz-naive
        # and tz-aware datetime-like objects` against order.entry_time (tz-aware, from the CSV)
        # the instant there's an open position to check its time-exit condition. This was THE
        # freeze: every candle from then on hit the same exception, forever, on a position that
        # could never close (see the try/except around the caller in _start_replay).
        closed = self.paper_trader.update_positions(
            current_prices, timestamp=now, time_exit_mins=self.time_exit_mins)
        for order in closed:
            asyncio.create_task(self._close_position_db(order))
        self._publish_state()
