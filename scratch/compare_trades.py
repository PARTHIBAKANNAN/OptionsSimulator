import os
import sys
import json
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.fyers.api_client import FyersAPIClient
from src.utils.options_pricing import to_fyers_symbol

IST = ZoneInfo("Asia/Kolkata")

TRADES = [
    {"id": 1, "strategy": "SENSEX_ORB_BEARISH_5M_ITM", "symbol": "SENSEX74900PE", "time": "2026-09-16 09:36:00", "app_entry": 673.87},
    {"id": 2, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "SENSEX74900PE", "time": "2026-09-16 09:40:00", "app_entry": 665.67},
    {"id": 3, "strategy": "SENSEX_OI_SHORT_SQUEEZE_CE", "symbol": "SENSEX74400CE", "time": "2026-09-16 09:25:00", "app_entry": 318.57},
    {"id": 4, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "SENSEX74300PE", "time": "2026-09-16 09:25:00", "app_entry": 295.65},
    {"id": 5, "strategy": "SENSEX_ORB_BEARISH_1M_ATM", "symbol": "SENSEX74300PE", "time": "2026-09-16 09:36:00", "app_entry": 305.41},
    {"id": 6, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "SENSEX74800PE", "time": "2026-09-16 10:26:00", "app_entry": 645.19},
    {"id": 7, "strategy": "SENSEX_RESISTANCE_REJECTION_5M_ITM", "symbol": "SENSEX74800PE", "time": "2026-09-16 10:36:00", "app_entry": 658.21},
    {"id": 8, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "NIFTY23250PE", "time": "2026-09-16 09:25:00", "app_entry": 152.20},
    {"id": 9, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 09:25:00", "app_entry": 506.41},
    {"id": 10, "strategy": "NIFTY_VWAP_POC_PULLBACK_CE", "symbol": "NIFTY23200CE", "time": "2026-09-16 09:26:00", "app_entry": 199.75},
    {"id": 11, "strategy": "BANKNIFTY_ORB_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 09:39:00", "app_entry": 520.87},
    {"id": 12, "strategy": "NIFTY_ORB_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "time": "2026-09-16 09:39:00", "app_entry": 180.38},
    {"id": 13, "strategy": "BANKNIFTY_ORB_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 09:39:00", "app_entry": 520.87},
    {"id": 14, "strategy": "SENSEX_RESISTANCE_REJECTION_5M_ITM", "symbol": "SENSEX74800PE", "time": "2026-09-16 11:01:00", "app_entry": 647.60},
    {"id": 15, "strategy": "SENSEX_OI_LONG_UNWINDING_PE", "symbol": "SENSEX74300PE", "time": "2026-09-16 10:35:00", "app_entry": 347.40},
    {"id": 16, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 09:46:00", "app_entry": 510.86},
    {"id": 17, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "time": "2026-09-16 09:46:00", "app_entry": 178.48},
    {"id": 18, "strategy": "SENSEX_OI_SHORT_SQUEEZE_CE", "symbol": "SENSEX74300CE", "time": "2026-09-16 09:55:00", "app_entry": 354.95},
    {"id": 19, "strategy": "SENSEX_ORB_BEARISH_1M_ATM", "symbol": "SENSEX74200PE", "time": "2026-09-16 11:27:00", "app_entry": 342.59},
    {"id": 20, "strategy": "SENSEX_ORB_BEARISH_5M_ITM", "symbol": "SENSEX74800PE", "time": "2026-09-16 11:27:00", "app_entry": 716.42},
    {"id": 21, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "SENSEX74200PE", "time": "2026-09-16 11:31:00", "app_entry": 333.73},
    {"id": 22, "strategy": "SENSEX_OI_LONG_UNWINDING_PE", "symbol": "SENSEX74200PE", "time": "2026-09-16 11:52:00", "app_entry": 333.23},
    {"id": 23, "strategy": "BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 10:21:00", "app_entry": 522.62},
    {"id": 24, "strategy": "NIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "NIFTY23300PE", "time": "2026-09-16 10:25:00", "app_entry": 190.29},
    {"id": 25, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "NIFTY23200PE", "time": "2026-09-16 11:31:00", "app_entry": 157.41},
    {"id": 26, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 11:31:00", "app_entry": 535.18},
    {"id": 27, "strategy": "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "symbol": "BANKNIFTY55900CE", "time": "2026-09-16 11:39:00", "app_entry": 822.97},
    {"id": 28, "strategy": "SENSEX_BB_SQUEEZE_EXPLOSION_CE", "symbol": "SENSEX73700CE", "time": "2026-09-16 13:46:00", "app_entry": 684.13},
    {"id": 29, "strategy": "NIFTY_ORB_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "time": "2026-09-16 12:23:00", "app_entry": 197.75},
    {"id": 30, "strategy": "BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 12:23:00", "app_entry": 528.83},
    {"id": 31, "strategy": "NIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "NIFTY23250PE", "time": "2026-09-16 12:28:00", "app_entry": 177.73},
    {"id": 32, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "NIFTY23250PE", "time": "2026-09-16 12:36:00", "app_entry": 175.83},
    {"id": 33, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 12:36:00", "app_entry": 530.83},
    {"id": 34, "strategy": "BANKNIFTY_GAMMA_WALL_BREAKOUT_PE", "symbol": "BANKNIFTY56000PE", "time": "2026-09-16 13:30:00", "app_entry": 518.07},
    {"id": 35, "strategy": "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "symbol": "BANKNIFTY55900CE", "time": "2026-09-16 14:20:00", "app_entry": 811.81},
]

def main():
    cfg = Config.load()
    client = FyersAPIClient(
        client_id=cfg.fyers_client_id,
        secret_key=cfg.fyers_secret_key,
        fy_id=cfg.fyers_fy_id,
        user_pin=cfg.fyers_user_pin,
        totp_secret=cfg.fyers_totp_secret,
        redirect_uri=cfg.fyers_redirect_uri,
    )
    token = client.authenticate_with_totp()
    if not token:
        print("Failed to authenticate with Fyers")
        return

    print("Authenticated successfully with Fyers API")
    results = []
    candle_cache = {}

    for t in TRADES:
        # Determine candidate symbols for the underlying expiry
        raw_sym = to_fyers_symbol(t["symbol"], for_date=date(2026, 9, 16))
        candidate_syms = [raw_sym]

        # For BankNifty / Sensex / Nifty also try weekly/monthly variants if symbol format differs
        if "BANKNIFTY" in t["symbol"]:
            # e.g., NSE:BANKNIFTY26SEP56000PE or NSE:BANKNIFTY2691656000PE
            candidate_syms.append(raw_sym.replace("26SEP", "26916"))
            candidate_syms.append(raw_sym.replace("26916", "26SEP"))
            candidate_syms.append(raw_sym.replace("26SEP", "26930"))
        elif "SENSEX" in t["symbol"]:
            candidate_syms.append(raw_sym.replace("26917", "26918"))
            candidate_syms.append(raw_sym.replace("26918", "26917"))
        elif "NIFTY" in t["symbol"]:
            candidate_syms.append(raw_sym.replace("26922", "26917"))
            candidate_syms.append(raw_sym.replace("26917", "26922"))

        df = None
        matched_sym = None
        for sym in candidate_syms:
            if sym not in candle_cache:
                try:
                    cdf = client.get_historical_data(symbol=sym, resolution="1", days=2)
                    candle_cache[sym] = cdf
                except Exception as e:
                    candle_cache[sym] = None
            if candle_cache.get(sym) is not None and not candle_cache[sym].empty:
                df = candle_cache[sym]
                matched_sym = sym
                break

        dt_entry = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
        fyers_open, fyers_high, fyers_low, fyers_close = None, None, None, None
        
        if df is not None and not df.empty:
            match = df[df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M") == dt_entry.strftime("%Y-%m-%d %H:%M")]
            if not match.empty:
                row = match.iloc[0]
                fyers_open = float(row["Open"])
                fyers_high = float(row["High"])
                fyers_low = float(row["Low"])
                fyers_close = float(row["Close"])

        results.append({
            "id": t["id"],
            "strategy": t["strategy"],
            "symbol": t["symbol"],
            "fyers_symbol": matched_sym or raw_sym,
            "entry_time": t["time"],
            "app_entry": t["app_entry"],
            "fyers_open": fyers_open,
            "fyers_high": fyers_high,
            "fyers_low": fyers_low,
            "fyers_close": fyers_close,
        })

    with open(PROJECT_ROOT / "scratch" / "trade_comparison_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("SUCCESS")

if __name__ == "__main__":
    main()
