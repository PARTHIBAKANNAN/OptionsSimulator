"""One-off utility: logs into Fyers via the automated TOTP flow and pulls N days
of 1-minute NIFTY candles into data/historical/nifty_90days.csv for the backtester."""
import sys
from pathlib import Path

from src.config import Config
from src.fyers.api_client import FyersAPIClient

NIFTY_SYMBOL = "NSE:NIFTY50-INDEX"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "historical" / "nifty_90days.csv"


def main(days: int = 90) -> None:
    config = Config.load()
    config.validate(require_fyers=True, require_telegram=False)

    client = FyersAPIClient(
        client_id=config.fyers_client_id, secret_key=config.fyers_secret_key,
        fy_id=config.fyers_fy_id, user_pin=config.fyers_user_pin,
        totp_secret=config.fyers_totp_secret, redirect_uri=config.fyers_redirect_uri,
    )

    print("Authenticating with Fyers (TOTP)...")
    client.authenticate_with_totp()
    print("Authenticated.")

    print(f"Fetching {days} days of 1-min NIFTY candles...")
    df = client.get_historical_data(NIFTY_SYMBOL, resolution="1", days=days)
    print(f"Got {len(df):,} candles: {df['Timestamp'].min()} -> {df['Timestamp'].max()}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    days_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    main(days_arg)
