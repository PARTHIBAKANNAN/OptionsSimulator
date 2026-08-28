import json
import sys
from pathlib import Path
from datetime import datetime
import zoneinfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Lot sizes for PnL scaling if needed, though realized_pnl in json is already total PnL
LOT_SIZES = {"NIFTY": 65, "SENSEX": 20, "BANKNIFTY": 30}

def parse_ist_time(ts_str):
    """Parses ISO timestamp string to IST time object."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        else:
            dt = dt.astimezone(IST)
        return dt.time()
    except Exception:
        return None

def calc_metrics(trades):
    if not trades:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "pnl": 0.0}
    
    total = len(trades)
    wins = len([t for t in trades if t.get("realized_pnl", 0) > 0])
    losses = len([t for t in trades if t.get("realized_pnl", 0) <= 0])
    win_rate = (wins / total * 100) if total > 0 else 0.0
    tot_pnl = sum(t.get("realized_pnl", 0) for t in trades)
    
    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "pnl": tot_pnl,
    }

def main():
    history_dir = PROJECT_ROOT / "data" / "backtest_results"
    history_files = list(history_dir.glob("*_history.json"))
    
    if not history_files:
        print("Error: No *_history.json files found in data/backtest_results")
        return

    print(f"=== 1-YEAR BACKTEST AUDIT: ALL {len(history_files)} STRATEGIES ===")
    print("Baseline (09:15+ IST) vs. Experimental Cutoff (Avoiding 09:15 - 09:25 AM IST)\n")

    results = []

    for fpath in sorted(history_files):
        strategy_name = fpath.name.replace("_history.json", "")
        with open(fpath, "r", encoding="utf-8") as f:
            trades = json.load(f)

        # Baseline: All trades
        base_metrics = calc_metrics(trades)

        # Experimental: Exclude trades with entry_time between 09:15:00 and 09:25:00 AM IST
        filtered_trades = []
        for t in trades:
            entry_t = parse_ist_time(t.get("entry_time"))
            if entry_t:
                # If entry time is between 09:15:00 and 09:24:59, skip
                if entry_t >= datetime.strptime("09:15:00", "%H:%M:%S").time() and entry_t < datetime.strptime("09:25:00", "%H:%M:%S").time():
                    continue
            filtered_trades.append(t)

        exp_metrics = calc_metrics(filtered_trades)

        pnl_diff = exp_metrics["pnl"] - base_metrics["pnl"]
        
        results.append({
            "strategy": strategy_name,
            "base_trades": base_metrics["trades"],
            "base_win_rate": base_metrics["win_rate"],
            "base_pnl": base_metrics["pnl"],
            "exp_trades": exp_metrics["trades"],
            "exp_win_rate": exp_metrics["win_rate"],
            "exp_pnl": exp_metrics["pnl"],
            "diff": pnl_diff,
        })

    # Group by Index (NIFTY, SENSEX, BANKNIFTY)
    print("=" * 115)
    print(f"{'Strategy Name':<42} | {'Base Trades':<11} | {'Base PnL (Rs)':<14} | {'Exp Trades':<10} | {'Exp PnL (Rs)':<14} | {'PnL Diff (Rs)':<13} | {'Base Win%':<9} | {'Exp Win%'}")
    print("=" * 115)

    tot_base_pnl = 0.0
    tot_exp_pnl = 0.0
    tot_base_trades = 0
    tot_exp_trades = 0

    for r in results:
        tot_base_pnl += r["base_pnl"]
        tot_exp_pnl += r["exp_pnl"]
        tot_base_trades += r["base_trades"]
        tot_exp_trades += r["exp_trades"]
        
        diff_str = f"+Rs.{r['diff']:,.2f}" if r["diff"] >= 0 else f"-Rs.{abs(r['diff']):,.2f}"
        
        print(f"{r['strategy']:<42} | {r['base_trades']:<11} | Rs.{r['base_pnl']:>11,.2f} | {r['exp_trades']:<10} | Rs.{r['exp_pnl']:>11,.2f} | {diff_str:>13} | {r['base_win_rate']:>8.1f}% | {r['exp_win_rate']:>8.1f}%")

    print("-" * 115)
    tot_diff = tot_exp_pnl - tot_base_pnl
    tot_diff_str = f"+Rs.{tot_diff:,.2f}" if tot_diff >= 0 else f"-Rs.{abs(tot_diff):,.2f}"
    print(f"{'TOTAL 32-STRATEGY MASTER PORTFOLIO':<42} | {tot_base_trades:<11} | Rs.{tot_base_pnl:>11,.2f} | {tot_exp_trades:<10} | Rs.{tot_exp_pnl:>11,.2f} | {tot_diff_str:>13}")
    print("=" * 115 + "\n")

    # Index Sub-Summaries
    for idx in ["NIFTY", "SENSEX", "BANKNIFTY"]:
        idx_res = [r for r in results if r["strategy"].startswith(idx)]
        b_pnl = sum(r["base_pnl"] for r in idx_res)
        e_pnl = sum(r["exp_pnl"] for r in idx_res)
        b_tr = sum(r["base_trades"] for r in idx_res)
        e_tr = sum(r["exp_trades"] for r in idx_res)
        d_pnl = e_pnl - b_pnl
        d_str = f"+Rs.{d_pnl:,.2f}" if d_pnl >= 0 else f"-Rs.{abs(d_pnl):,.2f}"
        print(f"[{idx} 1-YEAR SUB-TOTAL ({len(idx_res)} Strategies)]:")
        print(f"   Baseline P&L: Rs.{b_pnl:,.2f} ({b_tr} trades)")
        print(f"   09:25+ Cutoff P&L: Rs.{e_pnl:,.2f} ({e_tr} trades)")
        print(f"   Net P&L Difference: {d_str} ({(d_pnl/abs(b_pnl)*100 if b_pnl!=0 else 0):+.2f}%)\n")

if __name__ == '__main__':
    main()
