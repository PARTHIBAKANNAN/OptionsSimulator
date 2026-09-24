import sys
import json
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fyers_apiv3 import fyersModel
from src.config import Config

def main():
    cfg = Config.load()
    with open(PROJECT_ROOT / "fyers_token_cache.json", "r") as f:
        token = json.load(f)["access_token"]
        
    fyers = fyersModel.FyersModel(client_id=cfg.fyers_client_id, is_async=False, token=token, log_path=str(PROJECT_ROOT / "logs"))
    
    # Load all trades
    trades_path = PROJECT_ROOT / "data" / "market_analysis" / "trades_sept01_to_date.json"
    with open(trades_path, "r") as f:
        trades = json.load(f)
        
    print(f"Loaded {len(trades)} trades from {trades_path}")
    
    # Extract unique (symbol, trade_date)
    unique_contracts = set()
    for t in trades:
        unique_contracts.add(t["symbol"])
        
    print(f"Unique contracts to download: {len(unique_contracts)}")
    
    # Candidate date codes for Sept 2026
    date_codes = ["26SEP", "26922", "26917", "26918", "26911", "26910", "26904", "26903", "26925", "26924"]
    
    all_candles = {}
    end_epoch = int(time.time())
    start_epoch = end_epoch - 25 * 86400  # last 25 days covering Sept 1 to date
    
    for i, contract in enumerate(sorted(unique_contracts), 1):
        print(f"\n[{i:2d}/{len(unique_contracts)}] Resolving contract {contract}...")
        
        # Parse index, strike, option type
        # e.g. BANKNIFTY56000PE -> BANKNIFTY, 56000, PE
        if "BANKNIFTY" in contract:
            exchange = "NSE"
            idx_name = "BANKNIFTY"
            rem = contract.replace("BANKNIFTY", "")
        elif "SENSEX" in contract:
            exchange = "BSE"
            idx_name = "SENSEX"
            rem = contract.replace("SENSEX", "")
        elif "NIFTY" in contract:
            exchange = "NSE"
            idx_name = "NIFTY"
            rem = contract.replace("NIFTY", "")
        else:
            continue
            
        opt_type = rem[-2:]  # CE or PE
        strike = rem[:-2]
        
        # Try candidate formats
        matched = False
        for dc in date_codes:
            candidate_sym = f"{exchange}:{idx_name}{dc}{strike}{opt_type}"
            try:
                res = fyers.history(data={
                    "symbol": candidate_sym,
                    "resolution": "1",
                    "date_format": "0",
                    "range_from": str(start_epoch),
                    "range_to": str(end_epoch),
                    "cont_flag": "1"
                })
                time.sleep(0.5)  # rate limit protection
                
                if res.get("s") == "ok" and len(res.get("candles", [])) > 0:
                    candles = res.get("candles", [])
                    print(f"  --> FOUND: {candidate_sym} ({len(candles)} 1m candles)")
                    
                    formatted = []
                    for c in candles:
                        dt = datetime.fromtimestamp(c[0])
                        formatted.append({
                            "timestamp": dt.isoformat(),
                            "epoch": c[0],
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": int(c[5]) if len(c) > 5 else 0
                        })
                    all_candles[contract] = {
                        "fyers_symbol": candidate_sym,
                        "candle_count": len(formatted),
                        "candles": formatted
                    }
                    matched = True
                    break
            except Exception as e:
                time.sleep(0.5)
                continue
                
        if not matched:
            print(f"  --> NOT FOUND for any date code on {contract}")
            
    print(f"\n=======================================================")
    print(f"DOWNLOAD SUMMARY: {len(all_candles)} / {len(unique_contracts)} contracts successfully downloaded!")
    print(f"=======================================================")
    
    out_file = PROJECT_ROOT / "data" / "historical" / "all_option_contracts_candles_sept01_to_date.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({
            "status": "ok",
            "total_contracts": len(all_candles),
            "data": all_candles
        }, f, indent=2)
        
    print(f"Saved complete real 1-minute historical candles to {out_file}")

if __name__ == "__main__":
    main()
