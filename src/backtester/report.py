"""BacktestReport dataclass, metric calculation from a trade list, and top-6 (3 CE + 3 PE) selection."""
import json
import math
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BacktestReport:
    strategy: str
    direction: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    consecutive_wins: int
    consecutive_losses: int


def build_report(strategy_name: str, direction: str, closed_orders: list, initial_capital: float) -> BacktestReport:
    if not closed_orders:
        return BacktestReport(strategy_name, direction, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0)

    pnls = [o.realized_pnl for o in closed_orders]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    # float("inf") isn't valid JSON (RFC 8259) — it round-trips fine through Python's own
    # json.dumps/loads (non-standard extension), but crashes FastAPI's stricter response
    # encoder. 999.99 is a conventional "effectively infinite" sentinel: sorts highest, displays
    # sanely, and only ever occurs with zero losing trades (a tiny/unreliable sample either way).
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999.99 if gross_profit > 0 else 0.0

    equity = initial_capital
    peak = initial_capital
    max_dd = 0.0
    max_dd_pct = 0.0
    consecutive_wins = max_consecutive_wins = 0
    consecutive_losses = max_consecutive_losses = 0

    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        max_dd = max(max_dd, drawdown)
        max_dd_pct = max(max_dd_pct, drawdown / peak * 100 if peak > 0 else 0)

        if pnl > 0:
            consecutive_wins += 1
            consecutive_losses = 0
        else:
            consecutive_losses += 1
            consecutive_wins = 0
        max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

    return BacktestReport(
        strategy=strategy_name,
        direction=direction,
        total_trades=len(closed_orders),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=round(len(wins) / len(closed_orders) * 100, 2),
        profit_factor=profit_factor,
        total_pnl=round(sum(pnls), 2),
        max_drawdown=round(max_dd, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        consecutive_wins=max_consecutive_wins,
        consecutive_losses=max_consecutive_losses,
    )


def select_top_n(reports: dict, direction: str, n: int = 3) -> list[BacktestReport]:
    candidates = [r for r in reports.values() if r.direction == direction and r.total_trades > 0]
    candidates.sort(key=lambda r: (r.profit_factor, r.win_rate), reverse=True)
    return candidates[:n]


def print_backtest_report(reports: dict) -> None:
    ce_ranked = sorted([r for r in reports.values() if r.direction == "CE"],
                        key=lambda r: (r.profit_factor, r.win_rate), reverse=True)
    pe_ranked = sorted([r for r in reports.values() if r.direction == "PE"],
                        key=lambda r: (r.profit_factor, r.win_rate), reverse=True)
    hedge = [r for r in reports.values() if r.direction == "HEDGE"]

    def _print_group(title, ranked, top_n):
        print(f"\n{title}")
        print("-" * 80)
        print(f"{'Rank':<5}{'Strategy':<28}{'Trades':<8}{'Win%':<8}{'PF':<8}{'P&L':<12}{'DD%':<8}{'Status'}")
        print("-" * 80)
        for i, r in enumerate(ranked, 1):
            status = "DEPLOY" if i <= top_n and r.total_trades > 0 else "-"
            print(f"{i:<5}{r.strategy:<28}{r.total_trades:<8}{r.win_rate:<8}{r.profit_factor:<8}"
                  f"{r.total_pnl:<12}{r.max_drawdown_pct:<8}{status}")

    print("=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    _print_group("BULLISH (CE) STRATEGIES:", ce_ranked, 3)
    _print_group("BEARISH (PE) STRATEGIES:", pe_ranked, 3)

    if hedge:
        print("\nHEDGE STRATEGIES (expiry-day only — not ranked against directional strategies):")
        print("-" * 80)
        print(f"{'Strategy':<28}{'Trades':<8}{'Win%':<8}{'PF':<8}{'P&L':<12}{'DD%':<8}")
        print("-" * 80)
        for r in hedge:
            print(f"{r.strategy:<28}{r.total_trades:<8}{r.win_rate:<8}{r.profit_factor:<8}"
                  f"{r.total_pnl:<12}{r.max_drawdown_pct:<8}")

    deployed = select_top_n(reports, "CE", 3) + select_top_n(reports, "PE", 3)
    total_pnl = sum(r.total_pnl for r in deployed)
    avg_win_rate = sum(r.win_rate for r in deployed) / len(deployed) if deployed else 0
    print("\n" + "=" * 80)
    print(f"RECOMMENDED DEPLOYMENT: {len(deployed)} strategies")
    print(f"Total Backtest P&L: Rs.{total_pnl:,.2f}")
    print(f"Avg Win Rate: {avg_win_rate:.1f}%")
    print("=" * 80)


def save_report(reports: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: asdict(report) for name, report in reports.items()}
    payload["_selected"] = {
        "CE": [r.strategy for r in select_top_n(reports, "CE", 3)],
        "PE": [r.strategy for r in select_top_n(reports, "PE", 3)],
    }
    path.write_text(json.dumps(payload, indent=2))


def build_daily_breakdown(closed_orders: list) -> list[dict]:
    """Groups closed orders by entry date (the trading day the signal fired) into per-day stats."""
    by_day = defaultdict(list)
    for order in closed_orders:
        by_day[order.entry_time.date()].append(order)

    days = []
    cumulative_pnl = 0.0
    for day in sorted(by_day):
        orders = by_day[day]
        pnls = [o.realized_pnl for o in orders]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        day_pnl = round(sum(pnls), 2)
        cumulative_pnl = round(cumulative_pnl + day_pnl, 2)
        days.append({
            "date": day.isoformat(),
            "trades": len(orders),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(orders) * 100, 2),
            "pnl": day_pnl,
            "cumulative_pnl": cumulative_pnl,
        })
    return days


def save_daily_report(trade_histories: dict, path: Path) -> None:
    """trade_histories: {strategy_name: [closed Order, ...]} — see BacktestEngine.trade_histories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: build_daily_breakdown(orders) for name, orders in trade_histories.items()}
    path.write_text(json.dumps(payload, indent=2))


def required_capital_per_strategy(reports: dict, trade_histories: dict, buffer_pct: float = 30.0,
                                   round_to: float = 1000.0) -> dict:
    """Suggests standalone capital per strategy: what a single trade actually costs (the premium
    paid for a directional order, or the defined max_loss for an Iron Fly-style spread), plus a
    buffer_pct cushion (default 30%) to tolerate normal adverse moves — NOT sized to survive the
    worst historical drawdown outright. An earlier drawdown-multiple formula produced capital
    figures 6-9x larger than this (e.g. ~8.1L total vs ~90k across 9 strategies) because it was
    solving a different problem (survive a multi-week losing stretch without external top-ups)
    than the one actually being asked (what does it cost to place this trade, with a reasonable
    cushion). max_historical_drawdown is still reported alongside for visibility — several
    strategies' worst historical drawdown is 2-6x this capital figure, which is real risk
    information (the circuit breaker is what's meant to catch that, not the capital sizing).
    See docs/ARCHITECTURE.md.
    """
    result = {}
    for name, history in trade_histories.items():
        report = reports.get(name)
        if report is None or not history:
            continue

        first = history[0]
        if hasattr(first, "net_credit"):  # Iron Fly-style multi-leg position: risk = its defined max_loss
            per_trade_risk = sum(p.max_loss * p.qty * p.lot_size for p in history) / len(history)
        else:  # directional single-leg Order: risk = the premium actually paid
            per_trade_risk = sum(o.entry_price * o.qty * o.lot_size for o in history) / len(history)

        recommended = math.ceil(per_trade_risk * (1 + buffer_pct / 100) / round_to) * round_to

        result[name] = {
            "avg_trade_risk": round(per_trade_risk, 2),
            "max_historical_drawdown": report.max_drawdown,
            "recommended_capital": recommended,
        }
    return result


def save_capital_requirements(reports: dict, trade_histories: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(required_capital_per_strategy(reports, trade_histories), indent=2))


def load_capital_by_strategy(path: Path) -> dict:
    """Flattens a previously-saved capital_requirements.json into {strategy: recommended_capital},
    for feeding into PaperTrader's drawdown circuit breaker. Missing file -> {} (breaker disabled
    for every strategy until a capital_requirements.json exists from a prior run)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {name: info["recommended_capital"] for name, info in data.items()}
