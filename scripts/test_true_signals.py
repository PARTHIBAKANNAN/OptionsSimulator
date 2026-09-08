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
print("REAL SIGNALS PRODUCED TODAY ONCE EVALUATE_ALL BUG IS REMOVED")
print("=" * 80)

for index, creator_fn in [("NIFTY", create_nifty_strategies), ("SENSEX", create_sensex_strategies), ("BANKNIFTY", create_banknifty_strategies)]:
    candles = sqlite_cache.load_recent_candles(index, days=5)
    today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

    sim_dm = DataManager(underlying=index)
    sim_dm.load_historical(prior_candles)

    strategies = creator_fn()
    print(f"\n==================== {index} ====================")
    
    signals_today = []
    for c in today_candles:
        sim_dm.replay_candle(c)
        st = sim_dm.get_state()
        ts = c.timestamp
        if ts.time() < dtime(9, 25):
            continue
            
        for s in strategies:
            sig = s.evaluate(st)
            if sig:
                signals_today.append((c.timestamp.strftime('%H:%M'), s.name, sig.direction, sig.strike, sig.rationale))

    print(f"Total Signals Triggered Today: {len(signals_today)}")
    for t, n, d, stk, r in signals_today:
        print(f"  ⚡ [{t}] {n} -> {d} {stk} | Rationale: {r}")

