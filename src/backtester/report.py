"""BacktestReport dataclass, metric calculation from a trade list, and top-6 (3 CE + 3 PE) selection."""
import json
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
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

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
