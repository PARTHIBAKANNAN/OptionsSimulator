import sys
import json
import time
from pathlib import Path
from datetime import datetime, date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fyers_apiv3 import fyersModel
from src.config import Config
from src.utils.options_pricing import to_fyers_symbol

AUTH_CODE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBfaWQiOiI0RjZJMzdXS0VFIiwidXVpZCI6IjUyNTY5ZDg0MTYxOTRlYjY4NTZiZDg1MjcwZGEzNTVhIiwiaXBBZGRyIjoiIiwibm9uY2UiOiIiLCJzY29wZSI6IiIsImRpc3BsYXlfbmFtZSI6IkZBSzExNjk3Iiwib21zIjoiSzEiLCJoc21fa2V5IjoiMDc5OWZlNzQ5NDVjZDdkY2Q0M2EzYzFkN2M1MjM5MmQzMDNkMDYxOThmMDJiZjBkZTUxOTZkNmQiLCJpc0RkcGlFbmFibGVkIjoiTiIsImlzTXRmRW5hYmxlZCI6Ik4iLCJhdWQiOiJbXCJkOjFcIixcImQ6MlwiLFwieDowXCIsXCJ4OjFcIl0iLCJleHAiOjE3ODk5MzU5NTAsImlhdCI6MTc4OTkwNTk1MCwiaXNzIjoiYXBpLmxvZ2luLmZ5ZXJzLmluIiwibmJmIjoxNzg5OTA1OTUwLCJzdWIiOiJhdXRoX2NvZGUifQ.qHOWVtnmkYsDKBvZpE3tacFwsxe1Sii5DZAFjV70bCE"

def main():
    cfg = Config.load()
    print("Exchanging auth_code for access_token...")
    session = fyersModel.SessionModel(
        client_id=cfg.fyers_client_id,
        secret_key=cfg.fyers_secret_key,
        redirect_uri=cfg.fyers_redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    session.set_token(AUTH_CODE)
    auth_response = session.generate_token()
    access_token = auth_response.get("access_token")
    if not access_token:
        print("Failed to generate token:", auth_response)
        return
        
    print(f"Token generation SUCCESS! (Length: {len(access_token)})")
    
    # Cache token
    cache_path = PROJECT_ROOT / "fyers_token_cache.json"
    with open(cache_path, "w") as f:
        json.dump({"access_token": access_token, "created_at": datetime.now().isoformat()}, f, indent=2)
        
    # Init Fyers Model
    fyers = fyersModel.FyersModel(client_id=cfg.fyers_client_id, is_async=False, token=access_token, log_path=str(PROJECT_ROOT / "logs"))
    
    # Load all trades
    trades_path = PROJECT_ROOT / "data" / "market_analysis" / "trades_sept01_to_date.json"
    with open(trades_path, "r") as f:
        trades = json.load(f)
        
    print(f"Loaded {len(trades)} trades from {trades_path}")
    
    # Map symbols to download
    # We want 1-minute historical candles for all traded contracts on their active trading dates
    symbol_date_map = {}
    for t in trades:
        entry_dt = datetime.strptime(t["entry_time_ist"], "%Y-%m-%d %H:%M:%S")
        trade_date = entry_dt.date()
        simple_sym = t["symbol"]
        raw_sym = to_fyers_symbol(simple_sym, trade_date)
        
        if raw_sym not in symbol_date_map:
            symbol_date_map[raw_sym] = set()
        symbol_date_map[raw_sym].add(trade_date)
        
    print(f"Total unique raw symbols to fetch: {len(symbol_date_map)}")
    
    all_candles = {}
    success_count = 0
    fail_count = 0
    
    # Download 1-minute historical data for each symbol (last 25 days)
    for i, (sym, dates) in enumerate(symbol_date_map.items(), 1):
        print(f"[{i:2d}/{len(symbol_date_map)}] Fetching {sym}...", end="", flush=True)
        try:
            # Request history (up to 25 days)
            end_epoch = int(time.time())
            start_epoch = end_epoch - 25 * 86400
            
            res = fyers.history(data={
                "symbol": sym,
                "resolution": "1",
                "date_format": "0",
                "range_from": str(start_epoch),
                "range_to": str(end_epoch),
                "cont_flag": "1"
            })
            
            if res.get("s") == "ok" and res.get("candles"):
                candles = res.get("candles", [])
                # Convert to records
                formatted = []
                for c in candles:
                    # c = [epoch, open, high, low, close, volume]
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
                all_candles[sym] = formatted
                success_count += 1
                print(f" OK ({len(formatted)} candles)")
            else:
                print(f" EMPTY / ERROR: {res.get('message', res)}")
                fail_count += 1
        except Exception as e:
            print(f" EXCEPTION: {e}")
            fail_count += 1
            
        time.sleep(0.3)  # Fyers rate-limit safety
        
    print(f"\nFetch completed: {success_count} succeeded, {fail_count} failed")
    
    # Save output
    output_path = PROJECT_ROOT / "data" / "historical" / "all_option_contracts_candles_sept01_to_date.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "status": "ok",
            "total_symbols": len(all_candles),
            "candles": all_candles
        }, f, indent=2)
        
    print(f"Saved complete real 1-minute historical candle dataset to {output_path}")

if __name__ == "__main__":
    main()
