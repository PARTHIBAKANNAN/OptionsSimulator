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
    """NIFTY 5m VWAP Pullback & Bounce (CE). VWAP itself is the liquidity/"POC" reference level
    here — a real volume-profile Point of Control needs binned volume-at-price, which isn't built;
    session VWAP is the standard, honest substitute institutional desks use for the same purpose."""
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

        vwap_5m = indicators.get("vwap_5m")
        rsi_val = indicators.get("rsi_14_5m")
        if vwap_5m is None or rsi_val is None:
            return None

        current, prev = candles[-1], candles[-2]
        rng = current.high - current.low
        if rng <= 0:
            return None

        if prev.low <= vwap_5m and current.close > vwap_5m and rsi_val > 50.0:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m NIFTY VWAP pullback bounce (RSI: {rsi_val:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftyVwapPocBreakdownPE(BaseStrategy):
    """NIFTY 5m VWAP Breakdown (PE) — mirror of NiftyVwapPocPullbackCE; see its docstring."""
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

        vwap_5m = indicators.get("vwap_5m")
        rsi_val = indicators.get("rsi_14_5m")
        if vwap_5m is None or rsi_val is None:
            return None

        current, prev = candles[-1], candles[-2]
        if prev.high >= vwap_5m and current.close < vwap_5m and rsi_val < 45.0:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"5m NIFTY VWAP breakdown (RSI: {rsi_val:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftySupertrendCmfBullishCE(BaseStrategy):
    """NIFTY 5m Dual Supertrend (10,3 / 7,2) + Chaikin Money Flow, bullish (CE). Fires only when
    BOTH Supertrend periods agree the trend just flipped up AND money flow confirms buying
    pressure — real ATR-band-flip Supertrend and real CMF, not an EMA-alignment proxy."""
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
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        if spot is None or st_10_3_dir is None or st_7_2_dir is None or cmf is None:
            return None

        if st_10_3_dir == 1 and st_7_2_dir == 1 and cmf > 0:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Dual Supertrend(10,3/7,2) up + CMF {cmf:+.2f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class NiftySupertrendCmfBearishPE(BaseStrategy):
    """Mirror of NiftySupertrendCmfBullishCE — see its docstring."""
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
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        if spot is None or st_10_3_dir is None or st_7_2_dir is None or cmf is None:
            return None

        if st_10_3_dir == -1 and st_7_2_dir == -1 and cmf < 0:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Dual Supertrend(10,3/7,2) down + CMF {cmf:+.2f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


# =============================================================================
# 2. SENSEX EXPANSION STRATEGIES (4)
# =============================================================================

class SensexBbSqueezeExplosionCE(BaseStrategy):
    """SENSEX 5m Bollinger Squeeze Volatility Explosion (CE): band width was compressed (squeeze,
    ratio to its own 20-bar average < 0.85 last bar) and is now expanding sharply, with price
    actually breaking above the upper band — not just "price above two EMAs", a real squeeze-then-
    breakout, using the actual band levels."""
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
        bb_upper = indicators.get("bb_upper_5m")
        squeeze_prev = indicators.get("bb_squeeze_ratio_5m_prev")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if bb_upper is None or squeeze_prev is None or expansion is None:
            return None

        if squeeze_prev < 0.85 and expansion > 1.15 and current.close > bb_upper:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"BB squeeze({squeeze_prev:.2f})->explosion({expansion:.2f}) breakout above {bb_upper:.1f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexBbSqueezeExplosionPE(BaseStrategy):
    """Mirror of SensexBbSqueezeExplosionCE — see its docstring."""
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
        bb_lower = indicators.get("bb_lower_5m")
        squeeze_prev = indicators.get("bb_squeeze_ratio_5m_prev")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if bb_lower is None or squeeze_prev is None or expansion is None:
            return None

        if squeeze_prev < 0.85 and expansion > 1.15 and current.close < bb_lower:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"BB squeeze({squeeze_prev:.2f})->explosion({expansion:.2f}) breakdown below {bb_lower:.1f}",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexOiShortSqueezeCE(BaseStrategy):
    """SENSEX Short Squeeze Call Buying (CE).

    HONEST LIMITATION: a real "short squeeze" signal needs a time series of per-strike Open
    Interest (call-side OI unwinding while price rises, forcing short covering). Fyers' historical
    candle API has no per-strike OI history, and we don't have that archived, so this cannot be
    genuinely backtested over the past year yet — only validated live, where real tick-level OI
    IS captured (see DataManager.update_option_chain's OptionQuote.oi) but not currently read by
    any strategy. Until that live-OI wiring is built, this is a trend-confirmed EMA fallback (not
    a bare single-EMA check like before) — strictly better-filtered than the OI-blind original,
    but still not the real thing. Do not treat backtest results for this strategy as validating
    an OI edge."""
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
        ema20 = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if spot is None or ema20 is None or ema50_1h is None:
            return None

        if spot > ema20 and spot > ema50_1h:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX EMA trend breakout (OI data unavailable for backtest — see class docstring)",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexOiLongUnwindingPE(BaseStrategy):
    """SENSEX Long Unwinding Put Buying (PE) — mirror of SensexOiShortSqueezeCE; same honest
    limitation applies (no historical per-strike OI available). See its docstring."""
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
        ema20 = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if spot is None or ema20 is None or ema50_1h is None:
            return None

        if spot < ema20 and spot < ema50_1h:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale="SENSEX EMA trend breakdown (OI data unavailable for backtest — see class docstring)",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


# =============================================================================
# 3. BANKNIFTY EXPANSION STRATEGIES (4)
# =============================================================================

class BankNiftyDualSupertrendBbCE(BaseStrategy):
    """BANKNIFTY 5m Dual Supertrend (10,3 / 7,2) + CMF + BB Trend Lock (CE) — the superset of
    NiftySupertrendCmfBullishCE: both Supertrend periods flipped up, money flow confirms, AND
    Bollinger band width is actively expanding (the move has real volatility behind it, not just
    directional agreement on a quiet tape)."""
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
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if None in (spot, st_10_3_dir, st_7_2_dir, cmf, expansion):
            return None

        if st_10_3_dir == 1 and st_7_2_dir == 1 and cmf > 0 and expansion > 1.05:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Dual Supertrend up + CMF {cmf:+.2f} + BB expanding {expansion:.2f}x",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyDualSupertrendBbPE(BaseStrategy):
    """Mirror of BankNiftyDualSupertrendBbCE — see its docstring."""
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
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if None in (spot, st_10_3_dir, st_7_2_dir, cmf, expansion):
            return None

        if st_10_3_dir == -1 and st_7_2_dir == -1 and cmf < 0 and expansion > 1.05:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Dual Supertrend down + CMF {cmf:+.2f} + BB expanding {expansion:.2f}x",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyVwapBbLiquidityReboundCE(BaseStrategy):
    """BANKNIFTY 5m VWAP + BB Liquidity Sweep Rebound (CE): price sweeps below the lower Bollinger
    Band (a genuine liquidity grab below the band — stops/resting liquidity there) then reclaims
    session VWAP — real band + real VWAP, not a bare EMA touch."""
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
        bb_lower = indicators.get("bb_lower_5m")
        vwap_5m = indicators.get("vwap_5m")
        if bb_lower is None or vwap_5m is None:
            return None

        if prev.low <= bb_lower and current.close > vwap_5m:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Swept below lower BB ({bb_lower:.1f}), reclaimed VWAP ({vwap_5m:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyGammaWallBreakoutPE(BaseStrategy):
    """BANKNIFTY 5m Gamma Wall / Put Support Breakdown (PE).

    HONEST LIMITATION: a real Gamma Exposure (GEX) wall needs aggregated dealer gamma exposure
    across the full option chain (gamma x OI per strike, summed), which requires historical
    per-strike Greeks/OI data we don't have archived — the same data gap as the SENSEX OI
    strategies (see their docstrings). Until real-time GEX aggregation is built from live option-
    chain data, this is a documented placeholder: price sweeps above the upper Bollinger Band (a
    liquidity grab at the highs — the closest OHLCV-only analog to "price rejected at a
    dealer-hedging level") then breaks back below session VWAP. This is a real, sensible
    mean-reversion pattern in its own right, but it is NOT actually Gamma Wall detection — don't
    read backtest results here as validating a GEX edge."""
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
        bb_upper = indicators.get("bb_upper_5m")
        vwap_5m = indicators.get("vwap_5m")
        if bb_upper is None or vwap_5m is None:
            return None

        if prev.high >= bb_upper and current.close < vwap_5m:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Swept above upper BB ({bb_upper:.1f}), broke below VWAP ({vwap_5m:.1f}) "
                                            f"(GEX data unavailable — see class docstring)",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None
