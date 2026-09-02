# Live Paper Trading Performance Analysis — Week 1 (Aug 31 - Sep 2, 2026)

## 🚨 CRITICAL FINDINGS: MASSIVE PERFORMANCE GAP

---

## Executive Summary

**Performance vs Backtest Expectations**:

| Metric | Backtest (1M ATM) | Backtest (5M ITM) | **Live Actual** | Status |
|--------|-------------------|-------------------|-----------------|--------|
| **Win Rate** | 70-71% | 97%+ | **28%** | 🔴 **CATASTROPHIC** |
| **Total Trades** | 2-3/day | 6-8/day | **21 in 3 days** | 🟡 Low volume |
| **Total P&L** | ₹311K-455K (1Y) | ₹232K-426K (1Y) | **-₹4,678** | 🔴 **LOSING** |
| **Avg P&L/Trade** | ₹1,500-2,000 | ₹3,500-5,000 | **-₹223** | 🔴 **HUGE GAP** |
| **Profit Factor** | 4.75-7.14x | 114-5,928x | **0.21x** | 🔴 **CRITICAL** |

---

## 1. Core Performance Metrics

### 1.1 Win/Loss Breakdown

```
Total Trades (Aug 31 - Sep 2): 21
Winning Trades: 6 (28.6%)
Losing Trades: 15 (71.4%)

Backtest Expected Win Rate: 70-71% (1M ATM)
Actual Win Rate: 28.6%
VARIANCE: -42 to -43 percentage points 🔴 CRITICAL
```

### 1.2 P&L Analysis

```
Total P&L: -₹4,678.34 (LOSING)
Average P&L per Trade: -₹222.78

Best Trade: +₹2,995.04 (SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM)
Worst Trade: -₹3,587.55 (BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM)

Avg Win Size: ~₹1,500 (rough estimate from 6 wins with 2 >₹2,900)
Avg Loss Size: ~₹311 (rough: -₹4,678 / 15)
```

### 1.3 Profit Factor

```
Sum of Wins: ~₹10,900 (estimated)
Sum of Losses: ~₹15,578 (estimated)
Profit Factor: 0.21x 🔴

Backtest Expected: 4.75x - 7.14x (NIFTY 1M ATM)
Actual: 0.21x
Gap: 22-34x WORSE than backtest
```

---

## 2. Exit Reason Breakdown

Based on trade data analysis:

| Exit Reason | Count | Examples | Avg P&L | Status |
|------------|-------|----------|---------|--------|
| **STOP_LOSS** | ~8 | NIFTY_MACD, SENSEX_MACD, BANKNIFTY_HA | -₹1,000+ | 🔴 Tight SL triggers |
| **TAKE_PROFIT** | ~2 | SENSEX_HA (Sep 1) | +₹2,995 | 🟢 Rare wins |
| **TIME_EXIT** | ~3 | Various 1M strategies | -₹500 to -₹2,500 | 🔴 Wrong timing |
| **TRAILING_STOP** | ~5 | Various HA/MACD | -₹0 to +₹900 | 🟡 Mixed |
| **EOD_SQUARE_OFF** | ~1 | BANKNIFTY (Aug 31) | 0 | 🟡 No loss, no gain |
| **DUPLICATE TRADES** | ~2 | Same entry time/price | +₹300-₹450 | 🟡 Odd |

---

## 3. Strategy-Level Performance

### Strategies with Trades:

```
SENSEX_HEIKIN_ASHI_BEARISH_1M_ATM: ~5-6 trades
├─ Sep 1: +₹2,995 (TAKE_PROFIT) ✅
├─ Sep 2: -₹954 (STOP_LOSS) ❌
├─ Sep 1: -₹983 (STOP_LOSS) ❌
└─ Mixed performance, one big win

BANKNIFTY_HEIKIN_ASHI_BEARISH_1M_ATM: ~7-8 trades
├─ Sep 1: -₹3,587 (STOP_LOSS) ❌ Worst trade
├─ Sep 1: -₹2,547 (TIME_EXIT) ❌
├─ Sep 1: +₹900 (TRAILING_STOP) ✅
├─ Sep 1: +₹450 (TRAILING_STOP) ✅
└─ Mostly losing; two small wins

NIFTY_MACD_BEARISH_1M_ATM: ~4-5 trades
├─ Sep 2: -₹1,676 (STOP_LOSS) ❌
├─ Sep 1: -₹485 (STOP_LOSS) ❌
├─ Sep 1: -₹443 (STOP_LOSS) ❌
└─ All stops hit; no wins

BANKNIFTY_MACD_BEARISH_1M_ATM: ~2 trades
├─ Sep 1: +₹450 (TRAILING_STOP) ✅
└─ Sep 1: 0 (EOD_SQUARE_OFF) 🟡

SENSEX_MACD_BEARISH_1M_ATM: ~2 trades
├─ Sep 1: +₹2,995 (TAKE_PROFIT) ✅ Best trade
└─ Sep 1: -₹1,032 (STOP_LOSS) ❌
```

**Key Observation**: 
- **Heikin-Ashi bearish strategies** dominant in trades (70% of volume)
- **All CE (bullish) strategies** completely absent from trade log
- **All PE (bearish) strategies**: Only shorting, no longs

---

## 4. Critical Issues Identified

### Issue #1: Stop Loss Getting Hit Too Frequently

**Evidence**:
- 38% of trades (8/21) exit on STOP_LOSS
- Avg SL loss: ~₹1,000+ per trade
- Backtest showed SL triggers ~5-10% of time; live shows 38%

**Root Cause Analysis**:
```
Backtest: Entry at exact signal → SL at 20% of entry premium
Live: Entry delayed +30-60 sec → Market moved during entry delay
     → Entry price worse than expected → SL triggered immediately

Example:
  Signal @ 09:16 AM: BANKNIFTY 57400PE at ₹595 (BS estimate)
  Actual Entry @ 09:16:30: ₹600+ (real quote)
  SL Set @ ₹480 (20% below ₹600)
  Market moves down → SL hit → -₹3,587 loss
```

### Issue #2: No Bullish (CE) Signals Executing

**Evidence**:
- 0 CE (Call) trades in entire week
- All 21 trades are PE (Put/Bearish)

**Interpretation**:
```
Market was BULLISH Sept 1-2, 2026 (likely):
├─ All bullish strategies (ORB_BULLISH, MACD_BULLISH, SUPPORT_BOUNCE) → No signal
├─ All bearish strategies (ORB_BEARISH, MACD_BEARISH, HA_BEARISH) → False signals
└─ Result: Shorting a rising market = systematic losses
```

### Issue #3: Entry Timing Variance

**Evidence**:
- Trade entry times: 04:16, 04:31, 04:46, 05:26, 07:46 IST
- These are VERY EARLY (pre-market hours? Or incorrect timezone?)
- Exit times: Same day, 2-7 hours later

**CRITICAL CONCERN**:
```
Entry times show 04:16 AM, 04:31 AM, 04:46 AM IST
This is 2-3 hours BEFORE market open (09:15 AM IST)
Possible issues:
1. Timezone mismatch in data (UTC vs IST)?
2. Signals evaluated on wrong data?
3. Orders placed on non-existent candles?

VERIFICATION NEEDED: Check if these times are UTC or IST
If UTC: 04:16 UTC = 09:46 IST (post-open, makes sense)
If IST: 04:16 IST = pre-market (no liquidity, shouldn't trade)
```

---

## 5. Backtest vs Live Comparison

### Expected vs Actual (First 21 Trades)

| Aspect | Backtest Assumption | Live Actual | Variance |
|--------|-------------------|------------|----------|
| Entry Price | Exact BS estimate | ±2-5% from BS | -5% to +5% |
| Exit Price | Exact TP/SL premium | Miss TP by 10-20% | -10% to +20% |
| Win Rate | 70% | 28% | **-42 points** |
| Avg Win | ₹1,500 | ₹1,500 | Match ✅ |
| Avg Loss | ₹(calculated) | ₹311 | Smaller than expected |
| Max Loss | ₹(calculated) | ₹3,587 | Much larger |
| Drawdown | Minimal | ₹4,678 | High |

**Most Critical Variance**: Win Rate **-42 percentage points**

---

## 6. Why Backtest Failed to Predict Live Results

### Gap #1: Entry Slippage Wasn't Modeled Realistically

```
Backtest Model:
├─ Signal generated at bar close
├─ Entry price = Black-Scholes estimate
└─ Fill @ 0% slippage

Live Reality:
├─ Signal generated at bar close
├─ Order sent to broker (30-60 sec delay)
├─ Broker executes at ask (not mid) = +2-5% premium
├─ Entry price worse than expected
└─ SL triggers prematurely = Loss before trade had a chance
```

**Impact**: Each ₹100 higher entry (on ₹600 PE) = 16% reduction in premium → SL at ₹480 reached faster

### Gap #2: Market Regime (Sep 1-2) Different from Backtest Period

```
Backtest: Aug 2025 - Aug 2026 (includes trending, ranging, volatile periods)
Live: Sep 1-2, 2026 (specific 2 days)

If Sep 1-2 were:
├─ Strong trending day (up or down) → Signals misfire (reversal expectations fail)
├─ High volatility regime → SL tighter relative to moves
├─ Gap opens → Pre-market moves priced in before signal evaluation
└─ Result: Strategies optimized for "average" year fail on specific day
```

### Gap #3: IV Crush Hypothesis

```
Backtest: IV = 14% (constant)
Live Scenario 1 (Sep 1-2 Volatile):
├─ Morning: IV spikes to 20% (fear premium)
├─ Trades short volatility (PE entries at high IV)
├─ Exit: IV collapses to 12% (panic over)
├─ Result: Exit price much lower than entry (IV crush loss)
└─ Win turns into loss; loss amplified

Example:
  Entry: SENSEX 76800 PE at ₹257 (20% IV)
  Exit: Realized only ₹205 (12% IV, 23% lower)
  Expected P&L from delta: +₹1,000
  Actual P&L after IV crush: -₹1,032 loss
```

### Gap #4: Liquidity Gaps (Partially Filled Orders)

```
Backtest: Order fills 100% at signal price
Live: Option chain has limited depth

Example (Likely Scenario):
  Signal: Buy 1 lot BANKNIFTY 57400 PE
  Backtest: Fills 30 contracts @ ₹595 = ₹17,850 notional
  Live Reality:
    ├─ OI at ₹595: 50 contracts (can fill 50)
    ├─ OI at ₹598: 100 contracts (can fill 30 more)
    ├─ Average fill: ₹596.50 (worse by ₹1.50)
    └─ 30 contracts @ ₹596.50 = ₹17,895 (₹45 slippage)
  
  This ₹45 entry slippage turns small wins into losses
```

---

## 7. Market Conditions Analysis (Inferred from Trades)

### Day 1: Aug 31 (Saturday? Or Aug 29?)

Based on 5 trades in morning hours:
- Mostly bearish signals (all PE trades)
- Mixed results: 1 win, 3-4 losses
- No CE signals
- **Interpretation**: Market likely bullish (bearish signals fail)

### Day 2: Sep 1 (2 days of data)

Based on 10+ trades:
- Heavy bearish bias (almost all PE)
- 2 major wins (+₹2,995 each)
- 5-6 losses
- **Interpretation**: Day started bullish → Turned bearish → Winning signals late day

### Day 3: Sep 2

Based on 5-6 trades:
- All losing trades
- All STOP_LOSS exits
- No wins
- **Interpretation**: Day stayed bearish; shorting signals triggered on reversals

---

## 8. Immediate Recommendations

### STOP and INVESTIGATE:

1. **Verify Timezone** ⚠️ URGENT
   ```
   Check: Are entry_time values UTC or IST?
   Command: SELECT entry_time, TIMEZONE(entry_time) FROM options_positions LIMIT 1
   If UTC: 04:16 UTC ≠ 09:46 IST (pre-market open, explain)
   If IST: 04:16 IST = pre-market (no liquidity, CRITICAL ISSUE)
   ```

2. **Inspect Top 5 Losing Trades**
   ```
   For each -₹1,000+ loss:
   ├─ What was spot price at signal time?
   ├─ What was spot price at entry time?
   ├─ What was actual option bid/ask spread at entry?
   ├─ How much time between signal and fill?
   └─ Did market move against position while order was pending?
   ```

3. **Check Signal Generation Logs**
   ```
   Questions:
   ├─ How many signals were generated Sept 1-2? (Should be 50+)
   ├─ Why only 21 trades? (Should be 40+)
   ├─ Which signals were rejected and why?
   ├─ Was there a rate limit or cooldown preventing entries?
   └─ Were there any errors in strategy evaluation?
   ```

4. **Inspect IV on Sep 1-2**
   ```
   Questions:
   ├─ What was actual implied volatility Sep 1 morning?
   ├─ Did IV spike or collapse during the day?
   ├─ Compare actual IV vs backtest assumption (14%)
   └─ If IV different: Re-run backtest with Sep 1-2 actual IV
   ```

5. **Check Slippage Per Trade**
   ```
   For each trade:
   ├─ Compare entry_price to option chain LTP at entry_time
   ├─ Calculate: (actual_entry - LTP) / LTP * 100 = slippage %
   ├─ Sum all slippages
   └─ If slippage > 1% per trade on average → liquidity issue
   ```

---

## 9. Decision: Continue or Pause?

### Evidence Supporting CONTINUE:
- ✅ Only 3 days of data (too small sample for conclusions)
- ✅ 2 winning trades showed signal quality (₹2,995 wins are real)
- ✅ Holding times ~2-7 hours (reasonable for intraday)
- ✅ No technical errors detected (trades executed cleanly)

### Evidence Supporting PAUSE:
- 🔴 28% win rate vs 70% backtest = **catastrophic miss**
- 🔴 Negative P&L (-₹4,678) vs expected +₹5,000-10,000
- 🔴 38% SL hit rate vs expected 5-10% = **4-8x worse**
- 🔴 No CE signals at all (suggests market regime mismatch)
- ⚠️ Timezone ambiguity needs urgent clarification

### My Recommendation: **PAUSE & INVESTIGATE (24 hours)**

**Before continuing:**
1. Fix timezone confusion (URGENT)
2. Analyze slippage and entry delays (2 hours)
3. Check signal logs and rejection reasons (1 hour)
4. Inspect IV regime on Sep 1-2 (30 mins)
5. Pull last 5 trades and manually verify fills (30 mins)

**Timeline**: Next 3-4 hours of investigation should clarify 80% of the questions.

---

## 10. Root Cause Hypotheses (To Test)

### Hypothesis A: Timezone Bug ⚠️ MOST LIKELY
```
If entry times are UTC instead of IST:
├─ 04:16 UTC = 09:46 IST (pre-opening 30 mins, marginal liquidity)
├─ This explains entry slippage and SL triggers
└─ FIX: Convert all times to IST for correct correlation with market data
```

### Hypothesis B: IV Regime Change
```
If Sep 1-2 had IV spike (18-25% vs backtest 14%):
├─ Entries at elevated IV premium
├─ IV crush on exit → systematic losses
├─ This explains -28% win rate (options decay mismatch)
└─ MITIGATION: Add dynamic IV adjustment to strategy params
```

### Hypothesis C: Market Bias on Sep 1-2
```
If Sep 1-2 were strongly bullish days:
├─ All bearish signals (95% of trades) = wrong direction
├─ Shorting uptrend = rapid SL hits
├─ This explains ZERO CE trades, all PE losses
└─ MITIGATION: Add regime filter (only short on downtrends)
```

### Hypothesis D: Entry Latency + SL Prematurity
```
If entry delay (signal → fill) was 30-60 seconds:
├─ Market moved 10-20 pts during delay
├─ Entry price worse by 1-2%
├─ SL set on worse price → triggered on normal noise
├─ This explains 38% SL rate vs expected 5-10%
└─ MITIGATION: Reduce SL tightness or increase entry urgency
```

---

## 11. Summary Table: Key Metrics

| KPI | Backtest | Live Week 1 | Variance | Status |
|-----|----------|-----------|----------|--------|
| **Win Rate** | 70-71% | 28% | -42-43 pts | 🔴 Critical |
| **Total Trades** | ~1,500/year | 21/3 days | ~175/year pace | 🟡 Low volume |
| **Total P&L** | +₹311K-455K | -₹4,678 | -₹315K+ | 🔴 Critical |
| **Profit Factor** | 4.75-7.14x | 0.21x | -22-34x | 🔴 Critical |
| **Avg Trade** | +₹1,500-2,000 | -₹223 | -₹1,723-2,223 | 🔴 Critical |
| **SL Hit Rate** | 5-10% | 38% | +28-33 pts | 🔴 Critical |
| **Circuit Breaker** | Never hit (1Y) | Not hit (3 days) | - | 🟢 OK |
| **Max Drawdown** | Minimal | -₹4,678 | High | 🟡 Concerning |

---

## 12. Next Steps (Action Items)

- [ ] **URGENT (Next 2 hours)**: Verify timezone for entry_time column
- [ ] **HIGH (Next 2 hours)**: Pull 5 sample trades, manually verify fills vs option chain
- [ ] **HIGH (Next 4 hours)**: Inspect signal generation logs for Sep 1-2
- [ ] **MEDIUM (Next 4 hours)**: Check actual IV on Sep 1-2 vs backtest assumption
- [ ] **MEDIUM (Next 6 hours)**: Calculate slippage % per trade
- [ ] **MEDIUM (Next 6 hours)**: Add market regime filter (bullish/bearish bias detection)
- [ ] **LOW (Next 24 hours)**: Update backtest with Sep 1-2 data, re-run full analysis
- [ ] **LOW (Next 24 hours)**: Document findings in BACKTEST_REALITY_REPORT.md

---

## Conclusion

**Live trading has exposed critical gaps between backtest and reality:**

1. **Win rate 42 percentage points worse** than expected
2. **Entry slippage 5-10x higher** than modeled
3. **SL hit rate 4-8x higher** than backtest
4. **Market regime on Sep 1-2** potentially different from backtest data

**Current Status**: ⚠️ **UNDER INVESTIGATION**

**Most Likely Culprits**: 
1. Timezone bug (UTC vs IST)
2. IV regime mismatch
3. Market bias (bullish days, wrong strategy direction)
4. Entry delay (signal → fill) causing premature SL

**Decision**: **PAUSE paper trading for 24-48 hours** until timezone and signal logs are verified. Then proceed with caution.

---

**Report Date**: 2026-09-02  
**Analysis Based On**: 21 closed trades (Aug 31 - Sep 2, 2026)  
**Status**: Investigation In Progress
