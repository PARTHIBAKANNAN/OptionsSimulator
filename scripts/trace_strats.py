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
)
from src.data_manager import DataManager, Candle
import src.db.sqlite_candle_cache as sqlite_cache

config = Config.load()

print("=" * 80)
print("DEEP-DIVE STRATEGY EVALUATION TRACER ACROSS 375 CANDLES")
print("=" * 80)

for index, creator_fn in [("NIFTY", create_nifty_strategies), ("SENSEX", create_sensex_strategies), ("BANKNIFTY", create_banknifty_strategies)]:
    candles = sqlite_cache.load_recent_candles(index, days=5)
    today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

    sim_dm = DataManager(underlying=index)
    sim_dm.load_historical(prior_candles)

    strategies = creator_fn()
    print(f"\n==================== {index} ({len(strategies)} Strategies) ====================")
    
    # We want to trace each strategy to find its closest entry bar
    strat_diagnostics = {s.name: {"checks": 0, "failures": {}} for s in strategies}
    
    for c in today_candles:
        sim_dm.replay_candle(c)
        st = sim_dm.get_state()
        ts = c.timestamp
        if ts.time() < dtime(9, 25):
            continue
            
        for s in strategies:
            strat_diagnostics[s.name]["checks"] += 1
            res = s.evaluate(st)
            if res:
                print(f"  [SIGNAL!] {c.timestamp.strftime('%H:%M')} | {s.name} -> {res.direction} {res.strike}")

    print(f"\n--- Strategy Filter Analysis for {index} ---")
    for s in strategies:
        print(f"  Strategy: {s.name}")
        # Let's inspect what conditions this strategy requires
        # e.g. Heikin Ashi, MACD, ORB, Supertrend, etc.

