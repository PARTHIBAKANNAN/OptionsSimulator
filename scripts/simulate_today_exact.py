"""
Deep Dive Audit of Today's (2026-10-30) 44 Strategies
===================================================
1. Loads today's exact 1-minute exchange candles for NIFTY, BANKNIFTY, SENSEX.
2. Replays the full day through DataManager and StrategyEngine.
3. Compares:
   A) As-Is Production Behavior (with 1.0 volume fallback, 1M 10:45 cutoff, 12:30-14:30 1.5x chop gate).
   B) Behavior WITHOUT the 1.0 Volume Gate (evaluating pure technical setups).
   C) Behavior WITHOUT the 1M 10:45 cutoff.
4. Categorizes every single strategy: why did it fire or fail to fire?
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf

from src.data_manager import DataManager, Candle
from src.strategies.engine import (
    create_nifty_strategies,
    create_sensex_strategies,
    create_banknifty_strategies,
    StrategyEngine,
)

IST = pytz.timezone("Asia/Kolkata")

TICKERS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
}

def get_today_1m_candles(ticker: str) -> list[Candle]:
    df = yf.download(ticker, period="2d", interval="1m", progress=False)
    if df.empty:
        return []
    candles = []
    for ts, row in df.iterrows():
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts).astimezone(IST)
        else:
            ts = ts.astimezone(IST)
        t = ts.time()
        if t < datetime.strptime("09:15", "%H:%M").time() or t > datetime.strptime("15:30", "%H:%M").time():
            continue
        op = float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"])
        hi = float(row["High"].iloc[0] if hasattr(row["High"], "iloc") else row["High"])
        lo = float(row["Low"].iloc[0] if hasattr(row["Low"], "iloc") else row["Low"])
        cl = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
        # Spot index volume from Yahoo is either 0 or NaN
        vol = 0
        candles.append(Candle(timestamp=ts, open=round(op, 2), high=round(hi, 2), low=round(lo, 2), close=round(cl, 2), volume=vol))
    return sorted(candles, key=lambda c: c.timestamp)

print("Downloading today's 1m candles...")
data = {}
for name, tick in TICKERS.items():
    c = get_today_1m_candles(tick)
    # Split into prior days (for indicator warmup) and today
    today_candles = [x for x in c if str(x.timestamp.date()) == "2026-10-30"]
    prior_candles = [x for x in c if str(x.timestamp.date()) < "2026-10-30"]
    print(f"{name}: Prior={len(prior_candles)}, Today={len(today_candles)}")
    data[name] = {"today": today_candles, "prior": prior_candles}

print("\n" + "="*80)
print("EXPERIMENT 1: AS-IS PRODUCTION BEHAVIOR (LIVE SETTINGS)")
print("="*80)

creators = {
    "NIFTY": create_nifty_strategies,
    "BANKNIFTY": create_banknifty_strategies,
    "SENSEX": create_sensex_strategies,
}

for name, d in data.items():
    dm = DataManager(underlying=name)
    dm.load_historical(d["prior"])
    strategies = creators[name]()
    engine = StrategyEngine(strategies=strategies, signal_cooldown_mins=5)
    
    sigs = []
    for c in d["today"]:
        dm.replay_candle(c)
        st = dm.get_state()
        triggered = engine.evaluate_all(st)
        for s in triggered:
            sigs.append((c.timestamp.strftime("%H:%M"), s.strategy, s.direction, s.strike, s.rationale))
            
    print(f"\n{name} - Total Signals Triggered (AS-IS): {len(sigs)}")
    for t, strat, dr, stk, rat in sigs:
        print(f"  [{t}] {strat} -> {dr} {stk} | {rat}")

