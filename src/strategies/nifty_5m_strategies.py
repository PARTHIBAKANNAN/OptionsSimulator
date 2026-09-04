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
    """5-min pullback to 20-EMA in 1H uptrend with strong bullish close (CE)."""
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        avg_volume = indicators.get("avg_volume")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0 or current.close <= 0:
            return None

        closes_strong = (current.close - current.low) / rng >= 0.60
        volume_confirmed = avg_volume is None or avg_volume == 0 or current.volume > avg_volume

        if prev.low <= ema20_5m and current.close > ema20_5m and current.close > ema50_1h and closes_strong and volume_confirmed:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("nifty_price") or (candles[-1].close if candles else None)
        if spot is None or spot <= 0:
            return None

        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        if ha is None or ema50 is None:
            return None

        body = ha["close"] - ha["open"]
        prev_bullish = ha["prev_close"] > ha["prev_open"]
        if not (body > 0 and prev_bullish and spot > ema50):
            return None

        lower_wick = ha["open"] - ha["low"]
        if lower_wick > 0.30 * body:
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
        if ts is None or len(candles) < 2 or not self.can_trigger(ts):
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
            morning_candles = [
                c for c in candles
                if c.timestamp.date() == day and ORB_WINDOW_START <= c.timestamp.time() < ORB_WINDOW_END
            ]
            if morning_candles:
                self._range_high = max(c.high for c in morning_candles)
                self._range_low = min(c.low for c in morning_candles)
            else:
                return None

        indicators = data_state.get("indicators", {})
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        avg_volume = indicators.get("avg_volume")

        crossed_now = (prev.close <= self._range_high < current.close) or (prev.timestamp.time() < ORB_WINDOW_END and current.close > self._range_high)
        volume_confirmed = avg_volume is None or avg_volume == 0 or current.volume > avg_volume
        if crossed_now and volume_confirmed and (ema50 is not None and current.close > ema50):
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m ORB breakout above morning high {self._range_high:.1f} on volume",
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        avg_volume = indicators.get("avg_volume")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0 or current.close <= 0:
            return None

        closes_weak = (current.high - current.close) / rng >= 0.60
        volume_confirmed = avg_volume is None or avg_volume == 0 or current.volume > avg_volume
        if prev.high >= ema20_5m and current.close < ema20_5m and current.close < ema50_1h and closes_weak and volume_confirmed:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("nifty_price") or (candles[-1].close if candles else None)
        if spot is None or spot <= 0:
            return None

        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        if ha is None or ema50 is None:
            return None

        body = ha["open"] - ha["close"]
        prev_bearish = ha["prev_open"] > ha["prev_close"]
        if not (body > 0 and prev_bearish and spot < ema50):
            return None

        upper_wick = ha["high"] - ha["open"]
        if upper_wick > 0.30 * body:
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
        if ts is None or len(candles) < 2 or not self.can_trigger(ts):
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
            morning_candles = [
                c for c in candles
                if c.timestamp.date() == day and ORB_WINDOW_START <= c.timestamp.time() < ORB_WINDOW_END
            ]
            if morning_candles:
                self._range_high = max(c.high for c in morning_candles)
                self._range_low = min(c.low for c in morning_candles)
            else:
                return None

        indicators = data_state.get("indicators", {})
        ema50 = indicators.get("ema_50_1h") or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")
        avg_volume = indicators.get("avg_volume")

        crossed_now = (prev.close >= self._range_low > current.close) or (prev.timestamp.time() < ORB_WINDOW_END and current.close < self._range_low)
        volume_confirmed = avg_volume is None or avg_volume == 0 or current.volume > avg_volume
        if crossed_now and volume_confirmed and (ema50 is not None and current.close < ema50):
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
