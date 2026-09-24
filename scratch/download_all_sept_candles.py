import sys
import json
import urllib.request
import time
from pathlib import Path
from datetime import datetime, date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.options_pricing import to_fyers_symbol

# Load all trades from Sept 1st to date
with open(PROJECT_ROOT / "data" / "market_analysis" / "trades_sept01_to_date.json", "r") as f:
    trades = json.load(f)

print(f"Total trades: {len(trades)}")

# Group trades by date and extract contract symbols
symbols_by_date = {}
all_raw_symbols = set()

for t in trades:
    entry_dt = datetime.strptime(t["entry_time_ist"], "%Y-%m-%d %H:%M:%S")
    trade_date = entry_dt.date()
    simple_sym = t["symbol"]
    
    # Resolve exact Fyers symbol on that date
    raw_sym = to_fyers_symbol(simple_sym, trade_date)
    all_raw_symbols.add(raw_sym)
    
    d_str = str(trade_date)
    if d_str not in symbols_by_date:
        symbols_by_date[d_str] = set()
    symbols_by_date[d_str].add(raw_sym)

print(f"Total unique raw Fyers symbols across Sept 1st to date: {len(all_raw_symbols)}")
for d, syms in sorted(symbols_by_date.items()):
    print(f"  {d}: {len(syms)} symbols -> {list(syms)[:3]}...")

URL = "https://trading-dashboard-1.duckdns.org/options-simulator/api/public/fetch-contract-candles"

def fetch_in_batches(symbols, days=22, batch_size=10):
    symbols_list = list(symbols)
    all_candles = {}
    errors = {}
    
    for i in range(0, len(symbols_list), batch_size):
        batch = symbols_list[i:i + batch_size]
        print(f"\nFetching batch {i//batch_size + 1}/{(len(symbols_list)-1)//batch_size + 1} ({len(batch)} symbols)...")
        payload = json.dumps({"symbols": batch, "days": days}).encode("utf-8")
        req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
        
        success = False
        for attempt in range(1, 4):
            try:
                with urllib.request.urlopen(req, timeout=60) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    batch_candles = data.get("candles", {})
                    for sym, val in batch_candles.items():
                        if isinstance(val, list):
                            print(f"  + {sym}: {len(val)} candles")
                            all_candles[sym] = val
                        else:
                            print(f"  - {sym}: Error/empty -> {val}")
                            errors[sym] = val
                    success = True
                    break
            except Exception as e:
                print(f"  Attempt {attempt} failed: {e}")
                time.sleep(3)
                
        if not success:
            print(f"Failed batch: {batch}")
            
    return all_candles, errors

if __name__ == "__main__":
    all_candles, errors = fetch_in_batches(all_raw_symbols, days=22, batch_size=10)
    
    out_file = PROJECT_ROOT / "data" / "historical" / "all_option_contracts_candles_sept01_to_date.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump({"status": "ok", "total_symbols": len(all_candles), "candles": all_candles, "errors": errors}, f, indent=2)
        
    print(f"\nSaved {len(all_candles)} contract series to {out_file}")
