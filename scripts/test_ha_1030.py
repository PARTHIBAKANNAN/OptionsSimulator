import sqlite3
import os
import json
import sys
from datetime import datetime, timezone, timedelta, time as dtime

IST = timezone(timedelta(hours=5, minutes=30))
sys.path.insert(0, "/home/ubuntu/optionssimulator-app")

from src.config import Config
from src.data_manager import DataManager, Candle
from src.strategies.nifty_5m_strategies import NiftyHeikinAshiBullish5MITM
import src.db.sqlite_candle_cache as sqlite_cache

candles = sqlite_cache.load_recent_candles("NIFTY", days=5)
today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]

sim_dm = DataManager(underlying="NIFTY")
sim_dm.load_historical(prior_candles)

strat = NiftyHeikinAshiBullish5MITM()

for c in today_candles:
    sim_dm.replay_candle(c)
    if c.timestamp.time() == dtime(10, 30):
        st = sim_dm.get_state()
        ts = st.get("timestamp")
        print("can_trigger(ts):", strat.can_trigger(ts))
        
        indicators = st.get("indicators", {})
        candles = st.get("candles", [])
        spot = st.get("nifty_price") or (candles[-1].close if candles else None)
        print("spot:", spot)
        
        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        print("ha:", ha)
        print("ema50:", ema50)
        
        body = ha["close"] - ha["open"]
        prev_bullish = ha["prev_close"] > ha["prev_open"]
        print("body:", body)
        print("prev_bullish:", prev_bullish)
        print("spot > ema50:", spot > ema50)
        print("condition check 1 (body > 0 and prev_bullish and spot > ema50):", (body > 0 and prev_bullish and spot > ema50))
        
        lower_wick = ha["open"] - ha["low"]
        print("lower_wick:", lower_wick)
        print("0.30 * body:", 0.30 * body)
        print("lower_wick > 0.30 * body:", lower_wick > 0.30 * body)
        
        res = strat.evaluate(st)
        print("strat.evaluate(st) returned:", res)

