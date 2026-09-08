import sqlite3
import os
import json
import sys
from datetime import datetime, timezone, timedelta, time as dtime

IST = timezone(timedelta(hours=5, minutes=30))
sys.path.insert(0, "/home/ubuntu/optionssimulator-app")

from src.config import Config
from src.strategies.engine import (
    create_nifty_strategies,
    create_sensex_strategies,
    create_banknifty_strategies,
    StrategyEngine,
)
from src.data_manager import DataManager, Candle
import src.db.sqlite_candle_cache as sqlite_cache

config = Config.load()

print("=" * 80)
print(f"EOD AUTOPSY: FULL DAY TRADING & STRATEGY EVALUATION ({datetime.now(IST).strftime('%Y-%m-%d')})")
print("=" * 80)

creators = {
    "NIFTY": create_nifty_strategies,
    "SENSEX": create_sensex_strategies,
    "BANKNIFTY": create_banknifty_strategies,
}

for index, creator_fn in creators.items():
    candles = sqlite_cache.load_recent_candles(index, days=5)
    today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    
    print(f"\n{'#' * 30} {index} ({len(today_candles)} Today's Candles) {'#' * 30}")
    if not today_candles:
        print("NO CANDLES FOUND FOR TODAY!")
        continue

    day_open = today_candles[0].open
    day_close = today_candles[-1].close
    day_high = max(c.high for c in today_candles)
    day_low = min(c.low for c in today_candles)
    print(f"Session Summary: Open={day_open:.2f}, High={day_high:.2f}, Low={day_low:.2f}, Close={day_close:.2f} (Net Change: {day_close - day_open:+.2f} pts)")
    
    # Check volume in candles
    volumes = [c.volume for c in today_candles]
    non_zero_vol = sum(1 for v in volumes if v > 0)
    print(f"Volume Stats: Total Candles={len(today_candles)}, Non-zero Volume Candles={non_zero_vol}, Max Volume={max(volumes) if volumes else 0}")

    sim_dm = DataManager(underlying=index)
    prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]
    sim_dm.load_historical(prior_candles)
    
    strategies = creator_fn()
    sim_engine = StrategyEngine(strategies=strategies, signal_cooldown_mins=5)
    
    signals_triggered = []
    condition_failures = {s.name: {"total_evals": 0, "time_filter_blocked": 0, "reasons": {}} for s in strategies}
    
    for c in today_candles:
        sim_dm.replay_candle(c)
        st = sim_dm.get_state()
        
        # Test engine evaluate_all
        sigs = sim_engine.evaluate_all(st)
        for sig in sigs:
            signals_triggered.append((c.timestamp.strftime('%H:%M'), sig.strategy, sig.direction, sig.strike, sig.rationale))
            
        # Also test each strategy individually to diagnose reason for no signal
        ts = st.get("timestamp")
        is_past_925 = ts and hasattr(ts, "time") and ts.time() >= dtime(9, 25)
        
        for s in strategies:
            condition_failures[s.name]["total_evals"] += 1
            if not is_past_925:
                condition_failures[s.name]["time_filter_blocked"] += 1
                continue
            try:
                sig = s.evaluate(st)
                if not sig:
                    pass
            except Exception as e:
                err_key = f"Exception: {str(e)}"
                condition_failures[s.name]["reasons"][err_key] = condition_failures[s.name]["reasons"].get(err_key, 0) + 1

    print(f"\nSignals Triggered Throughout Entire Day (09:15 to 15:30): {len(signals_triggered)}")
    for t, n, d, stk, r in signals_triggered:
        print(f"  ⚡ [{t}] {n} -> {d} {stk} | Rationale: {r}")
        
    if not signals_triggered:
        print("  -> ZERO SIGNALS TRIGGERED.")

    # Deep dive into key strategy families: ORB, Heikin Ashi, MACD, Expansion
    print(f"\n--- Strategy Rule Deep-Dive & Exact Blocker Analysis ---")
    
    # 1. ORB Check
    orb_candles = [c for c in today_candles if c.timestamp.time() <= dtime(9, 25)]
    if orb_candles:
        orb_h = max(c.high for c in orb_candles)
        orb_l = min(c.low for c in orb_candles)
        print(f"  [ORB 09:15-09:25] Opening Range High = {orb_h:.2f}, Low = {orb_l:.2f} (Range = {orb_h - orb_l:.2f} pts)")
        breakout_up = [c for c in today_candles if c.timestamp.time() > dtime(9, 25) and c.close > orb_h]
        breakout_down = [c for c in today_candles if c.timestamp.time() > dtime(9, 25) and c.close < orb_l]
        print(f"  [ORB Breakout] 1m Closes above ORB High: {len(breakout_up)} bars | 1m Closes below ORB Low: {len(breakout_down)} bars")
        if breakout_up:
            print(f"    First Upside Breakout Bar: {breakout_up[0].timestamp.strftime('%H:%M')} (Close={breakout_up[0].close:.2f} > {orb_h:.2f})")
        if breakout_down:
            print(f"    First Downside Breakout Bar: {breakout_down[0].timestamp.strftime('%H:%M')} (Close={breakout_down[0].close:.2f} < {orb_l:.2f})")

print("\n" + "=" * 80)
