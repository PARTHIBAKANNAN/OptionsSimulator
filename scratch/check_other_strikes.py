import sys
sys.path.insert(0, '/home/ubuntu/optionssimulator-app')
from src.config import Config
from src.fyers.api_client import FyersAPIClient
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
cfg = Config.load()
client = FyersAPIClient(
    client_id=cfg.fyers_client_id, secret_key=cfg.fyers_secret_key,
    fy_id=cfg.fyers_fy_id, user_pin=cfg.fyers_user_pin,
    totp_secret=cfg.fyers_totp_secret, redirect_uri=cfg.fyers_redirect_uri
)
client.authenticate_with_totp()

start_ts = int(datetime.now(IST).replace(hour=12, minute=0, second=0).timestamp())
end_ts = int(datetime.now(IST).replace(hour=12, minute=10, second=0).timestamp())

# Check NIFTY 23450 PE and 23500 PE
for sym in ['NSE:NIFTY2692223450PE', 'NSE:NIFTY2692223500PE']:
    res = client.fyers.history(data={
        "symbol": sym, "resolution": "1", "date_format": "0",
        "range_from": str(start_ts), "range_to": str(end_ts), "cont_flag": "1"
    })
    candles = res.get("candles", [])
    for c in candles:
        dt = datetime.fromtimestamp(c[0], tz=IST)
        if dt.minute == 4:
            print(f"{sym} at 12:04 | O: {c[1]}, H: {c[2]}, L: {c[3]}, C: {c[4]}")
