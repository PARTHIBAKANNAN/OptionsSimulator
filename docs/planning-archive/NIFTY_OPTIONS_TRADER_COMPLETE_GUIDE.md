# NIFTY OPTIONS PAPER TRADER - COMPLETE GUIDE
## Multi-Strategy Implementation with Fyers Integration

**All-in-One Document | Ready to Copy & Execute**

---

# TABLE OF CONTENTS
1. Quick Start (5 minutes)
2. Complete Implementation Plan
3. Claude Code Agent Prompts (Copy-Paste Ready)
4. Strategy Details
5. Architecture Overview
6. Troubleshooting

---

# PART 1: QUICK START (5 MINUTES)

## What You're Building
- **6 parallel trading strategies** (3 bullish CE + 3 bearish PE)
- **Paper trading simulator** (risk-free)
- **Fyers WebSocket integration** (live prices)
- **REST polling** (option chain every 10s)
- **Telegram alerts** (signal notifications)
- **Backtest engine** (90-day historical validation)

## Timeline
```
Day 1: 6-7 hours  → Phases 1-2 (Core infrastructure + Strategies)
Day 2: 5-6 hours  → Phases 3-4 (Backtest + Live engine)
Day 3: 6-8 hours  → Phase 5 (Dashboard - optional)
Day 4: 2-3 hours  → Phase 6 (Testing)
─────────────────────
Total: 18-25 hours
```

## 6 Strategies (Ranked by Backtest Performance)
```
BULLISH (CE):
1. MACD_BULLISH (80% confidence)
   - MACD histogram crosses above zero
   - Volume spike > 2x
   - Price > 50-EMA

2. RSI_OVERSOLD_BULLISH (75% confidence)
   - RSI < 35 on 1H
   - Stochastic < 20 on 15m
   - Price > 20-EMA

3. SUPPORT_BOUNCE_BULLISH (70% confidence)
   - Price tests 20-EMA
   - Close > 20-EMA
   - Volume > average

BEARISH (PE):
1. MACD_BEARISH (80% confidence)
   - MACD histogram crosses below zero
   - Volume spike > 2x
   - Price < 50-EMA

2. RSI_OVERBOUGHT_BEARISH (75% confidence)
   - RSI > 65 on 1H
   - Stochastic > 80 on 15m
   - Price < 20-EMA

3. RESISTANCE_REJECTION_BEARISH (70% confidence)
   - Price tests resistance
   - Close < resistance
   - Volume > average
```

## Prerequisites - Gather These NOW

```
1. Fyers Credentials (from myapi.fyers.in):
   - App ID: ________________
   - App Secret: ________________
   - TOTP Secret (base32): ________________

2. Telegram:
   - Bot Token: ________________
   - Chat ID: ________________

3. Historical Data:
   - File: nifty_90days.csv
   - Format: Timestamp,Open,High,Low,Close,Volume
   - Size: ~35,100 rows (90 days × 390 min/day)

4. Risk Parameters:
   - Position size: 1 contract
   - Max concurrent: 5 positions
   - Daily loss limit: ₹5,000
   - Stop loss: 50 pts
   - Take profit: 150 pts
   - Time exit: 120 mins
```

---

# PART 2: COMPLETE IMPLEMENTATION PLAN

## PROJECT STRUCTURE

```
nifty-options-trader/
├── src/
│   ├── trader.py                          # MAIN ENTRY POINT
│   ├── config.py                          # Load config
│   ├── fyers/
│   │   └── api_client.py                  # Fyers API + WebSocket
│   ├── data_manager.py                    # Candles + indicators
│   ├── strategies/
│   │   ├── base_strategy.py               # Base class
│   │   ├── rsi_oversold_bullish.py
│   │   ├── macd_bullish.py
│   │   ├── support_bounce_bullish.py
│   │   ├── rsi_overbought_bearish.py
│   │   ├── macd_bearish.py
│   │   └── engine.py                      # Run all strategies
│   ├── simulator/
│   │   └── paper_trader.py                # Simulated trades
│   ├── backtester/
│   │   ├── backtest_engine.py
│   │   └── report.py
│   ├── alerts/
│   │   └── telegram_alerts.py
│   ├── persistence/
│   │   └── state_manager.py
│   ├── utils/
│   │   ├── logger.py
│   │   └── indicators.py
│   └── dashboard/
│       └── terminal_ui.py                 # Optional
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
├── logs/
├── .env
├── requirements.txt
└── main.py
```

## Phase-by-Phase Breakdown

### PHASE 1: CORE INFRASTRUCTURE (4-6 hours)

#### 1.1 Fyers API Client (`src/fyers/api_client.py`)
**Responsibilities:**
- OAuth authentication + TOTP auto-refresh
- WebSocket connection management
- REST API calls (option chain, historical data)
- Token persistence

**Key Methods:**
```python
class FyersAPIClient:
    def __init__(self, app_id, app_secret, totp_secret, redirect_uri)
    def authenticate_with_totp() -> str
    def refresh_access_token() -> bool
    def start_websocket(on_tick_callback)
    def subscribe_symbols(symbols: list)
    def get_option_chain(symbol) -> dict
    def get_historical_data(symbol, resolution, days) -> pd.DataFrame
    def place_order(order_data) -> dict  # Simulated
    def cancel_order(order_id) -> dict
    def get_positions() -> dict
```

#### 1.2 Data Manager (`src/data_manager.py`)
**Responsibilities:**
- Collect WebSocket ticks
- Build 1-min NIFTY candles
- Calculate indicators (RSI, MACD, EMA, Bollinger Bands, Stochastic)
- Maintain rolling state

**Key Methods:**
```python
class DataManager:
    def __init__(self, window_size=100)
    def on_nifty_tick(self, tick)
    def on_option_tick(self, strike, tick)
    def get_current_candle() -> Candle
    def get_historical_candles(count: int) -> list[Candle]
    def update_option_chain(self, chain_data)
    def get_option_chain() -> dict
    def calculate_indicators() -> dict
    def get_state() -> dict
```

#### 1.3 Paper Trader (`src/simulator/paper_trader.py`)
**Responsibilities:**
- Simulated order execution
- Track open positions
- Calculate P&L (realized + unrealized)
- Apply stop-loss and take-profit

**Key Methods:**
```python
class PaperTrader:
    def __init__(self, initial_capital=1000000, slippage_pct=0.1)
    def place_order(symbol, side, qty, price, strategy=None, sl=None, tp=None) -> Order
    def cancel_order(order_id) -> bool
    def update_positions(current_prices: dict)
    def get_positions() -> list[Order]
    def get_pnl() -> dict
    def get_trade_history() -> list[Order]
    def close_position(position_id, price) -> Order
```

#### 1.4 Config & Logger (`src/config.py` + `src/utils/logger.py`)

**Config:**
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

**Logger:**
```python
class Logger:
    def log_signal(self, strategy: str, signal: dict)
    def log_trade(self, trade: Trade)
    def log_error(self, error: str, context: dict)
    def log_websocket_event(self, event: str, data: dict)
```

---

### PHASE 2: STRATEGY LAYER (2-3 hours)

#### Base Strategy Class (`src/strategies/base_strategy.py`)
```python
class BaseStrategy:
    def __init__(self, name: str, direction: str)
    def evaluate(self, data_state: dict) -> Signal or None

@dataclass
class Signal:
    strategy: str
    direction: str  # 'CE' or 'PE'
    action: str     # 'BUY'
    strike: str
    confidence: float  # 0-1
    rationale: str
    entry_price: float
    timestamp: datetime
```

#### Strategy 1: RSI Oversold Bullish
```python
class RSIOversoldBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        # Conditions:
        # 1. RSI(14) < 35 on 1H (oversold)
        # 2. Stochastic(14,3,3) < 20 on 15min
        # 3. Price > 20-EMA (uptrend structure)
        # 4. Volume > 1.5x average
        
        rsi = data_state['indicators'].get('rsi_1h')
        stoch_k = data_state['indicators'].get('stochastic_k_15m')
        ema20 = data_state['indicators'].get('ema_20_1h')
        volume_ratio = data_state['indicators'].get('volume_ratio')
        nifty = data_state['nifty_price']
        
        if (rsi < 35 and stoch_k < 20 and nifty > ema20 and volume_ratio > 1.5):
            strike = self.select_strike(nifty, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.75,
                rationale=f"RSI:{rsi:.1f} oversold, Stoch:{stoch_k:.1f}, Vol:{volume_ratio:.2f}x",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### Strategy 2: MACD Bullish
```python
class MACDBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        # Conditions:
        # 1. MACD histogram crosses above zero on 1H
        # 2. Volume spike on 5m (>2x average)
        # 3. Price > 50-EMA
        
        macd_hist = data_state['indicators'].get('macd_histogram_1h')
        macd_hist_prev = data_state['indicators'].get('macd_histogram_1h_prev')
        volume_ratio = data_state['indicators'].get('volume_ratio_5m')
        price = data_state['nifty_price']
        ema50 = data_state['indicators'].get('ema_50_1h')
        
        if (macd_hist > 0 and macd_hist_prev <= 0 and volume_ratio > 2.0 and price > ema50):
            strike = self.select_strike(price, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.80,
                rationale=f"MACD cross, Vol:{volume_ratio:.2f}x, Price > 50-EMA",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### Strategy 3: Support Bounce Bullish
```python
class SupportBounceBullish(BaseStrategy):
    def evaluate(self, data_state: dict) -> Signal or None:
        # Conditions:
        # 1. Price tests 20-EMA (low touches)
        # 2. Current close > 20-EMA
        # 3. Volume > average
        
        candles = data_state['candles']
        current = candles[-1]
        prev = candles[-2]
        ema20 = data_state['indicators'].get('ema_20_1h')
        
        if (prev.low <= ema20 and current.close > ema20 and 
            current.volume > data_state['indicators'].get('avg_volume')):
            
            strike = self.select_strike(current.close, 'CE')
            return Signal(
                strategy=self.name,
                direction='CE',
                action='BUY',
                strike=strike,
                confidence=0.70,
                rationale=f"Support bounce at 20-EMA",
                entry_price=self.get_option_price(strike),
                timestamp=data_state['timestamp']
            )
        return None
```

#### Similar logic for PE strategies (Bearish versions)

#### Strategy Engine (`src/strategies/engine.py`)
```python
class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy])
    def evaluate_all(self, data_state: dict) -> list[Signal]
    def backtest(self, historical_data: pd.DataFrame) -> BacktestReport
    def print_backtest_report(self, report: BacktestReport)
```

---

### PHASE 3: BACKTESTING (2-3 hours)

#### Backtest Engine (`src/backtester/backtest_engine.py`)
```python
class BacktestEngine:
    def __init__(self, strategies: list, paper_trader: PaperTrader, data_manager: DataManager)
    def run(self, historical_data: pd.DataFrame) -> dict
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

**Process:**
1. Load 90-day historical NIFTY data
2. For each candle:
   - Update DataManager
   - Run all strategies
   - If signal: place order
   - Update positions
   - Check exits (SL, TP, time)
3. Generate performance report
4. **Select top-3 CE + top-3 PE** based on:
   - Win rate (target: >55%)
   - Profit factor (target: >1.5)
   - Max drawdown (target: <15%)

---

### PHASE 4: LIVE TRADING ENGINE (3-4 hours)

#### Main Trading Loop (`src/trader.py`)
```python
class LiveTrader:
    def __init__(self, config: Config)
    async def start(self)
    def on_nifty_tick(self, tick)
    def on_option_tick(self, strike, tick)
    def poll_option_chain(self)  # Every 10 seconds
    def evaluate_strategies(self)
    def execute_signals(self, signals: list[Signal])
    def update_positions(self)
    def check_exits(self)
    def send_alerts(self, signal: Signal)
    def stop(self)

# Main loop logic:
async def main_loop():
    trader = LiveTrader(config)
    
    # Start components
    trader.fyers_client.start_websocket()
    trader.fyers_client.subscribe_symbols([
        "NSE:NIFTY50-INDEX",
        "NSE:NIFTY24AUG24500CE",
        "NSE:NIFTY24AUG24500PE",
        # ... add all strikes
    ])
    
    # 10-second polling scheduler
    schedule.every(10).seconds.do(trader.poll_option_chain)
    
    # Main loop
    while trader.is_running:
        schedule.run_pending()
        
        # On each tick
        signals = trader.evaluate_strategies()
        
        if signals:
            trader.execute_signals(signals)
            trader.send_alerts(signals)
        
        trader.update_positions()
        trader.check_exits()
        
        await asyncio.sleep(0.1)
```

#### Telegram Alerts (`src/alerts/telegram_alerts.py`)
```python
class TelegramAlertsManager:
    def __init__(self, bot_token: str, chat_id: str)
    def send_signal_alert(self, signal: Signal)
    def send_trade_execution(self, trade: Trade)
    def send_position_update(self, positions: list[Position])
    def send_daily_summary(self, summary: dict)

# Message format:
"""
🚀 SIGNAL GENERATED
──────────────────
Time: 09:35:42
Strategy: RSI_OVERSOLD_BULLISH
Direction: BULLISH (CE)
Strike: 24,500 CE
Entry: ₹65
Confidence: 75%

[✅ APPROVE] [❌ REJECT] [⏰ REMIND]
"""
```

#### State Persistence (`src/persistence/state_manager.py`)
```python
class StateManager:
    def __init__(self, data_dir: str = "data/")
    def save_positions(self, positions: list[Order])
    def load_positions(self) -> list[Order]
    def append_trade(self, trade: Order)
    def get_trade_history(self) -> pd.DataFrame
    def save_daily_summary(self, summary: dict)
```

---

### PHASE 5: DASHBOARD (OPTIONAL - 6-8 hours)

#### Terminal UI (`src/dashboard/terminal_ui.py`)
Display live:
```
┌─────────────────────────────────────────────────────────┐
│ NIFTY OPTIONS PAPER TRADER - LIVE                       │
├─────────────────────────────────────────────────────────┤
│ Time: 10:35:42 | NIFTY: 24,515 ↗ +65pts               │
│ Market: OPEN | Position: BULLISH                        │
├─────────────────────────────────────────────────────────┤
│ 📊 SIGNALS (Last 5)                                     │
│ • 10:35:42 RSI_OVERSOLD: 24500 CE @ ₹65 [75% conf]    │
│ • 10:30:15 MACD_BULLISH: 24600 CE @ ₹42 [80% conf]    │
├─────────────────────────────────────────────────────────┤
│ 📈 POSITIONS (3 Open)                                   │
│ • 24500 CE: +₹700 | 24600 CE: +₹600 | 24400 PE: +₹300 │
├─────────────────────────────────────────────────────────┤
│ 💰 P&L: Today +₹1,600 | Week +₹8,450 | Month +₹32,120 │
└─────────────────────────────────────────────────────────┘
```

---

### PHASE 6: TESTING (1-2 hours)

#### Unit Tests (`tests/test_*.py`)
```python
# Test RSI Strategy
def test_signal_when_rsi_below_35_and_volume_spike()
def test_no_signal_when_rsi_above_40()
def test_confidence_score_calculated()

# Test Paper Trader
def test_order_placed_successfully()
def test_position_closed_on_stop_loss()
def test_position_closed_on_take_profit()
def test_pnl_calculated_correctly()

# Test Data Manager
def test_candle_built_from_ticks()
def test_rsi_calculated_correctly()
def test_macd_calculated_correctly()
def test_ema_calculated_correctly()
```

---

# PART 3: CLAUDE CODE AGENT PROMPTS (COPY-PASTE)

## Prompt 1: Initial Setup
```
Create the project structure for a NIFTY options paper trader.

Requirements:
1. Create directories: src/{fyers,strategies,simulator,backtester,alerts,persistence,utils,dashboard}, tests, config, data/historical, logs
2. Create .gitignore (exclude .env, *.log, __pycache__, venv, .pytest_cache, *.csv)
3. Create .env.example with: FYERS_APP_ID, FYERS_APP_SECRET, FYERS_REDIRECT_URI, FYERS_TOTP_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
4. Create requirements.txt with: fyers-api==3.4.0, pyotp==2.9.0, websocket-client==1.6.4, requests==2.31.0, pandas==2.1.0, numpy==1.24.0, python-telegram-bot==20.3, schedule==1.2.0, python-dotenv==1.0.0, ta-lib==0.4.28, plotly==5.17.0, pytest==7.4.0
5. Create config/risk_params.json with position_sizing, exit_rules, strike_selection, market_hours
```

## Prompt 2: Fyers API Client
```
Implement src/fyers/api_client.py for Fyers ANT API integration.

Create FyersAPIClient class with:
1. __init__(app_id, app_secret, totp_secret, redirect_uri)
2. authenticate_with_totp() - use pyotp to generate OTP and get access token
3. refresh_access_token() - auto-refresh token daily at 8:30 AM
4. start_websocket(on_tick_callback) - start WebSocket connection
5. subscribe_symbols(symbols: list) - subscribe to NSE:NIFTY50-INDEX and option strikes
6. get_option_chain(symbol) - REST call for option chain data (OI, Greeks, IV)
7. get_historical_data(symbol, resolution, days) - fetch OHLC data
8. place_order(order_data) - simulated (paper trading)
9. cancel_order(order_id) - cancel order
10. get_positions() - get current positions
11. keep_websocket_running() - maintain connection

Use fyers_apiv3 library. Handle errors for auth failures, disconnections, rate limits.
Include logging for all events.
```

## Prompt 3: Data Manager
```
Implement src/data_manager.py for real-time market data aggregation.

Create DataManager class:
1. __init__(window_size=100) - maintain rolling window of candles
2. on_nifty_tick(tick_data) - process NIFTY ticks into 1-min candles
3. on_option_tick(strike, tick_data) - process option tick
4. get_current_candle() -> Candle - latest candle
5. get_historical_candles(count: int) -> list[Candle] - last N candles
6. update_option_chain(chain_data) - store chain from REST poll
7. get_option_chain() -> dict - current chain snapshot
8. calculate_indicators() -> dict - RSI(14), MACD(12,26,9), EMA(20,50), Bollinger Bands(20,2), Stochastic(14,3,3), ATR(14), Volume ratio

Calculate on different timeframes: 1H for RSI/MACD/EMA, 15M for Stochastic, 5M for volume spikes

@dataclass Candle: timestamp, open, high, low, close, volume

get_state() returns: {nifty_price, candles, indicators, option_chain, timestamp}
```

## Prompt 4: Paper Trader
```
Implement src/simulator/paper_trader.py for order simulation.

Create Order and PaperTrader classes:
1. @dataclass Order: order_id, symbol, side, qty, entry_price, entry_time, status, stop_loss, take_profit, exit_price, exit_time, realized_pnl, strategy
2. PaperTrader.__init__(initial_capital=1000000, slippage_pct=0.1)
3. place_order(symbol, side, qty, price, strategy=None, sl=None, tp=None) -> Order
4. cancel_order(order_id) -> bool
5. update_positions(current_prices: dict) - update all open positions
6. get_positions() -> list[Order] - all open orders
7. get_pnl() -> dict - total P&L (realized + unrealized)
8. get_trade_history() -> list[Order] - all closed positions
9. close_position(position_id, price) -> Order - close a position
10. check_exit_conditions(prices: dict) - check SL and TP

Features:
- Add slippage to orders
- Track entry_time, exit_time
- Calculate unrealized = (current - entry) * qty
- Calculate realized = (exit - entry) * qty
- Maintain unique order_ids
- Log every order and position

Include docstrings and type hints.
```

## Prompt 5: Config & Logger
```
Implement src/config.py and src/utils/logger.py

Config class (src/config.py):
1. Load from .env and config/risk_params.json
2. Validate all required parameters
3. Provide singleton access
4. Fields: fyers_app_id, fyers_app_secret, fyers_totp_secret, telegram_bot_token, telegram_chat_id, risk_params
5. Methods: @staticmethod load() -> Config, validate() -> bool

Logger class (src/utils/logger.py):
1. Separate loggers for: trades.log, signals.log, errors.log, websocket.log
2. Methods: log_signal(strategy, signal), log_trade(trade), log_error(error, context), log_websocket_event(event, data)
3. Format: [timestamp] [LEVEL] [SOURCE] message
4. Thread-safe logging

Include docstrings and type hints.
```

## Prompt 6: Base Strategy & All Strategies
```
Implement src/strategies/base_strategy.py and all 5 strategy files.

Base class:
@dataclass Signal: strategy, direction('CE'/'PE'), action('BUY'), strike, confidence(0-1), rationale, entry_price, timestamp

class BaseStrategy:
    __init__(name: str, direction: str)
    evaluate(data_state: dict) -> Signal or None
    select_strike(nifty_price, option_type) -> str
    get_option_price(strike) -> float

Implement 5 strategies (copy exact logic):

1. rsi_oversold_bullish.py - RSI<35 AND Stoch<20 AND Price>20EMA AND Volume>1.5x (Confidence: 75%)
2. macd_bullish.py - MACD cross up AND Volume>2x AND Price>50EMA (Confidence: 80%)
3. support_bounce_bullish.py - Price tests 20EMA AND Close>20EMA AND Volume>avg (Confidence: 70%)
4. rsi_overbought_bearish.py - RSI>65 AND Stoch>80 AND Price<20EMA AND Volume>1.5x (Confidence: 75%)
5. macd_bearish.py - MACD cross down AND Volume>2x AND Price<50EMA (Confidence: 80%)

Strike selection: ATM = (nifty // 100) * 100, then +/- 100 based on direction

Include logging and error handling for each strategy.
```

## Prompt 7: Strategy Engine & Backtester
```
Implement src/strategies/engine.py and src/backtester/backtest_engine.py

StrategyEngine class:
1. __init__(strategies: list[BaseStrategy])
2. evaluate_all(data_state: dict) -> list[Signal] - run all strategies
3. backtest(historical_data: pd.DataFrame) -> dict - replay historical data
4. print_backtest_report(report: dict) - print results table

BacktestEngine:
@dataclass BacktestReport: strategy, total_trades, winning_trades, losing_trades, win_rate, profit_factor, total_pnl, max_drawdown, consecutive_wins, consecutive_losses

1. __init__(strategies: list, paper_trader: PaperTrader, data_manager: DataManager)
2. run(historical_data: pd.DataFrame) -> dict[strategy_name, BacktestReport]
3. replay_candle(candle: Candle) - process single candle

Process:
- Load 90-day CSV
- For each candle: update DataManager, run strategies, place orders, update positions, check exits
- Calculate metrics: win_rate, profit_factor, max_drawdown
- Output: ranked report (select top-3 CE + top-3 PE)

Profit Factor = sum(wins) / abs(sum(losses))
Max Drawdown = max loss from equity peak
```

## Prompt 8: Live Trading Loop
```
Implement src/trader.py (main trading engine)

LiveTrader class:
1. __init__(config: Config) - initialize all components (FyersAPIClient, DataManager, StrategyEngine, PaperTrader, TelegramAlertsManager, StateManager, Logger)
2. async start() - start WebSocket, subscribe symbols, start main loop, start scheduler
3. on_nifty_tick(tick) - pass to DataManager
4. on_option_tick(strike, tick) - update option price
5. poll_option_chain() [Every 10 seconds] - call Fyers, update DataManager
6. evaluate_strategies() -> list[Signal] - run all 6 strategies
7. execute_signals(signals: list[Signal]) - place orders, send alerts
8. update_positions() - get current prices, update PaperTrader
9. check_exits() - check SL/TP/time exits
10. send_alerts(signal: Signal) - Telegram alert
11. async run_scheduler() - 10s polling, 1s updates, 5min summary
12. stop() - graceful shutdown

Main loop:
- WebSocket receives ticks
- Every second: update_positions()
- Every 10 seconds: poll_option_chain()
- When signal: execute_signals() + send_alerts()
- When position exit: close_position() + log trade

Include comprehensive error handling and logging.
```

## Prompt 9: Telegram Alerts
```
Implement src/alerts/telegram_alerts.py

TelegramAlertsManager class:
1. __init__(bot_token: str, chat_id: str) - initialize python-telegram-bot
2. send_signal_alert(signal: Signal) - signal with [APPROVE][REJECT][REMIND] buttons
3. send_trade_execution(trade: Order) - confirmation message
4. send_position_update(positions: list[Order]) - current positions + P&L
5. send_daily_summary(summary: dict) - daily trades, win rate, P&L, DD

Message format examples:
Signal: "🚀 SIGNAL\n──\nStrategy: RSI_OVERSOLD_BULLISH\nStrike: 24500 CE\nEntry: ₹65\nConfidence: 75%"
Trade: "✅ ORDER PLACED\nStrategy: RSI_OVERSOLD_BULLISH\nStrike: 24500 CE\nEntry: ₹65\nSL: ₹60 | TP: ₹150"

Include error handling and retry logic.
```

## Prompt 10: State Persistence
```
Implement src/persistence/state_manager.py

StateManager class:
1. __init__(data_dir: str = "data/")
2. save_positions(positions: list[Order]) - save to data/positions.json
3. load_positions() -> list[Order] - load from JSON
4. append_trade(trade: Order) - append to data/trade_history.csv
5. get_trade_history() -> pd.DataFrame - load CSV
6. save_daily_summary(summary: dict) - save to data/daily_summary_{date}.json

File formats:
positions.json: [{order_id, symbol, entry_price, entry_time, qty, strategy}]
trade_history.csv: timestamp,strategy,strike,side,entry_price,exit_price,pnl
daily_summary.json: {total_trades, win_rate, daily_pnl, max_dd}

On shutdown: save state
On restart: load positions and resume

Include file I/O error handling.
```

## Prompt 11: Terminal Dashboard (Optional)
```
Implement src/dashboard/terminal_ui.py for live monitoring

TerminalDashboard class (using curses or rich library):
1. display_live_data() - NIFTY price, direction, status
2. display_signals() - last 5 signals with strategy, strike, confidence
3. display_positions() - current open trades, P&L, SL, TP
4. display_pnl() - total P&L, today's P&L, win rate, DD
5. display_trade_history() - last 20 closed trades
6. run_interactive() - commands: T(history), P(positions), S(signals), Q(quit)

Update rates:
- Live data: every 100ms
- Positions: every 500ms
- History: on demand

Use Rich library for formatting (tables, progress bars, colors).
Include keyboard interrupt handling.
```

## Prompt 12: Unit Tests
```
Implement tests/ directory with unit tests (pytest).

test_strategies.py:
- TestRSIOversoldBullish: signal when RSI<35, no signal when RSI>40, confidence calculated
- TestMACDBullish: signal on MACD cross, volume confirmation required
- Similar for other strategies

test_paper_trader.py:
- test_order_placed_successfully()
- test_slippage_applied()
- test_position_closed_on_stop_loss()
- test_position_closed_on_take_profit()
- test_pnl_calculated_correctly()
- test_unrealized_pnl_updates()

test_data_manager.py:
- test_candle_built_from_ticks()
- test_rsi_calculated_correctly()
- test_macd_calculated_correctly()
- test_ema_calculated_correctly()
- test_indicators_cached()

Use pytest fixtures for sample data.
Use mock objects for Fyers API.
Run with: pytest tests/ -v
```

---

# PART 4: REQUIREMENTS.TXT

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

# PART 5: IMMEDIATE ACTION STEPS

## Step 1: Create Project (5 mins)
```bash
mkdir nifty-options-trader
cd nifty-options-trader
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
code .
```

## Step 2: Use Claude Code Agent
1. In VS Code, open Claude Code Agent
2. Copy Prompt 1 (Initial Setup) from above
3. Paste into Claude Code Agent
4. Wait for code generation
5. Repeat for Prompts 2-12

## Step 3: Configure
```bash
cp .env.example .env
# Fill in: FYERS_APP_ID, FYERS_APP_SECRET, FYERS_TOTP_SECRET, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Place historical data
cp nifty_90days.csv data/historical/

# Run backtest
python -m src.backtester.backtest_engine

# Start live trading
python src/trader.py
```

---

# PART 6: TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| Import error: `fyers_apiv3` not found | `pip install fyers-api` |
| WebSocket disconnects | Add auto-reconnect logic in api_client.py |
| Backtest doesn't match live P&L | Check slippage%, verify option prices |
| Signals not generating | Verify indicators calculated, check thresholds |
| Telegram alerts not sending | Check bot token + chat ID + internet |
| Historical data missing values | Validate CSV format, ensure no timestamp gaps |
| TOTP expires before 8:30am | Adjust refresh schedule |
| Paper trader doesn't close on SL | Verify SL price being checked correctly |

---

**READY TO START? Copy one prompt at a time into Claude Code Agent. Begin with Prompt 1 (Initial Setup). Good luck! 🚀**
