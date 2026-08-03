# Claude Code Agent Prompts - Copy & Paste
## For NIFTY Options Paper Trader Implementation

Use these prompts directly in Claude Code Agent to generate phase-by-phase implementation.

---

## **INITIAL SETUP PROMPT**

```
Create the project structure for a NIFTY options paper trader. 

Requirements:
1. Create directory structure:
   - src/fyers/
   - src/strategies/
   - src/simulator/
   - src/backtester/
   - src/alerts/
   - src/persistence/
   - src/utils/
   - src/dashboard/
   - tests/
   - config/
   - data/historical/
   - logs/

2. Create .gitignore with:
   - .env
   - *.log
   - __pycache__/
   - venv/
   - .pytest_cache/
   - *.csv
   - data/historical/

3. Create .env.example:
   - FYERS_APP_ID=
   - FYERS_APP_SECRET=
   - FYERS_REDIRECT_URI=
   - FYERS_TOTP_SECRET=
   - TELEGRAM_BOT_TOKEN=
   - TELEGRAM_CHAT_ID=

4. Create requirements.txt with all dependencies

5. Create config/risk_params.json template with:
   - position_sizing
   - exit_rules
   - strike_selection
   - market_hours
```

---

## **PHASE 1A PROMPT: Fyers API Client**

```
Implement src/fyers/api_client.py for Fyers ANT API integration.

Requirements:
1. FyersAPIClient class with:
   - __init__(app_id, app_secret, totp_secret, redirect_uri)
   - authenticate_with_totp() - Generate OTP and get access token
   - refresh_access_token() - Auto-refresh token daily
   - start_websocket(on_tick_callback) - Start WebSocket connection
   - subscribe_symbols(symbols: list) - Subscribe to NSE:NIFTY50-INDEX and option strikes
   - get_option_chain(symbol) - REST call for option chain data
   - get_historical_data(symbol, resolution, days) - Fetch OHLC data
   - place_order(order_data) - Simulated (for paper trading)
   - cancel_order(order_id) - Cancel order
   - get_positions() - Get current positions
   - keep_websocket_running() - Maintain WebSocket connection

2. Error handling for:
   - Authentication failures
   - WebSocket disconnections
   - API rate limits
   - Invalid symbols

3. Logging for:
   - Authentication events
   - WebSocket connection status
   - API calls and responses
   - Errors and exceptions

4. Use fyers_apiv3 library (pip install fyers-api)
   - Import from fyers_apiv3.FyersWebsocket import data_ws, order_ws
   - Import from fyers_apiv3.FyersClient import FyersClient

5. Handle TOTP token generation using pyotp:
   - Use pyotp.TOTP(totp_secret).now() to get 6-digit code

6. Store access token securely:
   - Save to .env or config file
   - Auto-refresh at 8:30 AM daily

Include docstrings and type hints for all methods.
```

---

## **PHASE 1B PROMPT: Data Manager**

```
Implement src/data_manager.py for real-time market data aggregation.

Requirements:
1. DataManager class to:
   - Aggregate WebSocket ticks into 1-minute candles
   - Store rolling window of 100 candles
   - Calculate indicators on-the-fly

2. Key methods:
   - __init__(window_size=100)
   - on_nifty_tick(tick_data) - Process NIFTY tick
   - on_option_tick(strike, tick_data) - Process option strike tick
   - build_candle_from_ticks() - Convert ticks to 1-min candles
   - get_current_candle() -> Candle - Latest candle
   - get_historical_candles(count: int) -> list[Candle] - Last N candles
   - update_option_chain(chain_data) - Store chain data from REST poll
   - get_option_chain() -> dict - Get current chain snapshot
   - calculate_indicators() -> dict - Calculate all indicators
   - get_state() -> dict - Return complete state for strategies

3. Indicator calculations (use TA-Lib or manual):
   - RSI(14) on 1H timeframe
   - MACD(12,26,9) on 1H timeframe
   - EMA(20, 50) on 1H timeframe
   - Bollinger Bands(20, 2) on 1H
   - Stochastic(14,3,3) on 15min
   - ATR(14) for volatility
   - Volume ratio (current vs 20-period average)

4. Candle class:
   @dataclass
   class Candle:
       timestamp: datetime
       open: float
       high: float
       low: float
       close: float
       volume: int

5. State returned by get_state():
   {
       'nifty_price': float,
       'candles': list[Candle],
       'indicators': dict,
       'option_chain': dict,
       'timestamp': datetime
   }

6. Maintain separate timeframe data:
   - 1-minute candles (for 1H RSI, MACD, EMA)
   - 5-minute candles (for volume spikes)
   - 15-minute candles (for Stochastic)

Include docstrings and type hints.
```

---

## **PHASE 1C PROMPT: Paper Trader**

```
Implement src/simulator/paper_trader.py for order simulation.

Requirements:
1. Order and Position classes:
   @dataclass
   class Order:
       order_id: str
       symbol: str  # e.g., "NSE:NIFTY24AUG24500CE"
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

2. PaperTrader class with:
   - __init__(initial_capital=1000000, slippage_pct=0.1)
   - place_order(symbol, side, qty, price, strategy=None, sl=None, tp=None) -> Order
   - cancel_order(order_id) -> bool
   - update_positions(current_prices: dict) - Update all open positions
   - get_positions() -> list[Order] - Get all open positions
   - get_pnl() -> dict - Get total P&L (realized + unrealized)
   - get_trade_history() -> list[Order] - Get closed positions
   - close_position(position_id, price) -> Order - Close a position
   - check_exit_conditions(prices: dict) - Check SL and TP

3. Features:
   - Add slippage to orders (0.1% default)
   - Track entry_time and exit_time
   - Calculate realized_pnl and unrealized_pnl
   - Maintain order_id uniqueness
   - Support batch updates of positions

4. P&L calculation:
   unrealized = (current_price - entry_price) * qty
   realized = (exit_price - entry_price) * qty
   total_pnl = sum(realized) + sum(unrealized)

5. Logging:
   - Log every order placed
   - Log every position closed
   - Log P&L calculations

Include docstrings, type hints, and unit tests.
```

---

## **PHASE 1D PROMPT: Config & Logger**

```
Implement src/config.py and src/utils/logger.py

Config class (src/config.py):
1. Load from .env and config/risk_params.json
2. Validate all required parameters
3. Provide singleton access
4. Structure:
   class Config:
       fyers_app_id: str
       fyers_app_secret: str
       fyers_redirect_uri: str
       fyers_totp_secret: str
       telegram_bot_token: str
       telegram_chat_id: str
       risk_params: dict
       
       @staticmethod
       def load() -> Config
       def validate() -> bool

Logger class (src/utils/logger.py):
1. Separate loggers for:
   - trades.log (all trades)
   - signals.log (all signals)
   - errors.log (all errors)
   - websocket.log (connection events)
   
2. Methods:
   - log_signal(strategy: str, signal: dict)
   - log_trade(trade: Trade, order: Order)
   - log_error(error: str, context: dict)
   - log_websocket_event(event: str, data: dict)
   - log_position_update(position: Order, prices: dict)

3. Format:
   [2026-08-03 10:35:42.123] [INFO] [RSI_OVERSOLD_BULLISH] Signal generated: 24500 CE @ ₹65 (conf: 75%)

4. Ensure thread-safe logging for concurrent operations

Include docstrings and type hints.
```

---

## **PHASE 2 PROMPT: Base Strategy & All 5 Strategies**

```
Implement src/strategies/ with base class and 5 concrete strategies.

1. Base strategy class (base_strategy.py):
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

   class BaseStrategy:
       def __init__(self, name: str, direction: str)
       def evaluate(self, data_state: dict) -> Signal or None
       def select_strike(self, nifty_price, option_type) -> str
       def get_option_price(self, strike) -> float

2. Implement these 5 strategies:

   BULLISH (CE):
   a) RSIOversoldBullish (rsi_oversold_bullish.py)
      - RSI(14) < 35 on 1H
      - Stochastic(14,3,3) < 20 on 15min
      - Price > 20-EMA
      - Volume > 1.5x average
      - Confidence: 0.75

   b) MACDBullish (macd_bullish.py)
      - MACD histogram crosses above zero on 1H
      - Volume spike > 2x on 5min
      - Price > 50-EMA
      - Confidence: 0.80

   c) SupportBounceBullish (support_bounce_bullish.py)
      - Price tests 20-EMA (low touches)
      - Current close > 20-EMA
      - Volume > average
      - Confidence: 0.70

   BEARISH (PE):
   d) RSIOverboughtBearish (rsi_overbought_bearish.py)
      - RSI(14) > 65 on 1H
      - Stochastic(14,3,3) > 80 on 15min
      - Price < 20-EMA
      - Volume > 1.5x average
      - Confidence: 0.75

   e) MACDBearish (macd_bearish.py)
      - MACD histogram crosses below zero on 1H
      - Volume spike > 2x on 5min
      - Price < 50-EMA
      - Confidence: 0.80

3. Strike selection logic:
   - ATM = (nifty_price // 100) * 100
   - OTM = ATM ± 100 (based on direction)
   - Select based on Delta constraints (0.3-0.85)

4. Each strategy must have:
   - Docstrings explaining the logic
   - Type hints
   - Error handling
   - Logging

Include unit tests for signal generation logic.
```

---

## **PHASE 2B PROMPT: Strategy Engine**

```
Implement src/strategies/engine.py

StrategyEngine class:
1. __init__(strategies: list[BaseStrategy])
   - Store all 6 strategies (3 CE + 3 PE)

2. evaluate_all(data_state: dict) -> list[Signal]
   - Run all strategies in parallel
   - Return list of all signals
   - Include signal timestamp and confidence

3. backtest(historical_data: pd.DataFrame) -> BacktestReport
   - Replay historical data
   - Run strategies on each candle
   - Simulate trades through paper trader
   - Return performance metrics

4. print_backtest_report(report: BacktestReport)
   - Print formatted table of results
   - Sort by profit_factor descending
   - Show win rate, P&L, max drawdown

5. Signal deduplication:
   - Avoid firing same strategy twice in 5-minute window
   - Prevent duplicate signals on same strike

6. Logging:
   - Log each signal with timestamp, strike, confidence
   - Log strategy errors/exceptions

Include docstrings and type hints.
```

---

## **PHASE 3 PROMPT: Backtester**

```
Implement src/backtester/backtest_engine.py and report.py

1. BacktestReport dataclass:
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
       trades: list  # All trades

2. BacktestEngine class:
   - __init__(strategies: list, paper_trader: PaperTrader, data_manager: DataManager)
   - run(historical_data: pd.DataFrame) -> dict[strategy_name, BacktestReport]
   - replay_candle(candle: Candle) - Process single candle
   - _update_positions_from_prices() - Update P&L each bar

3. Backtest logic:
   - Load historical CSV
   - For each candle:
     a) Update DataManager with new candle
     b) Run all strategies
     c) If signal: place order via PaperTrader
     d) Update positions with current price
     e) Check exit conditions (SL, TP, time)
   - After all candles: generate report

4. BacktestReportGenerator (report.py):
   - print_results(reports: dict)
   - Select top-3 CE strategies, top-3 PE strategies
   - Format as ASCII table:
     Rank | Strategy | Win% | PF | P&L | DD% | Status
   - Save to data/backtest_results/report.json

5. Profit Factor calculation:
   PF = sum(winning_trades) / abs(sum(losing_trades))

6. Max Drawdown:
   Calculate running equity and find max loss from peak

Include comprehensive logging and error handling.
```

---

## **PHASE 4 PROMPT: Live Trading Loop**

```
Implement src/trader.py (main trading engine)

LiveTrader class:
1. __init__(self, config: Config)
   - Initialize all components:
     * FyersAPIClient
     * DataManager
     * StrategyEngine (with top-6 strategies from backtest)
     * PaperTrader
     * TelegramAlertsManager
     * StateManager
     * Logger

2. async def start(self)
   - Start Fyers WebSocket
   - Subscribe to NIFTY and option strikes
   - Start main event loop
   - Start scheduler for 10-sec polling

3. def on_nifty_tick(self, tick)
   - Pass to DataManager
   - Trigger strategy evaluation

4. def on_option_tick(self, strike, tick)
   - Update option price in DataManager

5. def poll_option_chain(self) [Every 10 seconds]
   - Call Fyers get_option_chain()
   - Update DataManager
   - Check for new OI skew signals

6. def evaluate_strategies(self) -> list[Signal]
   - Call StrategyEngine.evaluate_all()
   - Filter low-confidence signals
   - Avoid duplicate signals

7. def execute_signals(self, signals: list[Signal])
   - For each signal:
     a) Check if within max concurrent positions limit
     b) Place order via PaperTrader
     c) Log trade
     d) Send Telegram alert

8. def update_positions(self)
   - Get latest option prices
   - Update PaperTrader positions
   - Calculate P&L

9. def check_exits(self)
   - Check stop-loss levels
   - Check take-profit levels
   - Check time-based exits
   - Close positions if triggered

10. def send_alerts(self, signal: Signal)
    - Send to TelegramAlertsManager
    - Include: strike, entry price, confidence, rationale

11. async def run_scheduler(self)
    - Every 10 seconds: poll_option_chain()
    - Every 1 second: update_positions()
    - Every 5 minutes: send daily summary

12. def stop(self)
    - Graceful shutdown
    - Close all positions
    - Save state
    - Close WebSocket

Include comprehensive error handling and logging.
```

---

## **PHASE 4B PROMPT: Telegram Alerts**

```
Implement src/alerts/telegram_alerts.py

TelegramAlertsManager class:
1. __init__(self, bot_token: str, chat_id: str)
   - Initialize Python Telegram Bot (pip install python-telegram-bot)

2. Methods:
   - send_signal_alert(signal: Signal)
     * Message with signal details
     * Buttons: [✅ APPROVE] [❌ REJECT] [⏰ REMIND]
     
   - send_trade_execution(trade: Order)
     * Confirmation message
     * Show entry price, symbol, qty
     
   - send_position_update(positions: list[Order])
     * Current open positions
     * P&L for each
     * Total portfolio P&L
     
   - send_daily_summary(summary: dict)
     * Total trades today
     * Win rate
     * Daily P&L
     * Max drawdown

3. Message templates:
   Signal Alert:
   """
   🚀 SIGNAL GENERATED
   ──────────────────
   Strategy: RSI_OVERSOLD_BULLISH
   Strike: 24,500 CE
   Entry: ₹65
   Confidence: 75%
   Time: 09:35:42
   
   Rationale: RSI at 32, Stochastic at 18, Volume 2x avg
   
   [✅ APPROVE] [❌ REJECT] [⏰ REMIND IN 5min]
   """
   
   Trade Execution:
   """
   ✅ ORDER PLACED
   ──────────────
   Strategy: RSI_OVERSOLD_BULLISH
   Strike: 24,500 CE
   Entry: ₹65
   Qty: 1
   SL: ₹60 | TP: ₹150
   Time: 09:35:42
   """

4. Error handling:
   - Handle telegram API errors
   - Retry on failure
   - Log all alert sends

Include docstrings and type hints.
```

---

## **PHASE 4C PROMPT: State Persistence**

```
Implement src/persistence/state_manager.py

StateManager class:
1. __init__(self, data_dir: str = "data/")

2. Methods:
   - save_positions(positions: list[Order])
     * Save to JSON: data/positions.json
     * For recovery on restart
     
   - load_positions() -> list[Order]
     * Load from JSON
     * Return empty list if not found
     
   - append_trade(trade: Order)
     * Append to CSV: data/trade_history.csv
     * Columns: timestamp, strategy, strike, side, entry_price, exit_price, pnl
     
   - get_trade_history() -> pd.DataFrame
     * Load CSV and return DataFrame
     
   - save_daily_summary(summary: dict)
     * Save to JSON: data/daily_summary_{date}.json
     * Include: total_trades, win_rate, daily_pnl, max_dd

3. File formats:
   positions.json:
   [
     {
       "order_id": "...",
       "symbol": "NSE:NIFTY24AUG24500CE",
       "entry_price": 65.0,
       "entry_time": "2026-08-03T09:35:42",
       "qty": 1,
       "strategy": "RSI_OVERSOLD_BULLISH"
     }
   ]
   
   trade_history.csv:
   timestamp,strategy,strike,side,entry_price,exit_price,pnl
   2026-08-03 09:35:42,RSI_OVERSOLD_BULLISH,24500 CE,BUY,65.0,72.0,700
   ...

4. Graceful shutdown:
   - On SIGTERM/SIGINT: save state
   - On restart: load positions
   - Resume from last known state

Include error handling for file I/O.
```

---

## **PHASE 5 PROMPT: Terminal Dashboard (if you choose CLI)**

```
Implement src/dashboard/terminal_ui.py for live monitoring

TerminalDashboard class:
1. __init__(self, trader: LiveTrader)
   - Store reference to live trader
   - Set up terminal UI (using curses or rich library)

2. Methods:
   - display_live_data()
     * Update every 1 second
     * Show: NIFTY price, direction, +/- points
     * Market status (OPEN/CLOSED)
     
   - display_signals(signals: list[Signal])
     * Last 5 generated signals
     * Strategy, strike, confidence, time
     
   - display_positions(positions: list[Order])
     * Current open trades
     * Entry price, current price, P&L, SL, TP
     
   - display_pnl()
     * Total P&L (realized + unrealized)
     * Today's P&L
     * Win rate today
     * Max drawdown
     
   - display_trade_history(trades: list[Order])
     * Last 20 closed trades
     * Timestamp, strategy, strike, entry, exit, P&L
     
   - run_interactive()
     * Commands: 
       - T: Trade history
       - P: Positions
       - S: Signals
       - Q: Quit
       - C: Clear screen

3. Use Rich library for formatting:
   - Tables with colors
   - Progress bars for P&L
   - Live updates without flickering

4. Refresh rates:
   - Live data: every 100ms
   - Positions: every 500ms
   - History: on demand

Include keyboard interrupt handling for graceful exit.
```

---

## **PHASE 6 PROMPT: Unit Tests**

```
Implement tests/ directory with unit tests.

1. Test files structure:
   tests/test_strategies.py
   tests/test_paper_trader.py
   tests/test_data_manager.py
   tests/test_fyers_client.py

2. test_strategies.py:
   - TestRSIOversoldBullish
     * test_signal_when_rsi_below_35_and_volume_spike()
     * test_no_signal_when_rsi_above_40()
     * test_confidence_score_calculated_correctly()
   
   - TestMACDBullish
     * test_signal_on_macd_cross_above_zero()
     * test_volume_confirmation_required()
   
   - Similar tests for other strategies

3. test_paper_trader.py:
   - TestPaperTrader
     * test_order_placed_successfully()
     * test_slippage_applied_to_entry()
     * test_position_closed_on_stop_loss()
     * test_position_closed_on_take_profit()
     * test_pnl_calculated_correctly()
     * test_unrealized_pnl_updates()

4. test_data_manager.py:
   - TestDataManager
     * test_candle_built_from_ticks()
     * test_rsi_calculated_correctly()
     * test_macd_calculated_correctly()
     * test_ema_calculated_correctly()
     * test_indicators_cached_properly()

5. pytest configuration:
   - Use pytest.fixture for common data
   - Use mock objects for Fyers API
   - Run with: pytest tests/ -v

Include fixtures for sample market data and trades.
```

---

## **EXECUTION STEPS**

### **Step 1: Setup**
1. Copy this entire file into VS Code
2. Create project directory: `mkdir nifty-options-trader && cd nifty-options-trader`
3. Open in VS Code: `code .`

### **Step 2: Use Claude Code Agent**

In VS Code, use this exact flow:

```
1. Run initial setup prompt
   → Claude creates directory structure

2. Run PHASE 1A-D prompts sequentially
   → Creates all core infrastructure

3. Run PHASE 2 prompts
   → Implements all 5 strategies

4. Run PHASE 3 prompts
   → Backtester and report generation

5. Run PHASE 4 prompts
   → Live trading loop + alerts

6. Run PHASE 5 prompt (optional)
   → Dashboard UI

7. Run PHASE 6 prompts
   → Unit tests
```

### **Step 3: Between Each Phase**
```bash
# Run tests
pytest tests/ -v

# Check for errors
flake8 src/ --max-line-length=120

# Type checking (optional)
mypy src/
```

### **Step 4: Final Integration**
```bash
# Load config
cp .env.example .env
# Fill in your Fyers credentials and Telegram token

# Load historical data
# Place nifty_90days.csv in data/historical/

# Run backtest to select top-6 strategies
python -m src.backtester.backtest_engine

# Start live trading
python src/trader.py
```

---

## **DEBUGGING TIPS**

If Claude Code Agent generates code with errors:

```
"There's an import error in src/fyers/api_client.py. 
 Fix the FyersDataSocket import - it should be:
 from fyers_apiv3.FyersWebsocket import data_ws"

"Test src/strategies/rsi_oversold_bullish.py with this sample data:
 [...attach sample candle data...]
 Should generate signal when RSI=32"
```

---

## **Success Indicators**

After implementing each phase, you should see:

**Phase 1:** ✓ FyersAPIClient.authenticate_with_totp() works
**Phase 2:** ✓ All 5 strategies generate test signals
**Phase 3:** ✓ Backtest produces report with P&L rankings
**Phase 4:** ✓ Live trader connects to WebSocket and generates alerts
**Phase 5:** ✓ Dashboard displays positions and P&L in real-time
**Phase 6:** ✓ All tests pass (pytest)

---

**Ready to start? Run the initial setup prompt in Claude Code Agent!** 🚀
