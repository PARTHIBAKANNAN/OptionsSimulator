"""Runs every registered strategy against the current data_state, deduping and rate-limiting signals."""
from datetime import datetime, timedelta, time as dtime

from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.macd_bearish import MACDBearish


from src.strategies.nifty_5m_strategies import (
    NiftySupportBounce5MITM,
    NiftyHeikinAshiBullish5MITM,
    NiftyORBBullish5MITM,
    NiftyResistanceRejection5MITM,
    NiftyHeikinAshiBearish5MITM,
    NiftyORBBearish5MITM,
)
from src.strategies.sensex_5m_strategies import (
    SensexSupportBounce5MITM,
    SensexHeikinAshiBullish5MITM,
    SensexORBBullish5MITM,
    SensexResistanceRejection5MITM,
    SensexHeikinAshiBearish5MITM,
    SensexORBBearish5MITM,
)
from src.strategies.sensex_strategies import (
    SensexMACDBullish,
    SensexSupportBounceBullish,
    SensexHeikinAshiTrendBearish,
    SensexMACDBearish,
    SensexORBBearish,
)
from src.strategies.banknifty_5m_strategies import (
    BankNiftySupportBounce5MITM,
    BankNiftyHeikinAshiBullish5MITM,
    BankNiftyORBBullish5MITM,
    BankNiftyResistanceRejection5MITM,
    BankNiftyHeikinAshiBearish5MITM,
    BankNiftyORBBearish5MITM,
)
from src.strategies.banknifty_strategies import (
    BankNiftyMACDBullish,
    BankNiftySupportBounceBullish,
    BankNiftyHeikinAshiTrendBearish,
    BankNiftyMACDBearish,
    BankNiftyORBBearish,
)


from src.strategies.expansion_strategies import (
    NiftyVwapPocPullbackCE,
    NiftyVwapPocBreakdownPE,
    NiftySupertrendCmfBullishCE,
    NiftySupertrendCmfBearishPE,
    SensexBbSqueezeExplosionCE,
    SensexBbSqueezeExplosionPE,
    SensexOiShortSqueezeCE,
    SensexOiLongUnwindingPE,
    BankNiftyDualSupertrendBbCE,
    BankNiftyDualSupertrendBbPE,
    BankNiftyVwapBbLiquidityReboundCE,
    BankNiftyGammaWallBreakoutPE,
)


def create_nifty_strategies() -> list[BaseStrategy]:
    """Returns the 14 active NIFTY strategies (4 1M ATM + 6 5M ITM + 4 Expansion)."""
    return [
        ORBBullish(name="NIFTY_ORB_BULLISH_1M_ATM"),
        MACDBullish(name="NIFTY_MACD_BULLISH_1M_ATM"),
        HeikinAshiTrendBearish(name="NIFTY_HEIKIN_ASHI_BEARISH_1M_ATM"),
        MACDBearish(name="NIFTY_MACD_BEARISH_1M_ATM"),
        NiftySupportBounce5MITM(),
        NiftyHeikinAshiBullish5MITM(),
        NiftyORBBullish5MITM(),
        NiftyResistanceRejection5MITM(),
        NiftyHeikinAshiBearish5MITM(),
        NiftyORBBearish5MITM(),
        NiftyVwapPocPullbackCE(),
        NiftyVwapPocBreakdownPE(),
        NiftySupertrendCmfBullishCE(),
        NiftySupertrendCmfBearishPE(),
    ]


def create_sensex_strategies() -> list[BaseStrategy]:
    """Returns the 15 active SENSEX strategies (5 1M ATM + 6 5M ITM + 4 Expansion)."""
    return [
        SensexMACDBullish(name="SENSEX_MACD_BULLISH_1M_ATM"),
        SensexSupportBounceBullish(name="SENSEX_SUPPORT_BOUNCE_1M_ATM"),
        SensexHeikinAshiTrendBearish(name="SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM"),
        SensexMACDBearish(name="SENSEX_MACD_BEARISH_1M_ATM"),
        SensexORBBearish(name="SENSEX_ORB_BEARISH_1M_ATM"),
        SensexSupportBounce5MITM(),
        SensexHeikinAshiBullish5MITM(),
        SensexORBBullish5MITM(),
        SensexResistanceRejection5MITM(),
        SensexHeikinAshiBearish5MITM(),
        SensexORBBearish5MITM(),
        SensexBbSqueezeExplosionCE(),
        SensexBbSqueezeExplosionPE(),
        SensexOiShortSqueezeCE(),
        SensexOiLongUnwindingPE(),
    ]


def create_banknifty_strategies() -> list[BaseStrategy]:
    """Returns the 15 active BANKNIFTY strategies (5 1M ATM + 6 5M ITM + 4 Expansion)."""
    return [
        BankNiftyMACDBullish(name="BANKNIFTY_MACD_BULLISH_1M_ATM"),
        BankNiftySupportBounceBullish(name="BANKNIFTY_SUPPORT_BOUNCE_1M_ATM"),
        BankNiftyHeikinAshiTrendBearish(name="BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM"),
        BankNiftyMACDBearish(name="BANKNIFTY_MACD_BEARISH_1M_ATM"),
        BankNiftyORBBearish(name="BANKNIFTY_ORB_BEARISH_1M_ATM"),
        BankNiftySupportBounce5MITM(),
        BankNiftyHeikinAshiBullish5MITM(),
        BankNiftyORBBullish5MITM(),
        BankNiftyResistanceRejection5MITM(),
        BankNiftyHeikinAshiBearish5MITM(),
        BankNiftyORBBearish5MITM(),
        BankNiftyDualSupertrendBbCE(),
        BankNiftyDualSupertrendBbPE(),
        BankNiftyVwapBbLiquidityReboundCE(),
        BankNiftyGammaWallBreakoutPE(),
    ]


def create_all_strategies() -> list[BaseStrategy]:
    """Returns the full master roster of 44 active strategies (14 NIFTY + 15 SENSEX + 15 BANKNIFTY)."""
    return create_nifty_strategies() + create_sensex_strategies() + create_banknifty_strategies()


def create_live_strategies() -> list[BaseStrategy]:
    return create_all_strategies()


class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy] = None, signal_cooldown_mins: int = 5, logger=None):
        self.strategies = strategies if strategies is not None else create_all_strategies()
        self.signal_cooldown = timedelta(minutes=signal_cooldown_mins)
        self.logger = logger

    def evaluate_all(self, data_state: dict) -> list[Signal]:
        ts = data_state.get("timestamp")
        if ts and hasattr(ts, "time") and ts.time() < dtime(9, 25):
            return []

        signals = []
        for strategy in self.strategies:
            try:
                signal = strategy.evaluate(data_state)
            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Strategy {strategy.name} raised: {e}", {"strategy": strategy.name})
                continue

            if signal is None:
                continue

            if strategy.last_signal_time and signal.timestamp - strategy.last_signal_time < self.signal_cooldown:
                continue

            strategy.last_signal_time = signal.timestamp
            signals.append(signal)
            if self.logger:
                self.logger.log_signal(strategy.name, {
                    "strike": signal.strike, "entry_price": signal.entry_price,
                    "confidence": signal.confidence, "rationale": signal.rationale,
                })
        return signals
