# PROMPT FOR NEXT CLAUDE INSTANCE

**Copy this entire section and paste it as your instructions when you take over this project.**

---

## Context

You are resuming work on a **44-strategy options trading backtester** for Indian markets (NIFTY, SENSEX, BANKNIFTY). The code has just been fixed by the previous Claude instance. Your job: validate the fixes by running a fresh 365-day backtest and reporting results.

**Current state:**
- All code is fixed (real indicators, dead code removed, per-index routing, percentage exits)
- All code is committed (git commit 121639a)
- Ready for fresh backtest validation
- Previous session ended because the user's Claude subscription is ending

**Your immediate task:** Run the backtest and report findings.

---

## What You Need to Know

### The Problem (Solved)

The system had:
1. **Fake indicators**: Supertrend, CMF, VWAP, Bollinger Bands names but wrong/missing code
2. **Dead code**: `rsi_14_5m` referenced but never computed, causing VWAP strategies to never fire
3. **Broken data routing**: All 44 strategies backtested against NIFTY prices, ignoring their own underlyings (SENSEX/BANKNIFTY)
4. **Mis-scaled exits**: Flat 150-point take-profit unreachable for NIFTY premiums (₹30–130 range)
5. **State-restating bugs**: Heikin-Ashi strategies fired on every tick in a trend because no cooldown

**Result of old bugs:** Ghost 97%+ win rates in backtest, but -₹8,950 loss in live trading (Aug 31 – Sep 2)

### The Solution (Already Implemented)

All fixed in commit 121639a:
- ✅ Real Supertrend, CMF, VWAP, Bollinger Bands implemented
- ✅ `rsi_14_5m` now computed in DataManager
- ✅ Per-index data routing: BacktestEngine loads 3 separate CSV files, routes strategies to correct underlying
- ✅ Exit rules rescaled: 40% TP, percentage-based trailing tiers
- ✅ ORB consistency, Heikin-Ashi cooldown fixed

---

## Your 3-Step Task

### Step 1: Validate Setup

```bash
cd /path/to/OptionsSimulator

# Check all modified code compiles
python -m py_compile src/utils/indicators.py src/data_manager.py src/backtester/backtest_engine.py

# Check CSV data exists and has rows
wc -l data/historical/*.csv  # Should show ~92,700 each

# Check config is valid JSON
python -m json.tool config/risk_params.json > /dev/null && echo "✓ Config valid"

# Run unit tests (should pass)
pytest tests/test_paper_trader.py -v
```

**If all green:** proceed to Step 2

**If errors:** 
- CSV files missing? Run `python fetch_365day_historical.py` (requires Fyers API credentials)
- Import errors? Check `src/data_manager.py` line ~200 for Supertrend/CMF/VWAP computation
- Test failures? They should be fixed; if not, update test assertions to match new percentage-based tier logic

### Step 2: Run Fresh Backtest

```bash
python main.py 2>&1 | tee backtest_output.log
```

**Expected:**
- Console output showing strategy initialization, data loading, then bar-by-bar progress
- Runtime: 30 min – 2 hours (44 strategies × 92,700 candles × 3 indices)
- Memory usage: 1–2 GB peak
- No exceptions (warnings are okay)

**Monitor with:**
```bash
# In another terminal, watch progress
tail -f backtest_output.log | grep -E "Progress|Completed|Strategy|Error"
```

**Completion indicators:**
```bash
# Check if it finished
stat data/backtest_results/report.json | grep Modify  # Should show FRESH timestamp
ls -lh data/backtest_results/report.json              # Should exist, ~12KB
head -20 data/backtest_results/report.json            # Should show valid JSON with strategies
```

**If backtest fails:**
- **"KeyError: 'Timestamp'"**: CSV format wrong; check columns are `Timestamp, Open, High, Low, Close, Volume`
- **"NameError: Supertrend not defined"**: Fix didn't apply; check `src/data_manager.py` has `supertrend()` call
- **Memory error**: Machine too constrained; consider splitting backtest into per-index runs
- **No output for 20+ min**: Likely still running (bar loops are slow); let it continue

### Step 3: Analyze Results

When backtest finishes, run this analysis:

```python
import json

# Load new results
with open("data/backtest_results/report.json") as f:
    new = json.load(f)

# Load old (fake) results for comparison
with open("data/backtest_results/pre_fix_backup/report_OLD_fake_backtest.json") as f:
    old = json.load(f)

print("BEFORE vs AFTER COMPARISON\n")
print("Strategy".ljust(40), "Old WR%".ljust(10), "New WR%".ljust(10), "Change".ljust(10), "P&L Change")
print("-" * 90)

for s in sorted(new.keys()):
    old_wr = old.get(s, {}).get("win_rate", 0)
    old_pnl = old.get(s, {}).get("total_pnl", 0)
    new_wr = new[s]["win_rate"]
    new_pnl = new[s]["total_pnl"]
    wr_diff = new_wr - old_wr
    pnl_diff = new_pnl - old_pnl
    
    print(f"{s[:40].ljust(40)} {old_wr:6.1f}%    {new_wr:6.1f}%    {wr_diff:+6.1f}%      {pnl_diff:+,.0f}")

# Summary
total_old = sum(s.get("total_pnl", 0) for s in old.values())
total_new = sum(s.get("total_pnl", 0) for s in new.values())
print(f"\nPortfolio Total: {total_old:+,.0f} → {total_new:+,.0f}")
```

---

## What Results Should Show

### ✅ Good Signs

1. **Win rates drop significantly** (97%+ → 50–80% range)
   - This is EXPECTED and CORRECT; old results were inflated

2. **Strong families stay strong:**
   - Support Bounce / Resistance Rejection: still 90%+ WR
   - ORB: still 85%+ WR
   - MACD: still 60–70% WR

3. **Weak families now realistic:**
   - OI Squeeze: drops to 50–60% (it's supposed to be weak; no actual OI data)
   - Expansion strategies: now use real logic (Supertrend/CMF should improve from fake version)

4. **Total portfolio P&L** should still be positive (just lower than fake 97%+ backtest)

### ⚠️ Red Flags

1. **Results IDENTICAL to old report** (win rates unchanged)
   - Backtest used old code; check if fixes deployed to src/data_manager.py and src/backtester/backtest_engine.py
   - Search for `supertrend(` in data_manager.py; should be there

2. **Win rates still 97%+**
   - Same as above; code fixes didn't apply

3. **All strategies have NaN or 0 trades**
   - CSV format wrong or data_manager not loading correctly
   - Run `python -c "import pandas as pd; df = pd.read_csv('data/historical/nifty_365days.csv'); print(df.head()); print(f'Rows: {len(df)}')"` to verify

---

## Generate HTML Report

After backtest completes successfully, generate an interactive report:

```bash
python rebuild_report.py
```

This creates: `data/backtest_results/backtest_report.html`

Open in browser to see:
- Portfolio KPIs
- Charts (win rate by index, P&L by index, top 10 strategies)
- Sortable strategy table with search/filters
- Before/after comparison

---

## Report Template (What to Tell the User)

Once you have results, provide:

```
BACKTEST RESULTS — 365 Days, 44 Strategies, Fixed Code

PORTFOLIO SUMMARY
- Total Trades: [N]
- Average Win Rate: [X]%
- Total P&L: ₹[Y]
- Profit Factor: [Z]

BEFORE vs AFTER (Old Fake Backtest → New Real Backtest)
- Portfolio P&L: ₹[OLD] → ₹[NEW]  (change: [+/- %])
- Win Rate: [OLD]% → [NEW]%
- Most improved strategies: [list top 3]
- Most degraded strategies: [list bottom 3]

STRATEGIC INSIGHTS
- Support Bounce / Resistance Rejection: [WR]% — [COMMENT on whether it stayed strong]
- ORB family: [WR]% — [COMMENT]
- Expansion strategies: Now real logic (Supertrend, CMF, BB) — [COMMENT on performance]
- OI Squeeze: [WR]% — Shows expected weakness (no live OI data)

NEXT STEPS
[Based on results, recommend which strategies to keep/retire for 3-month validation phase]
```

---

## Documentation (Reference Only)

These markdown files provide deep context on WHY the fixes were needed:

- `HANDOFF_TO_NEXT_CLAUDE.md` — Complete technical summary of all fixes
- `QUANT_STRATEGY_ARCHITECTURE_REVIEW.md` — Graded 9 strategy families; identified fakes
- `WEEK1_DEEP_DIVE_AND_UNRESTRICTED_BACKTEST.md` — Root-cause analysis of live bugs
- `BACKTEST_RELIABILITY_REVIEW.md` — Why 97% backtests disagreed with -₹8,950 live losses

**You don't need to read these to run the backtest**, but they're useful if backtest results confuse you.

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| `FileNotFoundError: nifty_365days.csv` | Run `python fetch_365day_historical.py` (needs Fyers creds) |
| `NameError: Supertrend not defined` | Check `src/data_manager.py` has Supertrend call; check `src/utils/indicators.py` has definition |
| Backtest takes >3 hours | Normal; consider splitting into per-index runs if needed |
| Results identical to old report | Code fixes didn't apply; verify src/data_manager.py and src/backtester/backtest_engine.py |
| `KeyError: total_trades` in analysis script | report.json format wrong; check it contains all 44 strategies |
| CSV files have wrong row count | Data fetch may have failed; check internet/Fyers API credentials; try `fetch_365day_historical.py` again |

---

## Success = ?

You're done when:

1. ✅ Backtest runs to completion without exceptions
2. ✅ report.json exists with fresh timestamp and all 44 strategies
3. ✅ Win rates are 50–80% range (not 97%+)
4. ✅ Strong families (Support Bounce, ORB) still show >80% WR
5. ✅ Before/after comparison shows expected drops
6. ✅ HTML report generated and loads in browser
7. ✅ User receives clear findings + recommendation for next phase

**If all above: COMPLETE. User can now proceed to 3-month validation phase with confidence in the 44-strategy roster.**

---

## Key Contact Info / Files

- **Main entry point:** `python main.py`
- **All strategies:** `src/strategies/`
- **Indicators:** `src/utils/indicators.py`
- **Backtest engine:** `src/backtester/backtest_engine.py`
- **Config:** `config/risk_params.json`
- **Results dir:** `data/backtest_results/` (report.json here when done)
- **Historical data:** `data/historical/*.csv`

**If stuck:** Read `HANDOFF_TO_NEXT_CLAUDE.md` for 10-minute technical context.
