import sqlite3
import os
import json
import sys
from datetime import datetime, timezone, timedelta, time as dtime

IST = timezone(timedelta(hours=5, minutes=30))
sys.path.insert(0, "/home/ubuntu/optionssimulator-app")

from src.config import Config
from src.data_manager import DataManager, Candle
import src.db.sqlite_candle_cache as sqlite_cache

config = Config.load()

candles = sqlite_cache.load_recent_candles("NIFTY", days=5)
today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

sim_dm = DataManager(underlying="NIFTY")
sim_dm.load_historical(prior_candles)

print("=" * 80)
print("EXACT STEP-BY-STEP FILTER CHECKS ACROSS TODAY'S NIFTY SESSION")
print("=" * 80)

# Let's inspect during the big morning rally (09:40 to 11:30) and the afternoon drop (12:00 to 15:30)
for c in today_candles:
    sim_dm.replay_candle(c)
    t = c.timestamp.time()
    
    # Check at 10:30 (during the morning uptrend)
    if t == dtime(10, 30):
        st = sim_dm.get_state()
        inds = st["indicators"]
        print(f"\n--- TIME: 10:30 (Morning Uptrend, Nifty Spot={st['nifty_price']}) ---")
        print(f"EMA 50 (1H): {inds.get('ema_50_1h')} | EMA 20 (5M): {inds.get('ema_20_5m')} | EMA 50 (5M): {inds.get('ema_50_5m')}")
        print(f"MACD 5M Hist: {inds.get('macd_histogram_5m')} | Prev: {inds.get('macd_histogram_5m_prev')}")
        print(f"MACD 15M Hist: {inds.get('macd_histogram_15m')} | Prev: {inds.get('macd_histogram_15m_prev')}")
        print(f"Heikin Ashi 5M: {inds.get('heikin_ashi_5m')}")
        print(f"Heikin Ashi 15M: {inds.get('heikin_ashi_15m')}")
        print(f"Supertrend 10,3: {inds.get('supertrend_10_3')} (dir={inds.get('supertrend_10_3_direction')})")
        print(f"Supertrend 7,2: {inds.get('supertrend_7_2')} (dir={inds.get('supertrend_7_2_direction')})")
        print(f"RSI 14 (5M): {inds.get('rsi_14_5m')}")
        print(f"CMF 20 (5M): {inds.get('cmf_20_5m')}")
        print(f"BB Upper: {inds.get('bb_upper_5m')} | BB Lower: {inds.get('bb_lower_5m')} | BB Bandwidth: {inds.get('bb_bandwidth_5m')}")

    # Check at 14:00 (during afternoon downtrend)
    if t == dtime(14, 0):
        st = sim_dm.get_state()
        inds = st["indicators"]
        print(f"\n--- TIME: 14:00 (Afternoon Downtrend, Nifty Spot={st['nifty_price']}) ---")
        print(f"EMA 50 (1H): {inds.get('ema_50_1h')} | EMA 20 (5M): {inds.get('ema_20_5m')} | EMA 50 (5M): {inds.get('ema_50_5m')}")
        print(f"MACD 5M Hist: {inds.get('macd_histogram_5m')} | Prev: {inds.get('macd_histogram_5m_prev')}")
        print(f"MACD 15M Hist: {inds.get('macd_histogram_15m')} | Prev: {inds.get('macd_histogram_15m_prev')}")
        print(f"Heikin Ashi 5M: {inds.get('heikin_ashi_5m')}")
        print(f"Supertrend 10,3: {inds.get('supertrend_10_3')} (dir={inds.get('supertrend_10_3_direction')})")
        print(f"Supertrend 7,2: {inds.get('supertrend_7_2')} (dir={inds.get('supertrend_7_2_direction')})")
        print(f"RSI 14 (5M): {inds.get('rsi_14_5m')}")
        print(f"CMF 20 (5M): {inds.get('cmf_20_5m')}")

