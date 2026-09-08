"""
Comprehensive single-pass empirical backtest comparing:
1. Baseline (Current 14 NIFTY strategies without ADX filter)
2. ADX >= 20 on 5M Spot + Directional DI Gate (+DI > -DI for CE, -DI > +DI for PE)
3. ADX >= 25 on 5M Spot + Directional DI Gate

Source of truth:
- Historical dataset: data/historical/nifty_90days.csv (92,250 1-min candles)
- Exact Option pricing, PaperTrader risk rules, dynamic TSL, and transaction charges
"""
import sys
import json
from pathlib import Path
from datetime import datetime, time as dtime
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader
from src.strategies.engine import StrategyEngine, create_nifty_strategies
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol


def compute_adx_df(df_5m: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high = df_5m["High"]
    low = df_5m["Low"]
    close = df_5m["Close"]

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_smooth = pd.Series(tr, index=high.index).ewm(alpha=1 / period, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, np.nan)).fillna(0.0)
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, np.nan)).fillna(0.0)

    di_sum = plus_di + minus_di
    dx = 100 * ((plus_di - minus_di).abs() / di_sum.replace(0, np.nan)).fillna(0.0)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)

    return pd.DataFrame({"adx": adx, "plus_di": plus_di, "minus_di": minus_di}, index=df_5m.index)


def simulate_single_pass(csv_file: Path, min_adx: float, risk_params: dict):
    raw_df = pd.read_csv(csv_file)
    raw_df.columns = [c.lower() for c in raw_df.columns]
    raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
    raw_df = raw_df.sort_values("timestamp").reset_index(drop=True)

    # 5M ADX lookup
    df_indexed = raw_df.set_index("timestamp")
    df_5m = df_indexed.resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()
    df_5m.columns = ["Open", "High", "Low", "Close", "Volume"]
    adx_5m_df = compute_adx_df(df_5m, period=14)

    adx_lookup_dict = {
        ts: (row["adx"], row["plus_di"], row["minus_di"])
        for ts, row in adx_5m_df.iterrows()
    }

    dm = DataManager(window_size=3000, underlying="NIFTY")
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=65,
        max_concurrent_positions=10,
        max_daily_loss=50000,
        max_trades_per_day_per_strategy=5,
        expanding_dynamic_tsl_enabled=True,
        multi_index_tsl=risk_params.get("multi_index_tsl", {}),
    )
    strategies = create_nifty_strategies()
    engine = StrategyEngine(strategies=strategies)

    for row in raw_df.itertuples():
        ts = row.timestamp
        candle = Candle(
            timestamp=ts,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=int(getattr(row, "volume", 1000)),
        )
        dm.replay_candle(candle)
        state = dm.get_state()
        if state["nifty_price"] is None:
            continue

        # Check exits
        open_pos = trader.get_positions()
        if open_pos:
            current_prices = {}
            for o in open_pos:
                strike, opt_type = parse_option_symbol(o.symbol)
                dte_days = next_weekly_expiry_days(ts, index="NIFTY")
                px = black_scholes_price(
                    spot=candle.close,
                    strike=strike,
                    days_to_expiry=dte_days,
                    option_type=opt_type,
                    iv=0.15,
                )
                current_prices[o.symbol] = max(round(px, 2), 0.05)
            trader.update_positions(current_prices, timestamp=ts, time_exit_mins=120)

        # Signals
        signals = engine.evaluate_all(state)
        for sig in signals:
            if not (dtime(9, 20) <= ts.time() <= dtime(15, 0)):
                continue

            # ADX / DI filter
            if min_adx > 0:
                bucket_5m = ts.floor("5min")
                adx_info = adx_lookup_dict.get(bucket_5m)
                if not adx_info:
                    continue
                cur_adx, plus_di, minus_di = adx_info
                if cur_adx < min_adx:
                    continue
                if sig.direction == "CE" and plus_di <= minus_di:
                    continue
                if sig.direction == "PE" and minus_di <= plus_di:
                    continue

            # Option pricing
            strike, opt_type = parse_option_symbol(sig.strike)
            dte_days = next_weekly_expiry_days(ts, index="NIFTY")
            opt_px = black_scholes_price(
                spot=candle.close,
                strike=strike,
                days_to_expiry=dte_days,
                option_type=opt_type,
                iv=0.15,
            )
            ep = max(round(opt_px, 2), 0.05)

            is_itm = "_ITM" in sig.strategy or ep >= 200.0
            index_rules = risk_params.get("multi_index_tsl", {}).get("NIFTY", {})
            rule = index_rules.get("itm" if is_itm else "atm", {})
            sl_pct = rule.get("stop_loss_pct", 20)
            tp_pts = rule.get("target_pts", None)
            stop_loss = max(ep * (1 - sl_pct / 100.0), 0.05)
            take_profit = ep + tp_pts if tp_pts is not None else ep * 1.5

            try:
                trader.place_order(
                    symbol=sig.strike,
                    side="BUY",
                    qty=1,
                    price=ep,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy=sig.strategy,
                    timestamp=ts,
                    lot_size=65,
                )
            except Exception:
                pass

    # End of dataset close
    for o in trader.get_positions():
        trader.close_position(o.order_id, o.entry_price, timestamp=raw_df['timestamp'].iloc[-1], reason="END_OF_DATA")

    return trader.get_trade_history()


def run_all_benchmarks():
    csv_file = ROOT_DIR / "data" / "historical" / "nifty_90days.csv"
    with open(ROOT_DIR / "config" / "risk_params.json") as f:
        risk_params = json.load(f)

    summary_table = {}

    for min_adx in [0, 20, 25]:
        mode_label = "Baseline (No ADX Filter)" if min_adx == 0 else f"ADX >= {min_adx} (+DI / -DI Filter)"
        print(f"--> Simulating {mode_label}...")

        trades = simulate_single_pass(csv_file, min_adx, risk_params)
        total_trades = len(trades)

        wins = [t for t in trades if (t.net_pnl or 0) > 0]
        losses = [t for t in trades if (t.net_pnl or 0) < 0]
        full_sl_losses = [t for t in trades if t.exit_reason == "STOP_LOSS"]
        cost_exits = [t for t in trades if t.exit_reason == "TRAILING_STOP" and abs((t.exit_price or 0) - (t.entry_price or 0)) < 0.5]
        trailed_runner_wins = [t for t in trades if t.exit_reason == "TRAILING_STOP" and (t.net_pnl or 0) > 0]

        total_gross_pnl = sum((t.realized_pnl or 0) for t in trades)
        total_charges = sum((t.entry_charges or 0) + (t.exit_charges or 0) for t in trades)
        total_net_pnl = sum((t.net_pnl or 0) for t in trades)

        win_rate = (len(wins) / total_trades) * 100.0 if total_trades else 0
        gross_profit = sum(t.realized_pnl for t in wins if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in losses if t.realized_pnl < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0

        cum_pnl = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cum_pnl += (t.net_pnl or 0)
            if cum_pnl > peak:
                peak = cum_pnl
            dd = peak - cum_pnl
            if dd > max_dd:
                max_dd = dd

        summary_table[mode_label] = {
            "total_trades": total_trades,
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "full_sl_count": len(full_sl_losses),
            "cost_exit_count": len(cost_exits),
            "trailed_runner_wins": len(trailed_runner_wins),
            "gross_pnl": round(total_gross_pnl, 2),
            "total_charges": round(total_charges, 2),
            "net_pnl": round(total_net_pnl, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_dd, 2),
            "avg_trade_net": round(total_net_pnl / total_trades, 2) if total_trades else 0,
        }

    print("\n" + "=" * 90)
    print("EMPIRICAL ADX BENCHMARK RESULTS (NIFTY 90 DAYS)")
    print("=" * 90)
    print(json.dumps(summary_table, indent=2))


if __name__ == "__main__":
    run_all_benchmarks()
