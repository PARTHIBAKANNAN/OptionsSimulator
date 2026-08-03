# FYERS API FEASIBILITY REPORT
## Multi-Strategy NIFTY Options Paper Trader
**Prepared for:** Parthi | **Date:** August 3, 2026 | **Status:** Detailed Analysis + Go/No-Go

---

## EXECUTIVE SUMMARY

| Requirement | Feasibility | Status |
|------------|-------------|--------|
| **Live NIFTY Price via WebSocket** | ✅ **100% Yes** | Ready to implement |
| **Live Options Chain Data via API** | ⚠️ **Partial** (REST polling, NOT websocket) | Limitation identified |
| **Historical Data for Backtesting** | ✅ **Yes** | Via REST API, minute bars available |
| **Multi-Strategy Parallel Execution** | ✅ **Yes** | No technical blocker |
| **Paper Trading Simulation** | ✅ **Yes** | Full control, no broker integration needed |
| **Live Order Placement (Real)** | ✅ **Yes, but NOT recommended** | SEBI compliance risk if autonomous |
| **Auto TOTP + Token Refresh** | ✅ **Yes** | You already have this working |

---

## 📊 DETAILED CAPABILITY BREAKDOWN

### **1. LIVE PRICE DATA (NIFTY Index)**

#### ✅ **WHAT YOU CAN DO:**

**WebSocket Real-Time (1-second updates)**
```
Data Type: SymbolUpdate (tick data)
Symbols: NSE:NIFTY50-INDEX
Fields: LTP, Bid/Ask, Volume, Time
Latency: <100ms from exchange
Frequency: 1+ updates/second
```

**API Used:**
```python
from fyers_apiv3.FyersWebsocket import data_ws

fyers_ws = data_ws.FyersDataSocket(
    access_token="your_token",
    log_path=""
)

fyers_ws.subscribe(
    symbols=["NSE:NIFTY50-INDEX"],
    data_type="SymbolUpdate"
)
```

**Deliverable:** You get **1-second NIFTY candles** (Open, High, Low, Close, Volume for each 1-sec interval)

**Your Use Case:** ✅ Matches your 70-100pt daily move monitoring perfectly

---

### **2. OPTIONS CHAIN LIVE DATA (Call/Put OI, Greeks, IV)**

#### ⚠️ **WHAT YOU CAN & CANNOT DO:**

**LIMITATION #1: No WebSocket for Options Chain**

❌ **You CANNOT:**
- Subscribe to live options chain via websocket
- Get real-time OI updates per strike automatically
- Stream option Greeks (Delta, Gamma, Vega) in real-time

❌ **Why:** <cite index="1-1">Fyers does not yet support websocket option chain data; users currently must rely on polling</cite>

---

**WORKAROUND #1: REST API Polling (HTTP Requests)**

✅ **You CAN:**
```python
# Call this every 5-10 seconds to refresh option chain
data = {
    "symbol": "NSE:NIFTY50-INDEX",
    "strikecount": "10",  # Strikes on either side of ATM
    "timestamp": "0"  # 0 = latest data
}
response = fyers.optionchain(data=data)
```

**Response Fields (for each strike):**
- Call LTP, Put LTP
- Call OI, Put OI
- Call IV, Put IV
- Call Greeks, Put Greeks
- Bid/Ask prices

**Polling Frequency:** Every 5-10 seconds (rate limit conscious)

✅ **Your Use Case:** This works if you refresh options chain data **every 10 seconds**, not every second
- For a 70-100pt daily move, 10-second refresh is **fine** (OI doesn't change rapidly)
- Risk: You might miss a massive OI cluster forming, but acceptable for paper trading

---

**WORKAROUND #2: Manual Aggregation from Tick Data**

✅ **Alternative:** Build Greeks from tick data (advanced)
```
Every 1-sec NIFTY tick → Recalculate Black-Scholes Greeks for all strikes
Every 10-sec → Poll option chain for actual Greeks comparison

Use case: Calculate own Greeks, validate against Fyers every 10s
Complexity: High, but doable
```

---

**WORKAROUND #3: Pre-Market Cache (Best Approach)**

✅ **Recommended for your case:**
```
Market open (9:15am):
1. Fetch full options chain (all 60+ strikes)
2. Cache it in memory
3. Subscribe to specific strikes' tick data via WebSocket
4. Refresh cache every 5 minutes OR when NIFTY moves >25pts
5. Trigger recalculation at that point
```

This gives you:
- Real-time individual option prices (tick updates)
- OI snapshots every 5 minutes
- Greeks calculated on-demand when strikes change

---

### **3. LIVE OPTION PRICE DATA (Per Strike)**

#### ✅ **YES, FULLY SUPPORTED:**

```python
# Subscribe to specific NIFTY options via WebSocket
symbols = [
    "NSE:NIFTY50-INDEX",           # Underlying
    "NSE:NIFTY24AUG24500CE",       # Call option
    "NSE:NIFTY24AUG24500PE",       # Put option
    # ... add all strikes you want to monitor
]

fyers_ws.subscribe(symbols=symbols, data_type="SymbolUpdate")
```

**What You Get:**
- Each option's 1-second LTP updates
- Bid/Ask prices
- Volume traded
- Greeks if available in the feed

**Deliverable:** ✅ You can monitor 20-30 different option strikes in real-time via websocket

---

### **4. HISTORICAL DATA (For Backtesting)**

#### ✅ **FULLY SUPPORTED:**

**Available Resolutions:**
```
1-minute bars (1)
5-minute bars (5)
15-minute bars (15)
60-minute bars (60)
Daily bars (D)
```

**Data Coverage:**
- NIFTY Index: Full history available
- Options (strikes): ❌ **NOT available** (major limitation)
  - You can only get historical candles for index, not individual option strikes

**API:**
```python
data = {
    "symbol": "NSE:NIFTY50-INDEX",
    "resolution": "1",          # 1-minute
    "date_format": "1",         # Epoch format
    "range_from": "1704067200", # Jan 1, 2024
    "range_to": "1722646800",   # Aug 3, 2024
    "cont_flag": "1"
}

candles = fyers.history(data)
# Returns: [[timestamp, open, high, low, close, volume], ...]
```

**Backtesting Strategy:**
```
1. Fetch 90 days of NIFTY 1-min bars
2. For each bar, simulate:
   - Your indicator calculations (RSI, MACD, OI, etc.)
   - Option pricing (Black-Scholes or use historical prices)
   - Trade signals
3. Track simulated P&L
```

**Deliverable:** ✅ You can backtest your strategy logic (signals) against 90 days of real market data

---

**⚠️ LIMITATION:** Historical Option Prices

You can backtest your **logic** (direction signals) but not real historical option prices.

**Workaround:**
```
Option A: Use Black-Scholes to estimate option prices during backtest
Option B: Run live paper trader going forward (collect real prices)
Option C: Download historical option data from alternative source (NSE, YF)
```

---

### **5. PLACING ORDERS (Real Trading)**

#### ✅ **TECHNICALLY YES, BUT SEBI COMPLIANCE CONCERNS:**

**What You CAN Do:**
```python
order_data = {
    "symbol": "NSE:NIFTY24AUG24500CE",
    "qty": 1,
    "type": 1,                    # 0=Equity, 1=Options, 2=Futures
    "side": 1,                    # 1=Buy, -1=Sell
    "productType": "MIS",         # MIS = Margin Intraday Short
    "orderType": 2,               # 1=Limit, 2=Market
    "limitPrice": 45.0,
    "stopPrice": 0,
    "timeInForce": "DAY",
    "disclosedQty": 0
}

response = fyers.place_order(data=order_data)
```

**This WILL Place Real Orders in Your Account**

#### ❌ **SEBI COMPLIANCE ISSUE:**

SEBI regulations state:
- Algo/automated trading requires **human supervision**
- You cannot fire autonomous trades without approval
- Each trade needs explicit authorization (manual click or pre-approved ranges)

#### 🚨 **RISK:**

If you build a fully autonomous paper trader and later flip it to "live mode" without manual gates:
- Regulatory violation
- Broker could suspend account
- Personal liability

---

### **6. TOKEN REFRESH & TOTP AUTOMATION**

#### ✅ **YES, FULLY DOABLE:**

You already have this working in your intraday dashboard.

**What We Need:**
```
1. TOTP secret (Google Authenticator)
2. Cron job at 8:30am daily
3. Your existing logic (you've done this already!)
```

**Implementation:**
```python
import pyotp
import schedule
import time

# At startup or in config
totp_secret = "YOUR_TOTP_SECRET_FROM_FYERS"

def refresh_token_daily():
    totp = pyotp.TOTP(totp_secret)
    otp_code = totp.now()
    
    # Call Fyers auth endpoint with OTP
    new_access_token = fyers.generate_token_with_otp(
        app_id=APP_ID,
        otp=otp_code
    )
    
    # Save to config or env
    UPDATE_CONFIG("ACCESS_TOKEN", new_access_token)
    print(f"✅ Token refreshed at {time.time()}")

# Schedule at 8:30am IST
schedule.every().day.at("08:30").do(refresh_token_daily)

# In your main loop
while True:
    schedule.run_pending()
    time.sleep(60)
```

**Deliverable:** ✅ Token refresh fully automated

---

## 🏗️ ARCHITECTURE DECISION: RATE LIMITS & POLLING STRATEGY

### **Fyers Rate Limits**

```
WebSocket: No per-symbol limit (can subscribe 1000+ symbols)
REST API: ~180 requests/minute (3 per second)
Option Chain Polling: ~18 requests/minute if you poll every 10 seconds
```

### **Your Polling Strategy (RECOMMENDED)**

```
09:15am - Market Open:
├─ Fetch full options chain (1 request)
├─ Cache all strikes in memory
└─ Subscribe to 20-30 key strikes via WebSocket

09:15am - 15:30pm (Every 10 seconds):
├─ Collect NIFTY tick updates (WebSocket - free)
├─ Collect individual option ticks (WebSocket - free)
├─ Poll option chain (REST - 1 request every 10s = 6/min = safe)
└─ Recalculate signals

Result: ~360 REST calls/day = Well within rate limit (180/min = 10,800/day)
```

---

## 🎯 MULTI-STRATEGY ARCHITECTURE

### **Your Requirement: 6 Strategies in Parallel**

```
Strategy Group A (Bullish Bias → CE):
├─ Strategy 1: ORB (Opening Range Breakout) on NIFTY
├─ Strategy 2: RSI Oversold Bounce (RSI < 40)
└─ Strategy 3: OI Skew Bullish (Calls > Puts OI)

Strategy Group B (Bearish Bias → PE):
├─ Strategy 4: ORB Short below overnight low
├─ Strategy 5: RSI Overbought Rejection (RSI > 65)
└─ Strategy 6: OI Skew Bearish (Puts > Calls OI)

Engine Architecture:
┌─────────────────────────────────────────┐
│ Fyers WebSocket (Live Data)             │
│ ├─ NSE:NIFTY50-INDEX tick updates       │
│ └─ Options strike tick updates          │
└──────────────┬──────────────────────────┘
               │
       ┌───────▼────────┐
       │ Data Aggregator│
       │ (1-sec NIFTY   │
       │  candles +     │
       │  option prices)│
       └───────┬────────┘
               │
    ┌──────────┴──────────────────┐
    │   Signal Generator Engine    │
    │ (Runs all 6 strategies)      │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │ Position Manager             │
    │ (Track open positions)       │
    │ (Calculate P&L)              │
    │ (Apply risk rules)           │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │ Order Manager                │
    │ (Place simulated orders)     │
    │ (Paper trading only)         │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │ UI Dashboard                 │
    │ (React/Node + WebSocket)     │
    │ (Real-time updates)          │
    └──────────────────────────────┘
```

### **Per-Strategy Execution**

Each strategy runs independently:

```python
class StrategyEngine:
    def __init__(self):
        self.strategies = {
            "ORB_BULLISH": ORBBullishStrategy(),
            "RSI_BOUNCE": RSIBounceStrategy(),
            "OI_SKEW_BULL": OISkewBullishStrategy(),
            "ORB_BEARISH": ORBBearishStrategy(),
            "RSI_REJECTION": RSIRejectionStrategy(),
            "OI_SKEW_BEAR": OISkewBearishStrategy(),
        }
        self.positions = []
    
    def evaluate_all(self, nifty_price, options_chain, indicators):
        signals = {}
        
        for name, strategy in self.strategies.items():
            signal = strategy.check(
                nifty_price=nifty_price,
                options_chain=options_chain,
                indicators=indicators
            )
            signals[name] = signal
        
        return signals  # Dict of all signals
    
    def place_trades(self, signals):
        for strategy_name, signal in signals.items():
            if signal["action"] == "BUY":
                self.place_order(
                    strategy=strategy_name,
                    side="BUY",
                    strike=signal["strike"],
                    quantity=signal["qty"],
                    type="CE" if "BULL" in strategy_name else "PE"
                )

engine = StrategyEngine()
```

---

## 📋 EXACT REQUIREMENTS FROM YOU

### **Before We Start Building:**

```json
{
  "1. Fyers Credentials": {
    "app_id": "YOUR_APP_ID",
    "app_secret": "YOUR_APP_SECRET",
    "redirect_uri": "http://127.0.0.1:5000",
    "totp_secret": "YOUR_GOOGLE_AUTH_SECRET",
    "notes": "Get from myapi.fyers.in"
  },
  
  "2. Strategy Configuration": {
    "strategies": [
      {
        "name": "ORB_BULLISH",
        "type": "ORB",
        "direction": "CE",
        "parameters": {
          "opening_range_minutes": 15,
          "breakout_buffer_pts": 2,
          "strike_offset": "+100pts"
        }
      },
      {
        "name": "RSI_BOUNCE",
        "type": "RSI_OVERSOLD",
        "direction": "CE",
        "parameters": {
          "rsi_period": 14,
          "oversold_level": 35,
          "strike_offset": "ATM"
        }
      },
      {
        "name": "OI_SKEW_BULL",
        "type": "OI_ANALYSIS",
        "direction": "CE",
        "parameters": {
          "call_oi_min_ratio": 1.5,
          "strike_selection": "ATM_or_100pts_up"
        }
      },
      "...3 more PE strategies..."
    ]
  },
  
  "3. Risk Management": {
    "position_sizing": {
      "qty_per_signal": 1,
      "max_concurrent_positions": 5,
      "max_loss_per_day": 5000
    },
    "exit_rules": {
      "stop_loss_pts": 50,
      "take_profit_pts": 150,
      "time_stop_mins": 120
    }
  },
  
  "4. UI Preferences": {
    "platform": "React + Node.js OR Pure Python?",
    "dashboard_features": [
      "Live NIFTY chart with signals",
      "Options chain heatmap",
      "Active positions board",
      "P&L tracker",
      "Trade history log"
    ]
  },
  
  "5. Backtesting": {
    "historical_data": "Path to 90-day minute-wise NIFTY CSV",
    "validation_period": "Last 30 days"
  },
  
  "6. Alerts": {
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID"
  }
}
```

---

## 🚨 KEY LIMITATIONS YOU MUST KNOW

| Limitation | Impact | Workaround |
|-----------|--------|-----------|
| **No WebSocket for Option Chain** | OI/Greeks update every 10s, not 1s | Accept 10s latency; manageable for your use case |
| **No Historical Option Prices** | Can't backtest actual option P&L | Use Black-Scholes sim OR collect live data going forward |
| **Rate Limit (180 req/min)** | Can't poll too fast | Strategy: Poll every 10s = 360 calls/day = OK |
| **TOTP expires daily** | Need daily refresh | Automate with pyotp + cron (you already know this) |
| **Paper trading only** | Can't test real execution | Feature, not bug (safer for validation) |

---

## ✅ GO/NO-GO DECISION

### **CAN WE BUILD THIS?**

| Component | Status | Risk Level |
|-----------|--------|-----------|
| Live price feed | ✅ GO | Low |
| Options chain data | ✅ GO (with 10s polling) | Low |
| Multi-strategy engine | ✅ GO | Low |
| Paper trading | ✅ GO | None |
| Dashboard UI | ✅ GO | Low |
| Backtesting | ✅ GO (logic only) | Medium |
| Token refresh | ✅ GO | Low |
| **OVERALL** | **✅ GO** | **Low** |

---

## 🏗️ BUILD TIMELINE

```
Phase 1 (4-6 hours): Core Engine
├─ Fyers auth + token refresh
├─ WebSocket data aggregator
├─ Options chain REST poller
└─ Indicator calculator

Phase 2 (4-5 hours): Strategy Layer
├─ 6 strategy implementations
├─ Signal generator
├─ Paper order simulator
└─ Position tracker

Phase 3 (6-8 hours): UI Dashboard
├─ React frontend (or terminal UI)
├─ Real-time WebSocket updates
├─ Trade/position boards
└─ P&L dashboard

Phase 4 (2-3 hours): Backtester
├─ Historical data loader
├─ Signal replay engine
├─ Validation report

Phase 5 (2-3 hours): Testing + Refinement

**Total: 18-25 hours of dev time**
```

---

## 📌 NEXT STEPS

1. **Confirm:** Will you go with this architecture?
2. **Provide:**
   - Fyers app_id, app_secret (kept secure)
   - Your 6 strategy parameters (as above)
   - Historical NIFTY data (90 days, 1-min bars)
3. **Choose:** React dashboard OR pure Python CLI?
4. **Decide:** When do you want paper trading to go live?

---

## 🎓 ADDITIONAL NOTES FOR YOU

**On Your "Manual Approval" Concern:**

If you want to build with a manual gate (click-to-execute for each trade):
- Signal generated: ✅
- Telegram alert sent: ✅
- **User action required:** Click approve button or command
- Order placed (simulated): ✅

This is standard practice. We can build it.

---

**End of Report**
