"""
BANKNIFTY variants of 8 baseline strategies (4 CE, 4 PE) -- same signal logic, mirrored via
subclassing with BANKNIFTY_STRIKE_STEP=100 and underlying='BANKNIFTY'.
"""
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.heikin_ashi_trend_bullish import HeikinAshiTrendBullish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.orb_bearish import ORBBearish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish
from src.strategies.support_bounce_bullish import SupportBounceBullish

BANKNIFTY_STRIKE_STEP = 100


class BankNiftyMACDBullish(MACDBullish):
    def __init__(self, name: str = "BANKNIFTY_MACD_BULLISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyMACDBearish(MACDBearish):
    def __init__(self, name: str = "BANKNIFTY_MACD_BEARISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyORBBullish(ORBBullish):
    def __init__(self, name: str = "BANKNIFTY_ORB_BULLISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyORBBearish(ORBBearish):
    def __init__(self, name: str = "BANKNIFTY_ORB_BEARISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftySupportBounceBullish(SupportBounceBullish):
    def __init__(self, name: str = "BANKNIFTY_SUPPORT_BOUNCE_BULLISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyResistanceRejectionBearish(ResistanceRejectionBearish):
    def __init__(self, name: str = "BANKNIFTY_RESISTANCE_REJECTION_BEARISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyHeikinAshiTrendBullish(HeikinAshiTrendBullish):
    def __init__(self, name: str = "BANKNIFTY_HEIKIN_ASHI_TREND_BULLISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY")


class BankNiftyHeikinAshiTrendBearish(HeikinAshiTrendBearish):
    def __init__(self, name: str = "BANKNIFTY_HEIKIN_ASHI_TREND_BEARISH"):
        super().__init__(name=name, strike_step=BANKNIFTY_STRIKE_STEP, underlying="BANKNIFTY", apply_day_time_filter=False)


def create_all_banknifty_strategies() -> list:
    from src.strategies.banknifty_5m_strategies import (
        BankNiftySupportBounce5MITM,
        BankNiftyHeikinAshiBullish5MITM,
        BankNiftyORBBullish5MITM,
        BankNiftyResistanceRejection5MITM,
        BankNiftyHeikinAshiBearish5MITM,
        BankNiftyORBBearish5MITM,
    )
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
    ]
