import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
import json
import pytz
import yfinance as yf
from src.data_manager import Candle
from src.db.sqlite_candle_cache import save_candles, load_recent_candles

IST = pytz.timezone("Asia/Kolkata")
LAST_MARKET_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "last_market_state.json"

TICKER_MAP = {
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    "BANKNIFTY": "^NSEBANK",
}

PREV_CLOSE = {
    "NIFTY": 22520.45,
    "SENSEX": 72472.33,
    "BANKNIFTY": 55256.65,
}

def backfill():
    print("Backfilling today's (Oct 12, 2026) 1-minute spot candles...")
    summary = {}

    for underlying, ticker in TICKER_MAP.items():
        print(f"Downloading {underlying} ({ticker}) for 2026-10-12...")
        try:
            df = yf.download(ticker, start="2026-10-12", interval="1m", progress=False)
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

            # Filter market hours 09:15 to 15:30
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

            first_c = candles[0]
            last_c = candles[-1]
            day_high = max(c.high for c in candles)
            day_low = min(c.low for c in candles)
            p_close = PREV_CLOSE.get(underlying, first_c.open)
            diff = round(last_c.close - p_close, 2)
            pct = round((diff / p_close) * 100, 2)

            summary[underlying] = {
                "close": last_c.close,
                "prev_close": p_close,
                "change": diff,
                "change_pct": pct,
                "high": day_high,
                "low": day_low,
            }
            print(f"{underlying}: Close={last_c.close}, PrevClose={p_close}, Change={diff} ({pct}%)")

    # Update last_market_state.json so after-hours display shows today's exact values
    if summary:
        market_state = {}
        if LAST_MARKET_STATE_PATH.exists():
            try:
                market_state = json.loads(LAST_MARKET_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

        if "NIFTY" in summary:
            s = summary["NIFTY"]
            market_state["nifty_price"] = s["close"]
            market_state["nifty_prev_close"] = s["prev_close"]
            market_state["nifty_change"] = s["change"]
            market_state["nifty_change_pct"] = s["change_pct"]
            market_state["nifty_high"] = s["high"]
            market_state["nifty_low"] = s["low"]

        if "SENSEX" in summary:
            s = summary["SENSEX"]
            market_state["sensex_price"] = s["close"]
            market_state["sensex_prev_close"] = s["prev_close"]
            market_state["sensex_change"] = s["change"]
            market_state["sensex_change_pct"] = s["change_pct"]
            market_state["sensex_high"] = s["high"]
            market_state["sensex_low"] = s["low"]

        if "BANKNIFTY" in summary:
            s = summary["BANKNIFTY"]
            market_state["banknifty_price"] = s["close"]
            market_state["banknifty_prev_close"] = s["prev_close"]
            market_state["banknifty_change"] = s["change"]
            market_state["banknifty_change_pct"] = s["change_pct"]
            market_state["banknifty_high"] = s["high"]
            market_state["banknifty_low"] = s["low"]

        market_state["last_updated"] = datetime.now(IST).isoformat()

        LAST_MARKET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LAST_MARKET_STATE_PATH.write_text(json.dumps(market_state, indent=2), encoding="utf-8")
        print(f"Updated {LAST_MARKET_STATE_PATH} successfully:")
        print(json.dumps(market_state, indent=2))

if __name__ == "__main__":
    backfill()
