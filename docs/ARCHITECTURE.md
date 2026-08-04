# Architecture

Paper-trading only. No module in this codebase places a real order — see
[Why no real orders](#why-no-real-orders) below.

Two layers: a shared trading core (`src/`, unchanged since the CLI-only phase) and a web app
(`backend/` + `frontend/`) that wraps it. Live trading and its UI now live entirely in the web
app — the old terminal dashboard was retired once this replaced it.

## Module map

```
main.py                        CLI: runs the 90-day backtest only (see backend/ for live trading)
fetch_historical_data.py       One-off: TOTP-login to Fyers, pull N days of 1-min candles

src/                            Shared trading core — used by both the CLI and the backend
  config.py                    Loads .env + config/risk_params.json into one Config object
  data_manager.py               Candle building from ticks, indicator calculation, option-chain cache
  trader.py                     LiveTrader: wires WebSocket -> strategies -> paper trader -> alerts
  fyers/
    api_client.py                TOTP silent login, WebSocket streaming, REST (history/option chain)
  strategies/
    base_strategy.py             Signal dataclass, strike selection, option pricing fallback
    rsi_oversold_bullish.py      } the 6 strategies (3 CE + 3 PE) — see STRATEGIES.md
    macd_bullish.py              }
    support_bounce_bullish.py    }
    rsi_overbought_bearish.py    }
    macd_bearish.py              }
    resistance_rejection_bearish.py
    engine.py                     Runs all strategies, dedupes/cools down signals
  simulator/
    paper_trader.py               Simulated order execution, SL/TP/time-exit, P&L, risk limits
  backtester/
    backtest_engine.py             Replays historical candles per-strategy, independent PaperTrader each
    report.py                      Win rate / profit factor / drawdown, ranks and selects top 3 CE + 3 PE
  alerts/
    telegram_alerts.py             Signal alerts with Approve/Reject/Remind buttons
  persistence/
    state_manager.py               File-based positions/trades — used by the CLI/backtester only;
                                    the web backend persists to Postgres instead (see below)
  utils/
    indicators.py                  RSI/MACD/EMA/Bollinger/Stochastic/ATR/volume-ratio (pandas/numpy only)
    options_pricing.py             Black-Scholes estimate + option-symbol parsing
    logger.py                      Four topic loggers: trades, signals, errors, websocket

backend/                        FastAPI web app — wraps src/, adds auth/streaming/persistence
  run.py                          Entry point (uvicorn, reload=False — see below for why)
  app/
    main.py                        FastAPI app, middleware, auth routes, WS endpoint
    config.py                      Extends src/config.py's Config with web-only settings
    live_engine.py                 WebLiveEngine(LiveTrader): DB persistence, dual-path signal
                                    approval (web + Telegram), replay-mode fallback
    broadcaster.py                 Diffs state every STREAM_INTERVAL, fans out over WebSocket
    state.py                       SharedState + PendingSignalRegistry (thread<->asyncio handoff)
    supabase_auth.py / security.py Supabase JWT verification -> signed session cookie
    db.py                          asyncpg pool (Supabase Postgres)
    paper_router.py / backtest_router.py   REST endpoints (see below)
  migrations/001_options_positions.sql     Run once, manually, in Supabase's SQL editor

frontend/                       Vite + React (JS) + Tailwind — the actual UI
  src/
    hooks/useMarketStream.js       WebSocket connection (reconnect/backoff/heartbeat/resync)
    hooks/usePaperTradingSync.js   REST polling (trade history) + signal approve/reject
    store/marketStore.js / tradingStore.js   Hand-rolled external stores (no Redux)
    screens/                       LiveDashboard / BacktestReport / TradeHistory

tests/, backend/tests/          54 tests total (27 core + 27 backend)
```

## Data flow (live, via the web backend)

```
Fyers WebSocket ticks ──> DataManager (candles + indicators + option chain)
                                │
                                ▼
                        StrategyEngine.evaluate_all()  (all 6 strategies, deduped)
                                │
                                ▼
              PendingSignalRegistry: signal awaits approval, broadcast to the frontend
                     │ Telegram Approve/Reject  AND  web POST /api/paper/signals/{id}/approve
                     ▼ (whichever comes first)
                        PaperTrader.place_order()  (simulated fill, risk limits enforced)
                                │
                                ▼
                   Postgres (options_positions/options_signals) + Broadcaster -> WS -> browser
```

`Broadcaster` ticks every `STREAM_INTERVAL` seconds, diffs the current snapshot against the last
one, and sends `snapshot` (full state, on connect/resync) / `delta` (changed keys only) /
`heartbeat` (after 5s of no change) frames over `/ws/stream`. `LiveTrader.poll_option_chain()`
(inherited, unchanged) still runs every `polling.option_chain_interval_secs` to refresh OI/LTP.

## Live vs. replay mode

`WebLiveEngine` runs one of two ways, controlled by `DATA_ENGINE_ENABLED`:
- **Live** (`true`): holds the Fyers app's one allowed WebSocket connection, same as the CLI's
  `LiveTrader.start()`.
- **Replay** (`false`, the default): loops `data/historical/nifty_90days.csv` at high speed. This
  is what runs locally without live Fyers credentials/market hours, and is also the fallback if
  the live connection is blocked (e.g. by a corporate proxy — see below).

Only one instance across the whole VM (this app or a sibling project sharing the same Fyers app)
may run with `DATA_ENGINE_ENABLED=true` at a time.

## Data flow (backtest) — unchanged, CLI-only

Each strategy gets its own `DataManager` + `PaperTrader`, replayed independently against the same
historical candles — so one strategy's signals/risk limits never affect another's ranking. The
live engine is what applies *shared* risk limits (`max_concurrent_positions`, `max_daily_loss`)
once a top-6 set is actually deployed together. Deliberately no "run backtest from the web" button
— it's ~15 CPU-minutes on the deploy VM's single vCPU, which would starve live trading on the same
core; new backtests stay `python -m src.backtester.backtest_engine`.

## Key design decisions

- **`fyers-apiv3`, not `fyers-api`.** The original planning docs specified a package that doesn't
  exist on PyPI for API v3.
- **No real historical option prices.** Fyers only provides historical candles for the index, not
  individual option strikes. Backtesting/replay mark option positions to market with a
  Black-Scholes estimate (`utils/options_pricing.py`); live trading always prefers the real
  option-chain LTP when available.
- **`stop_loss_pct` is a percentage of the entry premium; `take_profit_pts` is still option-premium
  points (₹), not NIFTY index points.** Options are priced in rupees, not index points, so risk
  parameters apply to the traded instrument. `stop_loss_pct` (not a fixed point offset) so risk
  scales with each option's own price — a fixed-point stop on a cheap OTM option could exceed the
  whole premium, while the same points on an expensive ITM one barely mattered.
- **Trailing stop**: once a position is `trailing_activation_pct` in profit, the stop ratchets up to
  stay `trailing_stop_pct` below the peak premium seen since entry, locking in gains as a winner
  runs instead of relying solely on the fixed `take_profit_pts` ceiling. Implemented in
  `PaperTrader.update_positions()` (`src/simulator/paper_trader.py`) via `Order.peak_price`.
- **SL/TP exits fill at the configured stop/target price, not the observed mark.** Exits are only
  checked once per candle close; on a fast-moving candle the mark can already be well past the
  stop. A 90-day backtest showed this overshoot inflating realized SL losses by 20-100%+ beyond the
  intended risk — fixed by capping the fill at `order.stop_loss`/`order.take_profit` exactly.
- **`max_trades_per_day_per_strategy` (default 2)**: `PaperTrader` tracks trades opened per
  strategy per calendar day and rejects further entries past the cap via `RiskLimitExceeded`.
- **`DataManager`'s rolling window defaults to ~3000 one-minute candles (~7-8 trading days).**
  NIFTY's 6.25-hour trading day alone can never produce the 15 hourly candles RSI(14)/EMA(50)/
  MACD(26) need — a smaller window would mean strategies silently never fire. `LiveTrader` seeds
  this window from historical data on startup so day one isn't blind.
- **A 6th strategy, `RESISTANCE_REJECTION_BEARISH`, was added** (mirroring
  `SUPPORT_BOUNCE_BULLISH`) — the original Phase 2 spec only listed 5 strategies (3 CE / 2 PE), but
  every other planning doc describes the target as 3 CE + 3 PE.
- **TLS via `truststore`, not certifi.** On a network with TLS-inspecting corporate proxies
  (confirmed here: Zscaler on the Cognizant network), `requests`' bundled CA list won't trust the
  proxy's root CA. `truststore.inject_into_ssl()` in `api_client.py` uses the OS certificate store
  instead, which already trusts it.
- **`setuptools<81` is pinned.** `fyers-apiv3`'s WebSocket module imports `pkg_resources`, which
  newer `setuptools` no longer ships.
- **`reload=False` in `backend/run.py`.** Uvicorn's `--reload` spawns a second worker process on
  file changes; with only one Fyers WebSocket connection allowed per app, two workers would fight
  over it.
- **Session cookie, not a bearer token.** The browser verifies against Supabase Auth directly,
  then POSTs the resulting JWT to `/api/auth/login` once; the backend verifies it and mints a
  signed session cookie. Everything after that — including the WebSocket, which can't carry a
  custom `Authorization` header — just rides the cookie.
- **Dual-path signal approval.** A generated signal is sent to Telegram *and* broadcast to the
  frontend as pending; whichever channel responds first (Telegram button or web
  Approve/Reject) resolves it via `PendingSignalRegistry`'s shared `asyncio.Future`.
- **Web persistence best-effort.** If Postgres isn't reachable, `WebLiveEngine` logs and continues
  — in-memory paper-trading correctness never depends on the DB write succeeding.

## Isolation from TradeDashBoard (same VM)

|  | TradeDashBoard | OptionsSimulator |
|---|---|---|
| App dir | `/home/ubuntu/app` | `/home/ubuntu/optionssimulator-app` |
| Backend port | `127.0.0.1:8000` | `127.0.0.1:8001` |
| systemd service | `tradedashboard-backend` | `optionssimulator-backend` |
| Fyers app | `4F6I37WKEE-100` | `VGCKHJGNRB-100` (`TradeDashboardLocal`) |
| URL | `trading-dashboard-1.duckdns.org/` | `.../options-simulator/*` (path-based, same domain) |

See `deploy/README.md` for the full deploy setup.

## Why no real orders

`src/fyers/api_client.py` intentionally has no `place_order`/`cancel_order` methods. SEBI requires
human supervision for algorithmic trading — an autonomous system that can fire live orders without
per-trade approval is a compliance risk, not just an engineering one. All execution in this project
is simulated through `PaperTrader`. As a second layer of protection, the Fyers app used here
(`TradeDashboardLocal`) is registered as a **non-trading** app — Fyers rejects order-placement calls
for it at the API level regardless of what the code does.
