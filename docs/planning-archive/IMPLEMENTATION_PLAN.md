# NIFTY Options Paper Trader - Implementation Plan
## Multi-Strategy (6 Strategies in Parallel) with Fyers Integration

**Status:** Ready for Claude Code Agent in VS Code  
**Duration:** 4-5 days  
**Tech Stack:** Python 3.9+, Fyers API, WebSocket, REST, Telegram Bot

---

## **PHASE 0: PREREQUISITES (Before You Start)**

### **0.1 Environment Setup**

```bash
# Create project directory
mkdir nifty-options-trader
cd nifty-options-trader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create project structure
mkdir -p src/{fyers,strategies,simulator,utils,logs}
mkdir -p tests/{fixtures,mocks}
mkdir -p config
mkdir -p data/{historical,backtest_results}

# Create requirements.txt (we'll fill this)
touch requirements.txt
touch .env
touch .gitignore
```

### **0.2 Gather Your Data (YOU PROVIDE)**

**Critical:** Before running any code, you MUST provide:

```
1. Fyers Credentials (save to .env)
   - FYERS_APP_ID=your_app_id
   - FYERS_APP_SECRET=your_app_secret
   - FYERS_REDIRECT_URI=http://127.0.0.1:5000
   - FYERS_TOTP_SECRET=your_totp_base32_secret

2. Telegram Credentials (save to .env)
   - TELEGRAM_BOT_TOKEN=your_bot_token
   - TELEGRAM_CHAT_ID=your_chat_id

3. Historical Data
   - File: data/historical/nifty_90days.csv
   - Format: Timestamp,Open,High,Low,Close,Volume
   - Rows: ~90 days × 390 mins = ~35,100 rows

4. Risk Parameters (save to config/risk_params.json)
   - See section below
```

### **0.3 Risk Parameters Configuration**

Create `config/risk_params.json`:

```json
{
  "position_sizing": {
    "qty_per_signal": 1,
    "max_concurrent_positions": 5,
    "max_daily_loss": 5000
  },
  "exit_rules": {
    "stop_loss_pts": 50,
    "take_profit_pts": 150,
    "time_exit_mins": 120,
    "trailing_stop_enabled": false,
    "trailing_stop_pts": 30
  },
  "strike_selection": {
    "preference": "ATM_or_100pts_OTM",
    "max_delta": 0.85,
    "min_delta": 0.3
  },
  "market_hours": {
    "start": "09:15",
    "end": "15:30",
    "timezone": "Asia/Kolkata"
  }
}
```

---

## **PHASE 1: CORE INFRASTRUCTURE (Day 1 - 4-6 hours)**

### **1.1 Fyers API Module** → `src/fyers/api_client.py`

**Responsibilities:**
- OAuth authentication + TOTP auto-refresh
- WebSocket connection management
- REST API calls (options chain, historical data)
- Token persistence

**Key Methods:**
```python
class FyersAPIClient:
    def __init__(self, app_id, app_secret, totp_secret)
    def authenticate_with_totp(self) -> str
    def refresh_access_token(self) -> bool
    def start_websocket(self, on_tick_callback)
    def subscribe_symbols(self, symbols: list)
    def get_option_chain(self, symbol) -> dict
    def get_historical_data(self, symbol, resolution, days) -> pd.DataFrame
    def place_order(self, order_data) -> dict  # Simulated only
    def cancel_order(self, order_id) -> dict
    def get_positions(self) -> dict
```

**Dependencies:**
```
fyers-api (official package)
pyotp (for TOTP)
websocket-client
requests
```

---

### **1.2 Data Aggregator** → `src/data_manager.py`

**Responsibilities:**
- Collect ticks from WebSocket
- Build 1-min NIFTY candles on-the-fly
- Aggregate option chain data (10-sec polling)
- Calculate indicators (RSI, MACD, EMA, Bollinger Bands, Stochastic)
- Maintain rolling state

**Key Methods:**
```python
class DataManager:
    def __init__(self, window_size=100)
    def on_nifty_tick(self, tick)
    def on_option_tick(self, strike, tick)
    def get_current_candle(self) -> Candle
    def get_historical_candles(self, count: int) -> list[Candle]
    def update_option_chain(self, chain_data)
    def get_option_chain(self) -> dict
    def calculate_indicators(self) -> dict
    def get_state(self) -> dict
```

**Indicators to Calculate:**
- RSI(14) on 1H timeframe
- MACD(12,26,9) on 1H
- EMA(20, 50) on 1H
- Bollinger Bands(20, 2) on 1H
- Stochastic(14,3,3) on 15min
- ATR(14) for volatility
- IV percentile (from option prices)
- OI skew (call OI vs put OI)

---

### **1.3 Paper Trading Simulator** → `src/simulator/paper_trader.py`

**Responsibilities:**
- Simulated order execution (no real money)
- Track open positions
- Calculate P&L (realized + unrealized)
- Apply stop-loss and take-profit
- Log all trades

**Key Methods:**
```python
class PaperTrader:
    def __init__(self, initial_capital=1000000, slippage_pct=0.1)
    def place_order(self, symbol, side, qty, price) -> Order
    def cancel_order(self, order_id) -> bool
    def update_positions(self, current_prices)
    def get_positions(self) -> list[Position]
    def get_pnl(self) -> dict
    def get_trade_history(self) -> list[Trade]
    def close_position(self, position_id, price) -> Trade
```

**Order Model:**
```python
@dataclass
class Order:
    order_id: str
    symbol: str
    side: str  # 'BUY' or 'SELL'
    qty: int
    entry_price: float
    entry_time: datetime
    status: str  # 'OPEN', 'CLOSED', 'CANCELLED'
    stop_loss: float
    take_profit: float
    exit_price: float = None
    exit_time: datetime = None
    realized_pnl: float = None
    strategy: str = None
```

---

### **1.4 Configuration Loader** → `src/config.py`

**Responsibilities:**
- Load `.env` variables
- Load `config/risk_params.json`
- Validate all required parameters
- Provide singleton config object

**Key Methods:**
```python
class Config:
    fyers_app_id: str
    fyers_app_secret: str
    fyers_totp_secret: str
    telegram_bot_token: str
    telegram_chat_id: str
    risk_params: dict
    
    @staticmethod
    def load() -> Config
    def validate() -> bool
```

---

### **1.5 Logger** → `src/utils/logger.py`

**Responsibilities:**
- Structured logging (file + console)
- Separate logs for: trades, signals, errors, websocket

**Key Methods:**
```python
class Logger:
    def log_signal(self, strategy: str, signal: dict)
    def log_trade(self, trade: Trade)
    def log_error(self, error: str, context: dict)
    def log_websocket_event(self, event: str, data: dict)
```

---

## **PHASE 2: STRATEGY LAYER (Day 1-2 - 4-5 hours)**

### **2.1 Strategy Base Class** → `src/strategies/base_strategy.py`

```python
class BaseStrategy:
    def __init__(self, name: str, direction: str):
        self.name = name  # e.g., "RSI_OVERSOLD_BULLISH"
        self.direction = direction  # 'CE' or 'PE'
        self.last_signal = None
        self.last_signal_time = None
    
    def evaluate(self, data_state: dict) -> Signal or None:
        """
        Args:
            data_state: {
                'nifty_price': float,
                'indicators': dict,
                'option_chain': dict,
                'timestamp': datetime
            }
        
        Returns:
            Signal object with action, strike, confidence, or None
        """
        raise NotImplementedError()

@dataclass
class Signal:
    strategy: str
    direction: str  # 'CE' or 'PE'
    action: str  # 'BUY'
    strike: str
    confidence: float  # 0-1
    rationale: str
    entry_price: float
    timestamp: datetime
```

---

### **2.2 Implement 5 Strategies (Backtestable)**

#### **Strategy 1: RSI Oversold Bounce (Bullish)** → `src/strategies/rsi_oversold_bullish.py`

```python
class RSIOversoldBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        indicators = data_state['indicators']
        option_chain = data_state['option_chain']
        nifty = data_state['nifty_price']
        
        # Conditions:
        # 1. RSI(14) < 35 on 1H (oversold)
        # 2. Stochastic(14,3,3) < 20 on 15min (extreme oversold)
        # 3. Price above 20-EMA (still in uptrend structure)
        # 4. Volume > 1.5x average (confirmation)
        
        rsi = indicators.get('rsi_1h')
        stoch_k = indicators.get('stochastic_k_15m')
        ema20 = indicators.get('ema_20_1h')
        volume_ratio = indicators.get('volume_ratio')
        
        if (rsi < 35 and stoch_k < 20 and nifty > ema20 and volume_ratio > 1.5):
            strike = self.select_strike(nifty, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.75,
                rationale=f"RSI:{rsi:.1f} oversold, Stoch:{stoch_k:.1f}, Volume:{volume_ratio:.2f}x",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
    
    def select_strike(self, nifty_price, option_type):
        # ATM or 100pts up
        atm_strike = (nifty_price // 100) * 100
        return f"NIFTY{atm_strike}{'CE' if option_type == 'CE' else 'PE'}"
```

#### **Strategy 2: MACD Golden Cross + Volume (Bullish)** → `src/strategies/macd_bullish.py`

```python
class MACDBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        indicators = data_state['indicators']
        
        # Conditions:
        # 1. MACD histogram crosses above zero on 1H
        # 2. Volume spike on 5m (>2x average)
        # 3. Price above 50-EMA
        
        macd_hist = indicators.get('macd_histogram_1h')
        macd_hist_prev = indicators.get('macd_histogram_1h_prev')
        volume_ratio = indicators.get('volume_ratio_5m')
        price = data_state['nifty_price']
        ema50 = indicators.get('ema_50_1h')
        
        if (macd_hist > 0 and macd_hist_prev <= 0 and 
            volume_ratio > 2.0 and price > ema50):
            
            strike = self.select_strike(price, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.80,
                rationale=f"MACD cross, Volume:{volume_ratio:.2f}x, Price above 50-EMA",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### **Strategy 3: Support Bounce (Bullish)** → `src/strategies/support_bounce_bullish.py`

```python
class SupportBounceBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        indicators = data_state['indicators']
        candles = data_state['candles']  # Last 20 candles
        
        # Conditions:
        # 1. Price tests 20-EMA (touches but doesn't break)
        # 2. Close above 20-EMA on current candle
        # 3. Volume > average
        
        current = candles[-1]
        prev = candles[-2]
        ema20 = indicators.get('ema_20_1h')
        
        # Test: prev low <= ema20 and current close > ema20
        if (prev.low <= ema20 and current.close > ema20 and 
            current.volume > indicators.get('avg_volume')):
            
            strike = self.select_strike(current.close, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.70,
                rationale=f"Support bounce at 20-EMA, Close:{current.close:.1f} > EMA:{ema20:.1f}",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### **Strategy 4: RSI Overbought Rejection (Bearish)** → `src/strategies/rsi_overbought_bearish.py`

```python
class RSIOverboughtBearish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        indicators = data_state['indicators']
        
        # Mirror of Strategy 1, but for PE
        rsi = indicators.get('rsi_1h')
        stoch_k = indicators.get('stochastic_k_15m')
        ema20 = indicators.get('ema_20_1h')
        volume_ratio = indicators.get('volume_ratio')
        nifty = data_state['nifty_price']
        
        if (rsi > 65 and stoch_k > 80 and nifty < ema20 and volume_ratio > 1.5):
            strike = self.select_strike(nifty, 'PE')
            return Signal(
                strategy=self.name,
                direction='PE',
                action='BUY',
                strike=strike,
                confidence=0.75,
                rationale=f"RSI:{rsi:.1f} overbought, Stoch:{stoch_k:.1f}, Volume:{volume_ratio:.2f}x",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### **Strategy 5: MACD Death Cross + Volume (Bearish)** → `src/strategies/macd_bearish.py`

```python
class MACDBearish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        indicators = data_state['indicators']
        
        macd_hist = indicators.get('macd_histogram_1h')
        macd_hist_prev = indicators.get('macd_histogram_1h_prev')
        volume_ratio = indicators.get('volume_ratio_5m')
        price = data_state['nifty_price']
        ema50 = indicators.get('ema_50_1h')
        
        if (macd_hist < 0 and macd_hist_prev >= 0 and 
            volume_ratio > 2.0 and price < ema50):
            
            strike = self.select_strike(price, 'PE')
            return Signal(
                strategy=self.name,
                direction='PE',
                action='BUY',
                strike=strike,
                confidence=0.80,
                rationale=f"MACD cross, Volume:{volume_ratio:.2f}x, Price below 50-EMA",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

---

### **2.3 Strategy Engine** → `src/strategies/engine.py`

**Responsibilities:**
- Run all 6 strategies (backtest + live)
- Deduplicate signals (avoid multiple buys on same signal)
- Rate-limit signals per strategy
- Generate signal reports

**Key Methods:**
```python
class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy])
    def evaluate_all(self, data_state: dict) -> list[Signal]
    def backtest(self, historical_data: pd.DataFrame) -> BacktestReport
    def print_backtest_report(self, report: BacktestReport)
```

---

## **PHASE 3: BACKTESTING (Day 2 - 2-3 hours)**

### **3.1 Backtester** → `src/backtester/backtest_engine.py`

**Responsibilities:**
- Replay 90 days of historical data
- Execute strategies on each candle
- Simulate trades through paper trader
- Generate performance report

**Key Methods:**
```python
class BacktestEngine:
    def __init__(self, strategies: list, paper_trader: PaperTrader, data_manager: DataManager)
    def run(self, historical_data: pd.DataFrame) -> BacktestReport
    def replay_candle(self, candle: Candle)

@dataclass
class BacktestReport:
    strategy: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    consecutive_wins: int
    consecutive_losses: int
```

**Output:** Rank strategies by:
1. Win rate (>55% preferred)
2. Profit factor (>1.5 preferred)
3. Max drawdown (<15% preferred)

**Result:** Select top-3 for CE, top-3 for PE

---

### **3.2 Backtest Report Generator** → `src/backtester/report.py`

```
Sample Output:
================================================================================
BACKTEST RESULTS - 90 Days (May 1 - July 31, 2026)
================================================================================

BULLISH (CE) STRATEGIES:
────────────────────────────────────────────────────────────────────────────
Rank | Strategy              | Win% | PF   | P&L      | DD%   | Status
────────────────────────────────────────────────────────────────────────────
1    | MACD_BULLISH          | 62%  | 2.10 | +₹52,340 | -8.2% | ✓ DEPLOY
2    | RSI_OVERSOLD_BULLISH  | 58%  | 1.80 | +₹38,120 | -6.5% | ✓ DEPLOY
3    | SUPPORT_BOUNCE_BULLISH| 55%  | 1.60 | +₹31,290 | -9.1% | ✓ DEPLOY
4    | (Not selected)
5    | (Not selected)

BEARISH (PE) STRATEGIES:
────────────────────────────────────────────────────────────────────────────
Rank | Strategy              | Win% | PF   | P&L      | DD%   | Status
────────────────────────────────────────────────────────────────────────────
1    | MACD_BEARISH          | 61%  | 2.05 | +₹50,120 | -7.9% | ✓ DEPLOY
2    | RSI_OVERBOUGHT_BEARISH| 57%  | 1.75 | +₹36,890 | -6.8% | ✓ DEPLOY
3    | (RESISTANCE_REJECTION)| 54%  | 1.55 | +₹29,450 | -8.7% | ✓ DEPLOY
4    | (Not selected)
5    | (Not selected)

RECOMMENDED DEPLOYMENT: 6 strategies (3 CE + 3 PE)
Total Backtest P&L: +₹238,210
Avg Win Rate: 58%
Avg Profit Factor: 1.81
```

---

## **PHASE 4: LIVE ENGINE (Day 3 - 6-8 hours)**

### **4.1 Main Trading Loop** → `src/trader.py`

**Responsibilities:**
- Initialize all components
- Start WebSocket connections
- Run main event loop (10-sec polling)
- Collect signals from all strategies
- Place simulated orders
- Manage positions

**Key Methods:**
```python
class LiveTrader:
    def __init__(self, config: Config)
    def start(self)
    def on_nifty_tick(self, tick)
    def on_option_tick(self, strike, tick)
    def poll_option_chain(self)  # Every 10 seconds
    def evaluate_strategies(self)
    def execute_signals(self, signals: list[Signal])
    def update_positions(self)
    def check_exits(self)
    def send_alerts(self, signal: Signal)
    def run_scheduler(self)
    def stop(self)
```

**Main Loop Logic:**
```python
async def main_loop():
    trader = LiveTrader(config)
    
    # Start components
    trader.fyers_client.start_websocket()
    trader.fyers_client.subscribe_symbols([
        "NSE:NIFTY50-INDEX",
        "NSE:NIFTY24AUG24500CE",
        "NSE:NIFTY24AUG24500PE",
        # ... add all monitored strikes
    ])
    
    # Scheduler for 10-sec polling
    schedule.every(10).seconds.do(trader.poll_option_chain)
    
    # Main loop
    while trader.is_running:
        schedule.run_pending()
        
        # On each tick (WebSocket)
        signals = trader.evaluate_strategies()
        
        if signals:
            trader.execute_signals(signals)
            trader.send_alerts(signals)
        
        trader.update_positions()
        trader.check_exits()
        
        await asyncio.sleep(0.1)
```

---

### **4.2 Alert Manager** → `src/alerts/telegram_alerts.py`

**Responsibilities:**
- Send signal alerts to Telegram
- Interactive buttons (Approve/Reject/Remind)
- Position P&L updates
- Daily summary

**Key Methods:**
```python
class TelegramAlertsManager:
    def __init__(self, bot_token: str, chat_id: str)
    def send_signal_alert(self, signal: Signal)
    def send_trade_execution(self, trade: Trade)
    def send_position_update(self, positions: list[Position])
    def send_daily_summary(self, summary: dict)

# Sample message:
"""
🚀 SIGNAL GENERATED
──────────────────
Time: 09:35:42
Strategy: RSI Oversold Bounce
Direction: BULLISH (CE)
Strike: 24,500 CE
Entry: ₹65
Confidence: 75%

[✅ APPROVE] [❌ REJECT] [⏰ REMIND IN 5min]
"""
```

---

### **4.3 State Persistence** → `src/persistence/state_manager.py`

**Responsibilities:**
- Save current positions to JSON
- Save trade history to CSV
- Load state on restart
- Handle graceful shutdown

**Key Methods:**
```python
class StateManager:
    def save_positions(self, positions: list[Position])
    def load_positions(self) -> list[Position]
    def append_trade(self, trade: Trade)
    def get_trade_history(self) -> pd.DataFrame
    def save_daily_summary(self, summary: dict)
```

---

## **PHASE 5: DASHBOARD UI (Day 4 - 6-8 hours) - OPTIONAL**

### **5.1 Terminal UI** → `src/dashboard/terminal_ui.py`

If you choose CLI dashboard instead of React:

```
┌─────────────────────────────────────────────────────────────────────┐
│ NIFTY OPTIONS PAPER TRADER - LIVE                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Time: 10:35:42 IST | NIFTY: 24,515 ↗ +65pts | Market: OPEN        │
├─────────────────────────────────────────────────────────────────────┤
│ 📊 SIGNALS                                                          │
│ • 10:35:42 RSI_OVERSOLD_BULLISH: 24500 CE @ ₹65 [Confidence: 75%] │
│ • 10:30:15 MACD_BULLISH: 24600 CE @ ₹42 [Confidence: 80%]         │
├─────────────────────────────────────────────────────────────────────┤
│ 📈 POSITIONS (3 Open)                                              │
│ ┌──────────────────────────────────────────────────────────────┐  │
│ │ 24500 CE | Entry: ₹65 | Current: ₹72 | P&L: +₹700 | SL: ₹60 │  │
│ │ 24600 CE | Entry: ₹42 | Current: ₹48 | P&L: +₹600 | SL: ₹37 │  │
│ │ 24400 PE | Entry: ₹55 | Current: ₹52 | P&L: +₹300 | SL: ₹50 │  │
│ └──────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│ 💰 P&L SUMMARY                                                      │
│ Today: +₹1,600 | Week: +₹8,450 | Month: +₹32,120 | Drawdown: -2.1%│
├─────────────────────────────────────────────────────────────────────┤
│ Commands: [T]rade History | [P]ositions | [S]ignals | [Q]uit       │
└─────────────────────────────────────────────────────────────────────┘
```

---

### **5.2 React Dashboard (Alternative)** → `frontend/` directory

If you choose React dashboard:

**Components:**
- `LiveChart.tsx` - NIFTY price chart with signals
- `OptionChain.tsx` - Chain heatmap
- `PositionsBoard.tsx` - Open trades
- `P&LTracker.tsx` - Profit/loss chart
- `TradeHistory.tsx` - All trades log
- `Dashboard.tsx` - Main layout

**Backend:** Node.js express server + WebSocket to Python trader

---

## **PHASE 6: TESTING & REFINEMENT (Day 5 - 2-3 hours)**

### **6.1 Unit Tests** → `tests/test_*.py`

```python
# Example test structure:
class TestRSIOversoldStrategy:
    def test_signal_generated_when_rsi_below_35(self)
    def test_no_signal_when_rsi_above_35(self)
    def test_confidence_score_calculated(self)

class TestPaperTrader:
    def test_order_placed_successfully(self)
    def test_position_closed_on_sl(self)
    def test_pnl_calculated_correctly(self)

class TestDataManager:
    def test_indicators_calculated(self)
    def test_candle_built_from_ticks(self)
```

---

### **6.2 Integration Testing**

```
Test Scenario 1: Full Day Simulation
- Load 90-day historical data
- Run backtest with top-6 strategies
- Verify P&L calculation
- Check signal generation

Test Scenario 2: WebSocket Integration
- Mock Fyers WebSocket
- Send tick data
- Verify candle building
- Check indicator updates

Test Scenario 3: Order Execution
- Generate signal
- Place order via paper trader
- Update position
- Calculate P&L
```

---

## **IMPLEMENTATION CHECKLIST**

### **Before Starting:**
- [ ] Virtual environment created
- [ ] Requirements.txt prepared
- [ ] .env file with Fyers credentials
- [ ] Telegram bot created and token saved
- [ ] 90-day historical NIFTY data downloaded
- [ ] config/risk_params.json created

### **Phase 1 (Core Infrastructure):**
- [ ] Fyers API client (`src/fyers/api_client.py`)
- [ ] Data manager (`src/data_manager.py`)
- [ ] Paper trader (`src/simulator/paper_trader.py`)
- [ ] Config loader (`src/config.py`)
- [ ] Logger (`src/utils/logger.py`)

### **Phase 2 (Strategies):**
- [ ] Base strategy class (`src/strategies/base_strategy.py`)
- [ ] Strategy 1: RSI Oversold Bullish
- [ ] Strategy 2: MACD Bullish
- [ ] Strategy 3: Support Bounce Bullish
- [ ] Strategy 4: RSI Overbought Bearish
- [ ] Strategy 5: MACD Bearish
- [ ] Strategy engine (`src/strategies/engine.py`)

### **Phase 3 (Backtesting):**
- [ ] Backtest engine (`src/backtester/backtest_engine.py`)
- [ ] Report generator (`src/backtester/report.py`)
- [ ] Run backtest on 90-day data
- [ ] Select top-6 strategies
- [ ] Save backtest results

### **Phase 4 (Live Engine):**
- [ ] Main trading loop (`src/trader.py`)
- [ ] Alert manager (`src/alerts/telegram_alerts.py`)
- [ ] State persistence (`src/persistence/state_manager.py`)
- [ ] Test WebSocket integration
- [ ] Test signal generation
- [ ] Test order execution

### **Phase 5 (Dashboard):**
- [ ] Choose: Terminal UI or React
- [ ] Implement dashboard
- [ ] Real-time position updates
- [ ] P&L tracking
- [ ] Trade history view

### **Phase 6 (Testing):**
- [ ] Unit tests written
- [ ] Integration tests passed
- [ ] Full day simulation successful
- [ ] Telegram alerts working
- [ ] Graceful shutdown implemented

---

## **PROJECT STRUCTURE (Final)**

```
nifty-options-trader/
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── trader.py (main entry point)
│   ├── fyers/
│   │   ├── __init__.py
│   │   └── api_client.py
│   ├── data_manager.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base_strategy.py
│   │   ├── rsi_oversold_bullish.py
│   │   ├── macd_bullish.py
│   │   ├── support_bounce_bullish.py
│   │   ├── rsi_overbought_bearish.py
│   │   ├── macd_bearish.py
│   │   └── engine.py
│   ├── simulator/
│   │   ├── __init__.py
│   │   └── paper_trader.py
│   ├── backtester/
│   │   ├── __init__.py
│   │   ├── backtest_engine.py
│   │   └── report.py
│   ├── alerts/
│   │   ├── __init__.py
│   │   └── telegram_alerts.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── state_manager.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── indicators.py (RSI, MACD, EMA, etc.)
│   └── dashboard/
│       ├── __init__.py
│       └── terminal_ui.py
├── tests/
│   ├── __init__.py
│   ├── test_strategies.py
│   ├── test_paper_trader.py
│   ├── test_data_manager.py
│   └── fixtures/
│       └── sample_data.csv
├── config/
│   └── risk_params.json
├── data/
│   ├── historical/
│   │   └── nifty_90days.csv
│   └── backtest_results/
│       └── backtest_report.json
├── logs/
│   ├── trades.log
│   ├── signals.log
│   ├── errors.log
│   └── websocket.log
├── .env
├── .gitignore
├── requirements.txt
├── README.md
└── main.py (entry point)
```

---

## **REQUIREMENTS.txt**

```
fyers-api==3.4.0
pyotp==2.9.0
websocket-client==1.6.4
requests==2.31.0
pandas==2.1.0
numpy==1.24.0
python-telegram-bot==20.3
schedule==1.2.0
python-dotenv==1.0.0
ta-lib==0.4.28
plotly==5.17.0
pytest==7.4.0
```

---

## **ENTRY POINT - main.py**

```python
import asyncio
from src.config import Config
from src.trader import LiveTrader
from src.backtester.backtest_engine import BacktestEngine
from src.strategies.engine import StrategyEngine

async def main():
    # Load config
    config = Config.load()
    config.validate()
    
    # Decide: Backtest or Live
    print("NIFTY Options Paper Trader")
    print("1. Backtest")
    print("2. Start Live Trading")
    choice = input("Choose (1/2): ").strip()
    
    if choice == "1":
        print("\n🔄 Starting backtest...")
        backtest_and_select_strategies(config)
    elif choice == "2":
        print("\n🚀 Starting live trading...")
        trader = LiveTrader(config)
        await trader.start()

def backtest_and_select_strategies(config):
    """Backtest all strategies, select top 6"""
    import pandas as pd
    from src.strategies.engine import StrategyEngine
    
    data = pd.read_csv("data/historical/nifty_90days.csv")
    strategies = create_all_strategies()  # 5 bullish + 5 bearish
    
    results = {}
    for strategy in strategies:
        result = backtest_single_strategy(strategy, data, config)
        results[strategy.name] = result
    
    # Rank and select top-6
    top_6 = select_top_6(results)
    print(f"\n✓ Selected {len(top_6)} strategies for deployment:")
    for name in top_6:
        print(f"  - {name}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## **NEXT STEPS - HOW TO USE CLAUDE CODE AGENT**

### **Step 1: Initialize Project**
```bash
mkdir nifty-options-trader
cd nifty-options-trader
code .  # Open VS Code
```

### **Step 2: Use Claude Code Agent**

In VS Code terminal:
```bash
# Open Claude Code Agent (if installed)
claude-code

# Or via command palette:
# Cmd+Shift+P → "Claude Code Agent: Start"
```

### **Step 3: Feed This Plan**

Upload this file to Claude Code Agent:
```
"Implement Phase 1: Core Infrastructure. Start with src/fyers/api_client.py"
```

Claude will:
1. Create file structure
2. Write api_client.py with all methods
3. Create requirements.txt
4. Generate .env template
5. Ask for clarification if needed

### **Step 4: Iterative Development**

For each phase:
```
"Implement Phase 2: Strategies. Create all 5 strategy files with full logic."
```

Claude will generate complete, testable code.

---

## **TIPS FOR SUCCESS**

1. **One phase at a time** - Don't try to implement everything at once
2. **Test after each phase** - Run unit tests before moving on
3. **Save frequently** - Use Git to version control
4. **Keep logs** - Every trade, signal, error should be logged
5. **Validate data** - Ensure historical data is clean before backtesting
6. **Start small** - Backtest before going live
7. **Monitor closely** - Watch first day of live trading manually

---

## **ESTIMATED TIMELINE**

```
Day 1 (6h):  Phases 1-2 (Core infrastructure + Strategies)
Day 2 (5h):  Phase 3 (Backtesting) + Select top-6 strategies
Day 3 (8h):  Phase 4 (Live engine + WebSocket + Alerts)
Day 4 (8h):  Phase 5 (Dashboard UI)
Day 5 (3h):  Phase 6 (Testing + Refinement)

Total: ~30 hours (can be parallelized)
```

---

## **READY TO START?**

Proceed with:
1. Create project directory
2. Setup virtual environment
3. Gather credentials and data
4. Open this file in VS Code
5. Start Claude Code Agent
6. Begin Phase 1

**Good luck! 🚀**
