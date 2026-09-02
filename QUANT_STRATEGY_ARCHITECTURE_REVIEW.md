# Quant Architecture Review — All 44 Strategies
**Reviewed at the code level: every `evaluate()` method, every indicator formula in `src/utils/indicators.py`, cross-checked against what `DataManager` actually computes.**

---

## Headline finding, stated plainly

**Your 44 strategies are actually 9 distinct logic families, not 44 distinct ideas.** Most "strategies" are the same family re-run on NIFTY/SENSEX/BANKNIFTY with a different strike step. That's fine and normal. What's *not* fine: **6 of the 12 "Expansion" strategies (Supertrend+CMF, BB Squeeze, Dual Supertrend+BB) run the exact same formula** — `spot > EMA20(5m) AND spot > EMA50(1h)`, or the mirror for puts — **under three different sophisticated-sounding names, on three different indices, and none of the indicators in those names (Supertrend, CMF, Bollinger Bands) are computed anywhere in this codebase.** I confirmed this with a direct search: zero references to Supertrend, CMF, VWAP, or Bollinger Bands in `data_manager.py`, the only place indicators get computed. `bollinger_bands()` exists correctly in `indicators.py` as a utility function — it's just never called by the strategy named after it.

This isn't a style nitpick. It means when you see "3 strategies agreed" in a signal cluster, you may be looking at **one signal, counted three times**, dressed as independent confirmation. I found direct proof of this in my own replay log: on Sep 2 at 10:44:00, `BANKNIFTY_RESISTANCE_REJECTION_5M_ITM`, `BANKNIFTY_DUAL_SUPERTREND_BB_PE`, and `BANKNIFTY_GAMMA_WALL_BREAKOUT_PE` all fired **at the identical minute, at the identical price** — three "different" strategies reacting to the same EMA crossing.

---

## The 9 real logic families, graded

### 1. MACD Cross + 1H-EMA trend filter — Grade **C+**
*Covers: `NIFTY/SENSEX/BANKNIFTY_MACD_BULLISH/BEARISH_1M_ATM` (6 strategies)*

Correct math (`ema(fast) - ema(slow)`, standard 12/26/9), and it's genuinely **edge-triggered** — fires on a fresh histogram cross, not a persistent state, so it doesn't spam re-entries the way the Heikin-Ashi family does. Good.

Two real issues:
- It's labeled "1M_ATM" but the signal itself is a **15-minute MACD cross** — the "1M" only describes the execution/holding style, not the signal's own timeframe. Not wrong, but worth knowing what you're actually trading.
- Single trend filter (1H EMA, lagging by construction) is the only thing standing between this and "fighting the tape." This is *exactly* what happened Tuesday morning — the 1H EMA hadn't caught up to the morning rally yet, so bearish crosses fired into a rising market.

### 2. Heikin-Ashi 2-candle continuation + wick filter + 1H-EMA — Grade **B-** (5M-ITM) / **C** (1M-ATM)
*Covers: 3× `*_HEIKIN_ASHI_BEARISH_1M_ATM`, 6× `*_HEIKIN_ASHI_BULLISH/BEARISH_5M_ITM`*

HA transform itself is textbook-correct. The pattern (2 consecutive same-color candles, near-zero opposing wick, trend-aligned) is a legitimate continuation signal.

The real weakness: `current_bearish and prev_bearish and price<ema50` is a **state**, not an edge — it stays true for many consecutive bars in a real downtrend. The 1M-ATM version doesn't even call `can_trigger()` (no internal cooldown at all — its only throttle is the blunt daily-2-trade cap). This is why it was the strategy re-firing over and over in your live logs and is largely why HA-Bearish dominates your trade count: it's not "the market kept giving fresh setups," it's "the same setup kept re-qualifying because nothing resets it." The 5M-ITM version is better (has its own 15-min cooldown built in), hence the better grade there.

### 3. Opening Range Breakout (ORB) — Grade **B** (concept) / **C+** (as implemented)
*Covers: 1× NIFTY Bullish + 2× Bearish 1M-ATM, 6× 5M-ITM*

Classic, respected pattern, genuinely edge-triggered. But three concrete defects I found reading the code side-by-side:
- The **1M-ATM version requires volume confirmation** (`current.volume > avg_volume`); the **5M-ITM version drops that filter entirely**. That's backwards — your higher-conviction, more-capital-intensive ITM tier has *less* confirmation than the cheaper ATM tier.
- `NiftyORBBullish5MITM` has an EMA fallback chain (`ema_50_1h or ema_50_5m`); `NiftyORBBearish5MITM` has **none at all** — an unexplained asymmetry between the two mirror-image strategies.
- Despite the "5M" name, the breakout is checked on **1-minute** candle closes, not true 5-minute bar closes — noisier than the name implies.
- The live roster itself is asymmetric with no documented reason: only NIFTY gets a 1M-ATM *Bullish* ORB; SENSEX and BANKNIFTY only get the *Bearish* one. That's a silent directional tilt baked into the roster, independent of any single week's market direction.

### 4. Support Bounce / Resistance Rejection (20-EMA test + volume + strong-close + 1H-EMA) — Grade **A-**
*Covers: 3× `*_SUPPORT_BOUNCE_1M_ATM`, 6× 5M-ITM (Support Bounce + Resistance Rejection)*

**This is the best-architected family in your entire roster**, and it's not close. Four independent confirmations stacked before it fires: (1) price actually touched the level, (2) reclaimed/rejected it, (3) the higher-timeframe trend agrees, (4) the confirming candle closed strong (top/bottom 40% of its own range) *and* on above-average volume. That's a real, multi-factor design. The code comments even show genuine empirical iteration — a note describing a tested-and-rejected tighter volume threshold, with the actual backtest result (P&L dropped ~72%) cited as the reason it was reverted. That's the only strategy family in the codebase with visible evidence of real validation work behind its current parameters.

Only knock: the live roster wires the CE side (Support Bounce) at 1M-ATM but not the PE mirror (Resistance Rejection) at that tier — it only appears at 5M-ITM. Minor registry inconsistency, not a logic flaw.

### 5. VWAP/POC Pullback + RSI — Grade **C+**
*Covers: 2× NIFTY only*

The most legitimate of the "Expansion" strategies, but still a step down from #4: it has the touch-and-reclaim structure plus an RSI(>50 / <45) momentum filter, but is **missing the 1H-EMA trend filter and volume check** that Support Bounce/Resistance Rejection both require. No VWAP or Point-of-Control is actually computed — this is `ema_20_5m` relabeled. Zero signals fired in my 3-day replay; sample too small to call that a flaw on its own, but it's a strictly weaker cousin of #4 with a fancier name.

### 6, 7, 9. "Supertrend+CMF" / "BB Squeeze Explosion" / "Dual Supertrend+BB" — Grade **D**
*Covers: 2× NIFTY, 2× SENSEX, 2× BANKNIFTY — 6 strategies total*

Already stated above: **identical formula, three names.** `spot > ema_20_5m and spot > ema_50_1h` (mirrored for the bearish side). No Supertrend. No Chaikin Money Flow. No Bollinger Bands, squeeze or otherwise. This isn't "the indicator is a rough proxy" — it's "the named indicator doesn't exist in the code at all." As a bare 2-EMA-alignment check it's not *dangerous*, just badly mislabeled, and it triple-books the same underlying signal as independent evidence across your dashboard/reporting. **This is the first thing I'd fix or retire.**

### 8. "OI Short Squeeze" / "OI Long Unwinding" — Grade **D+**
*Covers: 2× SENSEX only*

Even thinner than #6/7/9: a **single** EMA check (`spot > ema_20_5m`), no higher-timeframe confirmation at all, and — despite the name — **no Open Interest data used anywhere**. This is the loosest-filtered strategy pair in the whole 44, and it trades **ATM** strikes (the most premium-sensitive to whipsaw). If I had to pick the single strategy pair most likely to bleed capital in a choppy market with no compensating upside, it's this one.

### 10, 11. "VWAP+BB Liquidity Rebound" / "Gamma Wall Breakout" — Grade **C-**
*Covers: 2× BANKNIFTY only*

A plain EMA touch-and-reclaim/-reject, structurally similar to #4 but with **none of #4's extra confirmations** — no volume filter, no RSI, no higher-timeframe EMA check. It's the weakest version of a good idea, run on your highest-premium, most capital-intensive index.

---

## Where this leaves the roster

| Family | Strategies | Grade | Real diversification value |
|---|---|---|---|
| Support Bounce / Resistance Rejection | 9 | A- | High — genuinely multi-factor |
| ORB | 9 | B / C+ | Medium — good idea, inconsistent implementation |
| Heikin-Ashi (5M) | 6 | B- | Medium |
| MACD Cross | 6 | C+ | Medium — single lagging filter |
| Heikin-Ashi (1M) | 3 | C | Low — no internal cooldown, restates itself |
| VWAP POC | 2 | C+ | Low — untested, thin sample |
| VWAP+BB Rebound / Gamma Wall | 2 | C- | Low |
| OI Squeeze/Unwinding | 2 | D+ | None found — no OI data, weakest filter |
| Supertrend+CMF / BB Squeeze / Dual Supertrend | 6 | D | **Negative** — inflates apparent signal agreement without adding real information |

**18 of your 44 strategies (the bottom three rows) are the ones I'd scrutinize hardest before your 3-month clock starts.** Not because I've proven they lose money — 2-6 trades each this week proves nothing either way — but because their *architecture* doesn't currently deliver what their names promise, and that will quietly bias any portfolio-level decision you make later (e.g., "keep the strategies that show the best win rate" will implicitly keep or cut near-duplicates together, hiding the redundancy rather than fixing it).

---

## On handling this week's volatile/choppy behavior — concrete suggestions

You asked specifically how to handle the kind of market you saw this week (gap, then either a real move or pure chop). Four concrete additions, none of which require rebuilding anything:

1. **Add a regime filter gate before any entry — chop vs. trend.** Right now every strategy relies on a single lagging 1-hour EMA as its only "is this a real move" check. A simple ADX(14) or ATR-expansion check on a 15m basis, computed once and shared across all strategies, would have flagged Wednesday's 09:30-onward session as non-trending and suppressed ORB/MACD/breakout-style entries for the rest of that day — exactly the session that produced 0/6 wins live.

2. **Replace or supplement the 1H-EMA "don't fight the tape" check with something faster.** The 1-hour EMA is why Tuesday's morning entries fired *into* a rally that was still forming — the EMA simply hadn't caught up yet. A short-lookback confirmation (e.g., last 3-5 one-minute bars' net direction must agree with the trade direction) would catch a fresh reversal much faster than a 1-hour average ever can.

3. **Make the 120-minute time-exit regime-aware, or just shorten it.** Your single worst BankNifty loss (-₹2,547) was a bearish trade held through a reversal that had already started — the trade was arguably right for the first 30-40 minutes and wrong for the last 80. A shorter default (45-60 min) with an explicit override for genuine trend days would cut a lot of that bleed.

4. **Rescale exit thresholds to be proportional to premium, not flat rupee points** — already flagged earlier, repeating here because it interacts directly with volatility handling: a flat 150-point target on a ₹35 NIFTY premium behaves completely differently under volatility than the same 150 points on a ₹500 BankNifty premium. Fix this before trying to tune anything else, because right now it's confounding every other comparison you'd want to make.

5. **Deduplicate or genuinely implement the Expansion tier.** Either build real Supertrend/CMF/VWAP/Bollinger/OI logic (there's real value in true multi-indicator confluence, if it's actually computed), or consciously retire the 6 strategies that are currently identical twins of each other. Right now they add apparent signal count without adding real information — which is a bad trade specifically in a choppy market, where you want fewer, better-confirmed entries, not more redundant ones.

---

## Bottom line, as you asked for directly

Your 44-strategy roster has **one genuinely well-built family** (Support Bounce/Resistance Rejection), **three reasonable-but-improvable families** (ORB, MACD, Heikin-Ashi), and **a third of the roster (the Expansion tier) that is more marketing than math** — sophisticated names attached to a 2-EMA check, in six cases literally identical to two other "different" strategies. None of this is fatal to your 3-month plan, but I would not let the clock start while a third of your strategies are silently duplicating each other under different names — you'd be spending three months measuring 9 ideas while believing you're measuring 44.
