import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRADES = [
    {"id": 1, "strategy": "SENSEX_ORB_BEARISH_5M_ITM", "symbol": "SENSEX74900PE", "fyers_sym": "BSE:SENSEX2691774900PE", "time": "2026-09-16 09:36:00", "app_entry": 673.87},
    {"id": 2, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "SENSEX74900PE", "fyers_sym": "BSE:SENSEX2691774900PE", "time": "2026-09-16 09:40:00", "app_entry": 665.67},
    {"id": 3, "strategy": "SENSEX_OI_SHORT_SQUEEZE_CE", "symbol": "SENSEX74400CE", "fyers_sym": "BSE:SENSEX2691774400CE", "time": "2026-09-16 09:25:00", "app_entry": 318.57},
    {"id": 4, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "SENSEX74300PE", "fyers_sym": "BSE:SENSEX2691774300PE", "time": "2026-09-16 09:25:00", "app_entry": 295.65},
    {"id": 5, "strategy": "SENSEX_ORB_BEARISH_1M_ATM", "symbol": "SENSEX74300PE", "fyers_sym": "BSE:SENSEX2691774300PE", "time": "2026-09-16 09:36:00", "app_entry": 305.41},
    {"id": 6, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "SENSEX74800PE", "fyers_sym": "BSE:SENSEX2691774800PE", "time": "2026-09-16 10:26:00", "app_entry": 645.19},
    {"id": 7, "strategy": "SENSEX_RESISTANCE_REJECTION_5M_ITM", "symbol": "SENSEX74800PE", "fyers_sym": "BSE:SENSEX2691774800PE", "time": "2026-09-16 10:36:00", "app_entry": 658.21},
    {"id": 8, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "NIFTY23250PE", "fyers_sym": "NSE:NIFTY2692223250PE", "time": "2026-09-16 09:25:00", "app_entry": 152.20},
    {"id": 9, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 09:25:00", "app_entry": 506.41},
    {"id": 10, "strategy": "NIFTY_VWAP_POC_PULLBACK_CE", "symbol": "NIFTY23200CE", "fyers_sym": "NSE:NIFTY2692223200CE", "time": "2026-09-16 09:26:00", "app_entry": 199.75},
    {"id": 11, "strategy": "BANKNIFTY_ORB_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 09:39:00", "app_entry": 520.87},
    {"id": 12, "strategy": "NIFTY_ORB_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "fyers_sym": "NSE:NIFTY2692223300PE", "time": "2026-09-16 09:39:00", "app_entry": 180.38},
    {"id": 13, "strategy": "BANKNIFTY_ORB_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 09:39:00", "app_entry": 520.87},
    {"id": 14, "strategy": "SENSEX_RESISTANCE_REJECTION_5M_ITM", "symbol": "SENSEX74800PE", "fyers_sym": "BSE:SENSEX2691774800PE", "time": "2026-09-16 11:01:00", "app_entry": 647.60},
    {"id": 15, "strategy": "SENSEX_OI_LONG_UNWINDING_PE", "symbol": "SENSEX74300PE", "fyers_sym": "BSE:SENSEX2691774300PE", "time": "2026-09-16 10:35:00", "app_entry": 347.40},
    {"id": 16, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 09:46:00", "app_entry": 510.86},
    {"id": 17, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "fyers_sym": "NSE:NIFTY2692223300PE", "time": "2026-09-16 09:46:00", "app_entry": 178.48},
    {"id": 18, "strategy": "SENSEX_OI_SHORT_SQUEEZE_CE", "symbol": "SENSEX74300CE", "fyers_sym": "BSE:SENSEX2691774300CE", "time": "2026-09-16 09:55:00", "app_entry": 354.95},
    {"id": 19, "strategy": "SENSEX_ORB_BEARISH_1M_ATM", "symbol": "SENSEX74200PE", "fyers_sym": "BSE:SENSEX2691774200PE", "time": "2026-09-16 11:27:00", "app_entry": 342.59},
    {"id": 20, "strategy": "SENSEX_ORB_BEARISH_5M_ITM", "symbol": "SENSEX74800PE", "fyers_sym": "BSE:SENSEX2691774800PE", "time": "2026-09-16 11:27:00", "app_entry": 716.42},
    {"id": 21, "strategy": "SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "SENSEX74200PE", "fyers_sym": "BSE:SENSEX2691774200PE", "time": "2026-09-16 11:31:00", "app_entry": 333.73},
    {"id": 22, "strategy": "SENSEX_OI_LONG_UNWINDING_PE", "symbol": "SENSEX74200PE", "fyers_sym": "BSE:SENSEX2691774200PE", "time": "2026-09-16 11:52:00", "app_entry": 333.23},
    {"id": 23, "strategy": "BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 10:21:00", "app_entry": 522.62},
    {"id": 24, "strategy": "NIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "NIFTY23300PE", "fyers_sym": "NSE:NIFTY2692223300PE", "time": "2026-09-16 10:25:00", "app_entry": 190.29},
    {"id": 25, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "NIFTY23200PE", "fyers_sym": "NSE:NIFTY2692223200PE", "time": "2026-09-16 11:31:00", "app_entry": 157.41},
    {"id": 26, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 11:31:00", "app_entry": 535.18},
    {"id": 27, "strategy": "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "symbol": "BANKNIFTY55900CE", "fyers_sym": "NSE:BANKNIFTY26SEP55900CE", "time": "2026-09-16 11:39:00", "app_entry": 822.97},
    {"id": 28, "strategy": "SENSEX_BB_SQUEEZE_EXPLOSION_CE", "symbol": "SENSEX73700CE", "fyers_sym": "BSE:SENSEX2691773700CE", "time": "2026-09-16 13:46:00", "app_entry": 684.13},
    {"id": 29, "strategy": "NIFTY_ORB_BEARISH_5M_ITM", "symbol": "NIFTY23300PE", "fyers_sym": "NSE:NIFTY2692223300PE", "time": "2026-09-16 12:23:00", "app_entry": 197.75},
    {"id": 30, "strategy": "BANKNIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 12:23:00", "app_entry": 528.83},
    {"id": 31, "strategy": "NIFTY_RESISTANCE_REJECTION_5M_ITM", "symbol": "NIFTY23250PE", "fyers_sym": "NSE:NIFTY2692223250PE", "time": "2026-09-16 12:28:00", "app_entry": 177.73},
    {"id": 32, "strategy": "NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "NIFTY23250PE", "fyers_sym": "NSE:NIFTY2692223250PE", "time": "2026-09-16 12:36:00", "app_entry": 175.83},
    {"id": 33, "strategy": "BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 12:36:00", "app_entry": 530.83},
    {"id": 34, "strategy": "BANKNIFTY_GAMMA_WALL_BREAKOUT_PE", "symbol": "BANKNIFTY56000PE", "fyers_sym": "NSE:BANKNIFTY26SEP56000PE", "time": "2026-09-16 13:30:00", "app_entry": 518.07},
    {"id": 35, "strategy": "BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE", "symbol": "BANKNIFTY55900CE", "fyers_sym": "NSE:BANKNIFTY26SEP55900CE", "time": "2026-09-16 14:20:00", "app_entry": 811.81},
]

def main():
    candles_file = PROJECT_ROOT / "data" / "historical" / "option_contracts_candles_20260916.json"
    with open(candles_file, "r") as f:
        data = json.load(f)
    
    candles_by_sym = data.get("candles", {})
    
    comparison = []
    for t in TRADES:
        sym = t["fyers_sym"]
        sym_candles = candles_by_sym.get(sym, [])
        
        # find matching candle
        entry_dt = datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S")
        entry_min_str = entry_dt.strftime("%Y-%m-%dT%H:%M")
        
        matched_bar = None
        for c in sym_candles:
            if c["timestamp"].startswith(entry_min_str):
                matched_bar = c
                break
                
        open_p = matched_bar["open"] if matched_bar else None
        high_p = matched_bar["high"] if matched_bar else None
        low_p = matched_bar["low"] if matched_bar else None
        close_p = matched_bar["close"] if matched_bar else None
        
        # diff against Fyers Open / Close
        diff_open = round(t["app_entry"] - open_p, 2) if open_p is not None else None
        diff_close = round(t["app_entry"] - close_p, 2) if close_p is not None else None

        comparison.append({
            "id": t["id"],
            "strategy": t["strategy"],
            "symbol": t["symbol"],
            "time": t["time"].split(" ")[1],
            "app_entry": t["app_entry"],
            "fyers_open": open_p,
            "fyers_high": high_p,
            "fyers_low": low_p,
            "fyers_close": close_p,
            "diff_vs_open": diff_open,
            "diff_vs_close": diff_close,
        })
        
    print(json.dumps(comparison, indent=2))

if __name__ == "__main__":
    main()
