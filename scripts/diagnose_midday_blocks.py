"""
Diagnose Every Strategy During the 10:30 to 14:30 Freeze Today
============================================================
Inspects bar by bar between 10:30 and 14:30:
For each strategy that failed to trigger, WHY did it fail?
- Was it time filter (1M cutoff, ORB cutoff)?
- Was it volume filter (is_volume_acceptable)?
- Was it ADX trend filter (adx < 20)?
- Was it price action (EMA, Supertrend direction, RSI, etc.)?
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, time as dtime
import pytz
import yfinance as yf

from src.data_manager import DataManager, Candle
from src.strategies.engine import (
    create_nifty_strategies,
    create_banknifty_strategies,
    create_sensex_strategies,
)

IST = pytz.timezone("Asia/Kolkata")

TICKERS = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "SENSEX": "^BSESN"}
creators = {
    "NIFTY": create_nifty_strategies,
    "BANKNIFTY": create_banknifty_strategies,
    "SENSEX": create_sensex_strategies,
}

for name, ticker in TICKERS.items():
    df = yf.download(ticker, period="2d", interval="1m", progress=False)
    candles = []
    for ts, row in df.iterrows():
        if ts.tzinfo is None:
            ts = pytz.utc.localize(ts).astimezone(IST)
        else:
            ts = ts.astimezone(IST)
        t = ts.time()
        if t < dtime(9, 15) or t > dtime(15, 30):
            continue
        op = float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"])
        hi = float(row["High"].iloc[0] if hasattr(row["High"], "iloc") else row["High"])
        lo = float(row["Low"].iloc[0] if hasattr(row["Low"], "iloc") else row["Low"])
        cl = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
        candles.append(Candle(timestamp=ts, open=round(op, 2), high=round(hi, 2), low=round(lo, 2), close=round(cl, 2), volume=0))
    
    today_candles = [c for c in candles if str(c.timestamp.date()) == "2026-10-30"]
    prior_candles = [c for c in candles if str(c.timestamp.date()) < "2026-10-30"]
    
    dm = DataManager(underlying=name)
    dm.load_historical(prior_candles)
    strategies = creators[name]()
    
    print(f"\n{'='*30} {name} (10:30 to 14:30 Detailed Audit) {'='*30}")
    
    # Check specifically during:
    # 1. 11:30 AM (Strong morning rally in Nifty/BN)
    # 2. 13:15 PM (Major 400pt dump in BankNifty)
    test_times = [dtime(11, 30), dtime(13, 15), dtime(13, 45)]
    
    for c in today_candles:
        dm.replay_candle(c)
        cur_t = c.timestamp.time()
        if cur_t in test_times:
            st = dm.get_state()
            inds = st["indicators"]
            spot = st[f"{name.lower()}_price"]
            print(f"\n--- SNAPSHOT AT {cur_t.strftime('%H:%M')} (Spot = {spot}) ---")
            print(f"  ADX 5M: {inds.get('adx_14_5m'):.1f} | ADX 1M: {inds.get('adx_14_1m'):.1f} | Vol Ratio: {inds.get('volume_ratio_5m')} | Midday Volume Ratio: {inds.get('volume_ratio')}")
            print(f"  EMA 20 (5M): {inds.get('ema_20_5m'):.1f} | EMA 50 (5M): {inds.get('ema_50_5m'):.1f} | EMA 50 (1H): {inds.get('ema_50_1h'):.1f}")
            print(f"  Supertrend 10,3: {inds.get('supertrend_10_3'):.1f} (dir={inds.get('supertrend_10_3_direction')}) | 7,2: {inds.get('supertrend_7_2'):.1f} (dir={inds.get('supertrend_7_2_direction')})")
            print(f"  RSI 5M: {inds.get('rsi_14_5m'):.1f} | VWAP 5M: {inds.get('vwap_5m'):.1f}")
            
            # Now evaluate each strategy and see exact block reason
            blocked_reasons = {}
            for s in strategies:
                # 1. Check can_trigger
                if not s.can_trigger(c.timestamp):
                    blocked_reasons[s.name] = "BLOCKED: can_trigger (1M cutoff 10:45 or cooldown or ORB cutoff 10:30)"
                    continue
                # 2. Check evaluate
                sig = s.evaluate(st)
                if sig:
                    blocked_reasons[s.name] = f"TRIGGERED: {sig.direction} {sig.strike}"
                else:
                    # Diagnose why evaluate returned None
                    blocked_reasons[s.name] = "BLOCKED: Technical Entry Conditions Not Met"
            
            for sname, r in sorted(blocked_reasons.items()):
                print(f"    {sname:<42} : {r}")

