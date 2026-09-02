"""
Replays historical NIFTY candles through each strategy independently (its own DataManager
+ PaperTrader, unconstrained by the others) to produce a fair, per-strategy ranking.
The live engine (src/trader.py) is what applies shared risk limits across the deployed set.
"""
from datetime import time as dtime

import pandas as pd

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.base_strategy import BaseStrategy
from src.strategies.engine import StrategyEngine
from src.strategies.iron_fly_hedge import IronFlyHedge, IronFlyPosition
from src.backtester.report import BacktestReport, build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

IRON_FLY_NAME = "IRON_FLY_HEDGE"
LOT_SIZE_BY_INDEX = {"NIFTY": 65, "SENSEX": 20, "BANKNIFTY": 30}


def _parse_hhmm(value: str) -> dtime:
    hour, minute = value.split(":")
    return dtime(int(hour), int(minute))


class BacktestEngine:
    def __init__(self, risk_params: dict, initial_capital: float = 1_000_000, logger=None,
                 capital_by_strategy: dict = None, index: str = "NIFTY"):
        self.risk_params = risk_params
        self.initial_capital = initial_capital
        self.logger = logger
        self.index = index  # 'NIFTY' or 'SENSEX' -- selects the expiry-day rule for pricing
        self.trade_histories: dict[str, list] = {}
        # {strategy_name: allocated_capital} from a prior run's capital_requirements.json — powers
        # PaperTrader's drawdown-%-of-capital circuit breaker below. None/{} disables it (no
        # chicken-and-egg problem: the first run just has no breaker until one exists to feed back
        # in). See load_capital_by_strategy in src/backtester/report.py.
        self.capital_by_strategy = capital_by_strategy or {}

        sizing = risk_params.get("position_sizing", {})
        self.qty_per_signal = sizing.get("qty_per_signal", 1)
        self.lot_size = sizing.get("lot_size", 65)
        self.max_concurrent_positions = sizing.get("max_concurrent_positions", 5)
        self.max_daily_loss = sizing.get("max_daily_loss", 5000)
        self.max_trades_per_day_per_strategy = sizing.get("max_trades_per_day_per_strategy", 2)

        exits = risk_params.get("exit_rules", {})
        self.stop_loss_pct = exits.get("stop_loss_pct", 20)
        self.take_profit_pct = exits.get("take_profit_pct", 40)
        self.time_exit_mins = exits.get("time_exit_mins", 120)
        self.trailing_stop_enabled = exits.get("trailing_stop_enabled", False)
        self.trailing_activation_pct = exits.get("trailing_activation_pct", 10.0)
        self.trailing_stop_pct = exits.get("trailing_stop_pct", 15.0)
        self.trailing_tiers_pct = exits.get("trailing_tiers_pct")

        iron_fly = risk_params.get("iron_fly", {})
        self.iron_fly_enabled = iron_fly.get("enabled", True)
        self.iron_fly_params = dict(
            wing_width_pts=iron_fly.get("wing_width_pts", 200),
            strike_step=iron_fly.get("strike_step", 100),
            entry_time=_parse_hhmm(iron_fly.get("entry_time", "09:45")),
            force_exit_time=_parse_hhmm(iron_fly.get("force_exit_time", "15:15")),
            profit_target_pct_of_credit=iron_fly.get("profit_target_pct_of_credit", 50.0),
            stop_loss_pct_of_max_loss=iron_fly.get("stop_loss_pct_of_max_loss", 50.0),
            max_vol_regime_ratio_to_enter=iron_fly.get("max_vol_regime_ratio_to_enter"),
            lot_size=self.lot_size,
            qty=self.qty_per_signal,
        )

        breaker = risk_params.get("circuit_breaker", {})
        self.consecutive_loss_limit = breaker.get("consecutive_loss_limit")
        self.consecutive_loss_cooldown_days = breaker.get("consecutive_loss_cooldown_days", 1)
        self.max_drawdown_pct_of_capital = breaker.get("max_drawdown_pct_of_capital")
        self.drawdown_cooldown_days = breaker.get("drawdown_cooldown_days", 3)
        self.drawdown_breaker_grace_trades = breaker.get("drawdown_breaker_grace_trades", 3)

    def run(self, historical_data: pd.DataFrame | dict[str, pd.DataFrame]) -> dict[str, BacktestReport]:
        """`historical_data`: either a single DataFrame (back-compat — every strategy replays the
        SAME series regardless of which index it actually trades; only ever correct if every
        strategy passed to this run happens to share one underlying) or, correctly, a
        {"NIFTY": df, "SENSEX": df, "BANKNIFTY": df} dict so each of the 44 strategies replays its
        OWN index's price history. create_all_strategies() returns strategies for all three
        indices, so a single shared df silently fed SENSEX/BANKNIFTY strategies NIFTY's price
        series with SENSEX/BANKNIFTY strike-step rounding applied to NIFTY numbers — see
        docs/ARCHITECTURE.md."""
        from src.strategies.engine import create_all_strategies

        if isinstance(historical_data, pd.DataFrame):
            historical_data = {"NIFTY": historical_data, "SENSEX": historical_data, "BANKNIFTY": historical_data}

        reports = {}
        self.trade_histories = {}  # strategy name -> closed Order list, for day-by-day reporting
        for strategy in create_all_strategies():
            df = historical_data.get(strategy.underlying)
            if df is None:
                if self.logger:
                    self.logger.log_error(f"No historical data for {strategy.underlying}, skipping {strategy.name}")
                continue
            trader = self._backtest_single(strategy, df)
            history = trader.get_trade_history()
            self.trade_histories[strategy.name] = history
            reports[strategy.name] = build_report(
                strategy.name, strategy.direction, history, self.initial_capital
            )

        if self.iron_fly_enabled:
            iron_fly_trades = self._backtest_iron_fly(historical_data.get("NIFTY"))
            self.trade_histories[IRON_FLY_NAME] = iron_fly_trades
            reports[IRON_FLY_NAME] = build_report(IRON_FLY_NAME, "HEDGE", iron_fly_trades, self.initial_capital)

        return reports

    def _backtest_single(self, strategy: BaseStrategy, df: pd.DataFrame) -> PaperTrader:
        index = strategy.underlying
        lot_size = LOT_SIZE_BY_INDEX.get(index, self.lot_size)
        data_manager = DataManager(window_size=3000, underlying=index)
        trader = PaperTrader(
            initial_capital=self.initial_capital,
            lot_size=lot_size,
            max_concurrent_positions=self.max_concurrent_positions,
            max_daily_loss=self.max_daily_loss,
            max_trades_per_day_per_strategy=self.max_trades_per_day_per_strategy,
            trailing_stop_enabled=self.trailing_stop_enabled,
            trailing_activation_pct=self.trailing_activation_pct,
            trailing_stop_pct=self.trailing_stop_pct,
            trailing_tiers_pct=self.trailing_tiers_pct,
            consecutive_loss_limit=self.consecutive_loss_limit,
            consecutive_loss_cooldown_days=self.consecutive_loss_cooldown_days,
            max_drawdown_pct_of_capital=self.max_drawdown_pct_of_capital,
            drawdown_cooldown_days=self.drawdown_cooldown_days,
            drawdown_breaker_grace_trades=self.drawdown_breaker_grace_trades,
            capital_by_strategy=self.capital_by_strategy,
            logger=self.logger,
        )
        engine = StrategyEngine(strategies=[strategy], logger=self.logger)

        for row in df.itertuples(index=False):
            candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                             low=row.Low, close=row.Close, volume=int(row.Volume))
            data_manager.replay_candle(candle)
            state = data_manager.get_state()
            if state["nifty_price"] is None:
                continue

            current_prices = self._mark_to_market(trader, state, index)
            trader.update_positions(current_prices, timestamp=state["timestamp"],
                                     time_exit_mins=self.time_exit_mins)

            for signal in engine.evaluate_all(state):
                stop_loss = max(signal.entry_price * (1 - self.stop_loss_pct / 100), 0.05)
                # Percentage of entry premium — see src/trader.py's matching comment.
                take_profit = signal.entry_price * (1 + self.take_profit_pct / 100)
                try:
                    trader.place_order(
                        symbol=signal.strike, side="BUY", qty=self.qty_per_signal,
                        price=signal.entry_price, stop_loss=stop_loss, take_profit=take_profit,
                        strategy=signal.strategy, timestamp=signal.timestamp, lot_size=lot_size,
                    )
                except RiskLimitExceeded:
                    continue

        return trader

    def _backtest_iron_fly(self, df: pd.DataFrame) -> list[IronFlyPosition]:
        if df is None:
            return []
        data_manager = DataManager(window_size=3000)
        iron_fly = IronFlyHedge(**self.iron_fly_params)
        closed: list[IronFlyPosition] = []

        for row in df.itertuples(index=False):
            candle = Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                             low=row.Low, close=row.Close, volume=int(row.Volume))
            data_manager.replay_candle(candle)
            state = data_manager.get_state()
            if state["nifty_price"] is None:
                continue

            if iron_fly.position is None:
                iron_fly.maybe_enter(state)
            else:
                position = iron_fly.check_exit(state)
                if position is not None:
                    closed.append(position)

        return closed

    def _mark_to_market(self, trader: PaperTrader, state: dict, index: str) -> dict:
        """`index` selects the expiry-day rule for THIS strategy's own underlying (NIFTY/SENSEX/
        BANKNIFTY each have different weekly expiry weekdays — see options_pricing.py) rather than
        the engine-wide `self.index` default, which was always "NIFTY" regardless of which index
        was actually being backtested."""
        prices = {}
        spot_price = state["nifty_price"]  # DataManager.get_state() always uses this generic key
        timestamp = state["timestamp"]
        days_to_expiry = next_weekly_expiry_days(timestamp, index=index)
        for order in trader.get_positions():
            strike, option_type = parse_option_symbol(order.symbol)
            if strike is None:
                continue
            prices[order.symbol] = black_scholes_price(
                spot=spot_price, strike=strike, days_to_expiry=days_to_expiry, option_type=option_type
            )
        return prices


if __name__ == "__main__":
    from pathlib import Path
    from src.config import Config
    from src.backtester.report import print_backtest_report, save_report

    config = Config.load()
    data_path = Path(__file__).resolve().parent.parent.parent / "data" / "historical" / "nifty_90days.csv"
    if not data_path.exists():
        raise SystemExit(f"Historical data not found at {data_path}. See HOW_TO_GET_90DAY_NIFTY_DATA.md")

    df = pd.read_csv(data_path, parse_dates=["Timestamp"])
    engine = BacktestEngine(risk_params=config.risk_params)
    reports = engine.run(df)

    print_backtest_report(reports)
    save_report(reports, Path(__file__).resolve().parent.parent.parent / "data" / "backtest_results" / "report.json")
