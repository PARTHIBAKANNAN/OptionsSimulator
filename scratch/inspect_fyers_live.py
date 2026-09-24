import os
import sys
import json
from datetime import datetime

sys.path.insert(0, "/home/ubuntu/optionssimulator-app")

from src.fyers.api_client import FyersAPIClient
from src.config import Config

def main():
    config = Config.load(env_path="/home/ubuntu/optionssimulator-app/.env")
    fyers = FyersAPIClient(
        client_id=config.fyers_client_id,
        secret_key=config.fyers_secret_key,
        fy_id=config.fyers_fy_id,
        user_pin=config.fyers_user_pin,
        totp_secret=config.fyers_totp_secret,
        redirect_uri=config.fyers_redirect_uri,
    )
    if not fyers.access_token:
        fyers.authenticate_with_totp()
    
    print("=== FYERS AUTH STATE ===")
    print("Access token present:", bool(fyers.access_token))
    
    for symbol, name in [("NSE:NIFTY50-INDEX", "NIFTY"), ("NSE:NIFTYBANK-INDEX", "BANKNIFTY"), ("BSE:SENSEX-INDEX", "SENSEX")]:
        print(f"\n=== {name} ({symbol}) OPTION CHAIN ===")
        try:
            chain = fyers.get_option_chain(symbol, strike_count=5)
            opts = chain.get("optionsChain", [])
            print(f"Total options returned: {len(opts)}")
            opts_sorted = sorted(opts, key=lambda x: (x.get("strike_price", 0), x.get("option_type", "")))
            for opt in opts_sorted:
                print(f"  Symbol: {opt.get('symbol'):<32} Strike: {opt.get('strike_price'):<8} Type: {opt.get('option_type'):<4} LTP: {opt.get('ltp'):<8} Bid: {opt.get('bid'):<8} Ask: {opt.get('ask'):<8}")
        except Exception as e:
            print(f"Error fetching option chain for {name}: {e}")

if __name__ == "__main__":
    main()
