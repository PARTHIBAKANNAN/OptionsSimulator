"""
NIFTY 5-Minute In-The-Money (ITM ~Rs.200) Strategy Suite
========================================================
Top-performing 6 strategies (3 CE & 3 PE) executing on 5-minute candle closes
with 1H 50-EMA trend alignment, ITM strike selection, and re-entry cooldown protection.
"""
from datetime import time as dtime
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal

ORB_WINDOW_START = dtime(9, 15)
ORB_WINDOW_END = dtime(9, 30)


class NiftySupportBounce5MITM(BaseStrategy):
    """5-min pullback to 20-EMA/50-EMA in 1H uptrend with strong bullish close (CE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_SUPPORT_BOUNCE_5M_ITM",
            direction="CE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0:
            return None

        closes_strong = (current.close - current.low) / rng >= 0.60
        if prev.low <= ema20_5m and current.close > ema20_5m and current.close > ema50_1h and closes_strong:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m support bounce off 20-EMA ({ema20_5m:.1f}) in 1H uptrend",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftyHeikinAshiBullish5MITM(BaseStrategy):
    """5-min Heikin-Ashi continuation: 2 consecutive green HA candles with flat bottoms in 1H uptrend (CE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_HEIKIN_ASHI_BULLISH_5M_ITM",
            direction="CE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("nifty_price")
        if spot is None:
            return None

        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h")
        if ha is None or ema50 is None:
            return None

        body = ha["close"] - ha["open"]
        prev_bullish = ha["prev_close"] > ha["prev_open"]
        if not (body > 0 and prev_bullish and spot > ema50):
            return None

        lower_wick = ha["open"] - ha["low"]
        if lower_wick > 0.15 * body:
            return None

        symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
        price = self.get_option_price(symbol, strike, spot, "CE", data_state)
        self.last_signal_time = ts
        return Signal(
            strategy=self.name, direction="CE", action="BUY", strike=symbol,
            confidence=0.80, rationale="5m Heikin-Ashi bullish trend continuation above 1H 50-EMA",
            entry_price=price, timestamp=ts, underlying=self.underlying,
        )


class NiftyORBBullish5MITM(BaseStrategy):
    """5-min Opening Range Breakout above 09:30 range high with 1H 50-EMA confirmation (CE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_ORB_BULLISH_5M_ITM",
            direction="CE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=30,
        )
        self._range_day = None
        self._range_high = None
        self._range_low = None

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        candles = data_state.get("candles", [])
        if len(candles) < 2 or not self.can_trigger(ts):
            return None

        current, prev = candles[-1], candles[-2]
        day = current.timestamp.date()
        t = current.timestamp.time()

        if day != self._range_day:
            self._range_day = day
            self._range_high = None
            self._range_low = None

        if t < ORB_WINDOW_START:
            return None
        if t < ORB_WINDOW_END:
            self._range_high = current.high if self._range_high is None else max(self._range_high, current.high)
            self._range_low = current.low if self._range_low is None else min(self._range_low, current.low)
            return None

        if self._range_high is None:
            return None

        indicators = data_state.get("indicators", {})
        ema50_1h = indicators.get("ema_50_1h")

        crossed_now = (prev.close <= self._range_high < current.close) or (prev.timestamp.time() < ORB_WINDOW_END and current.close > self._range_high)
        if crossed_now and (ema50_1h is None or current.close > ema50_1h):
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m ORB breakout above morning high {self._range_high:.1f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftyResistanceRejection5MITM(BaseStrategy):
    """5-min test of 20-EMA from below with strong rejection close in 1H downtrend (PE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_RESISTANCE_REJECTION_5M_ITM",
            direction="PE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0:
            return None

        closes_weak = (current.high - current.close) / rng >= 0.60
        if prev.high >= ema20_5m and current.close < ema20_5m and current.close < ema50_1h and closes_weak:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m resistance rejection off 20-EMA ({ema20_5m:.1f}) in 1H downtrend",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftyHeikinAshiBearish5MITM(BaseStrategy):
    """5-min Heikin-Ashi continuation: 2 consecutive red HA candles with flat tops in 1H downtrend (PE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM",
            direction="PE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("nifty_price")
        if spot is None:
            return None

        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h")
        if ha is None or ema50 is None:
            return None

        body = ha["open"] - ha["close"]
        prev_bearish = ha["prev_open"] > ha["prev_close"]
        if not (body > 0 and prev_bearish and spot < ema50):
            return None

        upper_wick = ha["high"] - ha["open"]
        if upper_wick > 0.15 * body:
            return None

        symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
        price = self.get_option_price(symbol, strike, spot, "PE", data_state)
        self.last_signal_time = ts
        return Signal(
            strategy=self.name, direction="PE", action="BUY", strike=symbol,
            confidence=0.80, rationale="5m Heikin-Ashi bearish continuation below 1H 50-EMA",
            entry_price=price, timestamp=ts, underlying=self.underlying,
        )


class NiftyORBBearish5MITM(BaseStrategy):
    """5-min Opening Range Breakdown below 09:30 range low with 1H 50-EMA confirmation (PE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_ORB_BEARISH_5M_ITM",
            direction="PE",
            strike_step=50,
            underlying="NIFTY",
            strike_mode="ITM",
            target_premium=200.0,
            min_cooldown_mins=30,
        )
        self._range_day = None
        self._range_high = None
        self._range_low = None

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        candles = data_state.get("candles", [])
        if len(candles) < 2 or not self.can_trigger(ts):
            return None

        current, prev = candles[-1], candles[-2]
        day = current.timestamp.date()
        t = current.timestamp.time()

        if day != self._range_day:
            self._range_day = day
            self._range_high = None
            self._range_low = None

        if t < ORB_WINDOW_START:
            return None
        if t < ORB_WINDOW_END:
            self._range_high = current.high if self._range_high is None else max(self._range_high, current.high)
            self._range_low = current.low if self._range_low is None else min(self._range_low, current.low)
            return None

        if self._range_low is None:
            return None

        indicators = data_state.get("indicators", {})
        ema50_1h = indicators.get("ema_50_1h")

        crossed_now = (prev.close >= self._range_low > current.close) or (prev.timestamp.time() < ORB_WINDOW_END and current.close < self._range_low)
        if crossed_now and (ema50_1h is None or current.close < ema50_1h):
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m ORB breakdown below morning low {self._range_low:.1f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None
