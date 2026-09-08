import os
import sys
import json
from datetime import datetime, timezone, timedelta, time as dtime

IST = timezone(timedelta(hours=5, minutes=30))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.config import Config
from src.strategies.engine import (
    create_nifty_strategies,
    create_sensex_strategies,
    create_banknifty_strategies,
    StrategyEngine,
)
from src.data_manager import DataManager, Candle
from src.simulator.paper_trader import PaperTrader
from src.trader import LOT_SIZE_BY_INDEX
from src.utils.options_pricing import (
    black_scholes_price,
    next_weekly_expiry_days,
    parse_option_symbol,
    format_display_symbol,
)
import src.db.sqlite_candle_cache as sqlite_cache

config = Config.load()
risk_params = config.risk_params
sizing = risk_params.get("position_sizing", {})
exits = risk_params.get("exit_rules", {})
charges = risk_params.get("charges")

paper_trader = PaperTrader(
    lot_size=sizing.get("lot_size", 65),
    max_concurrent_positions=sizing.get("max_concurrent_positions", 10),
    max_daily_loss=sizing.get("max_daily_loss", 50000),
    max_trades_per_day_per_strategy=sizing.get("max_trades_per_day_per_strategy", 2),
    trailing_stop_enabled=exits.get("trailing_stop_enabled", False),
    trailing_activation_pct=exits.get("trailing_activation_pct", 10.0),
    trailing_stop_pct=exits.get("trailing_stop_pct", 15.0),
    trailing_tiers_pct=exits.get("trailing_tiers_pct"),
    charges_rates=charges,
    enable_wallets=True,
)

data_managers = {
    "NIFTY": DataManager(underlying="NIFTY"),
    "SENSEX": DataManager(underlying="SENSEX"),
    "BANKNIFTY": DataManager(underlying="BANKNIFTY"),
}

strategy_engines = {
    "NIFTY": StrategyEngine(strategies=create_nifty_strategies(), signal_cooldown_mins=5),
    "SENSEX": StrategyEngine(strategies=create_sensex_strategies(), signal_cooldown_mins=5),
    "BANKNIFTY": StrategyEngine(strategies=create_banknifty_strategies(), signal_cooldown_mins=5),
}

# Pre-load 5 days prior candles
for index, dm in data_managers.items():
    candles = sqlite_cache.load_recent_candles(index, days=5)
    prior = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]
    dm.load_historical(prior)

today_candles_by_index = {}
for index in ["NIFTY", "SENSEX", "BANKNIFTY"]:
    candles = sqlite_cache.load_recent_candles(index, days=5)
    today = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    today_candles_by_index[index] = {c.timestamp.strftime("%H:%M"): c for c in today}

all_timestamps = sorted(list({c.timestamp.strftime("%H:%M") for clist in today_candles_by_index.values() for c in clist.values()}))

executed_trades = []
rejected_by_limits = []

print("=" * 85)
print(f"REPLAY SIMULATION: EXECUTING ALL 44 STRATEGIES ON TODAY'S PRICE ACTION ({datetime.now(IST).strftime('%Y-%m-%d')})")
print("=" * 85)

for ts_str in all_timestamps:
    current_prices = {}
    current_dt = None
    
    # 1. Advance candles across all 3 indices
    for index, dm in data_managers.items():
        c = today_candles_by_index[index].get(ts_str)
        if c:
            dm.replay_candle(c)
            current_dt = c.timestamp
            
    if not current_dt:
        continue

    # 2. Build current mark-to-market prices for active positions
    for pos in paper_trader.get_positions():
        dm = data_managers.get(pos.underlying, data_managers["NIFTY"])
        spot = dm.get_state()["nifty_price"]
        if spot:
            dte = next_weekly_expiry_days(current_dt, index=pos.underlying)
            strike, option_type = parse_option_symbol(pos.symbol)
            if strike:
                current_prices[pos.symbol] = black_scholes_price(
                    spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type
                )

    # 3. Check exits (Take Profit, Stop Loss, Trailing Stop, EOD Square-off)
    is_eod = current_dt.time() >= dtime(15, 29)
    closed = paper_trader.update_positions(
        current_prices, timestamp=current_dt, time_exit_mins=120, eod_square_off=is_eod
    )

    # 4. Evaluate new signals (if before 15:15)
    if dtime(9, 25) <= current_dt.time() <= dtime(15, 15):
        for index, dm in data_managers.items():
            state = dm.get_state()
            if state["nifty_price"] is None:
                continue
            sigs = strategy_engines[index].evaluate_all(state)
            for sig in sigs:
                lot_size = LOT_SIZE_BY_INDEX.get(sig.underlying, 65)
                sl = max(sig.entry_price * (1 - 0.20), 0.05)
                tp = sig.entry_price * (1 + 0.40)
                try:
                    order = paper_trader.place_order(
                        symbol=sig.strike,
                        side="BUY",
                        qty=1,
                        price=sig.entry_price,
                        stop_loss=sl,
                        take_profit=tp,
                        strategy=sig.strategy,
                        timestamp=sig.timestamp,
                        lot_size=lot_size,
                    )
                    executed_trades.append(order)
                except Exception as e:
                    rejected_by_limits.append((sig.strategy, str(e)))

# Close any remaining open positions at 15:30
final_closed = paper_trader.update_positions(
    current_prices, timestamp=current_dt, time_exit_mins=120, eod_square_off=True
)

all_closed = [o for o in paper_trader.orders.values() if o.status == "CLOSED"]
print(f"\nTotal Orders Attempted: {len(executed_trades) + len(rejected_by_limits)}")
print(f"Total Orders Executed:  {len(executed_trades)} (Risk Limits Blocked: {len(rejected_by_limits)})")
print(f"Total Closed Positions: {len(all_closed)}")

# Performance Breakdown
winning_trades = [o for o in all_closed if (o.net_pnl if o.net_pnl is not None else o.realized_pnl) > 0]
losing_trades = [o for o in all_closed if (o.net_pnl if o.net_pnl is not None else o.realized_pnl) <= 0]

total_gross_pnl = sum(o.realized_pnl for o in all_closed)
total_charges = sum((o.entry_charges + o.exit_charges) for o in all_closed)
total_net_pnl = sum((o.net_pnl if o.net_pnl is not None else (o.realized_pnl - (o.entry_charges + o.exit_charges))) for o in all_closed)
win_rate = (len(winning_trades) / len(all_closed) * 100) if all_closed else 0.0

print("\n" + "=" * 85)
print("TODAY'S SIMULATED PERFORMANCE SUMMARY (IF BUG DID NOT EXIST)")
print("=" * 85)
print(f"Total Trades Taken:     {len(all_closed)}")
print(f"Winning Trades:         {len(winning_trades)} ({win_rate:.1f}%)")
print(f"Losing Trades:          {len(losing_trades)} ({100 - win_rate:.1f}%)")
print(f"Gross P&L:              ₹{total_gross_pnl:+,.2f}")
print(f"Taxes & Charges:        ₹{total_charges:,.2f}")
print(f"NET REALIZED P&L:       ₹{total_net_pnl:+,.2f}")
print("=" * 85)

# Detailed Trade Log
print("\n--- DETAILED TRADE BREAKDOWN ---")
print(f"{'Exit Time':<10} | {'Strategy':<38} | {'Contract':<16} | {'Entry':<8} | {'Exit':<8} | {'Reason':<16} | {'Net P&L (₹)':<10}")
print("-" * 115)
for o in all_closed:
    net = o.net_pnl if o.net_pnl is not None else (o.realized_pnl - o.charges)
    print(f"{o.exit_time.strftime('%H:%M'):<10} | {o.strategy:<38} | {o.symbol:<16} | {o.entry_price:<8.2f} | {o.exit_price:<8.2f} | {o.exit_reason:<16} | {net:+10.2f}")

# Breakdown by Index
print("\n--- PERFORMANCE BY INDEX ---")
for idx in ["NIFTY", "SENSEX", "BANKNIFTY"]:
    idx_trades = [o for o in all_closed if o.underlying == idx]
    idx_wins = [o for o in idx_trades if (o.net_pnl if o.net_pnl is not None else o.realized_pnl) > 0]
    idx_pnl = sum((o.net_pnl if o.net_pnl is not None else (o.realized_pnl - o.charges)) for o in idx_trades)
    idx_wr = (len(idx_wins) / len(idx_trades) * 100) if idx_trades else 0.0
    print(f"  {idx:<10}: {len(idx_trades):>2} trades | Win Rate: {idx_wr:>5.1f}% | Net P&L: ₹{idx_pnl:+,.2f}")

