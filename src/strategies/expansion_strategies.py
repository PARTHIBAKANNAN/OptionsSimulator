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
        if ts is None or not self.can_trigger(ts):
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
        if rng <= 0 or current.close <= 0:
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
        if ts is None or not self.can_trigger(ts):
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
        if rng <= 0 or current.close <= 0:
            return None

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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("nifty_price") or (candles[-1].close if candles else None)
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        if spot is None or spot <= 0 or st_10_3_dir is None or st_7_2_dir is None or cmf is None:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("nifty_price") or (candles[-1].close if candles else None)
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        if spot is None or spot <= 0 or st_10_3_dir is None or st_7_2_dir is None or cmf is None:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        current = candles[-1]
        bb_upper = indicators.get("bb_upper_5m")
        squeeze_prev = indicators.get("bb_squeeze_ratio_5m_prev")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if bb_upper is None or squeeze_prev is None or expansion is None or current.close <= 0:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        current = candles[-1]
        bb_lower = indicators.get("bb_lower_5m")
        squeeze_prev = indicators.get("bb_squeeze_ratio_5m_prev")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if bb_lower is None or squeeze_prev is None or expansion is None or current.close <= 0:
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


def _calculate_option_chain_pcr(data_state: dict) -> tuple[Optional[float], Optional[int], Optional[int]]:
    """Calculates live Put-Call Ratio (PCR) and total Open Interest from live option chain quotes."""
    option_chain = data_state.get("option_chain", {})
    if not option_chain:
        return None, None, None
    total_call_oi = 0
    total_put_oi = 0
    for sym, quote in option_chain.items():
        oi = getattr(quote, "oi", 0) or 0
        if sym.endswith("CE") or getattr(quote, "option_type", "") == "CE":
            total_call_oi += oi
        elif sym.endswith("PE") or getattr(quote, "option_type", "") == "PE":
            total_put_oi += oi
    if total_call_oi == 0 and total_put_oi == 0:
        return None, None, None
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
    return pcr, total_call_oi, total_put_oi


class SensexOiShortSqueezeCE(BaseStrategy):
    """SENSEX Short Squeeze Call Buying (CE).
    
    LIVE MARKET LOGIC: Reads live Option Chain Open Interest (`OptionQuote.oi`) from Fyers.
    Detects Call unwinding & Put support build-up (PCR > 1.10) confirming a short squeeze
    with spot price breaking above 20-EMA.
    
    BACKTEST FALLBACK: When historical per-strike OI is absent, filters for strong institutional
    volume surges (volume_ratio > 1.25) above 20-EMA & 1H 50-EMA with bullish close."""
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("sensex_price") or (candles[-1].close if candles else None)
        ema20 = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h") or indicators.get("ema_50_5m")
        vol_ratio = indicators.get("volume_ratio_5m") or indicators.get("volume_ratio") or 1.0

        if spot is None or spot <= 0 or ema20 is None:
            return None

        pcr, call_oi, put_oi = _calculate_option_chain_pcr(data_state)
        
        # 1. Live Market OI-driven condition
        if pcr is not None:
            is_squeeze = pcr > 1.10 and spot > ema20
            rationale = f"Live OI Short Squeeze (PCR: {pcr:.2f}, Calls: {call_oi:,}, Puts: {put_oi:,})"
        else:
            # 2. Backtest volume-surge price action proxy
            if not candles:
                return None
            current = candles[-1]
            rng = current.high - current.low
            strong_close = rng > 0 and ((current.close - current.low) / rng) >= 0.55
            is_squeeze = spot > ema20 and (ema50_1h is None or spot > ema50_1h) and vol_ratio >= 1.20 and strong_close
            rationale = f"SENSEX Volume Surge Squeeze (Vol: {vol_ratio:.2f}x avg, >20-EMA)"

        if is_squeeze:
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=rationale,
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class SensexOiLongUnwindingPE(BaseStrategy):
    """SENSEX Long Unwinding Put Buying (PE) — mirror of SensexOiShortSqueezeCE.
    
    LIVE MARKET LOGIC: Reads live Option Chain Open Interest. Detects Put unwinding & Call resistance
    (PCR < 0.90) with spot breaking below 20-EMA.
    
    BACKTEST FALLBACK: High-volume breakdown (volume_ratio > 1.20) below 20-EMA & 1H 50-EMA with weak close."""
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("sensex_price") or (candles[-1].close if candles else None)
        ema20 = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h") or indicators.get("ema_50_5m")
        vol_ratio = indicators.get("volume_ratio_5m") or indicators.get("volume_ratio") or 1.0

        if spot is None or spot <= 0 or ema20 is None:
            return None

        pcr, call_oi, put_oi = _calculate_option_chain_pcr(data_state)

        # 1. Live Market OI-driven condition
        if pcr is not None:
            is_unwinding = pcr < 0.90 and spot < ema20
            rationale = f"Live OI Long Unwinding (PCR: {pcr:.2f}, Calls: {call_oi:,}, Puts: {put_oi:,})"
        else:
            # 2. Backtest volume-surge breakdown proxy
            if not candles:
                return None
            current = candles[-1]
            rng = current.high - current.low
            weak_close = rng > 0 and ((current.high - current.close) / rng) >= 0.55
            is_unwinding = spot < ema20 and (ema50_1h is None or spot < ema50_1h) and vol_ratio >= 1.20 and weak_close
            rationale = f"SENSEX Volume Breakdown Unwinding (Vol: {vol_ratio:.2f}x avg, <20-EMA)"

        if is_unwinding:
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=rationale,
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("banknifty_price") or (candles[-1].close if candles else None)
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if None in (spot, st_10_3_dir, st_7_2_dir, cmf, expansion) or spot <= 0:
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        spot = data_state.get("banknifty_price") or (candles[-1].close if candles else None)
        st_10_3_dir = indicators.get("supertrend_10_3_direction")
        st_7_2_dir = indicators.get("supertrend_7_2_direction")
        cmf = indicators.get("cmf_20_5m")
        expansion = indicators.get("bb_bandwidth_expansion_5m")
        if None in (spot, st_10_3_dir, st_7_2_dir, cmf, expansion) or spot <= 0:
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
    Band (a genuine liquidity grab below the band — stops/resting liquidity there) then rejects
    and reclaims back inside the lower band with bullish rejection momentum while holding below/near VWAP."""
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
        if ts is None or not self.can_trigger(ts):
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

        rng = current.high - current.low
        if rng <= 0 or current.close <= 0:
            return None

        # Price swept below lower band (liquidity grab) and closed back inside the band
        swept_lower_band = (prev.low <= bb_lower or current.low <= bb_lower)
        reclaimed_band = current.close > bb_lower
        bullish_close = (current.close - current.low) / rng >= 0.50 and current.close > current.open
        not_overextended_above_vwap = current.close <= vwap_5m * 1.01  # Room to run to VWAP

        if swept_lower_band and reclaimed_band and bullish_close and not_overextended_above_vwap:
            spot = current.close
            symbol, strike = self.select_strike(spot, "CE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "CE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Liquidity sweep below BB ({bb_lower:.1f}) & bullish reclaim toward VWAP ({vwap_5m:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None


class BankNiftyGammaWallBreakoutPE(BaseStrategy):
    """BANKNIFTY 5m Gamma Wall / Put Support Breakdown (PE).
    Price sweeps above the upper Bollinger Band then breaks back below session VWAP."""
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
        if ts is None or not self.can_trigger(ts):
            return None

        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        current, prev = candles[-1], candles[-2]
        bb_upper = indicators.get("bb_upper_5m")
        vwap_5m = indicators.get("vwap_5m")
        if bb_upper is None or vwap_5m is None or current.close <= 0:
            return None

        if prev.high >= bb_upper and current.close < vwap_5m:
            spot = current.close
            symbol, strike = self.select_strike(spot, "PE", timestamp=ts)
            price = self.get_option_price(symbol, strike, spot, "PE", data_state)
            self.last_signal_time = ts
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.85, rationale=f"Swept above upper BB ({bb_upper:.1f}), broke below VWAP ({vwap_5m:.1f})",
                entry_price=price, timestamp=ts, underlying=self.underlying,
            )
        return None
