import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
import pytz
import yfinance as yf
from src.data_manager import Candle
from src.db.sqlite_candle_cache import save_candles, load_recent_candles

IST = pytz.timezone("Asia/Kolkata")

TICKER_MAP = {
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
}

def backfill():
    print("Fetching missing candles from Oct 07 to Oct 09...")
    for underlying, ticker in TICKER_MAP.items():
        print(f"Downloading {underlying} ({ticker})...")
        df = yf.download(ticker, start="2026-10-07", end="2026-10-10", interval="1m", progress=False)
        if df.empty:
            print(f"No data returned for {ticker}")
            continue

        candles = []
        for ts, row in df.iterrows():
            if ts.tzinfo is None:
                ts = pytz.utc.localize(ts).astimezone(IST)
            else:
                ts = ts.astimezone(IST)

            # Filter market hours 09:15 to 15:30
            if ts.time() < datetime.strptime("09:15", "%H:%M").time() or ts.time() > datetime.strptime("15:30", "%H:%M").time():
                continue

            open_val = float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"])
            high_val = float(row["High"].iloc[0] if hasattr(row["High"], "iloc") else row["High"])
            low_val = float(row["Low"].iloc[0] if hasattr(row["Low"], "iloc") else row["Low"])
            close_val = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
            vol_val = int(row["Volume"].iloc[0] if hasattr(row["Volume"], "iloc") else (row["Volume"] or 0))

            candle = Candle(
                timestamp=ts,
                open=round(open_val, 2),
                high=round(high_val, 2),
                low=round(low_val, 2),
                close=round(close_val, 2),
                volume=vol_val,
                delta=0.0
            )
            candles.append(candle)

        print(f"Saving {len(candles)} candles for {underlying}...")
        save_candles(underlying, candles)

        loaded = load_recent_candles(underlying, days=14)
        print(f"Total recent candles in cache for {underlying}: {len(loaded)}. Latest: {loaded[-1].timestamp} Close: {loaded[-1].close}")

if __name__ == "__main__":
    backfill()
