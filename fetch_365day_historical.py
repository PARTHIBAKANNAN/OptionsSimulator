"""
Pulls 365 days of 1-minute historical candles for NIFTY, SENSEX, and BANKNIFTY from Fyers,
replacing the stale/uneven data/historical/*.csv files (previously: NIFTY 90 days, SENSEX 1 year,
BANKNIFTY missing entirely) with a consistent 365-day window for all three, so the re-run backtest
compares strategies on an equal footing.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.fyers.api_client import FyersAPIClient

INDICES = {
    "NIFTY": ("NSE:NIFTY50-INDEX", "nifty_365days.csv"),
    "SENSEX": ("BSE:SENSEX-INDEX", "sensex_365days.csv"),
    "BANKNIFTY": ("NSE:NIFTYBANK-INDEX", "banknifty_365days.csv"),
}
OUTPUT_DIR = PROJECT_ROOT / "data" / "historical"


def main():
    config = Config.load()
    config.validate(require_fyers=True, require_telegram=False)

    client = FyersAPIClient(
        client_id=config.fyers_client_id, secret_key=config.fyers_secret_key,
        fy_id=config.fyers_fy_id, user_pin=config.fyers_user_pin,
        totp_secret=config.fyers_totp_secret, redirect_uri=config.fyers_redirect_uri,
    )
    print("Authenticating with Fyers (TOTP)...")
    client.authenticate_with_totp()
    print("Authenticated.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for index_name, (symbol, filename) in INDICES.items():
        print(f"Fetching 365 days of 1-min {index_name} candles ({symbol})...")
        df = client.get_historical_data(symbol, resolution="1", days=365)
        print(f"  Got {len(df):,} candles: {df['Timestamp'].min()} -> {df['Timestamp'].max()}")
        out_path = OUTPUT_DIR / filename
        df.to_csv(out_path, index=False)
        print(f"  Saved to {out_path}\n")

    print("Done. All three indices now have a consistent 365-day 1-min history.")


if __name__ == "__main__":
    main()
