"""
5-Minute NIFTY Strategy Suite Backtest
======================================
Replays 18,450 5-minute NIFTY candles (245 trading days: Aug 2025 - Aug 2026) across
both Bullish (CE) and Bearish (PE) 5-minute strategies with ITM strike selection (~Rs.200).

Exit Rules:
  - Take Profit: 50 option premium points (+25% on Rs.200 option)
  - Stop Loss: 20% of entry premium
  - Trailing Stop: armed at +15% gain, trails 15% from peak
  - Time Exit: 90 minutes (18 5-minute bars)
"""
import json
import math
import sys
import time
from datetime import time as dtime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.data_manager import Candle, DataManager
from src.simulator.paper_trader import PaperTrader, RiskLimitExceeded
from src.strategies.base_strategy import BaseStrategy, Signal
from src.backtester.report import build_report
from src.utils.options_pricing import black_scholes_price, next_weekly_expiry_days, parse_option_symbol

NIFTY_5M_CSV = PROJECT_ROOT / "data" / "historical" / "nifty_5min.csv"
OUTPUT_REPORT = PROJECT_ROOT / "data" / "backtest_results" / "nifty_5min_report.json"

ORB_WINDOW_START = dtime(9, 15)
ORB_WINDOW_END = dtime(9, 30)


# ============================================================================
# 5-Minute Strategy Implementations
# ============================================================================

class ORBBullish5M(BaseStrategy):
    """5-min Opening Range Breakout: 09:15-09:30 range broken upward on a 5m close."""
    def __init__(self):
        super().__init__(name="ORB_BULLISH_5M", direction="CE", strike_step=50, underlying="NIFTY")
        self._range_day = None
        self._range_high = None
        self._range_low = None

    def evaluate(self, data_state: dict):
        candles = data_state.get("candles", [])
        if len(candles) < 2:
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

        if prev.close <= self._range_high < current.close:
            if ema50_1h is None or current.close > ema50_1h:
                nifty = current.close
                symbol, strike = self.select_strike(nifty, "CE")
                price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
                return Signal(
                    strategy=self.name, direction="CE", action="BUY", strike=symbol,
                    confidence=0.80, rationale=f"5m ORB breakout above {self._range_high:.1f}",
                    entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
                )
        return None


class ORBBearish5M(BaseStrategy):
    """5-min Opening Range Breakdown: 09:15-09:30 range broken downward on a 5m close."""
    def __init__(self):
        super().__init__(name="ORB_BEARISH_5M", direction="PE", strike_step=50, underlying="NIFTY")
        self._range_day = None
        self._range_high = None
        self._range_low = None

    def evaluate(self, data_state: dict):
        candles = data_state.get("candles", [])
        if len(candles) < 2:
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

        if prev.close >= self._range_low > current.close:
            if ema50_1h is None or current.close < ema50_1h:
                nifty = current.close
                symbol, strike = self.select_strike(nifty, "PE")
                price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
                return Signal(
                    strategy=self.name, direction="PE", action="BUY", strike=symbol,
                    confidence=0.80, rationale=f"5m ORB breakdown below {self._range_low:.1f}",
                    entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
                )
        return None


class MACDBullish5M(BaseStrategy):
    """5-minute MACD crossover confirmed by 1H 50-EMA trend."""
    def __init__(self):
        super().__init__(name="MACD_BULLISH_5M", direction="CE", strike_step=50, underlying="NIFTY")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        macd_hist = indicators.get("macd_histogram_5m")
        macd_hist_prev = indicators.get("macd_histogram_5m_prev")
        ema50 = indicators.get("ema_50_1h")
        if None in (macd_hist, macd_hist_prev, ema50):
            return None

        if macd_hist > 0 and macd_hist_prev <= 0 and nifty > ema50:
            symbol, strike = self.select_strike(nifty, "CE")
            price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.75, rationale="5m MACD bullish crossover above 1H 50-EMA",
                entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
            )
        return None


class MACDBearish5M(BaseStrategy):
    """5-minute MACD cross-under confirmed by 1H 50-EMA trend."""
    def __init__(self):
        super().__init__(name="MACD_BEARISH_5M", direction="PE", strike_step=50, underlying="NIFTY")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        macd_hist = indicators.get("macd_histogram_5m")
        macd_hist_prev = indicators.get("macd_histogram_5m_prev")
        ema50 = indicators.get("ema_50_1h")
        if None in (macd_hist, macd_hist_prev, ema50):
            return None

        if macd_hist < 0 and macd_hist_prev >= 0 and nifty < ema50:
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.75, rationale="5m MACD bearish breakdown below 1H 50-EMA",
                entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
            )
        return None


class HeikinAshiTrendBearish5M(BaseStrategy):
    """5-minute Heikin-Ashi breakdown: 2 red 5m HA candles with little/no upper wick."""
    def __init__(self):
        super().__init__(name="HEIKIN_ASHI_BEARISH_5M", direction="PE", strike_step=50, underlying="NIFTY")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        nifty = data_state.get("nifty_price")
        if nifty is None:
            return None

        ha = indicators.get("heikin_ashi_5m")
        ema50 = indicators.get("ema_50_1h")
        if ha is None or ema50 is None:
            return None

        body = ha["open"] - ha["close"]
        current_bearish = body > 0
        prev_bearish = ha["prev_open"] > ha["prev_close"]
        if not (current_bearish and prev_bearish and nifty < ema50):
            return None

        upper_wick = ha["high"] - ha["open"]
        if upper_wick > 0.15 * body:
            return None

        symbol, strike = self.select_strike(nifty, "PE")
        price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
        return Signal(
            strategy=self.name, direction="PE", action="BUY", strike=symbol,
            confidence=0.75, rationale="5m Heikin-Ashi bearish continuation below 1H 50-EMA",
            entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
        )


class SupportBounceBullish5M(BaseStrategy):
    """5-min pullback to 20-EMA/50-EMA in established uptrend with strong bullish close."""
    def __init__(self):
        super().__init__(name="SUPPORT_BOUNCE_5M", direction="CE", strike_step=50, underlying="NIFTY")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        candle_range = current.high - current.low
        if candle_range <= 0:
            return None

        closes_strong = (current.close - current.low) / candle_range >= 0.60

        if (prev.low <= ema20_5m and current.close > ema20_5m and current.close > ema50_1h
                and closes_strong):
            nifty = current.close
            symbol, strike = self.select_strike(nifty, "CE")
            price = self.get_option_price(symbol, strike, nifty, "CE", data_state)
            return Signal(
                strategy=self.name, direction="CE", action="BUY", strike=symbol,
                confidence=0.70, rationale=f"5m support bounce at 20-EMA ({ema20_5m:.1f})",
                entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
            )
        return None


class ResistanceRejectionBearish5M(BaseStrategy):
    """5-min test of 20-EMA from below with strong rejection close in downtrend."""
    def __init__(self):
        super().__init__(name="RESISTANCE_REJECTION_5M", direction="PE", strike_step=50, underlying="NIFTY")

    def evaluate(self, data_state: dict):
        indicators = data_state.get("indicators", {})
        candles = data_state.get("candles", [])
        if len(candles) < 2:
            return None

        ema20_5m = indicators.get("ema_20_5m")
        ema50_1h = indicators.get("ema_50_1h")
        if ema20_5m is None or ema50_1h is None:
            return None

        current, prev = candles[-1], candles[-2]
        candle_range = current.high - current.low
        if candle_range <= 0:
            return None

        closes_weak = (current.high - current.close) / candle_range >= 0.60

        if (prev.high >= ema20_5m and current.close < ema20_5m and current.close < ema50_1h
                and closes_weak):
            nifty = current.close
            symbol, strike = self.select_strike(nifty, "PE")
            price = self.get_option_price(symbol, strike, nifty, "PE", data_state)
            return Signal(
                strategy=self.name, direction="PE", action="BUY", strike=symbol,
                confidence=0.70, rationale=f"5m resistance rejection at 20-EMA ({ema20_5m:.1f})",
                entry_price=price, timestamp=data_state["timestamp"], underlying=self.underlying,
            )
        return None


# ============================================================================
# ITM Strike Selector & Mark-to-Market
# ============================================================================

def select_itm_strike(spot: float, option_type: str, dte: float, target_premium: float = 200.0) -> tuple[str, float]:
    strike_step = 50
    atm_strike = round(spot / strike_step) * strike_step
    best_strike = atm_strike
    best_price = black_scholes_price(spot, atm_strike, dte, option_type)
    best_diff = abs(best_price - target_premium)

    for k in range(1, 12):
        strike = atm_strike - k * strike_step if option_type == "CE" else atm_strike + k * strike_step
        price = black_scholes_price(spot, strike, dte, option_type)
        diff = abs(price - target_premium)
        if diff < best_diff:
            best_diff = diff
            best_strike = strike
            best_price = price
        elif price > target_premium + 100:
            break

    return f"NIFTY{int(best_strike)}{option_type}", float(best_strike)


def mark_to_market(trader: PaperTrader, state: dict) -> dict:
    prices = {}
    spot = state["nifty_price"]
    timestamp = state["timestamp"]
    dte = next_weekly_expiry_days(timestamp, index="NIFTY")
    for order in trader.get_positions():
        strike, option_type = parse_option_symbol(order.symbol)
        if strike is None:
            continue
        prices[order.symbol] = black_scholes_price(
            spot=spot, strike=strike, days_to_expiry=dte, option_type=option_type
        )
    return prices


# ============================================================================
# Backtest Engine Runner
# ============================================================================

def run_5m_strategy(strategy: BaseStrategy, df: pd.DataFrame, target_tp_pts: float = 50.0) -> tuple[object, list]:
    data_manager = DataManager(window_size=3000, underlying="NIFTY")
    trader = PaperTrader(
        initial_capital=1_000_000,
        lot_size=65,
        max_concurrent_positions=5,
        max_daily_loss=5000,
        max_trades_per_day_per_strategy=2,
        trailing_stop_enabled=True,
        trailing_activation_pct=15.0,
        trailing_stop_pct=15.0,
    )

    stop_loss_pct = 20.0
    time_exit_mins = 90  # 18 5-minute bars

    for row in df.itertuples(index=False):
        candle = Candle(
            timestamp=row.Timestamp, open=row.Open, high=row.High,
            low=row.Low, close=row.Close, volume=int(row.Volume)
        )
        data_manager.replay_candle(candle)
        state = data_manager.get_state()
        if state["nifty_price"] is None:
            continue

        current_prices = mark_to_market(trader, state)
        trader.update_positions(current_prices, timestamp=state["timestamp"], time_exit_mins=time_exit_mins)

        signal = strategy.evaluate(state)
        if signal is None:
            continue

        spot = state["nifty_price"]
        ts = state["timestamp"]
        dte = next_weekly_expiry_days(ts, index="NIFTY")

        symbol, strike = select_itm_strike(spot, signal.direction, dte, target_premium=200.0)
        entry_price = black_scholes_price(spot, strike, dte, signal.direction)

        stop_loss = max(entry_price * (1 - stop_loss_pct / 100), 0.05)
        take_profit = entry_price + target_tp_pts

        try:
            trader.place_order(
                symbol=symbol, side="BUY", qty=1, price=entry_price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=strategy.name, timestamp=ts, lot_size=65
            )
        except RiskLimitExceeded:
            continue

    history = trader.get_trade_history()
    report = build_report(strategy.name, strategy.direction, history, 1_000_000)
    return report, history


def main():
    t0 = time.time()
    print("\n" + "=" * 90)
    print("  5-MINUTE NIFTY STRATEGY SUITE BACKTEST (1-YEAR: 18,450 BARS)")
    print("  Strike Selection: ITM (~Rs.200) | Take Profit: 50 pts | SL: 20% | Trailing: +15%/15%")
    print("=" * 90 + "\n")

    df = pd.read_csv(NIFTY_5M_CSV, parse_dates=["Timestamp"])
    print(f"Loaded {len(df):,} 5-minute candles: {df['Timestamp'].min().date()} -> {df['Timestamp'].max().date()}\n")

    strategies = [
        ORBBullish5M(),
        MACDBullish5M(),
        SupportBounceBullish5M(),
        ORBBearish5M(),
        MACDBearish5M(),
        HeikinAshiTrendBearish5M(),
        ResistanceRejectionBearish5M(),
    ]

    results = {}
    print(f"  {'Strategy':<30} | {'Trades':>6} {'Wins':>5} {'Losses':>6} {'Win Rate':>8} {'PF':>6} | {'Total P&L (Rs)':>14} | {'Max DD%':>7}")
    print("  " + "-" * 88)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for strat in strategies:
        r, history = run_5m_strategy(strat, df, target_tp_pts=50.0)
        total_pnl += r.total_pnl
        total_trades += r.total_trades
        total_wins += r.winning_trades

        pf_str = f"{r.profit_factor:.2f}" if r.profit_factor < 900 else "inf"
        print(f"  {r.strategy:<30} | {r.total_trades:>6} {r.winning_trades:>5} {r.losing_trades:>6} {r.win_rate:>7.1f}% {pf_str:>6} | Rs.{r.total_pnl:>10,.2f} | {r.max_drawdown_pct:>6.2f}%")

        results[r.strategy] = {
            "direction": r.direction,
            "total_trades": r.total_trades,
            "winning_trades": r.winning_trades,
            "losing_trades": r.losing_trades,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "total_pnl": r.total_pnl,
            "max_drawdown_pct": r.max_drawdown_pct,
            "exit_reasons": {
                "take_profit_hits": sum(1 for o in history if o.exit_reason == "TAKE_PROFIT"),
                "trailing_stop_hits": sum(1 for o in history if o.exit_reason == "TRAILING_STOP"),
                "stop_loss_hits": sum(1 for o in history if o.exit_reason == "STOP_LOSS"),
                "time_exit_hits": sum(1 for o in history if o.exit_reason == "TIME_EXIT"),
            }
        }

    print("  " + "-" * 88)
    overall_win_rate = (total_wins / total_trades * 100) if total_trades else 0
    print(f"  {'PORTFOLIO TOTAL (NIFTY 5M)':<30} | {total_trades:>6} {total_wins:>5} {total_trades - total_wins:>6} {overall_win_rate:>7.1f}% {'—':>6} | Rs.{total_pnl:>10,.2f} |")
    print("=" * 90)

    print(f"\nCompleted in {time.time() - t0:.1f}s")
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Report saved to {OUTPUT_REPORT}\n")


if __name__ == "__main__":
    main()
