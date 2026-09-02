# Deep-Dive: Why 5M-ITM Didn't Fire + Unrestricted 3-Day Backtest of All 44 Strategies
**Evidence sources: VM logs via SSH (`130.210.42.240`), git history, and a from-scratch replay of the
real production strategy code against fresh 1-min Fyers candles for Aug 31 – Sep 2, 2026.**

---

## Part 1 — Is the 5M-ITM absence a bug or a market condition? **Bug. Confirmed from the server's own error log, not inferred.**

I SSH'd into the deployment VM and read `logs/errors.log` (and its rotated backups) directly.

**Monday Aug 31 — 96,562 identical crashes, all on this one day:**
```
2026-08-31 08:58:18 | ERROR | Strategy NIFTY_SUPERTREND_CMF_BULLISH_CE raised: name 'OPENING_CUTOFF_TIME' is not defined
... (96,562 total occurrences, spanning 08:58 to 09:59 UTC = 14:28 to 15:29 IST, i.e. essentially the whole session)
0 occurrences on Sep 1 or Sep 2
```
This is a `NameError` inside `BaseStrategy.can_trigger()` — a constant referenced in the Aug 28
commit that added the 09:25 cutoff, but not actually *defined* until the fix landed Monday evening.
**It affected exactly the 30 strategies whose `evaluate()` calls `self.can_trigger()` — all 18
5M-ITM strategies plus all 12 "Expansion" strategies (VWAP, Supertrend+CMF, BB Squeeze, OI, Dual
Supertrend, Gamma Wall).** The 14 classic 1M-ATM strategies (MACD/ORB/HA) don't call
`can_trigger()` at all, which is exactly why those were the only ones that traded Monday.

I cross-checked deploy timestamps against the VM's own `systemctl`/`journalctl` restart history
(the VM clock is UTC): the fix (commit `c982d14`) was committed 21:51 IST Monday and deployed by a
restart at 21:55 IST — **after Monday's market close**. So Monday's entire session ran broken,
start to finish.

**Tuesday Sep 1 — the crash is gone, but the strategies still can't fire, for a different reason:**
The restart that would have shipped the *next* fix (`ema_50_1h` fallback + lower bar-count
requirement, commits `a3ac71b`/`64e528c`) didn't happen until **17:26–19:33 IST Tuesday evening**
— again, after that day's market close. So all of Tuesday ran on code where `can_trigger()` no
longer crashes, but `ema_50_1h` was still `None` (needed ≥15 one-hour bars, pre-fix), so every
5M-ITM strategy's `if ema50 is None: return None` fired silently all day. `signals.log` for Sep 1
confirms only 5 strategy names ever produced a loggable signal that day (all 1M-ATM), matching this
exactly.

**Wednesday Sep 2 — both known bugs are fixed, yet still zero. This is a real, unresolved anomaly, not something I'm attributing to the same two bugs.**
`signals.log` for Sep 2 shows only **3** strategy names fired all day (`*_HEIKIN_ASHI_BEARISH_1M_ATM`
for all three indices) — not even `MACD_BEARISH_1M_ATM`, which had fired the day before. Zero of
the 30 `can_trigger()`-gated strategies produced a single signal, and `errors.log` shows **no
exceptions at all** for Sep 2 (other than an unrelated Telegram method-name bug in the pre-market
AI job). No crash, no logged rejection — they just silently never signaled.

I built an independent, faithful replay of the exact same strategy code against the exact same real
market data (Part 2 below) specifically to test this. **That replay shows 17 signals *should* have
fired from this cohort on Wednesday alone**, using the current (both-bugs-fixed) code on the same
real prices. Since my clean replay disagrees with what the live server actually did on Wednesday,
there is something *else* still wrong, specific to the live deployment, that my replay doesn't
reproduce. My leading hypothesis (not yet confirmed): the local SQLite candle cache introduced in
the same Tuesday-evening commit was on its first live day and may have interacted badly with the
10-day REST re-seed (`_seed_historical_candles`, which runs once per calendar day and should have
independently refreshed 1H history from Fyers regardless of the SQLite cache) — but I found no
error logged for that seed call either, so I can't confirm it from logs alone. **I'm flagging this
as open rather than guessing further** — the concrete next step is checking `fyersRequests.log`
around Wednesday 03:45 IST market open for the historical-seed REST calls, and ideally adding a
one-line `log_websocket_event` confirming `ema_50_1h`'s actual value at, say, 10:00 AM each morning,
so this is directly observable in future instead of requiring log archaeology.

---

## Part 2 — Unrestricted 3-day backtest: where SHOULD the 5M-ITM (and every other) strategy have triggered?

I wrote `replay_3day_unrestricted.py`, which:
- Uses the **actual production code** — `create_nifty_strategies()` / `create_sensex_strategies()` /
  `create_banknifty_strategies()` from `src/strategies/engine.py`, unmodified.
- Feeds it the **real 1-min candles** pulled fresh from Fyers for Aug 28 (warm-up only, not counted)
  through Sep 2 (`data/market_analysis/*_week_candles.csv`).
- Removes every *portfolio-level* restriction, as you asked — `max_trades_per_day_per_strategy`,
  `max_concurrent_positions`, `max_daily_loss`, consecutive-loss breaker, wallet balance checks are
  all disabled. Each strategy's own internal signal logic and cooldown (part of the strategy
  itself, e.g. the 15-min re-entry gap on 5M-ITM strategies) is left intact, since that's the
  strategy, not a risk cap.
- Prices signals and simulates SL/TP/trailing/time-exit using Black-Scholes (same substitute the
  project's own replay/backtest code uses when no live option-chain history exists), with the exact
  same `risk_params.json` exit rules as live (20% SL, flat 150-pt TP, 15%-trail).

**Result: 41 of 44 strategies produced at least one trade in 3 days.** Only 3 were genuinely quiet
(`NIFTY_VWAP_POC_PULLBACK_CE`, `NIFTY_VWAP_POC_BREAKDOWN_PE`, `SENSEX_SUPPORT_BOUNCE_5M_ITM`) — for
those three, absence is a real "no qualifying setup," not a bug.

### The 5M-ITM tier specifically — proof the bugs cost you both signals and mixed real P&L
```
Day           Trades   Wins   Win rate   Net P&L
Mon Aug 31      51       22     43%      -₹12,769   (blocked live by Bug #1)
Tue Sep 1       33       20     61%      +₹15,495   (blocked live by Bug #2)
Wed Sep 2       17        7     41%       -₹7,242   (blocked live by the unresolved Part-1 issue)
─────────────────────────────────────────────────
3-day total    101       49     48.5%     -₹4,517
```
Two things jump out:

1. **The absence was 100% structural, not a quiet market** — 101 qualifying setups fired across the
   18 strategies in 3 days (roughly 34/day), not "market too calm to trigger anything." You lost
   real opportunity, in both directions: Monday would have lost more (-₹12.8K, worse than what
   actually happened), but Tuesday would have made +₹15.5K, which is more than enough to have turned
   this week from -₹8,950 to roughly break-even had 5M-ITM been running.

2. **48.5% win rate over 101 trades is nowhere near the 97%+ figures in the 1-year backtest
   report.** This is a genuinely useful out-of-sample check, independent of anything about bugs:
   `NIFTY_SUPPORT_BOUNCE_5M_ITM` backtests at 97.7% WR/133 trades but was 0-for-2 here;
   `NIFTY_ORB_BULLISH_5M_ITM` backtests near-98% but was 0-for-3. Sample size is small (2-6 trades
   per strategy), so this alone doesn't disprove the backtest, but it's the first live-adjacent
   evidence directly contradicting those headline numbers, and it reinforces my earlier concern
   that the 5M-ITM backtest win rates were overstated.

Full per-strategy scorecard (all 44, unrestricted, 3 days) and every individual trade are saved to
`data/market_analysis/replay_trades.csv` and `replay_signal_log.csv` for your own review — happy to
walk through any specific strategy's trade list in the next session.

### Top and bottom performers across all 44, unrestricted, this week
```
Best:   BANKNIFTY_HEIKIN_ASHI_BEARISH_5M_ITM   12 trades, 66.7% WR, +₹15,129
        NIFTY_HEIKIN_ASHI_BEARISH_5M_ITM         8 trades, 37.5% WR,  +₹9,077
        BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM    22 trades, 54.5% WR,  +₹4,714

Worst:  SENSEX_BB_SQUEEZE_EXPLOSION_PE          21 trades, 52.4% WR,  -₹7,030
        NIFTY_SUPPORT_BOUNCE_5M_ITM               2 trades,  0.0% WR, -₹5,283
        SENSEX_ORB_BULLISH_5M_ITM                 2 trades,  0.0% WR, -₹3,732
        NIFTY_ORB_BULLISH_5M_ITM                  3 trades,  0.0% WR, -₹3,394
        BANKNIFTY_DUAL_SUPERTREND_BB_CE          12 trades, 41.7% WR, -₹3,505
```
Notice all four ORB/Support-Bounce 0%-WR entries are exactly the strategies whose exit thresholds
(flat 150-pt TP, 20/35/50-pt trailing-stop tiers) I flagged in the earlier review as calibrated for
BANKNIFTY/SENSEX-scale premiums, not NIFTY's — this week's clean replay independently reproduces
that same weak spot.

---

## Part 3 — Was this actually a "highly volatile" 3 days? (checked, not assumed)

Computed directly from the real 1-min candles:

```
Index       Aug31 range   Sep1 range   Sep2 range   (as % of day's open)
NIFTY          0.56%         0.79%         0.52%
SENSEX         0.55%         0.75%         0.56%
BANKNIFTY      1.46%         1.07%         0.70%
```
**NIFTY and SENSEX were moderately volatile, not extreme** — 0.5-0.8% intraday range is a normal
trading day, not a stress event. **BANKNIFTY was genuinely more volatile, especially Monday
(1.46% range)** — and Monday was also the day BANKNIFTY closed *up* +1.17% while NIFTY/SENSEX
closed *down*, i.e. it briefly decoupled from the other two. That divergence, combined with a 20%
flat SL, is a believable explanation for BANKNIFTY-specific whipsaw that day, but it doesn't apply
broadly to "the whole week was highly volatile" — most of the damage this week came from the
structural issues in Parts 1 and the exit-rule mismatch in Part 2, not from unusually wild markets.

---

## Part 4 — Is the current 44-strategy set stable? What needs to change before your 3-month clock starts?

**Direct answer: no, not yet — but the fixes needed are specific and known, not a redesign.**
Given your plan (3 months clean paper trading → pick winners → 2 months validation → live capital),
I'd treat this week as pre-season, not week 1 of the 3 months, for these reasons:

1. **Two of three days had 30 of 44 strategies structurally disabled** (Part 1) — you were
   effectively running a 14-strategy test, not a 44-strategy one, for most of the week. Don't let
   the 3-month clock start until you've confirmed all 44 fire cleanly (the Wednesday anomaly in
   Part 1 needs to be closed out first — I'd want one full clean day showing signals from all four
   strategy families — ORB, HA, MACD, and the 5M-ITM/Expansion cohort — before trusting the clock).
2. **The flat 150-pt TP / point-based trailing-stop tiers are mis-scaled for NIFTY specifically**,
   confirmed independently in both the live trade log and this week's clean replay. This will keep
   suppressing NIFTY 1M-ATM and NIFTY 5M-ITM performance for the whole 3 months if left as-is — it's
   not something you'd want to discover in month 3 as "NIFTY strategies underperform," when it's
   actually an exit-rule scaling bug, not a signal-quality problem. I'd fix this *before* starting
   the clock, since changing it mid-experiment would invalidate the comparison across the 3 months.
3. **This week's individual scorecard (Part 2) already tells you something real**: strategies with
   0% win rate over 2-3 trades don't mean much yet, but the pattern — every 0%-WR strategy this week
   being an ORB/Support-Bounce type with the exit-scaling issue — is a leading indicator worth
   watching once #2 above is fixed, not dismissing.
4. **Everything else looks structurally sound for a 3-month unattended run**: charges model is
   realistic, EOD square-off works, trailing-stop step logic matches its own documented design
   exactly (verified against the code), and the disabled Monday/Tuesday+10-12 dead-zone filter from
   `heikin_ashi_trend_bearish.py` is a good example of the platform already having produced one
   genuine, data-backed finding from a prior backtest — it's just currently switched off with no
   re-validation. Worth deciding explicitly whether to re-enable it or intentionally retire that
   finding, rather than leaving it in a disabled-by-default limbo.

**Recommended sequence before the 3-month clock starts:**
1. Resolve the Wednesday anomaly (Part 1) — get one full clean trading day with signals from all
   four strategy families confirmed in `signals.log`.
2. Rescale `take_profit_pts` and the trailing-stop point tiers per index (or as a % of entry
   premium instead of a flat point count).
3. Decide on the Monday/Tuesday + 10:00-12:00 filter (re-enable with fresh validation, or explicitly
   retire it) rather than leaving it silently off.
4. *Then* start the 3-month clock, so the 44 strategies are genuinely being compared on equal
   footing from day one, not carrying forward this week's structural noise.

---

## Files produced this session
- `fetch_week_market_data.py` — pulls clean 1-min NIFTY/SENSEX/BANKNIFTY candles from Fyers
- `data/market_analysis/{NIFTY,SENSEX,BANKNIFTY}_week_candles.csv` — the real candle data used throughout
- `analyze_trades_vs_market.py` + `data/market_analysis/trades_clean_ist.csv` — your 23 live trades, IST-converted, cross-referenced against real spot prices
- `replay_3day_unrestricted.py` + `data/market_analysis/replay_signal_log.csv` / `replay_trades.csv` — the unrestricted 44-strategy replay behind Part 2
- `WEEK1_ROOT_CAUSE_ANALYSIS.md` — prior session's answers to the original 5 questions (superseded/confirmed by this deeper VM-log-based version)

## Open item for next session
Close out the Wednesday anomaly — I'd like to check `fyersRequests.log` around market open and
possibly add a one-line diagnostic log for `ema_50_1h` availability each morning, so this class of
issue is visible going forward instead of requiring manual log archaeology each time.
