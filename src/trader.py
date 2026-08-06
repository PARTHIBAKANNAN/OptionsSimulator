"""
Live paper-trading loop: WebSocket ticks feed the DataManager continuously, option chain
is polled every 10s, strategies are evaluated on every tick. By default every signal is
auto-approved into a (simulated) order — see WebLiveEngine.execute_signal and
config/risk_params.json's live_mode.auto_approve; a manual Telegram/web approval tap is
still available by turning that off, but isn't required for paper trading (no real order
ever reaches a broker either way — see docs/planning-archive/FYERS_FEASIBILITY_REPORT.md).

Every "now" used for market-hours/login-time decisions MUST be IST wall-clock time, built via
datetime.now(IST) — never bare datetime.now(). The deploy VM's system clock runs UTC (confirmed
via `timedatectl`), so a naive datetime.now() is off from real IST time by 5.5 hours; comparing
that against "09:15"-"15:30" market hours would have silently never detected market-open at all.
"""
import asyncio
import traceback
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.backtester.report import load_capital_by_strategy
from src.config import Config
from src.data_manager import DataManager
from src.fyers.api_client import FyersAPIClient
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.engine import StrategyEngine
from src.alerts.telegram_alerts import TelegramAlertsManager
from src.persistence.state_manager import StateManager
from src.utils.logger import get_logger

NIFTY_SYMBOL = "NSE:NIFTY50-INDEX"
IST = ZoneInfo("Asia/Kolkata")
# Fyers tokens are valid for the calendar day only. TradeDashBoard's own proven scheduler
# refreshes at 08:45 IST before market open; ours does the same at 08:50 IST — see
# LiveTrader.start(). This entire mechanism lives inside OUR process/event loop only (no shared
# scheduler, no shared Fyers app/credentials with TradeDashBoard — see docs/ARCHITECTURE.md).
DAILY_LOGIN_TIME = dtime(8, 50)
CAPITAL_REQUIREMENTS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "backtest_results" / "capital_requirements.json"
)


def is_market_open(now: datetime, risk_params: dict) -> bool:
    """`now` must already be IST wall-clock time — build it with datetime.now(IST), not bare
    datetime.now() (see module docstring)."""
    hours = risk_params.get("market_hours", {})
    start = dtime.fromisoformat(hours.get("start", "09:15"))
    end = dtime.fromisoformat(hours.get("end", "15:30"))
    return start <= now.time() <= end and now.weekday() < 5


class LiveTrader:
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger()

        self.data_manager = DataManager()
        self.strategy_engine = StrategyEngine(logger=self.logger)
        sizing = config.risk_params.get("position_sizing", {})
        exits = config.risk_params.get("exit_rules", {})
        # Same circuit breakers validated in backtesting (see BacktestEngine) — capital_by_strategy
        # comes from the latest data/backtest_results/capital_requirements.json (written by
        # `python main.py`); missing/empty file just disables the drawdown breaker until one exists.
        breaker = config.risk_params.get("circuit_breaker", {})
        capital_by_strategy = load_capital_by_strategy(CAPITAL_REQUIREMENTS_PATH)
        self.paper_trader = PaperTrader(
            lot_size=sizing.get("lot_size", 65),
            max_concurrent_positions=sizing.get("max_concurrent_positions", 5),
            max_daily_loss=sizing.get("max_daily_loss", 5000),
            max_trades_per_day_per_strategy=sizing.get("max_trades_per_day_per_strategy", 2),
            trailing_stop_enabled=exits.get("trailing_stop_enabled", False),
            trailing_activation_pct=exits.get("trailing_activation_pct", 10.0),
            trailing_stop_pct=exits.get("trailing_stop_pct", 15.0),
            consecutive_loss_limit=breaker.get("consecutive_loss_limit"),
            consecutive_loss_cooldown_days=breaker.get("consecutive_loss_cooldown_days", 1),
            max_drawdown_pct_of_capital=breaker.get("max_drawdown_pct_of_capital"),
            drawdown_cooldown_days=breaker.get("drawdown_cooldown_days", 3),
            drawdown_breaker_grace_trades=breaker.get("drawdown_breaker_grace_trades", 3),
            capital_by_strategy=capital_by_strategy,
            charges_rates=config.risk_params.get("charges"),
            enable_wallets=True,
            logger=self.logger,
        )
        self.qty_per_signal = sizing.get("qty_per_signal", 1)
        self.stop_loss_pct = exits.get("stop_loss_pct", 20)
        self.take_profit_pts = exits.get("take_profit_pts", 150)
        self.time_exit_mins = exits.get("time_exit_mins", 120)
        self.poll_interval = config.risk_params.get("polling", {}).get("option_chain_interval_secs", 10)
        self.auto_mode = config.risk_params.get("live_mode", {}).get("auto_approve", True)

        self.fyers = FyersAPIClient(
            client_id=config.fyers_client_id, secret_key=config.fyers_secret_key,
            fy_id=config.fyers_fy_id, user_pin=config.fyers_user_pin,
            totp_secret=config.fyers_totp_secret, redirect_uri=config.fyers_redirect_uri,
            logger=self.logger,
        )
        self.telegram = None
        if config.telegram_bot_token and config.telegram_chat_id:
            self.telegram = TelegramAlertsManager(config.telegram_bot_token, config.telegram_chat_id, self.logger)

        self.state_manager = StateManager()
        self.is_running = False
        self._monitored_symbols: set[str] = set()
        self.recent_signals: list = []
        self._connected = False
        self._last_login_date = None
        self._historical_seeded_date = None

    # ---- Tick handlers (called synchronously from the WebSocket thread) --------

    def on_tick(self, message: dict) -> None:
        symbol = message.get("symbol")
        if symbol is None:
            return
        tick = {"ltp": message.get("ltp"), "volume": message.get("vol_traded_today", 0),
                "timestamp": datetime.now(IST)}
        if symbol == NIFTY_SYMBOL:
            self.data_manager.on_nifty_tick(tick)
        else:
            tick.update({"bid": message.get("bid_price1", 0), "ask": message.get("ask_price1", 0),
                         "oi": message.get("oi", 0)})
            self.data_manager.on_option_tick(symbol, tick)

    def _seed_historical_candles(self) -> None:
        """Warms up the 1H/15m/5m indicators before market open so day-1 strategies aren't blind."""
        try:
            history = self.fyers.get_historical_data(NIFTY_SYMBOL, resolution="1", days=10)
            self.data_manager.load_historical(history)
            self.logger.log_websocket_event("historical_seed_loaded", {"candles": len(history)})
        except Exception as e:
            self.logger.log_error(f"Historical seeding failed, starting cold: {e}")

    # ---- Daily login / connect / disconnect state machine ------------------------

    def ensure_connection_state(self, now: datetime) -> bool:
        """Given the current IST wall-clock time: performs the daily Fyers login if due, and
        connects/disconnects the websocket to match market-open state. Returns whether the
        market is open right now (so the caller knows whether to run strategy evaluation this
        tick). Pure decision logic, deliberately factored out of the polling loop below so it's
        directly unit-testable without mocking asyncio.sleep."""
        market_open = self.config.force_market_open or is_market_open(now, self.config.risk_params)
        # force_market_open also bypasses the wall-clock login gate, so testing outside
        # 08:50-market-hours (or on a weekend) still authenticates immediately.
        past_login_time = self.config.force_market_open or (now.weekday() < 5 and now.time() >= DAILY_LOGIN_TIME)

        # Daily fresh token, once per calendar day — previously authenticate_with_totp() only ran
        # once at process start, ever, with no re-login mechanism at all. A token is only valid
        # for its calendar day, so a process left running past midnight would silently go dark
        # with no valid token until someone manually restarted it. See docs/ARCHITECTURE.md.
        if past_login_time and self._last_login_date != now.date():
            if self.fyers.refresh_access_token():
                self._last_login_date = now.date()
                self._connected = False  # reconnect below with the fresh token
            else:
                self.logger.log_error("Daily Fyers token refresh failed; will retry next tick.")

        # Seed recent historical candles (including the last close) as soon as there's a valid
        # token, even before market opens — otherwise the dashboard has nothing at all to show
        # (no NIFTY price, every strategy indistinguishable from "never started") until the first
        # live tick arrives, hours later. Once per calendar day, independent of market_open.
        if self.fyers.access_token and self._historical_seeded_date != now.date():
            self._seed_historical_candles()
            self._historical_seeded_date = now.date()

        if market_open and not self._connected and self.fyers.access_token:
            self.fyers.start_websocket(self.on_tick)
            self.fyers.subscribe_symbols([NIFTY_SYMBOL])
            self._connected = True
        elif not market_open and self._connected:
            self.fyers.stop_websocket()
            self._connected = False
            self._monitored_symbols = set()

        return market_open

    # ---- Main loop ---------------------------------------------------------------

    async def start(self) -> None:
        if self.telegram:
            await self.telegram.start_listening()

        self.is_running = True
        last_poll = 0.0
        loop = asyncio.get_event_loop()

        try:
            while self.is_running:
                try:
                    now = datetime.now(IST)
                    market_open = self.ensure_connection_state(now)

                    if not market_open:
                        self._on_market_closed_tick()
                        await asyncio.sleep(5)
                        continue

                    if loop.time() - last_poll >= self.poll_interval:
                        await self.poll_option_chain()
                        last_poll = loop.time()

                    signals = self.evaluate_strategies()
                    for signal in signals:
                        asyncio.create_task(self.execute_signal(signal))

                    self.check_exits()
                except Exception:
                    # An uncaught exception here would otherwise silently kill the whole engine
                    # task with no visible trace (asyncio's default handler for an unretrieved
                    # task exception can go missing once uvicorn reconfigures the root logger) —
                    # exactly what caused the original freeze bug (see _start_replay). Log with
                    # the full traceback and keep looping instead of dying on whatever tick
                    # triggers this.
                    self.logger.log_error(f"Unhandled exception in live loop:\n{traceback.format_exc()}")

                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def poll_option_chain(self) -> None:
        try:
            chain = self.fyers.get_option_chain(NIFTY_SYMBOL)
            self.data_manager.update_option_chain(chain)
            # update_option_chain() now stores each quote under BOTH the raw Fyers symbol (e.g.
            # "NSE:NIFTY2681124600CE") and a simplified "NIFTY24600CE" key strategies actually use
            # (see its docstring) -- only the former is ever valid to hand to Fyers' own
            # subscribe_symbols(); the simplified key isn't a real tradable symbol at all.
            all_symbols = {s for s in self.data_manager.get_option_chain().keys() if s.startswith("NSE:")}
            new_symbols = all_symbols - self._monitored_symbols
            if new_symbols:
                self.fyers.subscribe_symbols(list(new_symbols))
                self._monitored_symbols |= new_symbols
        except Exception as e:
            self.logger.log_error(f"poll_option_chain failed: {e}")

    def evaluate_strategies(self):
        state = self.data_manager.get_state()
        if state["nifty_price"] is None:
            return []
        signals = self.strategy_engine.evaluate_all(state)
        for signal in signals:
            self.recent_signals.append(signal)
        self.recent_signals = self.recent_signals[-10:]
        return signals

    async def execute_signal(self, signal) -> None:
        if self.telegram and not self.auto_mode:
            signal_id = await self.telegram.send_signal_alert(signal)
            decision = await self.telegram.await_decision(signal_id, timeout_secs=300)
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

        self.state_manager.save_positions(self.paper_trader.get_positions())
        if self.telegram:
            await self.telegram.send_trade_execution(order)

    def check_exits(self) -> None:
        # Must pass an explicit IST-aware timestamp — otherwise update_positions() defaults to
        # tz-naive datetime.now(), which raises `TypeError: Cannot subtract tz-naive and
        # tz-aware datetime-like objects` against order.entry_time (tz-aware, from on_tick's
        # datetime.now(IST)) the instant a position survives to its time-exit check. See
        # WebLiveEngine._check_exits_replay's identical fix for the original freeze bug.
        current_prices = {sym: q.ltp for sym, q in self.data_manager.get_option_chain().items()}
        closed = self.paper_trader.update_positions(
            current_prices, timestamp=datetime.now(IST), time_exit_mins=self.time_exit_mins)
        for order in closed:
            self.state_manager.append_trade(order)
        if closed:
            self.state_manager.save_positions(self.paper_trader.get_positions())

    def _on_market_closed_tick(self) -> None:
        """Called every ~5s while the market is shut, instead of evaluate_strategies()/
        check_exits() (which the main loop skips entirely in that branch). No-op here — the CLI
        trader has no shared state to keep fresh — but WebLiveEngine overrides this to keep
        publishing state (last NIFTY price, every strategy as WAITING) so the web dashboard shows
        a proper "market closed" picture instead of going stale or blank. See docs/ARCHITECTURE.md."""

    async def stop(self) -> None:
        self.is_running = False
        self.fyers.stop_websocket()
        if self.telegram:
            await self.telegram.stop_listening()
