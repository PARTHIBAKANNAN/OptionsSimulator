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

# Let's check SENSEX 74300PE at 12:04!
for sym in [
    'BSE:SENSEX2691774300PE', 'BSE:SENSEX2691774300CE', 
    'BSE:SENSEX2691774200PE', 'BSE:SENSEX2691774400PE',
    'NSE:NIFTY2692223400PE', 'NSE:NIFTY2692223300PE',
    'NSE:NIFTY2692223350CE'
]:
    res = client.fyers.history(data={
        "symbol": sym, "resolution": "1", "date_format": "0",
        "range_from": str(start_ts), "range_to": str(end_ts), "cont_flag": "1"
    })
    candles = res.get("candles", [])
    for c in candles:
        dt = datetime.fromtimestamp(c[0], tz=IST)
        if dt.minute == 4:
            print(f"{sym} at 12:04 | O: {c[1]}, H: {c[2]}, L: {c[3]}, C: {c[4]}")
            if any(abs(x - 171.85) < 0.5 or abs(x - 161.85) < 0.5 for x in [c[1], c[2], c[3], c[4]]):
                print(f"--> MATCH FOUND FOR {sym}!")
