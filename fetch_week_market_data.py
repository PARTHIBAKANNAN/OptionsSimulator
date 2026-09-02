"""
Fetch market data for this week's trading (Aug 31 - Sep 2, 2026)
for NIFTY, SENSEX, and BANKNIFTY to analyze vs paper trading performance.

Usage:
    python fetch_week_market_data.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.fyers.api_client import FyersAPIClient

# Index symbols on Fyers
INDICES = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
}

# Output directory
DATA_DIR = PROJECT_ROOT / "data" / "market_analysis"
DATA_DIR.mkdir(parents=True, exist_ok=True)

IST = __import__("zoneinfo").ZoneInfo("Asia/Kolkata")


def fetch_index_data(client: FyersAPIClient, index_name: str, symbol: str, days: int = 5) -> pd.DataFrame:
    """Fetch 1-minute candles for an index."""
    print(f"  Fetching {days} days of 1-min {index_name} candles...")
    try:
        df = client.get_historical_data(symbol, resolution="1", days=days)
        print(f"    [OK] Got {len(df):,} candles: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        return df
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def analyze_market_data(df: pd.DataFrame, index_name: str) -> dict:
    """Analyze market data for the week."""
    if df is None or len(df) == 0:
        return None

    # Convert timestamp if needed
    if isinstance(df['Timestamp'].iloc[0], str):
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Group by date
    df['Date'] = df['Timestamp'].dt.date

    daily_stats = []
    for date in sorted(df['Date'].unique()):
        day_data = df[df['Date'] == date]

        stats = {
            'Date': date,
            'Open': day_data['Open'].iloc[0],
            'High': day_data['High'].max(),
            'Low': day_data['Low'].min(),
            'Close': day_data['Close'].iloc[-1],
            'Volume': day_data['Volume'].sum(),
            'Trades': len(day_data),
            'Change': ((day_data['Close'].iloc[-1] - day_data['Open'].iloc[0]) / day_data['Open'].iloc[0] * 100),
            'Direction': 'UP' if day_data['Close'].iloc[-1] > day_data['Open'].iloc[0] else 'DOWN',
        }
        daily_stats.append(stats)

    return pd.DataFrame(daily_stats)


def main():
    print("\n" + "=" * 80)
    print("MARKET DATA FETCHER — Week of Aug 31 - Sep 2, 2026")
    print("=" * 80)

    # Load config and authenticate
    print("\n1. Authenticating with Fyers...")
    config = Config.load()
    config.validate(require_fyers=True, require_telegram=False)

    client = FyersAPIClient(
        client_id=config.fyers_client_id,
        secret_key=config.fyers_secret_key,
        fy_id=config.fyers_fy_id,
        user_pin=config.fyers_user_pin,
        totp_secret=config.fyers_totp_secret,
        redirect_uri=config.fyers_redirect_uri,
    )

    print("   Authenticating with TOTP...")
    try:
        client.authenticate_with_totp()
        print("   [OK] Authenticated successfully")
    except Exception as e:
        print(f"   [ERROR] Authentication failed: {e}")
        return

    # Fetch data for each index
    print("\n2. Fetching market data for 3 indices (5 days)...")
    market_data = {}
    daily_summaries = {}

    for index_name, symbol in INDICES.items():
        print(f"\n   {index_name}:")
        df = fetch_index_data(client, index_name, symbol, days=5)
        market_data[index_name] = df

        if df is not None:
            # Save to CSV
            output_file = DATA_DIR / f"{index_name}_week_candles.csv"
            df.to_csv(output_file, index=False)
            print(f"    [OK] Saved to {output_file.name}")

            # Analyze
            summary = analyze_market_data(df, index_name)
            daily_summaries[index_name] = summary

    # Generate analysis report
    print("\n3. Generating analysis report...")
    report_file = DATA_DIR / "MARKET_ANALYSIS_REPORT.md"

    with open(report_file, 'w') as f:
        f.write("# Market Data Analysis — Week of Aug 31 - Sep 2, 2026\n\n")
        f.write("## Daily Market Summary\n\n")

        for index_name, summary in daily_summaries.items():
            if summary is None:
                continue

            f.write(f"### {index_name}\n\n")
            f.write("| Date | Open | High | Low | Close | Change % | Direction | Volume | Candles |\n")
            f.write("|------|------|------|-----|-------|----------|-----------|--------|----------|\n")

            for _, row in summary.iterrows():
                f.write(
                    f"| {row['Date']} | {row['Open']:.2f} | {row['High']:.2f} | "
                    f"{row['Low']:.2f} | {row['Close']:.2f} | {row['Change']:+.2f}% | "
                    f"{row['Direction']} | {row['Volume']:,.0f} | {row['Trades']} |\n"
                )
            f.write("\n")

        f.write("\n## Interpretation\n\n")

        # Analyze overall market direction
        bullish_days = sum(1 for s in daily_summaries.values() if s is not None and (s['Direction'] == 'UP').sum() > 0)
        bearish_days = sum(1 for s in daily_summaries.values() if s is not None and (s['Direction'] == 'DOWN').sum() > 0)

        f.write(f"**Week Overview**: {bullish_days} bullish index-days, {bearish_days} bearish index-days\n\n")
        f.write("**Analysis**: \n\n")

        for index_name, summary in daily_summaries.items():
            if summary is None:
                continue

            f.write(f"**{index_name}**:\n")
            for _, row in summary.iterrows():
                direction_mark = "[UP]" if row['Direction'] == 'UP' else "[DOWN]"
                f.write(f"- {row['Date']}: {direction_mark} {row['Change']:+.2f}% | {row['Open']:.0f} to {row['Close']:.0f}\n")
            f.write("\n")

    print(f"   [OK] Report saved to {report_file.name}")

    # Print summary to console
    print("\n4. Quick Summary:\n")
    for index_name, summary in daily_summaries.items():
        if summary is not None:
            print(f"\n{index_name}:")
            print(summary.to_string(index=False))

    print("\n" + "=" * 80)
    print("[SUCCESS] Market data fetched and analyzed successfully!")
    print(f"[OK] Output saved to: {DATA_DIR}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
