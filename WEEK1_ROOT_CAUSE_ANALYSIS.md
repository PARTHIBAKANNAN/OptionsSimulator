# Week 1 Root Cause Analysis — Answers to the 5 Questions
**Trading days analyzed: Mon Aug 31, Tue Sep 1, Wed Sep 2, 2026 (23 trades, -₹8,950 net)**

All findings below are backed by: (a) clean 1-min NIFTY/SENSEX/BANKNIFTY candles pulled fresh from
Fyers (`data/market_analysis/*_week_candles.csv`, verified timestamps already in IST), (b) the 23
trades converted from UTC to IST and cross-referenced against real spot prices at each entry/exit
(`data/market_analysis/trades_clean_ist.csv`), and (c) direct reads of the strategy/engine code and
git history. Nothing here is inferred from trade patterns alone.

---

## 0. Timezone check (housekeeping, now resolved)

The DB stores `entry_time`/`exit_time` in UTC (`+00:00`), confirmed via `src/fyers/api_client.py:277`
(`pd.to_datetime(..., utc=True).dt.tz_convert(IST)`). Converting your 23 trades:

- `04:16 UTC` → **09:46 AM IST** (31 min after 09:15 open — correct, not pre-market)
- `07:46 UTC` → **13:16 PM IST**
- All 23 trades fall inside 09:15–15:30 IST market hours. **No timezone bug.** My earlier "pre-market" concern was wrong — apologies, that was based on misreading the raw UTC strings without converting.

---

## 1. Why did only PE strategies execute?

**Root cause: a persistent 1-hour downtrend across the whole week, correctly gating out every bullish strategy.**

Actual daily closes (from freshly-pulled Fyers data):

```
NIFTY:      Aug28 24,175.65 → Aug31 24,080.40 → Sep1 24,055.80 → Sep2 23,893.50
SENSEX:     Aug28 77,264.51 → Aug31 76,957.27 → Sep1 76,944.28 → Sep2 76,507.45
BANKNIFTY:  Aug28 57,496.30 → Aug31 58,024.95(intraday high, closed lower next day) → Sep1 57,409.60 → Sep2 57,100.00
```

NIFTY and SENSEX ground steadily lower across 4 straight sessions. Every bullish 1M-ATM strategy
(`macd_bullish.py`, and the SENSEX/BANKNIFTY subclasses of it, plus `support_bounce_bullish.py`)
requires `spot > ema_50_1h` before it will even look for its own trigger:

```python
# src/strategies/macd_bullish.py:26
if macd_hist > 0 and macd_hist_prev <= 0 and nifty > ema50:
```

In a multi-day grind lower, the lagging 1-hour 50-EMA sits above spot almost the entire time, so
`nifty > ema50` is false nearly all week — the bullish gate structurally never opens. Meanwhile the
mirror-image bearish gate (`nifty < ema50` in `macd_bearish.py`) is true almost continuously, so PE
signals fire repeatedly. **This is the trend filter working exactly as designed** — it is not a bug.
It's a direct, mechanical consequence of the week being a one-directional grind down.

---

## 2. Why did no CE strategies execute? (same question, confirmed from the other side)

Confirmed by the spot cross-reference file: every CE-gated strategy (`ORB_BULLISH`, `MACD_BULLISH`,
`SUPPORT_BOUNCE_BULLISH`, `HEIKIN_ASHI_BULLISH`) needs `spot > ema_50_1h`. Even on Sep 2 — the one
day all three indices closed slightly up — the *intraday* move was tiny (NIFTY +0.15%, from a lower
base than Aug 28) and price was still recovering from three days of decline, so it plausibly never
cleared the lagging 1H EMA by session's end. I did not find any code path that disables/filters CE
signals independently of this trend gate — no separate "bearish-only mode" or override exists in
`engine.py`, `live_engine.py`, or `risk_params.json`. **It's the same root cause as Q1, not a
second, independent issue.**

---

## 3. Why did no 5M-ITM strategies execute? — **this one IS a confirmed bug, not the market**

This is the most important finding. Zero of the 18 5M-ITM strategies (6 each for NIFTY/SENSEX/BANKNIFTY)
produced a single trade in 3 days. Backtest base rate for just one of them
(`NIFTY_SUPPORT_BOUNCE_5M_ITM`) is 133 trades / ~245 days ≈ 0.54/day — across 18 strategies over 3
days that's roughly **29 signals expected**, not 0. That gap is too large to be explained by "quiet
market." I checked the git history and found two sequential, self-documented, dated bugs that cover
almost exactly the affected sessions:

**Bug #1 — undefined `OPENING_CUTOFF_TIME` (active all day Mon Aug 31):**
```
c152aa2  Fri Aug 28 15:16  "add 09:25 AM cutoff gate..."
         -> can_trigger() references OPENING_CUTOFF_TIME, but the constant is NOT defined anywhere yet
c982d14  Mon Aug 31 21:51  "fix: define OPENING_CUTOFF_TIME in base_strategy.py restoring
                            5-minute ITM strategy execution"
```
Every 5M-ITM strategy's `evaluate()` calls `self.can_trigger(ts)` as its first line
(`nifty_5m_strategies.py:31` etc.). Between Aug 28 and the evening of Aug 31, that call raised a
`NameError` on every single tick, for every 5M-ITM strategy, on all three indices.
`StrategyEngine.evaluate_all()` catches per-strategy exceptions and silently continues
(`src/strategies/engine.py:151-156`), so this crashed invisibly — no error surfaced anywhere you'd
have seen it, it just guaranteed zero 5M-ITM signals were structurally possible **all day Monday**.
The fix landed at 21:51 IST Monday evening, after market close.

**Bug #2 — missing `ema_50_1h` fallback (active all day Tue Sep 1):**
```
64e528c  Tue Sep 1 19:12  "1H EMA resolution, and strategy restriction cleanups"
```
Before this commit, every 5M-ITM strategy did:
```python
ema50_1h = indicators.get("ema_50_1h")      # no fallback
if ema20_5m is None or ema50_1h is None:
    return None                              # silently exits, every time, if 1H EMA isn't ready
```
and `ema_50_1h` itself required `len(resampled_1h_bars) >= 15` before it was computed at all
(`data_manager.py`, pre-fix). With the local SQLite candle cache also being introduced in this same
commit (candle-history persistence across restarts was being reworked at the same time), the 1H
window plausibly hadn't accumulated 15 bars yet on a live, recently-restarted engine — so
`ema_50_1h` was `None` and every 5M-ITM strategy returned `None` on every tick, all day **Tuesday**.
The commit message explicitly says "1H EMA resolution... cleanups," and the diff adds an
`or indicators.get("ema_50_5m") or indicators.get("ema_20_5m")` fallback to every 5M-ITM strategy
file (`nifty_5m_strategies.py`, `sensex_5m_strategies.py`, `banknifty_5m_strategies.py` — all three
touched in the same commit, all with the same fallback added), landing 19:12 IST Tuesday evening.

**Net effect: 5M-ITM strategies were structurally incapable of firing for the entire Monday and
Tuesday sessions** — two out of your three trading days — due to bugs that were being actively
patched, by you, on the evenings of those exact two days. Wednesday (Sep 2) ran with both fixes
live before market open, and 5M-ITM *still* produced zero trades — that one day I can't yet
attribute to a known bug; it's consistent with either (a) genuinely low realized volatility not
producing a qualifying support-bounce/ORB-breakout/resistance-rejection pattern, or (b) the brand-new
SQLite candle cache still warming up its 1H window on its first live day. I don't have enough
evidence to pick between those two — **flagging as open, not resolved.**

---

## 4. Why is live behaving so differently from backtest?

Four separable, independently-confirmed factors, roughly in order of impact:

**(a) 5M-ITM — the strategies with the best backtest numbers (97%+ WR) never got to run.**
Two of your three days had them completely disabled by the bugs in Q3. The backtest's headline
"reliable" tier (NIFTY_ORB_5M_ITM 98%, NIFTY_SUPPORT_BOUNCE_5M_ITM 97.7%, etc.) simply had zero
chance to show up this week — its absence isn't a live-vs-backtest gap, it's a "didn't run" gap.

**(b) The only strategies that DID run (1M-ATM PE) are the backtest's weaker, noisier tier — and
this week hit exactly the two days a prior backtest flagged as bad, with the filter for it switched off.**
`heikin_ashi_trend_bearish.py` contains a dated, self-documented finding:
```python
# Trade-log analysis (Quantman full-year backtest) showed Monday+Tuesday and the 10:00-12:00
# window are net losers while every other day/time is profitable -- excluded rather than tuned.
EXCLUDED_WEEKDAYS = {0, 1}  # Monday, Tuesday
DEAD_ZONE_START, DEAD_ZONE_END = dtime(10, 0), dtime(12, 0)
```
But every live instance is constructed with `apply_day_time_filter=False` (confirmed in
`engine.py`, `sensex_strategies.py:59`, and the Sep-1-evening commit which explicitly *flipped the
default from True to False*, commenting "so NIFTY executes on all trading days alongside SENSEX and
BANKNIFTY"). Your trading week was Monday, Tuesday, Wednesday — i.e. it **opened on exactly the two
days your own prior backtest identified as net-loss days**, with the guardrail for that finding
disabled. Cross-checking the trade log: several of the worst losses (SENSEX -₹1,032 ×2, NIFTY
-₹485) fall inside the 10:00–12:00 "dead zone" the filter was built to exclude.

**(c) Tuesday (Sep 1) was NIFTY's *and* BANKNIFTY's weekly options expiry day (0-DTE).**
NSE moved NIFTY expiry to Tuesday effective Sep 2025; BANKNIFTY has been Tuesday since 2023
(both documented in `src/utils/options_pricing.py`). 0-DTE options carry maximum gamma/theta — the
BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM trade that lost ₹3,587 (your worst trade) entered on exactly
this day, held 87 minutes, and decayed hard even though spot only moved +0.44% against it. Monday
was 1-DTE for the same two indices — also unusually gamma-heavy.

**(d) The 20% stop-loss / flat 150-point take-profit is genuinely too tight for NIFTY's premium
scale — and this is true in the backtest too, not just live.** I checked: `main.py`'s
`BacktestEngine` (which produced the official `report.json` numbers) reads the exact same
`config/risk_params.json` — `stop_loss_pct: 20`, `take_profit_pts: 150` — as live
(`src/backtester/backtest_engine.py:48-49` vs `src/trader.py:106-107`). **So this is not a
live-only misconfiguration; backtest and live use identical exit rules for the 1M-ATM strategies.**
But the number itself is a poor fit for NIFTY: your NIFTY entries this week were premiums of ₹28-₹128.
A 20% SL on a ₹128 premium is only ₹25.6 — for a near-ATM option (delta ≈ 0.5), that's roughly
**51 NIFTY points** of adverse move to trigger the stop. 51 points on a 24,000 NIFTY is 0.21%
— well within one hour's normal noise, in either direction, regardless of the day's overall trend.
Cross-referencing the trade log confirms this exactly: every STOP_LOSS exit sits at almost precisely
-20.08% of entry premium while the underlying spot moved only 0.02%–0.23% during the hold — i.e.
the stops weren't hit because the market moved against the trade, they were hit by ordinary
intra-hour chop. The flat 150-point take-profit has the mirror problem: reachable for SENSEX/BANKNIFTY
premiums (₹250-600, needs a ~25-60% gain) but requiring 100%+ on a ₹30-130 NIFTY premium — structurally
almost unreachable in a 1-2 hour window. Zero of your 5 NIFTY trades this week hit TAKE_PROFIT; the
two big wins that did hit TP were both SENSEX (premium ₹248-270 → able to reach +150pts).
The separate 5M-ITM backtest scripts (`backtest_5min_nifty.py`, `fast_backtest_5min_nifty.py`) *do*
use a smaller, appropriately-scaled `target_tp_pts=50.0` for ITM contracts — so this specific
mis-scaling is confined to the 1M-ATM tier, but it's been there in both backtest and live the whole
time, on all three indices.

**Ranking by estimated contribution to this week's -₹8,950:**
1. 5M-ITM disabled 2/3 days → your best-performing tier contributed literally nothing (opportunity cost, not a loss, but explains most of the backtest-vs-reality gap in *composition*)
2. Monday+Tuesday dead-zone filter disabled → traded into the exact days/hours a prior backtest said to avoid
3. Sep 1 0-DTE gamma/theta → amplified the single worst loss (-₹3,587) and several fast SL hits
4. 20%-SL-too-tight-for-NIFTY-premium → structural, was already true in the 1-year backtest, but a bad week of chop exposes it harder than a trending week would

---

## 5. How reliable is the backtest, given all this?

**This week's -₹8,950 is not clean evidence against the backtest — it's contaminated by (b) and (a) above, and the sample is far too small on top of that.** Specifically:

- 5M-ITM (the tier with the most extreme, most suspicious-looking backtest win rates — 97-98%,
  profit factors in the hundreds/thousands, which I flagged as statistically implausible in the
  earlier review) **never traded live this week at all**. We still have zero live evidence either
  confirming or refuting those numbers.
- The 1M-ATM tier that *did* trade landed on the two days + one 0-DTE day that stack the deck
  against it, with a known protective filter switched off. 5 NIFTY trades, 6 SENSEX, 6-7 BANKNIFTY
  — that's not enough trades per strategy (2-3 each) to draw a win-rate conclusion in either
  direction; one or two trades flip the percentage by 20+ points.
- What this week *did* newly confirm, independent of sample size: the flat 150-pt TP / 20%-of-premium
  SL is measurably miscalibrated for NIFTY's premium scale, and that mis-scaling is present in the
  backtest numbers too — so the backtest's NIFTY 1M-ATM win rates were likely always more dependent
  on the trailing-stop/occasional-big-day path than on clean TP hits, in both places, consistently.

My standing assessment from the earlier review (backtest reliability materially overstated,
particularly the 5M-ITM 97%+ figures) is **unchanged by this week's data** — it's neither confirmed
nor refuted, because the bug in Q3 prevented the relevant strategies from being tested at all. **The
honest conclusion is: we don't yet have a fair live sample for either tier.** 1M-ATM traded through
adverse structural conditions (disabled filter, 0-DTE); 5M-ITM didn't trade at all.

---

## Recommendations, ranked

1. **Re-enable the Monday/Tuesday + 10:00-12:00 exclusion filter** (`apply_day_time_filter=True`)
   for the Heikin-Ashi bearish strategies, or decide explicitly that you no longer trust that prior
   finding — but right now it's disabled with no stated re-validation, and this week walked
   straight into what it warned about.
2. **Rescale `take_profit_pts` and the trailing-stop point tiers per index** instead of one flat
   number — e.g. as a multiple of typical entry premium (roughly what `target_premium` already does
   for ITM strike selection) rather than an absolute point count calibrated to BANKNIFTY/SENSEX
   scale.
3. **Give 5M-ITM a clean, bug-free week** before drawing any conclusion about it, live or backtest.
   It hasn't been tested yet.
4. **Confirm whether Wednesday's zero 5M-ITM signals is a warm-up artifact or still a bug** — worth
   watching the next 2-3 days specifically for this, now that both known bugs are fixed.
5. Consider whether 0-DTE days (NIFTY/BANKNIFTY Tuesdays) warrant their own tighter position sizing
   or a skip rule, given the gamma amplification observed on the -₹3,587 trade.

---

## Open questions for you

- Do you want me to re-enable the day/time filter and re-run a quick forward simulation on this same
  week's data to see what it would have excluded?
- Do you want me to pull Thursday/Friday (Sep 3-4) trades once available to check whether 5M-ITM
  starts firing now that both bugs are fixed?
- Should I look at whether `main.py`'s BacktestEngine reports 5M-ITM win rates using this same flat
  150pt TP, or the scaled 50pt version from `backtest_5min_nifty.py` — right now I've confirmed the
  1M-ATM backtest matches live's config, but haven't traced which script actually produced the
  `NIFTY_SUPPORT_BOUNCE_5M_ITM` 97.7%-WR number in `report.json`.
