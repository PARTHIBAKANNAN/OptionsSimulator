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
print("DEEP DIVE: STEP-BY-STEP FILTER REJECTION ANALYSIS")
print("=" * 80)

# Let's inspect NIFTY strategies at the exact moment of breakout (e.g. 09:55 AM)
candles = sqlite_cache.load_recent_candles("NIFTY", days=5)
today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

sim_dm = DataManager(underlying="NIFTY")
sim_dm.load_historical(prior_candles)

strategies = create_nifty_strategies()

# Let's inspect NIFTY_ORB_BULLISH_1M_ATM, NIFTY_ORB_BULLISH_5M_ITM, NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM, etc.
for c in today_candles:
    sim_dm.replay_candle(c)
    if c.timestamp.time() in [dtime(9, 31), dtime(9, 55), dtime(10, 0), dtime(10, 30), dtime(11, 0), dtime(11, 30), dtime(12, 0), dtime(14, 0), dtime(15, 0)]:
        st = sim_dm.get_state()
        print(f"\n--- TIME: {c.timestamp.strftime('%H:%M')} | Spot={c.close:.2f} | Open={c.open:.2f} High={c.high:.2f} Low={c.low:.2f} ---")
        for s in strategies:
            # Let's check why s returned None
            res = s.evaluate(st)
            if res:
                print(f"  [TRIGGERED] {s.name} -> {res}")
            else:
                # Let's check internal conditions of s
                pass

print("\n--- DETAILED INSPECTION OF ORB IMPLEMENTATION ---")
from src.strategies.orb_bullish import ORBBullish
from src.strategies.nifty_5m_strategies import NiftyORBBullish5MITM, NiftyHeikinAshiBullish5MITM

st_955 = None
sim_dm = DataManager(underlying="NIFTY")
sim_dm.load_historical(prior_candles)
for c in today_candles:
    sim_dm.replay_candle(c)
    if c.timestamp.time() == dtime(9, 55):
        st_955 = sim_dm.get_state()
        break

if st_955:
    orb_1m = ORBBullish(name="NIFTY_ORB_BULLISH_1M_ATM")
    print("NIFTY_ORB_BULLISH_1M_ATM evaluate result at 09:55:", orb_1m.evaluate(st_955))
    orb_5m = NiftyORBBullish5MITM()
    print("NIFTY_ORB_BULLISH_5M_ITM evaluate result at 09:55:", orb_5m.evaluate(st_955))
    ha_5m = NiftyHeikinAshiBullish5MITM()
    print("NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM evaluate result at 09:55:", ha_5m.evaluate(st_955))

