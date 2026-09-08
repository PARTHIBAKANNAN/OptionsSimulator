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
print("TESTING SIGNAL GENERATION: WITH vs WITHOUT VOLUME ZERO-BUG")
print("=" * 80)

for index, creator_fn in [("NIFTY", create_nifty_strategies), ("SENSEX", create_sensex_strategies), ("BANKNIFTY", create_banknifty_strategies)]:
    candles = sqlite_cache.load_recent_candles(index, days=5)
    today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

    print(f"\n==================== {index} ====================")
    
    # 1. Standard (As-Is in production right now)
    sim_dm = DataManager(underlying=index)
    sim_dm.load_historical(prior_candles)
    strategies = creator_fn()
    sim_engine = StrategyEngine(strategies=strategies, signal_cooldown_mins=5)
    
    signals_as_is = []
    for c in today_candles:
        sim_dm.replay_candle(c)
        st = sim_dm.get_state()
        sigs = sim_engine.evaluate_all(st)
        for sig in sigs:
            signals_as_is.append((c.timestamp.strftime('%H:%M'), sig.strategy, sig.direction, sig.strike, sig.rationale))
    
    print(f"Signals triggered with AS-IS code: {len(signals_as_is)}")
    for t, n, d, stk, r in signals_as_is:
        print(f"  [{t}] {n} -> {d} {stk} ({r})")

    # 2. Fixed volume check (handling volume=0 for spot index ticks)
    # Let's test by patching volume confirmation or synthetic tick volume
    sim_dm_fixed = DataManager(underlying=index)
    sim_dm_fixed.load_historical(prior_candles)
    strategies_fixed = creator_fn()
    sim_engine_fixed = StrategyEngine(strategies=strategies_fixed, signal_cooldown_mins=5)

    signals_fixed = []
    for c in today_candles:
        # Give candle a baseline volume or evaluate with volume fallback
        c_mod = Candle(timestamp=c.timestamp, open=c.open, high=c.high, low=c.low, close=c.close, volume=1000, delta=c.delta)
        sim_dm_fixed.replay_candle(c_mod)
        st = sim_dm_fixed.get_state()
        # Ensure indicators don't block on 0 volume
        sigs = sim_engine_fixed.evaluate_all(st)
        for sig in sigs:
            signals_fixed.append((c.timestamp.strftime('%H:%M'), sig.strategy, sig.direction, sig.strike, sig.rationale))
            
    print(f"\nSignals triggered if Spot Index Volume is handled properly: {len(signals_fixed)}")
    for t, n, d, stk, r in signals_fixed:
        print(f"  ⚡ [{t}] {n} -> {d} {stk} | Rationale: {r}")

