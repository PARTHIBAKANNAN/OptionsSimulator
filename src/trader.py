"""
Live paper-trading loop: WebSocket ticks feed the DataManager continuously, option chain
is polled every 10s, strategies are evaluated on every tick, and every signal requires an
explicit Telegram approval tap before the PaperTrader fires a (simulated) order.
"""
import asyncio
from datetime import datetime, time as dtime

from src.config import Config
from src.data_manager import DataManager
from src.fyers.api_client import FyersAPIClient
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.engine import StrategyEngine
from src.alerts.telegram_alerts import TelegramAlertsManager
from src.persistence.state_manager import StateManager
from src.utils.logger import get_logger

NIFTY_SYMBOL = "NSE:NIFTY50-INDEX"


def is_market_open(now: datetime, risk_params: dict) -> bool:
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
        self.paper_trader = PaperTrader(
            lot_size=sizing.get("lot_size", 75),
            max_concurrent_positions=sizing.get("max_concurrent_positions", 5),
            max_daily_loss=sizing.get("max_daily_loss", 5000),
            logger=self.logger,
        )
        self.qty_per_signal = sizing.get("qty_per_signal", 1)
        self.stop_loss_pts = exits.get("stop_loss_pts", 50)
        self.take_profit_pts = exits.get("take_profit_pts", 150)
        self.time_exit_mins = exits.get("time_exit_mins", 120)
        self.poll_interval = config.risk_params.get("polling", {}).get("option_chain_interval_secs", 10)

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

    # ---- Tick handlers (called synchronously from the WebSocket thread) --------

    def on_tick(self, message: dict) -> None:
        symbol = message.get("symbol")
        if symbol is None:
            return
        tick = {"ltp": message.get("ltp"), "volume": message.get("vol_traded_today", 0),
                "timestamp": datetime.now()}
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

    # ---- Main loop ---------------------------------------------------------------

    async def start(self) -> None:
        self.fyers.authenticate_with_totp()
        self._seed_historical_candles()
        self.fyers.start_websocket(self.on_tick)
        self.fyers.subscribe_symbols([NIFTY_SYMBOL])

        if self.telegram:
            await self.telegram.start_listening()

        self.is_running = True
        last_poll = 0.0
        loop = asyncio.get_event_loop()

        try:
            while self.is_running:
                now = datetime.now()
                if not self.config.force_market_open and not is_market_open(now, self.config.risk_params):
                    await asyncio.sleep(5)
                    continue

                if loop.time() - last_poll >= self.poll_interval:
                    await self.poll_option_chain()
                    last_poll = loop.time()

                signals = self.evaluate_strategies()
                for signal in signals:
                    asyncio.create_task(self.execute_signal(signal))

                self.check_exits()
                await asyncio.sleep(1)
        finally:
            await self.stop()

    async def poll_option_chain(self) -> None:
        try:
            chain = self.fyers.get_option_chain(NIFTY_SYMBOL)
            self.data_manager.update_option_chain(chain)
            new_symbols = set(self.data_manager.get_option_chain().keys()) - self._monitored_symbols
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
        if self.telegram:
            signal_id = await self.telegram.send_signal_alert(signal)
            decision = await self.telegram.await_decision(signal_id, timeout_secs=300)
            if decision != "approve":
                return

        stop_loss = max(signal.entry_price - self.stop_loss_pts, 0.05)
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
        current_prices = {sym: q.ltp for sym, q in self.data_manager.get_option_chain().items()}
        closed = self.paper_trader.update_positions(current_prices, time_exit_mins=self.time_exit_mins)
        for order in closed:
            self.state_manager.append_trade(order)
        if closed:
            self.state_manager.save_positions(self.paper_trader.get_positions())

    async def stop(self) -> None:
        self.is_running = False
        self.fyers.stop_websocket()
        if self.telegram:
            await self.telegram.stop_listening()
