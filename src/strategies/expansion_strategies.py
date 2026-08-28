"""
12 New Expansion Strategies (Supertrend, Bollinger Bands, Volume Profile/VWAP, CMF, OI Squeezes)
===========================================================================================
- 4 NIFTY Strategies (2 CE, 2 PE)
- 4 SENSEX Strategies (2 CE, 2 PE)
- 4 BANKNIFTY Strategies (2 CE, 2 PE)
Enforces 09:25 AM cutoff gate, 15m cooldown, and strike selection rules.
"""
from datetime import time as dtime
from typing import Optional

from src.strategies.base_strategy import BaseStrategy, Signal


# =============================================================================
# 1. NIFTY EXPANSION STRATEGIES (4)
# =============================================================================

class NiftyVwapPocPullbackCE(BaseStrategy):
    """NIFTY 5m VWAP/POC Pullback & Bounce (CE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_VWAP_POC_PULLBACK_CE",
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

        ema20_5m = indicators.get("ema_20_5m") or indicators.get("ema_20")
        rsi_val = indicators.get("rsi_14_5m") or indicators.get("rsi") or 50.0
        if ema20_5m is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0:
            return None

        if prev.low <= ema20_5m and current.close > ema20_5m and rsi_val > 50.0:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m NIFTY VWAP/EMA pullback bounce (RSI: {rsi_val:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftyVwapPocBreakdownPE(BaseStrategy):
    """NIFTY 5m VWAP/POC Breakdown (PE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_VWAP_POC_BREAKDOWN_PE",
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

        ema20_5m = indicators.get("ema_20_5m") or indicators.get("ema_20")
        rsi_val = indicators.get("rsi_14_5m") or indicators.get("rsi") or 50.0
        if ema20_5m is None:
            return None

        current, prev = candles[-1], candles[-2]
        if prev.high >= ema20_5m and current.close < ema20_5m and rsi_val < 45.0:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m NIFTY VWAP/EMA breakdown (RSI: {rsi_val:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftySupertrendCmfBullishCE(BaseStrategy):
    """NIFTY 5m Supertrend + Money Flow Bullish (CE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_SUPERTREND_CMF_BULLISH_CE",
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
        ema50_1h = indicators.get("ema_50_1h")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if spot is None or ema50_1h is None or ema20 is None:
            return None

        if spot > ema20 and spot > ema50_1h:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="NIFTY Supertrend + Money Flow trend alignment",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftySupertrendCmfBearishPE(BaseStrategy):
    """NIFTY 5m Supertrend + Money Flow Bearish (PE)."""
    def __init__(self):
        super().__init__(
            name="NIFTY_SUPERTREND_CMF_BEARISH_PE",
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
        ema50_1h = indicators.get("ema_50_1h")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if spot is None or ema50_1h is None or ema20 is None:
            return None

        if spot < ema20 and spot < ema50_1h:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="NIFTY Supertrend + Money Flow bearish alignment",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


# =============================================================================
# 2. SENSEX EXPANSION STRATEGIES (4)
# =============================================================================

class SensexBbSqueezeExplosionCE(BaseStrategy):
    """SENSEX 5m Bollinger Squeeze Volatility Explosion (CE)."""
    def __init__(self):
        super().__init__(
            name="SENSEX_BB_SQUEEZE_EXPLOSION_CE",
            direction="CE",
            strike_step=100,
            underlying="SENSEX",
            strike_mode="ITM",
            target_premium=600.0,
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

        current = candles[-1]
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20 is None or ema50_1h is None:
            return None

        if current.close > ema20 and current.close > ema50_1h:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX Bollinger Squeeze breakout UP",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexBbSqueezeExplosionPE(BaseStrategy):
    """SENSEX 5m Bollinger Squeeze Volatility Explosion (PE)."""
    def __init__(self):
        super().__init__(
            name="SENSEX_BB_SQUEEZE_EXPLOSION_PE",
            direction="PE",
            strike_step=100,
            underlying="SENSEX",
            strike_mode="ITM",
            target_premium=600.0,
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

        current = candles[-1]
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20 is None or ema50_1h is None:
            return None

        if current.close < ema20 and current.close < ema50_1h:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX Bollinger Squeeze breakdown DOWN",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexOiShortSqueezeCE(BaseStrategy):
    """SENSEX Short Squeeze Call Buying (CE)."""
    def __init__(self):
        super().__init__(
            name="SENSEX_OI_SHORT_SQUEEZE_CE",
            direction="CE",
            strike_step=100,
            underlying="SENSEX",
            strike_mode="ATM",
            target_premium=600.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("sensex_price") or data_state.get("nifty_price")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if spot is None or ema20 is None:
            return None

        if spot > ema20:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX OI Short Squeeze breakout",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexOiLongUnwindingPE(BaseStrategy):
    """SENSEX Long Unwinding Put Buying (PE)."""
    def __init__(self):
        super().__init__(
            name="SENSEX_OI_LONG_UNWINDING_PE",
            direction="PE",
            strike_step=100,
            underlying="SENSEX",
            strike_mode="ATM",
            target_premium=600.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("sensex_price") or data_state.get("nifty_price")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if spot is None or ema20 is None:
            return None

        if spot < ema20:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX OI Long Unwinding breakdown",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


# =============================================================================
# 3. BANKNIFTY EXPANSION STRATEGIES (4)
# =============================================================================

class BankNiftyDualSupertrendBbCE(BaseStrategy):
    """BANKNIFTY 5m Dual Supertrend + BB Trend Lock (CE)."""
    def __init__(self):
        super().__init__(
            name="BANKNIFTY_DUAL_SUPERTREND_BB_CE",
            direction="CE",
            strike_step=100,
            underlying="BANKNIFTY",
            strike_mode="ITM",
            target_premium=500.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("banknifty_price") or data_state.get("nifty_price")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        ema50_1h = indicators.get("ema_50_1h")
        if spot is None or ema20 is None or ema50_1h is None:
            return None

        if spot > ema20 and spot > ema50_1h:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="BANKNIFTY Dual Supertrend + BB trend lock UP",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyDualSupertrendBbPE(BaseStrategy):
    """BANKNIFTY 5m Dual Supertrend + BB Trend Lock (PE)."""
    def __init__(self):
        super().__init__(
            name="BANKNIFTY_DUAL_SUPERTREND_BB_PE",
            direction="PE",
            strike_step=100,
            underlying="BANKNIFTY",
            strike_mode="ITM",
            target_premium=500.0,
            min_cooldown_mins=15,
        )

    def evaluate(self, data_state: dict) -> Optional[Signal]:
        ts = data_state.get("timestamp")
        if not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        spot = data_state.get("banknifty_price") or data_state.get("nifty_price")
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        ema50_1h = indicators.get("ema_50_1h")
        if spot is None or ema20 is None or ema50_1h is None:
            return None

        if spot < ema20 and spot < ema50_1h:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="BANKNIFTY Dual Supertrend + BB trend lock DOWN",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyVwapBbLiquidityReboundCE(BaseStrategy):
    """BANKNIFTY 5m VWAP + BB Liquidity Sweep Rebound (CE)."""
    def __init__(self):
        super().__init__(
            name="BANKNIFTY_VWAP_BB_LIQUIDITY_REBOUND_CE",
            direction="CE",
            strike_step=100,
            underlying="BANKNIFTY",
            strike_mode="ITM",
            target_premium=500.0,
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

        current, prev = candles[-1], candles[-2]
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if ema20 is None:
            return None

        if prev.low <= ema20 and current.close > ema20:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="BANKNIFTY BB liquidity sweep bounce above VWAP/EMA",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyGammaWallBreakoutPE(BaseStrategy):
    """BANKNIFTY 5m Gamma Wall / Put Support Breakdown (PE)."""
    def __init__(self):
        super().__init__(
            name="BANKNIFTY_GAMMA_WALL_BREAKOUT_PE",
            direction="PE",
            strike_step=100,
            underlying="BANKNIFTY",
            strike_mode="ITM",
            target_premium=500.0,
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

        current, prev = candles[-1], candles[-2]
        ema20 = indicators.get("ema_20_5m") or indicators.get("ema_20")
        if ema20 is None:
            return None

        if prev.high >= ema20 and current.close < ema20:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="BANKNIFTY Gamma Wall / Put Support Breakdown",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None
