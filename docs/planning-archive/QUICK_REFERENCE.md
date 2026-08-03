# Quick Reference Card
## NIFTY Options Paper Trader - Everything at a Glance

---

## **PROJECT OVERVIEW**

**What:** 6-strategy parallel NIFTY options paper trader with Fyers integration  
**Why:** Backtest + validate strategies risk-free before live trading  
**How:** WebSocket for live prices, REST polling for OI chain, simulate trades  
**Timeline:** 4-5 days  
**Tech:** Python 3.9+, Fyers API, Telegram, SQLite

---

## **THE 6 STRATEGIES (Backtest Ranking Order)**

### **BULLISH (CE)**
1. **MACD_BULLISH** - MACD cross above zero + volume spike + price > 50-EMA (Confidence: 80%)
2. **RSI_OVERSOLD_BULLISH** - RSI < 35 + Stoch < 20 + price > 20-EMA (Confidence: 75%)
3. **SUPPORT_BOUNCE_BULLISH** - Price tests 20-EMA + close > EMA + volume (Confidence: 70%)

### **BEARISH (PE)**
1. **MACD_BEARISH** - MACD cross below zero + volume spike + price < 50-EMA (Confidence: 80%)
2. **RSI_OVERBOUGHT_BEARISH** - RSI > 65 + Stoch > 80 + price < 20-EMA (Confidence: 75%)
3. **RESISTANCE_REJECTION_BEARISH** - Price tests resistance + close < resistance + volume (Confidence: 70%)

---

## **PROJECT STRUCTURE (Final)**

```
nifty-options-trader/
├── src/
│   ├── trader.py ..................... MAIN ENTRY POINT
│   ├── config.py ..................... Load config + validate
│   ├── fyers/
│   │   └── api_client.py ............. Fyers API + WebSocket
│   ├── data_manager.py ............... Real-time ticks → candles + indicators
│   ├── strategies/
│   │   ├── base_strategy.py .......... Base class for all strategies
│   │   ├── rsi_oversold_bullish.py ... Strategy 1
│   │   ├── macd_bullish.py ........... Strategy 2
│   │   ├── support_bounce_bullish.py . Strategy 3
│   │   ├── rsi_overbought_bearish.py . Strategy 4
│   │   ├── macd_bearish.py ........... Strategy 5
│   │   └── engine.py ................. Run all strategies
│   ├── simulator/
│   │   └── paper_trader.py ........... Simulated order execution + P&L
│   ├── backtester/
│   │   ├── backtest_engine.py ........ Replay 90 days + generate report
│   │   └── report.py ................. Format results
│   ├── alerts/
│   │   └── telegram_alerts.py ........ Send alerts + buttons
│   ├── persistence/
│   │   └── state_manager.py .......... Save/load state
│   ├── utils/
│   │   ├── logger.py ................. Structured logging
│   │   └── indicators.py ............. Calculate RSI, MACD, EMA, etc.
│   └── dashboard/
│       └── terminal_ui.py ............ Live monitoring UI (optional)
├── tests/
│   ├── test_strategies.py
│   ├── test_paper_trader.py
│   └── test_data_manager.py
├── config/
│   └── risk_params.json
├── data/
│   ├── historical/
│   │   └── nifty_90days.csv
│   └── backtest_results/
├── logs/ (auto-created)
├── .env (create from .env.example)
├── requirements.txt
└── main.py or entry point
```

---

## **PHASED BUILD TIMELINE**

```
DAY 1 (6-7 hours)
├─ PHASE 1: Core Infrastructure (4-6h)
│  ├─ Fyers API client (1h)
│  ├─ Data manager (1.5h)
│  ├─ Paper trader (1.5h)
│  └─ Config + Logger (1h)
├─ PHASE 2: Strategies (2-3h)
│  ├─ Base strategy class (0.5h)
│  ├─ Implement 5 strategies (1.5h)
│  └─ Strategy engine (0.5h)

DAY 2 (5-6 hours)
├─ PHASE 3: Backtesting (2-3h)
│  ├─ Backtest engine (1.5h)
│  ├─ Report generator (0.5h)
│  └─ Run backtest + select top-6 (1h)
├─ PHASE 4: Live Engine (3-4h)
│  ├─ Main trading loop (2h)
│  ├─ Telegram alerts (1h)
│  └─ State persistence (0.5h)

DAY 3 (6-8 hours)
├─ PHASE 5: Dashboard (6-8h) [OPTIONAL]
│  ├─ Terminal UI (3-4h)
│  └─ Or React + Node.js (6-8h)

DAY 4 (2-3 hours)
├─ PHASE 6: Testing & Polish
│  ├─ Unit tests (1.5h)
│  ├─ Integration testing (1h)
│  └─ Refinement (0.5h)

TOTAL: 18-25 hours of dev time
```

---

## **KEY PROMPTS FOR CLAUDE CODE AGENT**

| Phase | Prompt | Expected Output |
|-------|--------|-----------------|
| 1A | "Implement src/fyers/api_client.py" | FyersAPIClient class with auth + WebSocket |
| 1B | "Implement src/data_manager.py" | DataManager class with candle building + indicators |
| 1C | "Implement src/simulator/paper_trader.py" | PaperTrader class with order execution |
| 1D | "Implement src/config.py and src/utils/logger.py" | Config + Logger classes |
| 2 | "Implement all 5 strategies" | All strategy files with evaluate() methods |
| 3 | "Implement src/backtester/" | BacktestEngine + report generation |
| 4 | "Implement src/trader.py" | Main trading loop with WebSocket + polling |
| 4B | "Implement src/alerts/telegram_alerts.py" | TelegramAlertsManager with buttons |
| 4C | "Implement src/persistence/state_manager.py" | State save/load for recovery |
| 5 | "Implement src/dashboard/terminal_ui.py" | Live terminal UI (optional) |
| 6 | "Implement tests/" | Unit tests for all modules |

---

## **DATA REQUIREMENTS**

### **You Must Provide:**

```
1. Fyers Credentials (.env)
   - FYERS_APP_ID
   - FYERS_APP_SECRET
   - FYERS_TOTP_SECRET (base32 from Google Auth)
   
2. Telegram Credentials (.env)
   - TELEGRAM_BOT_TOKEN
   - TELEGRAM_CHAT_ID

3. Historical Data (data/historical/nifty_90days.csv)
   - Format: Timestamp,Open,High,Low,Close,Volume
   - Duration: 90 days (last 90 trading days)
   - Frequency: 1-minute bars
   - Expected rows: ~35,100

4. Risk Parameters (config/risk_params.json)
   - Position sizing (qty, max concurrent, daily loss limit)
   - Exit rules (SL, TP, time exit)
   - Strike selection (ATM vs OTM)
```

---

## **CORE CLASSES & METHODS**

### **FyersAPIClient**
```python
client = FyersAPIClient(app_id, secret, totp_secret)
client.authenticate_with_totp()  # Get access token
client.start_websocket(on_tick_callback)
client.subscribe_symbols(["NSE:NIFTY50-INDEX", "NSE:NIFTY24AUG24500CE"])
chain = client.get_option_chain("NSE:NIFTY50-INDEX")
```

### **DataManager**
```python
dm = DataManager(window_size=100)
dm.on_nifty_tick(tick_data)  # Process each tick
dm.update_option_chain(chain_data)  # Every 10 seconds
indicators = dm.calculate_indicators()
state = dm.get_state()  # For strategies
```

### **PaperTrader**
```python
trader = PaperTrader(initial_capital=1000000)
order = trader.place_order("NIFTY24500CE", "BUY", 1, 65.0, sl=60, tp=150)
trader.update_positions({'NIFTY24500CE': 72.0})
pnl = trader.get_pnl()
positions = trader.get_positions()
```

### **StrategyEngine**
```python
engine = StrategyEngine([strategy1, strategy2, ...])
signals = engine.evaluate_all(data_state)  # Returns list[Signal]
report = engine.backtest(historical_data)
```

### **LiveTrader (Main)**
```python
trader = LiveTrader(config)
await trader.start()  # Starts WebSocket + polling
# ... signals generated → alerts sent → orders executed
trader.stop()  # Graceful shutdown
```

---

## **TYPICAL EXECUTION FLOW**

```
1. User starts: python src/trader.py
   
2. LiveTrader initializes:
   ├─ Fyers API authentication (with TOTP)
   ├─ Start WebSocket for NIFTY + option strikes
   ├─ Load last backtest results
   └─ Load saved positions (if restart)

3. On each NIFTY tick (real-time):
   ├─ DataManager.on_nifty_tick()
   ├─ Build 1-min candles
   ├─ Calculate indicators
   └─ Trigger strategy evaluation

4. Every 10 seconds:
   ├─ poll_option_chain() via REST
   ├─ Update DataManager.option_chain
   └─ Check for OI-based signals

5. When signal generated:
   ├─ Log signal (signals.log)
   ├─ Send Telegram alert
   ├─ Wait for user approval (button tap)
   ├─ Place simulated order
   ├─ Update positions
   └─ Calculate unrealized P&L

6. On position exit (SL/TP/time):
   ├─ Close position
   ├─ Calculate realized P&L
   ├─ Log trade (trades.log)
   └─ Send completion alert

7. Continuous:
   ├─ Update position P&L every second
   ├─ Save state every 5 minutes
   └─ Send daily summary at market close

8. On shutdown (Ctrl+C):
   ├─ Close all positions
   ├─ Save final state
   ├─ Close WebSocket
   └─ Exit gracefully
```

---

## **TROUBLESHOOTING**

| Issue | Solution |
|-------|----------|
| **Import error: `fyers_apiv3` not found** | `pip install fyers-api` |
| **WebSocket disconnects after 30min** | Add auto-reconnect logic in api_client.py |
| **Backtest doesn't match live P&L** | Check slippage% match, verify option prices |
| **Signals not generating** | Verify indicators calculated correctly, check threshold values |
| **Telegram alerts not sending** | Check bot token + chat ID, verify internet connection |
| **Historical data missing values** | Validate CSV format, ensure no gaps in timestamps |
| **Paper trader positions not closing on SL** | Verify SL price being checked correctly |
| **TOTP expires before 8:30am** | Token refresh scheduled before market open |

---

## **PERFORMANCE EXPECTATIONS**

### **After 90-Day Backtest:**
```
Expected Results (based on NIFTY dynamics):
├─ Total trades: 150-250
├─ Win rate: 55-65%
├─ Profit factor: 1.5-2.2
├─ Total P&L: ₹20,000 - ₹50,000 (simulated)
├─ Max drawdown: -5% to -15%
├─ Consecutive wins: 5-8
└─ Consecutive losses: 2-4
```

### **Live Trading First Day:**
```
First day benchmarks:
├─ Signals generated: 3-8
├─ Trades executed: 2-5
├─ Successful trades: 50-70%
├─ Daily P&L: ±₹500 - ₹2,000
└─ Realized slippage: 0.1-0.3%
```

---

## **CHECKLIST: BEFORE GOING LIVE**

- [ ] Backtest completed, report reviewed
- [ ] Top-6 strategies selected (3 CE + 3 PE)
- [ ] All unit tests passing
- [ ] WebSocket connection stable (tested 30+ min)
- [ ] Telegram alerts working (test message sent/received)
- [ ] Paper trader P&L calculation verified
- [ ] State persistence tested (restart + recover)
- [ ] Position exit logic verified (SL/TP works)
- [ ] Risk parameters set conservatively
- [ ] Logs generated properly (trades.log, signals.log, errors.log)
- [ ] Historical data loaded and validated
- [ ] Market hours set correctly (9:15-15:30 IST)
- [ ] TOTP refresh scheduled for 8:30 AM

---

## **WHAT'S NOT INCLUDED (Out of Scope)**

- ❌ Real money trading (paper only)
- ❌ Advanced Greeks calculation (use Black-Scholes estimate)
- ❌ Multi-expiry handling (today's expiry only)
- ❌ Sector hedge strategies (NIFTY directional only)
- ❌ ML/reinforcement learning strategies
- ❌ Options spread strategies (single leg only)
- ❌ Sentiment analysis or news feeds
- ❌ Advanced portfolio optimization

---

## **QUICK START (5 Minutes)**

```bash
# 1. Create project
mkdir nifty-options-trader && cd nifty-options-trader

# 2. Setup Python
python -m venv venv
source venv/bin/activate

# 3. Create dirs
mkdir -p src/{fyers,strategies,simulator,backtester,alerts,persistence,utils,dashboard}
mkdir -p tests data/historical config logs

# 4. Copy requirements.txt (from IMPLEMENTATION_PLAN.md)
# Install: pip install -r requirements.txt

# 5. Copy Claude Code Agent prompts
# Paste first prompt into Claude Code Agent

# 6. Wait for code generation
# Test: pytest tests/

# 7. Backtest
# python -m src.backtester.backtest_engine

# 8. Go live
# python src/trader.py
```

---

**NEXT STEP:** Open VS Code, use CLAUDE_CODE_AGENT_PROMPTS.md with Claude Code Agent 🚀
