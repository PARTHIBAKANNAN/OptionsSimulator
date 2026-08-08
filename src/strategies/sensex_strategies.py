"""SENSEX variants of 8 NIFTY strategies (4 CE, 4 PE) -- same signal logic, mirrored via
subclassing rather than duplicated. create_all_sensex_strategies() is the full backtest set;
create_live_sensex_strategies() is the curated 5-strategy live roster. RSI_OVERSOLD_BULLISH is not
mirrored here, matching its NIFTY exclusion from create_all_strategies().

SENSEX_STRIKE_STEP=100 is confirmed correct (NIFTY's own is 50 -- see the strike-step fix in
docs/ARCHITECTURE.md). Lot size (20, per the recent contract-size change) is a backtest/order-sizing
concern, not a strategy concern, so it's passed to BacktestEngine/PaperTrader at run time instead.
"""
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.strategies.heikin_ashi_trend_bullish import HeikinAshiTrendBullish
from src.strategies.macd_bearish import MACDBearish
from src.strategies.macd_bullish import MACDBullish
from src.strategies.orb_bearish import ORBBearish
from src.strategies.orb_bullish import ORBBullish
from src.strategies.resistance_rejection_bearish import ResistanceRejectionBearish
from src.strategies.support_bounce_bullish import SupportBounceBullish

SENSEX_STRIKE_STEP = 100


class SensexMACDBullish(MACDBullish):
    def __init__(self):
        super().__init__(name="SENSEX_MACD_BULLISH", strike_step=SENSEX_STRIKE_STEP, underlying="SENSEX")


class SensexMACDBearish(MACDBearish):
    def __init__(self):
        super().__init__(name="SENSEX_MACD_BEARISH", strike_step=SENSEX_STRIKE_STEP, underlying="SENSEX")


class SensexORBBullish(ORBBullish):
    def __init__(self):
        super().__init__(name="SENSEX_ORB_BULLISH", strike_step=SENSEX_STRIKE_STEP, underlying="SENSEX")


class SensexORBBearish(ORBBearish):
    def __init__(self):
        super().__init__(name="SENSEX_ORB_BEARISH", strike_step=SENSEX_STRIKE_STEP, underlying="SENSEX")


class SensexSupportBounceBullish(SupportBounceBullish):
    def __init__(self):
        super().__init__(name="SENSEX_SUPPORT_BOUNCE_BULLISH", strike_step=SENSEX_STRIKE_STEP, underlying="SENSEX")


class SensexResistanceRejectionBearish(ResistanceRejectionBearish):
    def __init__(self):
        super().__init__(name="SENSEX_RESISTANCE_REJECTION_BEARISH", strike_step=SENSEX_STRIKE_STEP,
                          underlying="SENSEX")


class SensexHeikinAshiTrendBullish(HeikinAshiTrendBullish):
    def __init__(self):
        super().__init__(name="SENSEX_HEIKIN_ASHI_TREND_BULLISH", strike_step=SENSEX_STRIKE_STEP,
                          underlying="SENSEX")


class SensexHeikinAshiTrendBearish(HeikinAshiTrendBearish):
    def __init__(self):
        # Unfiltered -- the Mon/Tue + 10-12 exclusion is NIFTY-specific tuning, not assumed here.
        super().__init__(name="SENSEX_HEIKIN_ASHI_TREND_BEARISH", strike_step=SENSEX_STRIKE_STEP,
                          underlying="SENSEX", apply_day_time_filter=False)


def create_all_sensex_strategies() -> list:
    return [
        SensexMACDBullish(),
        SensexMACDBearish(),
        SensexORBBullish(),
        SensexORBBearish(),
        SensexSupportBounceBullish(),
        SensexResistanceRejectionBearish(),
        SensexHeikinAshiTrendBullish(),
        SensexHeikinAshiTrendBearish(),
    ]


def create_live_sensex_strategies() -> list:
    # Curated live roster (5 of the 8 backtested above), picked after the full 1-year comparison:
    # CE MACD_BULLISH (shipped unfiltered -- its Friday-exclusion improvement tested well but
    # isn't split-half validated yet) + SUPPORT_BOUNCE_BULLISH; PE HEIKIN_ASHI_TREND_BEARISH
    # (unfiltered), MACD_BEARISH, ORB_BEARISH. ORB_BULLISH and RESISTANCE_REJECTION_BEARISH were
    # weaker performers and HEIKIN_ASHI_TREND_BULLISH hasn't been validated -- see docs/ARCHITECTURE.md.
    return [
        SensexMACDBullish(),
        SensexSupportBounceBullish(),
        SensexHeikinAshiTrendBearish(),
        SensexMACDBearish(),
        SensexORBBearish(),
    ]
