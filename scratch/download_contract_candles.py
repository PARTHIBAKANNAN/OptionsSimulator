import urllib.request
import json
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# List of distinct option symbols from today's trades
SYMBOLS = [
    "BSE:SENSEX2691774900PE",
    "BSE:SENSEX2691774400CE",
    "BSE:SENSEX2691774300PE",
    "BSE:SENSEX2691774800PE",
    "NSE:NIFTY2692223250PE",
    "NSE:BANKNIFTY26SEP56000PE",
    "NSE:NIFTY2692223200CE",
    "NSE:NIFTY2692223300PE",
    "BSE:SENSEX2691774300CE",
    "BSE:SENSEX2691774200PE",
    "NSE:NIFTY2692223200PE",
    "NSE:BANKNIFTY26SEP55900CE",
    "BSE:SENSEX2691773700CE",
]

URL = "https://trading-dashboard-1.duckdns.org/options-simulator/api/public/fetch-contract-candles"

def main():
    print(f"Requesting 1-minute historical candles for {len(SYMBOLS)} contracts from server...")
    payload = json.dumps({"symbols": SYMBOLS, "days": 2}).encode("utf-8")
    req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
    
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                data = json.loads(res.read().decode("utf-8"))
                output_file = PROJECT_ROOT / "data" / "historical" / "option_contracts_candles_20260916.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"Saved {len(data.get('candles', {}))} contract candle series to {output_file}")
                return
        except Exception as e:
            print(f"Attempt {attempt} failed: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
