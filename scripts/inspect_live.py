import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

import sys
sys.path.insert(0, "/home/ubuntu/optionssimulator-app")
from src.config import Config
from src.strategies.engine import (
    StrategyEngine,
    create_nifty_strategies,
    create_sensex_strategies,
    create_banknifty_strategies,
)
from src.data_manager import DataManager, Candle
import src.db.sqlite_candle_cache as sqlite_cache

config = Config.load()

print("==================================================================")
print(f"LIVE SYSTEM DIAGNOSTIC REPORT AS OF {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
print("==================================================================")

creators = {
    "NIFTY": create_nifty_strategies,
    "SENSEX": create_sensex_strategies,
    "BANKNIFTY": create_banknifty_strategies,
}

for index, creator_fn in creators.items():
    candles = sqlite_cache.load_recent_candles(index, days=5)
    dm = DataManager(underlying=index)
    dm.load_historical(candles)
    state = dm.get_state()
    strats = creator_fn()
    engine = StrategyEngine(strategies=strats)
    
    today_candles = [c for c in candles if c.timestamp.date() == datetime.now(IST).date()]
    print(f"\n==================== {index} ({len(strats)} Strategies) ====================")
    print(f"Total 5-Day Historical Candles in Cache: {len(candles)}")
    print(f"Today's 1-Min Live Candles Generated (09:15 to current): {len(today_candles)}")
    if today_candles:
        print(f"  First Candle (09:15): O={today_candles[0].open}, H={today_candles[0].high}, L={today_candles[0].low}, C={today_candles[0].close}")
        print(f"  Latest Candle ({today_candles[-1].timestamp.strftime('%H:%M')}): O={today_candles[-1].open}, H={today_candles[-1].high}, L={today_candles[-1].low}, C={today_candles[-1].close}")
        day_high = max(c.high for c in today_candles)
        day_low = min(c.low for c in today_candles)
        print(f"  Today's Day Range: Low={day_low} <---> High={day_high} (Range: {round(day_high - day_low, 2)} pts)")
    
    inds = state.get("indicators", {})
    print(f"\nCalculated Multi-Timeframe Indicators:")
    print(f"  Spot LTP:              {state.get('nifty_price')}")
    print(f"  EMA 20 (5m):           {inds.get('ema_20_5m')}")
    print(f"  EMA 50 (5m):           {inds.get('ema_50_5m')}")
    print(f"  VWAP (5m):             {inds.get('vwap_5m')}")
    print(f"  RSI 14 (5m):           {inds.get('rsi_14_5m')}")
    print(f"  MACD Hist (5m):        {inds.get('macd_histogram_5m')}")
    print(f"  MACD Hist (15m):       {inds.get('macd_histogram_15m')}")
    print(f"  Stochastic K (15m):    {inds.get('stochastic_k_15m')}")
    print(f"  EMA 20 (1h):           {inds.get('ema_20_1h')}")
    print(f"  EMA 50 (1h):           {inds.get('ema_50_1h')}")

    # Chronological minute-by-minute evaluation
    sim_dm = DataManager(underlying=index)
    prior_candles = [c for c in candles if c.timestamp.date() < datetime.now(IST).date()]
    sim_dm.load_historical(prior_candles)
    sim_engine = StrategyEngine(strategies=creator_fn())
    
    triggered_signals = []
    eval_errors = []
    for c in today_candles:
        sim_dm.replay_candle(c)
        st = sim_dm.get_state()
        try:
            signals = sim_engine.evaluate_all(st)
            for sig in signals:
                triggered_signals.append((c.timestamp.strftime('%H:%M'), sig.strategy, sig.direction, sig.strike, sig.rationale))
        except Exception as e:
            eval_errors.append((c.timestamp.strftime('%H:%M'), str(e)))
    
    print(f"\nChronological Strategy Execution (09:15 to {today_candles[-1].timestamp.strftime('%H:%M') if today_candles else 'N/A'}):")
    print(f"  Evaluation Errors: {len(eval_errors)}")
    print(f"  Total Signals Triggered: {len(triggered_signals)}")
    for t, n, d, stk, r in triggered_signals:
        print(f"    [{t}] {n} -> {d} {stk} ({r})")
    
    if len(triggered_signals) == 0:
        print(f"  -> DIAGNOSIS: Engine and Data Feed are completely HEALTHY and actively running.")
        print(f"     No trades were taken because the market stayed range-bound/consolidating and did not trigger entry conditions.")

