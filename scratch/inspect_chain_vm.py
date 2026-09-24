import json
import os
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

with open('/home/ubuntu/optionssimulator-app/fyers_token_cache.json') as f:
    token_cache = json.load(f)

access_token = token_cache['access_token']

load_dotenv('/home/ubuntu/optionssimulator-app/backend/.env')
client_id = os.getenv("FYERS_CLIENT_ID", "")

fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, is_async=False, log_path="")

for name, sym in [("SENSEX", "BSE:SENSEX-INDEX"), ("NIFTY", "NSE:NIFTY50-INDEX"), ("BANKNIFTY", "NSE:NIFTYBANK-INDEX")]:
    print(f"\n================ {name} ({sym}) ================")
    res = fyers.optionchain(data={"symbol": sym, "strikecount": "5", "timestamp": ""})
    data = res.get("data", {})
    chain = data.get("optionsChain", [])
    print(f"Total options rows: {len(chain)}")
    
    # Collect all unique symbols and expiry patterns
    all_syms = [r.get("symbol") for r in chain if r.get("symbol")]
    print("First 10 symbols:")
    for s in all_syms[:10]:
        print("  ", s)
    
    # Check what strikes match 74600 / 23650 / 56600
    target_strikes = [74600, 23650, 56600]
    matched = [r for r in chain if r.get("strike_price") in target_strikes]
    print(f"Matched target strikes:")
    for m in matched:
        print("  ", m.get("symbol"), m.get("strike_price"), m.get("option_type"), "ltp:", m.get("ltp"))
