"""
Backtest Comparison: ATM vs ITM Strike Selection
================================================
Reruns all 9 deployed live strategies (4 NIFTY + 5 SENSEX) across 1 year of historical data:
  1. ATM Mode: standard ATM strike selection
  2. ITM Mode: ITM strike selection targeting ~Rs.200 premium for NIFTY, ~Rs.600 for SENSEX

Outputs full comparison metrics: Win Rate, Profit Factor, Total P&L, Max Drawdown %, and Exit Reasons.
"""
import json
import sys
import time
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.engine import create_all_strategies
from src.strategies.sensex_strategies import create_live_sensex_strategies
from src.backtester.report import build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

NIFTY_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_90days.csv"
SENSEX_CSV = PROJECT_ROOT / "data" / "historical" / "sensex_1year.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "backtest_results" / "itm_vs_atm_report.json"


def select_itm_strike(spot: float, option_type: str, dte: float, underlying: str = "NIFTY",
                      target_premium: float = None) -> tuple[str, float]:
    """Selects an ITM strike targeting ~Rs.200 for NIFTY, ~Rs.600 for SENSEX."""
    strike_step = 50 if underlying == "NIFTY" else 100
    if target_premium is None:
        target_premium = 200.0 if underlying == "NIFTY" else 600.0

    atm_strike = round(spot / strike_step) * strike_step
    best_strike = atm_strike
    best_price = black_scholes_price(spot, atm_strike, dte, option_type)
    best_diff = abs(best_price - target_premium)

    for k in range(1, 15):
        if option_type == "CE":
            strike = atm_strike - k * strike_step
        else:
            strike = atm_strike + k * strike_step

        price = black_scholes_price(spot, strike, dte, option_type)
        diff = abs(price - target_premium)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_price = price
        elif price > target_premium + 100:
            break

    symbol = f"{underlying}{int(best_strike)}{option_type}"
    return symbol, float(best_strike)


def mark_to_market(trader: PaperTrader, state: dict, index: str) -> dict:
    prices = {}
    spot = state["nifty_price"]
    timestamp = state["timestamp"]
    dte = next_weekly_expiry_days(timestamp, index=index)
    for order in trader.get_positions():
        strike, option_type = parse_option_symbol(order.symbol)
        if strike is None:
            continue
        prices[order.symbol] = black_scholes_price(
            spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type
        )
    return prices


def run_strategy_backtest(strategy: BaseStrategy, df: pd.DataFrame, risk_params: dict,
                          mode: str = "ATM") -> tuple[object, list]:
    """
    mode: 'ATM' or 'ITM'
    """
    sizing = risk_params.get("position_sizing", {})
    exits = risk_params.get("exit_rules", {})
    breaker = risk_params.get("circuit_breaker", {})
    underlying = getattr(strategy, "underlying", "NIFTY")
    lot_size = 65 if underlying == "NIFTY" else 20
    target_prem = 200.0 if underlying == "NIFTY" else 600.0

    data_manager = DataManager(window_size=3000, underlying=underlying)
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=lot_size,
        max_concurrent_positions=sizing.get("max_concurrent_positions", 5),
        max_daily_loss=sizing.get("max_daily_loss", 5000),
        max_trades_per_day_per_strategy=sizing.get("max_trades_per_day_per_strategy", 2),
        trailing_stop_enabled=exits.get("trailing_stop_enabled", True),
        trailing_activation_pct=exits.get("trailing_activation_pct", 10.0),
        trailing_stop_pct=exits.get("trailing_stop_pct", 15.0),
        consecutive_loss_limit=breaker.get("consecutive_loss_limit"),
        consecutive_loss_cooldown_days=breaker.get("consecutive_loss_cooldown_days", 1),
        max_drawdown_pct_of_capital=breaker.get("max_drawdown_pct_of_capital"),
        drawdown_cooldown_days=breaker.get("drawdown_cooldown_days", 3),
        drawdown_breaker_grace_trades=breaker.get("drawdown_breaker_grace_trades", 3),
    )

    stop_loss_pct = exits.get("stop_loss_pct", 20)
    take_profit_pts = exits.get("take_profit_pts", 150)
    time_exit_mins = exits.get("time_exit_mins", 120)

    for row in df.itertuples(index=False):
        candle = Candle(
            timestamp=row.Timestamp, open=row.Open, high=row.High,
            low=row.Low, close=row.Close, volume=int(row.Volume)
        )
        data_manager.replay_candle(candle)
        state = data_manager.get_state()
        if state["nifty_price"] is None:
            continue

        current_prices = mark_to_market(trader, state, underlying)
        trader.update_positions(current_prices, timestamp=state["timestamp"],
                                time_exit_mins=time_exit_mins)

        # Evaluate strategy
        try:
            signal = strategy.evaluate(state)
        except Exception:
            continue

        if signal is None:
            continue

        # Override strike and entry price if in ITM mode
        spot = state["nifty_price"]
        ts = state["timestamp"]
        dte = next_weekly_expiry_days(ts, index=underlying)

        if mode == "ITM":
            symbol, strike = select_itm_strike(spot, signal.direction, dte, underlying, target_prem)
            entry_price = black_scholes_price(spot, strike, dte, signal.direction)
        else:
            symbol = signal.strike
            strike, _ = parse_option_symbol(symbol)
            entry_price = signal.entry_price

        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + take_profit_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1,
                price=entry_price, stop_loss=stop_loss, take_profit=take_profit,
                strategy=strategy.name, timestamp=ts, lot_size=lot_size
            )
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(strategy.name, strategy.direction, history, 1_000_000)
    return report, history


def main():
    t0 = time.time()
    config = Config.load()
    risk_params = config.risk_params

    print("\n" + "=" * 80)
    print("  OPTIONS SIMULATOR: 9 STRATEGIES BACKTEST (ATM vs ITM)")
    print("  NIFTY Target ITM Premium: ~Rs.200 | SENSEX Target ITM Premium: ~Rs.600")
    print("=" * 80 + "\n")

    # Load data
    print("Loading NIFTY dataset...")
    df_nifty = pd.read_csv(NIFTY_CSV, parse_dates=["Timestamp"])
    # If 1-min data is too heavy, sample to 5-min or 15-min
    if len(df_nifty) > 10000:
        print(f"  Resampling NIFTY {len(df_nifty):,} bars down to 15-min bars for clean, high-speed execution...")
        df_nifty["Timestamp"] = pd.to_datetime(df_nifty["Timestamp"])
        df_nifty = df_nifty.set_index("Timestamp").resample("15min").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna().reset_index()

    print(f"  NIFTY candles: {len(df_nifty):,} bars")

    print("\nLoading SENSEX dataset...")
    df_sensex = pd.read_csv(SENSEX_CSV, parse_dates=["Timestamp"])
    print(f"  SENSEX candles: {len(df_sensex):,} bars")

    nifty_strategies = create_all_strategies()
    sensex_strategies = create_live_sensex_strategies()

    all_results = {}

    # Run NIFTY strategies
    print("\n" + "-" * 80)
    print("  RUNNING 4 NIFTY STRATEGIES (ATM vs ITM ~Rs.200)")
    print("-" * 80)

    for strat in nifty_strategies:
        print(f"  Running {strat.name} (ATM) ...", end="", flush=True)
        t = time.time()
        r_atm, h_atm = run_strategy_backtest(strat, df_nifty, risk_params, mode="ATM")
        print(f" done ({time.time()-t:.1f}s) | Trades: {r_atm.total_trades} | Win: {r_atm.win_rate}% | P&L: Rs.{r_atm.total_pnl:,.2f}")

        print(f"  Running {strat.name} (ITM) ...", end="", flush=True)
        t = time.time()
        # Instantiate fresh instance
        fresh_strat = type(strat)()
        r_itm, h_itm = run_strategy_backtest(fresh_strat, df_nifty, risk_params, mode="ITM")
        print(f" done ({time.time()-t:.1f}s) | Trades: {r_itm.total_trades} | Win: {r_itm.win_rate}% | P&L: Rs.{r_itm.total_pnl:,.2f}")

        all_results[strat.name] = {
            "underlying": "NIFTY",
            "direction": strat.direction,
            "ATM": {
                "trades": r_atm.total_trades, "win_rate": r_atm.win_rate, "pf": r_atm.profit_factor,
                "pnl": r_atm.total_pnl, "max_dd_pct": r_atm.max_drawdown_pct,
                "tp_hits": sum(1 for o in h_atm if o.exit_reason == "TAKE_PROFIT"),
                "trail_hits": sum(1 for o in h_atm if o.exit_reason == "TRAILING_STOP"),
                "sl_hits": sum(1 for o in h_atm if o.exit_reason == "STOP_LOSS"),
                "time_hits": sum(1 for o in h_atm if o.exit_reason == "TIME_EXIT"),
            },
            "ITM": {
                "trades": r_itm.total_trades, "win_rate": r_itm.win_rate, "pf": r_itm.profit_factor,
                "pnl": r_itm.total_pnl, "max_dd_pct": r_itm.max_drawdown_pct,
                "tp_hits": sum(1 for o in h_itm if o.exit_reason == "TAKE_PROFIT"),
                "trail_hits": sum(1 for o in h_itm if o.exit_reason == "TRAILING_STOP"),
                "sl_hits": sum(1 for o in h_itm if o.exit_reason == "STOP_LOSS"),
                "time_hits": sum(1 for o in h_itm if o.exit_reason == "TIME_EXIT"),
            }
        }

    # Run SENSEX strategies
    print("\n" + "-" * 80)
    print("  RUNNING 5 SENSEX STRATEGIES (ATM vs ITM ~Rs.600)")
    print("-" * 80)

    for strat in sensex_strategies:
        print(f"  Running {strat.name} (ATM) ...", end="", flush=True)
        t = time.time()
        r_atm, h_atm = run_strategy_backtest(strat, df_sensex, risk_params, mode="ATM")
        print(f" done ({time.time()-t:.1f}s) | Trades: {r_atm.total_trades} | Win: {r_atm.win_rate}% | P&L: Rs.{r_atm.total_pnl:,.2f}")

        print(f"  Running {strat.name} (ITM) ...", end="", flush=True)
        t = time.time()
        fresh_strat = type(strat)()
        r_itm, h_itm = run_strategy_backtest(fresh_strat, df_sensex, risk_params, mode="ITM")
        print(f" done ({time.time()-t:.1f}s) | Trades: {r_itm.total_trades} | Win: {r_itm.win_rate}% | P&L: Rs.{r_itm.total_pnl:,.2f}")

        all_results[strat.name] = {
            "underlying": "SENSEX",
            "direction": strat.direction,
            "ATM": {
                "trades": r_atm.total_trades, "win_rate": r_atm.win_rate, "pf": r_atm.profit_factor,
                "pnl": r_atm.total_pnl, "max_dd_pct": r_atm.max_drawdown_pct,
                "tp_hits": sum(1 for o in h_atm if o.exit_reason == "TAKE_PROFIT"),
                "trail_hits": sum(1 for o in h_atm if o.exit_reason == "TRAILING_STOP"),
                "sl_hits": sum(1 for o in h_atm if o.exit_reason == "STOP_LOSS"),
                "time_hits": sum(1 for o in h_atm if o.exit_reason == "TIME_EXIT"),
            },
            "ITM": {
                "trades": r_itm.total_trades, "win_rate": r_itm.win_rate, "pf": r_itm.profit_factor,
                "pnl": r_itm.total_pnl, "max_dd_pct": r_itm.max_drawdown_pct,
                "tp_hits": sum(1 for o in h_itm if o.exit_reason == "TAKE_PROFIT"),
                "trail_hits": sum(1 for o in h_itm if o.exit_reason == "TRAILING_STOP"),
                "sl_hits": sum(1 for o in h_itm if o.exit_reason == "STOP_LOSS"),
                "time_hits": sum(1 for o in h_itm if o.exit_reason == "TIME_EXIT"),
            }
        }

    # Summary table
    print("\n" + "=" * 95)
    print("  FINAL SIDE-BY-SIDE SUMMARY: ATM vs ITM (ALL 9 DEPLOYED STRATEGIES)")
    print("=" * 95)
    print(f"  {'Strategy':<36} | {'ATM P&L (Rs)':>14} {'Win%':>6} {'PF':>5} | {'ITM P&L (Rs)':>14} {'Win%':>6} {'PF':>5} | {'Delta P&L':>12}")
    print("  " + "-" * 91)

    total_atm_pnl = 0.0
    total_itm_pnl = 0.0

    for name, d in all_results.items():
        atm = d["ATM"]
        itm = d["ITM"]
        total_atm_pnl += atm["pnl"]
        total_itm_pnl += itm["pnl"]
        delta = itm["pnl"] - atm["pnl"]
        pf_atm = f"{atm['pf']:.2f}" if atm['pf'] < 900 else "inf"
        pf_itm = f"{itm['pf']:.2f}" if itm['pf'] < 900 else "inf"
        print(f"  {name:<36} | Rs.{atm['pnl']:>10,.2f} {atm['win_rate']:>5.1f}% {pf_atm:>5} | Rs.{itm['pnl']:>10,.2f} {itm['win_rate']:>5.1f}% {pf_itm:>5} | Rs.{delta:>+10,.2f}")

    print("  " + "-" * 91)
    grand_delta = total_itm_pnl - total_atm_pnl
    print(f"  {'TOTAL (9 STRATEGIES)':<36} | Rs.{total_atm_pnl:>10,.2f} {' ':>6} {' ':>5} | Rs.{total_itm_pnl:>10,.2f} {' ':>6} {' ':>5} | Rs.{grand_delta:>+10,.2f}")
    print("=" * 95)

    print(f"\nCompleted in {time.time() - t0:.1f}s")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"Report saved to {OUTPUT_REPORT}\n")


if __name__ == "__main__":
    main()
