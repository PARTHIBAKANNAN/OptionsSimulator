"""
Replays historical NIFTY candles through each strategy independently (its own DataManager
+ PaperTrader, unconstrained by the others) to produce a fair, per-strategy ranking.
The live engine (src/trader.py) is what applies shared risk limits across the deployed set.
"""
import pandas as pd

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.base_strategy import BaseStrategy
from src.strategies.engine import StrategyEngine
from src.backtester.report import BacktestReport, build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol


class BacktestEngine:
    def __init__(self, risk_params: dict, initial_capital: float = 1_000_000, logger=None):
        self.risk_params = risk_params
        self.initial_capital = initial_capital
        self.logger = logger

        sizing = risk_params.get("position_sizing", {})
        self.qty_per_signal = sizing.get("qty_per_signal", 1)
        self.lot_size = sizing.get("lot_size", 75)
        self.max_concurrent_positions = sizing.get("max_concurrent_positions", 5)
        self.max_daily_loss = sizing.get("max_daily_loss", 5000)

        exits = risk_params.get("exit_rules", {})
        self.stop_loss_pts = exits.get("stop_loss_pts", 50)
        self.take_profit_pts = exits.get("take_profit_pts", 150)
        self.time_exit_mins = exits.get("time_exit_mins", 120)

    def run(self, historical_data: pd.DataFrame) -> dict[str, BacktestReport]:
        from src.strategies.engine import create_all_strategies

        reports = {}
        for strategy in create_all_strategies():
            trader = self._backtest_single(strategy, historical_data)
            reports[strategy.name] = build_report(
                strategy.name, strategy.direction, trader.get_trade_history(), self.initial_capital
            )
        return reports

    def _backtest_single(self, strategy: BaseStrategy, df: pd.DataFrame) -> PaperTrader:
        data_manager = DataManager(window_size=3000)
        trader = PaperTrader(
            initial_capital=self.initial_capital,
            lot_size=self.lot_size,
            max_concurrent_positions=self.max_concurrent_positions,
            max_daily_loss=self.max_daily_loss,
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

            current_prices = self._mark_to_market(trader, state)
            trader.update_positions(current_prices, timestamp=state["timestamp"],
                                     time_exit_mins=self.time_exit_mins)

            for signal in engine.evaluate_all(state):
                stop_loss = max(signal.entry_price - self.stop_loss_pts, 0.05)
                take_profit = signal.entry_price + self.take_profit_pts
                try:
                    trader.place_order(
                        symbol=signal.strike, side="BUY", qty=self.qty_per_signal,
                        price=signal.entry_price, stop_loss=stop_loss, take_profit=take_profit,
                        strategy=signal.strategy, timestamp=signal.timestamp,
                    )
                except RiskLimitExceeded:
                    continue

        return trader

    @staticmethod
    def _mark_to_market(trader: PaperTrader, state: dict) -> dict:
        prices = {}
        nifty_price = state["nifty_price"]
        timestamp = state["timestamp"]
        days_to_expiry = next_weekly_expiry_days(timestamp)
        for order in trader.get_positions():
            strike, option_type = parse_option_symbol(order.symbol)
            if strike is None:
                continue
            prices[order.symbol] = black_scholes_price(
                spot=nifty_price, strike=strike, days_to_expiry=days_to_expiry, option_type=option_type
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
