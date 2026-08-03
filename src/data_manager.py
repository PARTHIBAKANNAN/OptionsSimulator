"""
Builds 1-minute NIFTY candles from ticks (or ingests historical candles for backtesting),
resamples to the timeframes each strategy needs, and exposes a single `data_state` dict
that strategies evaluate against.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from src.utils import indicators as ind


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass
class OptionQuote:
    symbol: str
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    oi: int = 0
    volume: int = 0
    updated_at: Optional[datetime] = None


class DataManager:
    def __init__(self, window_size: int = 3000):
        # ~7-8 trading days of 1-min candles (390 min/day) — enough to accumulate
        # 15+ hourly candles for RSI(14)/EMA(50)/MACD(26) on the 1H timeframe.
        self.window_size = window_size
        self.candles: list[Candle] = []
        self._current: Optional[Candle] = None
        self.option_chain: dict[str, OptionQuote] = {}

        # Multi-timeframe indicators only change when their bar actually closes — recomputing a
        # full resample of up to `window_size` candles on every single 1-min tick is both wasteful
        # (O(window_size) per tick) and repaints (an "RSI(1H)" that changes every minute based on a
        # still-forming hourly candle isn't a real 1H RSI). Cache by bar-close bucket instead.
        self._cached_values: dict = {}
        self._cached_bucket: dict[str, Optional[datetime]] = {"1h": None, "15min": None, "5min": None}

    # ---- Candle building from live ticks ----------------------------------

    def on_nifty_tick(self, tick: dict) -> None:
        """tick: {'ltp': float, 'volume': int (cumulative or delta), 'timestamp': datetime}"""
        ts = tick.get("timestamp") or datetime.now()
        price = float(tick["ltp"])
        volume = int(tick.get("volume", 0))
        minute_bucket = ts.replace(second=0, microsecond=0)

        if self._current is None or self._current.timestamp != minute_bucket:
            if self._current is not None:
                self._push_candle(self._current)
            self._current = Candle(timestamp=minute_bucket, open=price, high=price, low=price,
                                    close=price, volume=volume)
        else:
            self._current.high = max(self._current.high, price)
            self._current.low = min(self._current.low, price)
            self._current.close = price
            self._current.volume += volume

    def _push_candle(self, candle: Candle) -> None:
        self.candles.append(candle)
        if len(self.candles) > self.window_size:
            self.candles = self.candles[-self.window_size:]

    def on_option_tick(self, symbol: str, tick: dict) -> None:
        quote = self.option_chain.get(symbol, OptionQuote(symbol=symbol))
        quote.ltp = float(tick.get("ltp", quote.ltp))
        quote.bid = float(tick.get("bid", quote.bid))
        quote.ask = float(tick.get("ask", quote.ask))
        quote.oi = int(tick.get("oi", quote.oi))
        quote.volume = int(tick.get("volume", quote.volume))
        quote.updated_at = tick.get("timestamp") or datetime.now()
        self.option_chain[symbol] = quote

    # ---- Historical seeding (backtest) -------------------------------------

    def load_historical(self, df: pd.DataFrame) -> None:
        """df columns: Timestamp, Open, High, Low, Close, Volume"""
        candles = [
            Candle(timestamp=row.Timestamp, open=row.Open, high=row.High,
                   low=row.Low, close=row.Close, volume=int(row.Volume))
            for row in df.itertuples(index=False)
        ]
        self.candles = candles[-self.window_size:]
        self._current = None

    def replay_candle(self, candle: Candle) -> None:
        """Feed one historical candle at a time, as the backtester steps through the data."""
        self._push_candle(candle)

    # ---- Accessors ----------------------------------------------------------

    def get_current_candle(self) -> Optional[Candle]:
        return self._current or (self.candles[-1] if self.candles else None)

    def get_historical_candles(self, count: int = None) -> list:
        return self.candles[-count:] if count else list(self.candles)

    def update_option_chain(self, chain_data: dict) -> None:
        for row in chain_data.get("optionsChain", []):
            symbol = row.get("symbol")
            if not symbol:
                continue
            self.option_chain[symbol] = OptionQuote(
                symbol=symbol,
                ltp=float(row.get("ltp", 0)),
                oi=int(row.get("oi", 0)),
                volume=int(row.get("volume", 0)),
                updated_at=datetime.now(),
            )

    def get_option_chain(self) -> dict:
        return dict(self.option_chain)

    # ---- Indicators -----------------------------------------------------------

    def _closed_candles_df(self) -> pd.DataFrame:
        """Only fully-closed 1-min candles — excludes the still-forming `self._current`, so
        resampling this never mixes a partial higher-timeframe bar into the result."""
        return pd.DataFrame([{
            "Timestamp": c.timestamp, "Open": c.open, "High": c.high,
            "Low": c.low, "Close": c.close, "Volume": c.volume,
        } for c in self.candles])

    @staticmethod
    def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        indexed = df.set_index("Timestamp")
        return indexed.resample(rule).agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
        }).dropna()

    def calculate_indicators(self) -> dict:
        if len(self.candles) < 5:
            return {}

        out = dict(self._cached_values)
        latest_ts = pd.Timestamp(self.candles[-1].timestamp)
        closed_df = None  # built lazily, at most once per call, only if a bucket actually advanced

        for rule, key_prefix in (("1h", "1h"), ("15min", "15m"), ("5min", "5m")):
            bucket = latest_ts.floor(rule)
            if self._cached_bucket[rule] == bucket:
                continue
            self._cached_bucket[rule] = bucket
            if closed_df is None:
                closed_df = self._closed_candles_df()
            resampled = self._resample(closed_df, rule)
            if len(resampled) and resampled.index[-1] == bucket:
                # That last row is the bucket we just crossed into — it has only this one
                # candle in it so far, not a fully-closed bar. Use everything before it.
                resampled = resampled.iloc[:-1]

            if rule == "1h" and len(resampled) >= 15:
                out["rsi_1h"] = float(ind.rsi(resampled["Close"], 14).iloc[-1])
                out["ema_20_1h"] = float(ind.ema(resampled["Close"], 20).iloc[-1])
                ema50_period = min(50, len(resampled))
                out["ema_50_1h"] = float(ind.ema(resampled["Close"], ema50_period).iloc[-1])
                macd_df = ind.macd(resampled["Close"])
                out["macd_histogram_1h"] = float(macd_df["histogram"].iloc[-1])
                out["macd_histogram_1h_prev"] = (
                    float(macd_df["histogram"].iloc[-2]) if len(macd_df) >= 2 else out["macd_histogram_1h"]
                )
            elif rule == "15min" and len(resampled) >= 15:
                stoch = ind.stochastic(resampled["High"], resampled["Low"], resampled["Close"])
                out["stochastic_k_15m"] = float(stoch["k"].iloc[-1])
            elif rule == "5min" and len(resampled) >= 20:
                out["volume_ratio_5m"] = float(ind.volume_ratio(resampled["Volume"]).iloc[-1])

        # Raw 1-min volume stats are cheap (last 20 candles) and update every tick, unlike the
        # resampled indicators above.
        if len(self.candles) >= 20:
            recent = self.candles[-20:]
            avg_volume = sum(c.volume for c in recent) / 20
            out["avg_volume"] = avg_volume
            out["volume_ratio"] = (self.candles[-1].volume / avg_volume) if avg_volume else 1.0

        self._cached_values = out
        return out

    def get_state(self) -> dict:
        current = self.get_current_candle()
        return {
            "nifty_price": current.close if current else None,
            "timestamp": current.timestamp if current else datetime.now(),
            "indicators": self.calculate_indicators(),
            "option_chain": self.get_option_chain(),
            "candles": self.get_historical_candles(),
        }
