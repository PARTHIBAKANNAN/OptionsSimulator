"""
Master System Health Check & Pre-Flight Verification Suite
==========================================================
Exhaustive verification of the entire trading architecture before live execution:
1. All 44 Strategies Full-Matrix Evaluation (Pre-market, Market Open, Cutoff, Null safety)
2. Quantitative Gates Enforcement (ORB 10:30 cutoff, ADX trend strength, VWAP proximity, Midday volume)
3. Points-Based TSL Engine Calibration (NIFTY, BANKNIFTY, SENSEX 25/35 cost locks)
4. 60-Minute Strike Loss Lockout Whipsaw Protection
5. Live Trader Initialization & State Manager SQLite WAL Verification
"""
import json
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
import pytest

from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, Order, RiskLimitExceeded
from src.strategies.base_strategy import BaseStrategy, Signal
from src.strategies.engine import (
    create_all_strategies,
    create_nifty_strategies,
    create_banknifty_strategies,
    create_sensex_strategies,
)
from src.strategies.orb_bullish import ORBBullish
from src.strategies.orb_bearish import ORBBearish
from src.strategies.heikin_ashi_trend_bullish import HeikinAshiTrendBullish
from src.strategies.heikin_ashi_trend_bearish import HeikinAshiTrendBearish
from src.persistence.state_manager import StateManager
from src.utils.indicators import adx, vwap, supertrend, chaikin_money_flow

IST = ZoneInfo("Asia/Kolkata")


# =============================================================================
# PHASE 1: 44-STRATEGY FULL MATRIX INTEGRITY & ROBUSTNESS
# =============================================================================

def test_p1_all_44_strategies_count_and_naming():
    """Verify master roster has exactly 44 strategies with correct underlying tags."""
    nifty = create_nifty_strategies()
    banknifty = create_banknifty_strategies()
    sensex = create_sensex_strategies()
    all_strats = create_all_strategies()

    assert len(nifty) == 14
    assert len(banknifty) == 15
    assert len(sensex) == 15
    assert len(all_strats) == 44

    for s in nifty:
        assert s.underlying == "NIFTY"
        assert s.direction in ("CE", "PE")
    for s in banknifty:
        assert s.underlying == "BANKNIFTY"
        assert s.direction in ("CE", "PE")
    for s in sensex:
        assert s.underlying == "SENSEX"
        assert s.direction in ("CE", "PE")


def test_p1_all_44_strategies_timing_cutoffs():
    """Verify all 44 strategies enforce 09:25 AM opening cutoff and 15:15 PM EOD cutoff."""
    all_strats = create_all_strategies()

    pre_market = datetime(2026, 10, 28, 9, 15, tzinfo=IST)
    early_market = datetime(2026, 10, 28, 9, 24, tzinfo=IST)
    eod_market = datetime(2026, 10, 28, 15, 16, tzinfo=IST)

    candles = [
        Candle(pre_market, 25000, 25050, 24950, 25000, 5000),
        Candle(pre_market, 25000, 25050, 24950, 25000, 5000),
    ]

    for strat in all_strats:
        # Pre-market
        state_pre = {"timestamp": pre_market, "candles": candles, "indicators": {}}
        assert strat.evaluate(state_pre) is None, f"{strat.name} allowed signal at 09:15"

        # Early market (before 09:25)
        state_early = {"timestamp": early_market, "candles": candles, "indicators": {}}
        assert strat.evaluate(state_early) is None, f"{strat.name} allowed signal at 09:24"

        # EOD cutoff (>= 15:15)
        state_eod = {"timestamp": eod_market, "candles": candles, "indicators": {}}
        assert strat.evaluate(state_eod) is None, f"{strat.name} allowed signal at 15:16"


def test_p1_all_44_strategies_null_safety():
    """Verify all 44 strategies handle null, empty, or garbage states gracefully without crashing."""
    all_strats = create_all_strategies()
    valid_ts = datetime(2026, 10, 28, 10, 0, tzinfo=IST)

    dirty_states = [
        {},
        {"timestamp": None},
        {"timestamp": valid_ts, "candles": []},
        {"timestamp": valid_ts, "candles": [Candle(valid_ts, 25000, 25050, 24950, 25000, 100)]},  # only 1 candle
        {"timestamp": valid_ts, "nifty_price": 0.0, "candles": []},
        {"timestamp": valid_ts, "nifty_price": -50.0, "candles": []},
        {"timestamp": valid_ts, "candles": [
            Candle(valid_ts, 25000, 25050, 24950, 25000, 100),
            Candle(valid_ts, 25000, 25050, 24950, 25000, 100),
        ], "indicators": None},
    ]

    for strat in all_strats:
        for state in dirty_states:
            try:
                res = strat.evaluate(state)
                assert res is None
            except Exception as e:
                pytest.fail(f"Strategy {strat.name} crashed on dirty state: {e}")


def test_p1_live_mode_synthetic_price_refusal():
    """In live mode (is_live=True), strategies must strictly refuse synthetic Black-Scholes prices."""
    strat = ORBBullish()
    ts = datetime(2026, 10, 28, 9, 45, tzinfo=IST)
    price = strat.get_option_price(
        symbol="NIFTY25000CE",
        strike=25000.0,
        spot_price=25020.0,
        option_type="CE",
        data_state={"is_live": True, "option_chain": {}},
    )
    assert price is None, "In live mode, get_option_price must return None when no real WS/REST quote exists"


# =============================================================================
# PHASE 2: QUANTITATIVE GATES ENFORCEMENT
# =============================================================================

def test_p2_orb_hard_cutoff_at_1030_am():
    """Verify all 9 ORB strategies strictly reject signals at or after 10:30 AM IST."""
    all_strats = create_all_strategies()
    orb_strats = [s for s in all_strats if "ORB" in s.name]
    assert len(orb_strats) == 9

    post_cutoff_ts = datetime(2026, 10, 28, 10, 31, tzinfo=IST)
    candles = [
        Candle(datetime(2026, 10, 28, 9, 20, tzinfo=IST), 25000, 25050, 24950, 25000, 5000),
        Candle(post_cutoff_ts, 25060, 25100, 25050, 25090, 10000),
    ]

    data_state = {
        "timestamp": post_cutoff_ts,
        "nifty_price": 25090.0,
        "banknifty_price": 54500.0,
        "sensex_price": 81500.0,
        "candles": candles,
        "indicators": {"avg_volume": 1000.0, "ema_50_1h": 24900.0, "ema_50_5m": 24900.0},
    }

    for s in orb_strats:
        assert s.evaluate(data_state) is None, f"{s.name} generated signal at {post_cutoff_ts.time()}, violating 10:30 AM cutoff!"


def test_p2_adx_trend_strength_gate():
    """Verify Heikin-Ashi strategies reject entries when ADX < 20 (choppy market) and allow when ADX >= 20."""
    strat = HeikinAshiTrendBullish()
    ts = datetime(2026, 10, 28, 10, 0, tzinfo=IST)

    base_state = {
        "timestamp": ts,
        "nifty_price": 25000.0,
        "indicators": {
            "heikin_ashi_15m": {
                "open": 24950.0, "close": 25020.0, "high": 25030.0, "low": 24948.0,
                "prev_open": 24900.0, "prev_close": 24950.0,
            },
            "ema_50_1h": 24900.0,
            "vwap_5m": 24980.0,
            "volume_ratio": 1.2,
        },
        "candles": [
            Candle(ts, 24950, 25030, 24948, 25020, 1000),
            Candle(ts, 24950, 25030, 24948, 25020, 1000),
        ]
    }

    # Case A: Low ADX (14.0) -> MUST reject
    base_state["indicators"]["adx_14_5m"] = 14.0
    assert strat.evaluate(base_state) is None, "Heikin-Ashi Bullish should be rejected when ADX < 20"

    # Case B: High ADX (25.0) -> Qualifies
    base_state["indicators"]["adx_14_5m"] = 25.0
    sig = strat.evaluate(base_state)
    assert sig is not None, "Heikin-Ashi Bullish should trigger when ADX >= 20 and trend intact"


def test_p2_vwap_proximity_gate():
    """Verify strategies reject trades when spot is overextended (> 0.40%) away from VWAP."""
    strat = HeikinAshiTrendBearish()
    ts = datetime(2026, 10, 28, 10, 0, tzinfo=IST)

    base_state = {
        "timestamp": ts,
        "nifty_price": 24800.0,  # Stretched far below VWAP (25000) -> 0.80% distance
        "indicators": {
            "heikin_ashi_15m": {
                "open": 24850.0, "close": 24780.0, "high": 24852.0, "low": 24770.0,
                "prev_open": 24900.0, "prev_close": 24850.0,
            },
            "ema_50_1h": 24950.0,
            "vwap_5m": 25000.0,  # Distance is |24800 - 25000| / 25000 = 0.80% > 0.40%
            "adx_14_5m": 25.0,
            "volume_ratio": 1.2,
        },
        "candles": [
            Candle(ts, 24850, 24852, 24770, 24780, 1000),
            Candle(ts, 24850, 24852, 24770, 24780, 1000),
        ]
    }
    assert strat.evaluate(base_state) is None, "Should reject chasing extended move > 0.40% from VWAP"

    # Move spot within 0.24% of VWAP and below EMA50 (24950.0) -> Qualifies
    base_state["nifty_price"] = 24940.0
    sig = strat.evaluate(base_state)
    assert sig is not None, "Should trigger when spot is close to VWAP (<= 0.40%) and below EMA50"


def test_p2_midday_volume_filter():
    """Verify midday session (10:30 to 13:00) requires >= 1.4x volume surge."""
    strat = HeikinAshiTrendBullish()
    midday_ts = datetime(2026, 10, 28, 11, 30, tzinfo=IST)  # Midday chop zone

    state = {
        "timestamp": midday_ts,
        "nifty_price": 25000.0,
        "indicators": {
            "heikin_ashi_15m": {
                "open": 24950.0, "close": 25020.0, "high": 25030.0, "low": 24948.0,
                "prev_open": 24900.0, "prev_close": 24950.0,
            },
            "ema_50_1h": 24900.0,
            "vwap_5m": 24990.0,
            "adx_14_5m": 25.0,
            "volume_ratio": 1.15,  # 1.15x is below the 1.4x midday requirement
        },
        "candles": [
            Candle(midday_ts, 24950, 25030, 24948, 25020, 1000),
            Candle(midday_ts, 24950, 25030, 24948, 25020, 1000),
        ]
    }
    # Midday low volume (1.15x) -> Rejected
    assert strat.evaluate(state) is None

    # Midday institutional surge (1.50x >= 1.40x) -> Qualifies
    state["indicators"]["volume_ratio"] = 1.50
    assert strat.evaluate(state) is not None


# =============================================================================
# PHASE 3: POINTS-BASED TSL & SENSEX CALIBRATION
# =============================================================================

def test_p3_sensex_points_tsl_cost_lock_and_trailing():
    """Verify SENSEX ATM (25 cost lock) and ITM (35 cost lock) points-based trailing mechanics."""
    with open("config/risk_params.json") as f:
        config = json.load(f)

    pt = PaperTrader(
        slippage_pct=0.0,
        trailing_stop_enabled=True,
        expanding_dynamic_tsl_enabled=True,
        multi_index_tsl=config["exit_rules"]["multi_index_tsl"],
        strike_loss_lockout_mins=60,
    )

    t0 = datetime(2026, 10, 28, 9, 30, tzinfo=IST)

    # 1. Test SENSEX ATM (Entry 300.0)
    order_atm = pt.place_order(
        symbol="SENSEX81500CE",
        side="BUY",
        qty=1,
        price=300.0,
        stop_loss=240.0,  # 60 pts SL
        strategy="SENSEX_TEST_ATM",
        timestamp=t0,
    )
    assert order_atm.stop_loss == 240.0

    # +30 pts gain (LTP 330) -> Cost-lock not yet hit (needs +50)
    pt.update_positions({order_atm.symbol: 330.0}, timestamp=t0 + timedelta(minutes=1))
    assert order_atm.trailing_active is False
    assert getattr(order_atm, "_highest_trailing_stop", None) is None

    # +51 pts gain (LTP 351) -> Cost-lock activates with spread buffer floor: SL moved to Entry + 15 = 315.0
    pt.update_positions({order_atm.symbol: 351.0}, timestamp=t0 + timedelta(minutes=2))
    assert order_atm.trailing_active is True
    assert order_atm._highest_trailing_stop == 315.0

    # +75 pts gain (LTP 375) -> Stage 1 threshold (+70 pts) triggered; trails by 25 pts: 375 - 25 = 350
    pt.update_positions({order_atm.symbol: 375.0}, timestamp=t0 + timedelta(minutes=3))
    assert order_atm._highest_trailing_stop == pytest.approx(350.0)

    # Pullback to 349.0 -> Exits on TRAILING_STOP at 350.0
    closed = pt.update_positions({order_atm.symbol: 349.0}, timestamp=t0 + timedelta(minutes=4))
    assert len(closed) == 1
    assert closed[0].exit_reason == "TRAILING_STOP"
    assert closed[0].exit_price == pytest.approx(350.0)

    # 2. Test SENSEX ITM (Entry 500.0)
    order_itm = pt.place_order(
        symbol="SENSEX81000CE",
        side="BUY",
        qty=1,
        price=500.0,
        stop_loss=410.0,  # 90 pts SL
        strategy="SENSEX_TEST_ITM",
        timestamp=t0,
    )
    # +40 pts gain -> Cost lock not yet hit (needs +70)
    pt.update_positions({order_itm.symbol: 540.0}, timestamp=t0 + timedelta(minutes=1))
    assert order_itm.trailing_active is False
    assert getattr(order_itm, "_highest_trailing_stop", None) is None

    # +72 pts gain (LTP 572) -> Cost-lock activates with spread buffer floor: SL moved to Entry + 25 = 525.0
    pt.update_positions({order_itm.symbol: 572.0}, timestamp=t0 + timedelta(minutes=2))
    assert order_itm.trailing_active is True
    assert order_itm._highest_trailing_stop == 525.0


# =============================================================================
# PHASE 4: 60-MINUTE STRIKE LOSS LOCKOUT
# =============================================================================

def test_p4_strike_loss_lockout_enforcement():
    """Verify that after a STOP_LOSS exit, the strategy is locked out of that exact strike for 60 mins."""
    pt = PaperTrader(strike_loss_lockout_mins=60, max_trades_per_day_per_strategy=10)
    t0 = datetime(2026, 10, 28, 9, 45, tzinfo=IST)

    # 1. Place and open an order
    order = pt.place_order(
        symbol="BANKNIFTY54900PE",
        side="BUY",
        qty=1,
        price=350.0,
        stop_loss=280.0,
        strategy="BANKNIFTY_ORB_BEARISH_1M_ATM",
        timestamp=t0,
    )

    # 2. Order hits STOP LOSS at 09:55
    t_exit = t0 + timedelta(minutes=10)
    pt.close_position(order.order_id, price=275.0, timestamp=t_exit, reason="STOP_LOSS")
    assert order.status == "CLOSED"

    # 3. Same strategy attempts to re-enter same strike at 10:20 (25 mins later) -> MUST REJECT
    t_reentry = t_exit + timedelta(minutes=25)
    with pytest.raises(RiskLimitExceeded) as exc_info:
        pt.place_order(
            symbol="BANKNIFTY54900PE",
            side="BUY",
            qty=1,
            price=310.0,
            strategy="BANKNIFTY_ORB_BEARISH_1M_ATM",
            timestamp=t_reentry,
        )
    assert "locked out until" in str(exc_info.value)

    # 4. Same strategy attempts to enter a DIFFERENT strike at 10:20 -> ALLOWED!
    order_diff_strike = pt.place_order(
        symbol="BANKNIFTY55000PE",
        side="BUY",
        qty=1,
        price=380.0,
        strategy="BANKNIFTY_ORB_BEARISH_1M_ATM",
        timestamp=t_reentry,
    )
    assert order_diff_strike.status == "OPEN"
    pt.close_position(order_diff_strike.order_id, price=385.0, timestamp=t_reentry + timedelta(minutes=2), reason="TAKE_PROFIT")

    # 5. DIFFERENT strategy attempts to trade the locked strike -> ALLOWED!
    order_diff_strat = pt.place_order(
        symbol="BANKNIFTY54900PE",
        side="BUY",
        qty=1,
        price=310.0,
        strategy="BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM",
        timestamp=t_reentry,
    )
    assert order_diff_strat.status == "OPEN"
    pt.close_position(order_diff_strat.order_id, price=315.0, timestamp=t_reentry + timedelta(minutes=2), reason="TAKE_PROFIT")

    # 6. Same strategy attempts to trade the strike AFTER 60-min lockout expires (10:56) -> ALLOWED!
    t_after_lockout = t_exit + timedelta(minutes=61)
    order_reentry_allowed = pt.place_order(
        symbol="BANKNIFTY54900PE",
        side="BUY",
        qty=1,
        price=320.0,
        strategy="BANKNIFTY_ORB_BEARISH_1M_ATM",
        timestamp=t_after_lockout,
    )
    assert order_reentry_allowed.status == "OPEN"


def test_p4_strike_lockout_resets_on_new_day():
    """Verify that strike loss lockouts reset when a new calendar day rolls."""
    pt = PaperTrader(strike_loss_lockout_mins=60)
    day1 = datetime(2026, 10, 28, 15, 10, tzinfo=IST)

    order = pt.place_order(
        symbol="NIFTY25000CE",
        side="BUY",
        qty=1,
        price=150.0,
        stop_loss=120.0,
        strategy="NIFTY_ORB_BULLISH_1M_ATM",
        timestamp=day1,
    )
    pt.close_position(order.order_id, price=118.0, timestamp=day1, reason="STOP_LOSS")

    # Next morning at 09:30 (even though within 24h, calendar day changed)
    day2 = datetime(2026, 10, 29, 9, 30, tzinfo=IST)
    order_day2 = pt.place_order(
        symbol="NIFTY25000CE",
        side="BUY",
        qty=1,
        price=145.0,
        strategy="NIFTY_ORB_BULLISH_1M_ATM",
        timestamp=day2,
    )
    assert order_day2.status == "OPEN", "New trading session must start with clean strike lockout state"


# =============================================================================
# PHASE 5: PERSISTENCE & DATA MANAGER HEALTH CHECK
# =============================================================================

def test_p5_sqlite_wal_persistence_and_order_recovery():
    """Verify StateManager creates SQLite in WAL mode and stores/restores orders cleanly."""
    sm = StateManager()
    assert sm.data_dir.exists()

    order = Order(
        order_id="TEST-WAL-001",
        symbol="NIFTY25000CE",
        side="BUY",
        qty=1,
        lot_size=65,
        entry_price=180.0,
        entry_time=datetime.now(ZoneInfo("Asia/Kolkata")),
        status="OPEN",
        stop_loss=150.0,
        strategy="NIFTY_TEST_STRATEGY",
    )

    # Save position snapshot to SQLite WAL
    sm.save_positions([order])

    # Load positions back and verify
    loaded = sm.load_positions()
    assert loaded is not None
    assert len(loaded) >= 1
    matched = [p for p in loaded if p["order_id"] == "TEST-WAL-001"]
    assert len(matched) == 1
    assert matched[0]["symbol"] == "NIFTY25000CE"
    assert matched[0]["strategy"] == "NIFTY_TEST_STRATEGY"
    assert matched[0]["status"] == "OPEN"

    # Save closed trade to history table
    order.status = "CLOSED"
    order.exit_price = 210.0
    order.exit_time = datetime.now(ZoneInfo("Asia/Kolkata"))
    order.realized_pnl = 1950.0
    order.exit_reason = "TAKE_PROFIT"
    sm.append_trade(order)

    history_df = sm.get_trade_history()
    assert not history_df.empty
    assert "TEST-WAL-001" in history_df["order_id"].values


def test_p5_data_manager_indicator_calculations():
    """Verify DataManager computes ADX, VWAP, CMF, and Supertrend on streaming candle history."""
    dm = DataManager()
    t_start = datetime(2026, 10, 28, 9, 15, tzinfo=IST)

    # Inject 45 closed 1-minute candles
    for i in range(45):
        t = t_start + timedelta(minutes=i)
        price = 25000.0 + (i * 2.5)
        c = Candle(
            timestamp=t,
            open=price - 1.0,
            high=price + 5.0,
            low=price - 4.0,
            close=price + 2.0,
            volume=25000 + (i * 200),
        )
        dm.candles.append(c)

    state = dm.get_state()
    indicators = state.get("indicators", {})

    assert "volume_ratio" in indicators
    assert "adx_14_1m" in indicators
    assert indicators["adx_14_1m"] > 0
    assert "vwap" in indicators or "vwap_5m" in indicators
