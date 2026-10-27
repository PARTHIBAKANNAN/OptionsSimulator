import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
import json
import pytz
import yfinance as yf
from src.data_manager import Candle
from src.db.sqlite_candle_cache import save_candles

IST = pytz.timezone("Asia/Kolkata")
LAST_MARKET_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "last_market_state.json"

TICKER_MAP = {
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
}

def backfill_recent():
    print("Backfilling recent 5 days of 1-minute spot candles from exchange...")
    summary = {}

    for underlying, ticker in TICKER_MAP.items():
        print(f"Downloading {underlying} ({ticker}) period=5d, interval=1m...")
        try:
            df = yf.download(ticker, period="5d", interval="1m", progress=False)
        except Exception as e:
            print(f"Error downloading {ticker}: {e}")
            continue

        if df.empty:
            print(f"No data returned for {ticker}")
            continue

        candles = []
        for ts, row in df.iterrows():
            if ts.tzinfo is None:
                ts = pytz.utc.localize(ts).astimezone(IST)
            else:
                ts = ts.astimezone(IST)

            t = ts.time()
            if t < datetime.strptime("09:15", "%H:%M").time() or t > datetime.strptime("15:30", "%H:%M").time():
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

        if candles:
            print(f"Saving {len(candles)} candles into SQLite for {underlying}...")
            save_candles(underlying, candles)

            last_c = candles[-1]
            day_high = max(c.high for c in candles[-375:]) if len(candles) >= 375 else max(c.high for c in candles)
            day_low = min(c.low for c in candles[-375:]) if len(candles) >= 375 else min(c.low for c in candles)
            first_today = candles[-375].open if len(candles) >= 375 else candles[0].open
            diff = round(last_c.close - first_today, 2)
            pct = round((diff / first_today) * 100, 2)

            summary[underlying] = {
                "close": last_c.close,
                "prev_close": first_today,
                "change": diff,
                "change_pct": pct,
                "high": day_high,
                "low": day_low,
            }
            print(f"{underlying}: Close={last_c.close}, High={day_high}, Low={day_low}")

    if summary:
        market_state = {}
        if LAST_MARKET_STATE_PATH.exists():
            try:
                market_state = json.loads(LAST_MARKET_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

        for idx, key_prefix in [("NIFTY", "nifty"), ("SENSEX", "sensex"), ("BANKNIFTY", "banknifty")]:
            if idx in summary:
                s = summary[idx]
                market_state[f"{key_prefix}_price"] = s["close"]
                market_state[f"{key_prefix}_prev_close"] = s["prev_close"]
                market_state[f"{key_prefix}_change"] = s["change"]
                market_state[f"{key_prefix}_change_pct"] = s["change_pct"]
                market_state[f"{key_prefix}_high"] = s["high"]
                market_state[f"{key_prefix}_low"] = s["low"]

        market_state["last_updated"] = datetime.now(IST).isoformat()
        LAST_MARKET_STATE_PATH.write_text(json.dumps(market_state, indent=2), encoding="utf-8")
        print("Updated last_market_state.json successfully.")

if __name__ == "__main__":
    backfill_recent()
