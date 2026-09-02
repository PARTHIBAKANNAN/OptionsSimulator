import json
from pathlib import Path

RESULTS_DIR = Path("data/backtest_results")
NEW_PATH = RESULTS_DIR / "report.json"
OLD_PATH = RESULTS_DIR / "pre_fix_backup" / "report_OLD_fake_backtest.json"

with open(NEW_PATH) as f:
    new = json.load(f)

with open(OLD_PATH) as f:
    old = json.load(f)

print("=" * 115)
print(f"{'Strategy Name':<42} | {'Old WR':<8} | {'New WR':<8} | {'Diff':<8} | {'Trades':<8} | {'New PnL (INR)':<15} | {'Old PnL (INR)':<15}")
print("=" * 115)

for s in sorted(new.keys()):
    old_data = old.get(s, {})
    old_wr = old_data.get("win_rate", 0.0)
    old_pnl = old_data.get("total_pnl", 0.0)
    new_wr = new[s]["win_rate"]
    new_pnl = new[s]["total_pnl"]
    new_tr = new[s]["total_trades"]
    wr_diff = new_wr - old_wr
    print(f"{s:<42} | {old_wr:6.1f}% | {new_wr:6.1f}% | {wr_diff:+6.1f}% | {new_tr:^8d} | Rs.{new_pnl:11,.2f} | Rs.{old_pnl:11,.2f}")

tot_trades = sum(s.get("total_trades", 0) for s in new.values())
tot_pnl = sum(s.get("total_pnl", 0) for s in new.values())
tot_old_pnl = sum(s.get("total_pnl", 0) for s in old.values())
print("=" * 115)
print(f"PORTFOLIO TOTAL: {len(new)} Strategies | {tot_trades:,} Trades")
print(f"Old Fake Portfolio P&L: Rs.{tot_old_pnl:,.2f} -> New Real Portfolio P&L: Rs.{tot_pnl:,.2f}")
print("=" * 115)
