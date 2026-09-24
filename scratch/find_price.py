import sys, time
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

# Let's check history of NSE:NIFTY2692223350PE today
sym = "NSE:NIFTY2692223350PE"
today_str = datetime.now(IST).strftime("%Y-%m-%d")
# Range from 09:15 to 12:30 today
start_ts = int(datetime.now(IST).replace(hour=9, minute=15, second=0).timestamp())
end_ts = int(datetime.now(IST).timestamp())

res = client.fyers.history(data={
    "symbol": sym, "resolution": "1", "date_format": "0",
    "range_from": str(start_ts), "range_to": str(end_ts), "cont_flag": "1"
})

candles = res.get("candles", [])
print(f"Total candles for {sym}: {len(candles)}")
for c in candles:
    dt = datetime.fromtimestamp(c[0], tz=IST)
    if dt.hour == 12 and dt.minute in range(0, 10):
        print(f"{dt.strftime('%H:%M')} | O: {c[1]}, H: {c[2]}, L: {c[3]}, C: {c[4]}, V: {c[5]}")

# Also check NSE:NIFTY26SEP23350PE
sym_m = "NSE:NIFTY26SEP23350PE"
res_m = client.fyers.history(data={
    "symbol": sym_m, "resolution": "1", "date_format": "0",
    "range_from": str(start_ts), "range_to": str(end_ts), "cont_flag": "1"
})
candles_m = res_m.get("candles", [])
print(f"\nTotal candles for {sym_m}: {len(candles_m)}")
for c in candles_m:
    dt = datetime.fromtimestamp(c[0], tz=IST)
    if dt.hour == 12 and dt.minute in range(0, 10):
        print(f"{dt.strftime('%H:%M')} | O: {c[1]}, H: {c[2]}, L: {c[3]}, C: {c[4]}, V: {c[5]}")
